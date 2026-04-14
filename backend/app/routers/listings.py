"""Listings read/write endpoints for the dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from ..db import ensure_dashboard_schema, get_db
from ..models import AIEvaluation, Listing
from ..models import NotificationEvent
from ..schemas import (
    LatestAIEval,
    ListingRerunRequest,
    ListingRerunResponse,
    ListingRow,
    ListingUpdateRequest,
    PagedResponse,
)
from ..services.rerun_queue import enqueue_listing_reruns
from ..services.vram import infer_vram

router = APIRouter(prefix="/api/listings", tags=["listings"])

SORT_COLUMNS: dict[str, str] = {
    "last_seen_at": "listings.last_seen_at",
    "first_seen_at": "listings.first_seen_at",
    "title": "listings.title",
    "current_price": "COALESCE(NULLIF(regexp_replace(listings.current_price, '[^0-9]', '', 'g'), ''), '0')::bigint",
    "location": "COALESCE(listings.location, '')",
    "availability": "COALESCE(listings.availability, '')",
    "score": "latest_eval.score",
    "evaluated_at": "latest_eval.evaluated_at",
    "listing_kind": "latest_eval.listing_kind",
    "user_feedback": "COALESCE(listings.user_feedback, '')",
    "user_note": "COALESCE(listings.user_note, '')",
    "message_sent": "COALESCE(notification_sent.message_sent, false)",
}


def resolved_vram(listing: Listing, ai: LatestAIEval | None) -> str | None:
    return listing.vram_override or infer_vram(listing.title, listing.description, ai)


@router.get("", response_model=PagedResponse[ListingRow])
def list_listings(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    # text search
    title: str | None = Query(None, description="Case-insensitive title search"),
    search: str | None = Query(
        None, description="Case-insensitive search in title and description"
    ),
    # score filters
    score_min: int | None = Query(None, ge=0, le=5),
    score_max: int | None = Query(None, ge=0, le=5),
    listing_kind: str | None = Query(None),
    marketplace: str | None = Query(None),
    # date ranges on listings
    last_seen_from: datetime | None = Query(None),
    last_seen_to: datetime | None = Query(None),
    # date ranges on ai eval
    evaluated_from: datetime | None = Query(None),
    evaluated_to: datetime | None = Query(None),
    # sort
    sort_by: str = Query("last_seen_at"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
):
    ensure_dashboard_schema()
    direction = "ASC" if sort_dir == "asc" else "DESC"
    inferred_vram_text = "concat_ws(' ', listings.title, listings.description, latest_eval.comment, latest_eval.conclusion)"
    vram_text = f"COALESCE(NULLIF(listings.vram_override, ''), {inferred_vram_text})"
    vram_exact_match = f"""regexp_match(
        {vram_text},
        '(?i)(vram|video memory|graphics memory|gpu memory|grafikminne|minne på grafikkort)\\D{{0,24}}(\\d{{1,2}})\\s*(gb|g(b)?|gig(abyte)?s?)'
    )"""
    vram_any_match = f"""regexp_match(
        {vram_text},
        '(?i)\\b(\\d{{1,2}})\\s*(gb|g(b)?|gig(abyte)?s?)\\b'
    )"""
    vram_exact = f"({vram_exact_match})[2]"
    vram_any = f"({vram_any_match})[1]"
    vram_amount = f"COALESCE({vram_exact}, {vram_any}, '0')::bigint"
    vram_uncertain = f"""CASE
        WHEN {vram_amount} = 0 THEN 1
        WHEN {vram_exact} IS NOT NULL THEN 0
        ELSE 1
    END"""
    sort_col = SORT_COLUMNS.get(sort_by, "listings.last_seen_at")

    # Subquery: latest ai_evaluation per listing (by evaluated_at DESC, id DESC as tie-break)
    latest_eval_sq = (
        select(
            AIEvaluation.id.label("eval_id"),
            AIEvaluation.listing_id,
            AIEvaluation.score,
            AIEvaluation.conclusion,
            AIEvaluation.comment,
            AIEvaluation.listing_kind,
            AIEvaluation.model,
            AIEvaluation.response_model,
            AIEvaluation.evaluated_at,
            func.row_number()
            .over(
                partition_by=AIEvaluation.listing_id,
                order_by=[AIEvaluation.evaluated_at.desc(), AIEvaluation.id.desc()],
            )
            .label("rn"),
        )
    ).subquery("latest_eval")

    notification_sent_sq = (
        select(
            NotificationEvent.listing_id.label("listing_id"),
            func.bool_or(NotificationEvent.status == "sent").label("message_sent"),
        ).group_by(NotificationEvent.listing_id)
    ).subquery("notification_sent")

    base_q = (
        select(
            Listing.id,
            Listing.listing_key,
            Listing.marketplace,
            Listing.marketplace_listing_id,
            Listing.canonical_post_url,
            Listing.title,
            Listing.current_price,
            Listing.original_price,
            Listing.description,
            Listing.location,
            Listing.skick,
            Listing.availability,
            Listing.is_tradera,
            notification_sent_sq.c.message_sent,
            Listing.vram_override,
            Listing.contacted_seller,
            Listing.user_note,
            Listing.user_feedback,
            Listing.first_seen_at,
            Listing.last_seen_at,
            # AI cols
            latest_eval_sq.c.eval_id,
            latest_eval_sq.c.score,
            latest_eval_sq.c.conclusion,
            latest_eval_sq.c.comment,
            latest_eval_sq.c.listing_kind,
            latest_eval_sq.c.model,
            latest_eval_sq.c.response_model,
            latest_eval_sq.c.evaluated_at,
        )
        .select_from(Listing)
        .outerjoin(
            latest_eval_sq,
            (latest_eval_sq.c.listing_id == Listing.id) & (latest_eval_sq.c.rn == 1),
        )
        .outerjoin(notification_sent_sq, notification_sent_sq.c.listing_id == Listing.id)
    )

    # Apply filters
    if title:
        base_q = base_q.where(Listing.title.ilike(f"%{title}%"))
    if search:
        search_pattern = f"%{search}%"
        base_q = base_q.where(
            or_(Listing.title.ilike(search_pattern), Listing.description.ilike(search_pattern))
        )
    if marketplace:
        base_q = base_q.where(Listing.marketplace == marketplace)
    if last_seen_from:
        base_q = base_q.where(Listing.last_seen_at >= last_seen_from)
    if last_seen_to:
        base_q = base_q.where(Listing.last_seen_at <= last_seen_to)
    if score_min is not None:
        base_q = base_q.where(latest_eval_sq.c.score >= score_min)
    if score_max is not None:
        base_q = base_q.where(latest_eval_sq.c.score <= score_max)
    if listing_kind:
        base_q = base_q.where(latest_eval_sq.c.listing_kind == listing_kind)
    if evaluated_from:
        base_q = base_q.where(latest_eval_sq.c.evaluated_at >= evaluated_from)
    if evaluated_to:
        base_q = base_q.where(latest_eval_sq.c.evaluated_at <= evaluated_to)

    # Total count (wrap to avoid repeating joins)
    count_sq = base_q.subquery("count_sq")
    total: int = db.execute(select(func.count()).select_from(count_sq)).scalar_one()

    # Sort + paginate
    if sort_by == "vram":
        order_by = [
            text(f"{vram_amount} {direction}"),
            text(f"{vram_uncertain} ASC"),
            text(f"listings.last_seen_at DESC"),
        ]
    else:
        order_by = [text(f"{sort_col} {direction}")]

    rows = db.execute(
        base_q.order_by(*order_by).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items: list[ListingRow] = []
    for r in rows:
        ai = None
        if r.eval_id is not None:
            ai = LatestAIEval(
                eval_id=r.eval_id,
                score=r.score,
                conclusion=r.conclusion,
                comment=r.comment,
                listing_kind=r.listing_kind,
                model=r.model,
                response_model=r.response_model,
                evaluated_at=r.evaluated_at,
            )
        items.append(
            ListingRow(
                id=r.id,
                listing_key=r.listing_key,
                marketplace=r.marketplace,
                marketplace_listing_id=r.marketplace_listing_id,
                canonical_post_url=r.canonical_post_url,
                title=r.title,
                current_price=r.current_price,
                original_price=r.original_price,
                description=r.description,
                location=r.location,
                skick=r.skick,
                availability=r.availability,
                is_tradera=r.is_tradera,
                message_sent=bool(r.message_sent),
                vram=resolved_vram(r, ai),
                vram_override=r.vram_override,
                contacted_seller=r.contacted_seller,
                user_note=r.user_note,
                user_feedback=r.user_feedback,
                first_seen_at=r.first_seen_at,
                last_seen_at=r.last_seen_at,
                ai=ai,
            )
        )

    return PagedResponse(items=items, total=total, page=page, page_size=page_size)


@router.patch("/{listing_id}", response_model=ListingRow)
def update_listing(
    listing_id: int,
    payload: ListingUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
):
    ensure_dashboard_schema()
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    if "user_note" in payload.model_fields_set:
        if payload.user_note is None:
            raise HTTPException(status_code=400, detail="user_note cannot be null")
        listing.user_note = payload.user_note.strip()
    if "user_feedback" in payload.model_fields_set:
        if payload.user_feedback not in {None, "up", "down"}:
            raise HTTPException(
                status_code=400, detail="user_feedback must be 'up', 'down', or null"
            )
        listing.user_feedback = payload.user_feedback
    if "vram_override" in payload.model_fields_set:
        listing.vram_override = payload.vram_override.strip() if payload.vram_override else None
    if "contacted_seller" in payload.model_fields_set:
        if payload.contacted_seller is None:
            raise HTTPException(status_code=400, detail="contacted_seller cannot be null")
        listing.contacted_seller = payload.contacted_seller

    db.add(listing)
    db.commit()
    db.refresh(listing)

    latest_eval_sq = (
        select(
            AIEvaluation.id.label("eval_id"),
            AIEvaluation.listing_id,
            AIEvaluation.score,
            AIEvaluation.conclusion,
            AIEvaluation.comment,
            AIEvaluation.listing_kind,
            AIEvaluation.model,
            AIEvaluation.response_model,
            AIEvaluation.evaluated_at,
            func.row_number()
            .over(
                partition_by=AIEvaluation.listing_id,
                order_by=[AIEvaluation.evaluated_at.desc(), AIEvaluation.id.desc()],
            )
            .label("rn"),
        )
    ).subquery("latest_eval")

    notification_sent_sq = (
        select(
            NotificationEvent.listing_id.label("listing_id"),
            func.bool_or(NotificationEvent.status == "sent").label("message_sent"),
        ).group_by(NotificationEvent.listing_id)
    ).subquery("notification_sent")

    row = db.execute(
        select(
            Listing.id,
            Listing.listing_key,
            Listing.marketplace,
            Listing.marketplace_listing_id,
            Listing.canonical_post_url,
            Listing.title,
            Listing.current_price,
            Listing.original_price,
            Listing.description,
            Listing.location,
            Listing.skick,
            Listing.availability,
            Listing.is_tradera,
            notification_sent_sq.c.message_sent,
            Listing.vram_override,
            Listing.contacted_seller,
            Listing.user_note,
            Listing.user_feedback,
            Listing.first_seen_at,
            Listing.last_seen_at,
            latest_eval_sq.c.eval_id,
            latest_eval_sq.c.score,
            latest_eval_sq.c.conclusion,
            latest_eval_sq.c.comment,
            latest_eval_sq.c.listing_kind,
            latest_eval_sq.c.model,
            latest_eval_sq.c.response_model,
            latest_eval_sq.c.evaluated_at,
        )
        .select_from(Listing)
        .outerjoin(
            latest_eval_sq,
            (latest_eval_sq.c.listing_id == Listing.id) & (latest_eval_sq.c.rn == 1),
        )
        .outerjoin(notification_sent_sq, notification_sent_sq.c.listing_id == Listing.id)
        .where(Listing.id == listing_id)
    ).one()

    ai = None
    if row.eval_id is not None:
        ai = LatestAIEval(
            eval_id=row.eval_id,
            score=row.score,
            conclusion=row.conclusion,
            comment=row.comment,
            listing_kind=row.listing_kind,
            model=row.model,
            response_model=row.response_model,
            evaluated_at=row.evaluated_at,
        )

    return ListingRow(
        id=row.id,
        listing_key=row.listing_key,
        marketplace=row.marketplace,
        marketplace_listing_id=row.marketplace_listing_id,
        canonical_post_url=row.canonical_post_url,
        title=row.title,
        current_price=row.current_price,
        original_price=row.original_price,
        description=row.description,
        location=row.location,
        skick=row.skick,
        availability=row.availability,
        is_tradera=row.is_tradera,
        message_sent=bool(row.message_sent),
        vram=resolved_vram(row, ai),
        vram_override=row.vram_override,
        contacted_seller=row.contacted_seller,
        user_note=row.user_note,
        user_feedback=row.user_feedback,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        ai=ai,
    )


@router.post("/rerun", response_model=ListingRerunResponse)
def rerun_selected_listings(
    payload: ListingRerunRequest,
    db: Annotated[Session, Depends(get_db)],
):
    ensure_dashboard_schema()
    listing_ids = list(dict.fromkeys(payload.listing_ids))
    if not listing_ids:
        raise HTTPException(status_code=400, detail="listing_ids must not be empty")
    if len(listing_ids) > 50:
        raise HTTPException(status_code=400, detail="listing_ids must contain at most 50 items")

    return ListingRerunResponse(results=enqueue_listing_reruns(db, listing_ids))
