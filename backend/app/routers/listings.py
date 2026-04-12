"""GET /api/listings — listings joined to the latest ai_evaluations row."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AIEvaluation, Listing
from ..schemas import LatestAIEval, ListingRow, PagedResponse

router = APIRouter(prefix="/api/listings", tags=["listings"])

SORT_COLUMNS: dict[str, str] = {
    "last_seen_at": "listings.last_seen_at",
    "first_seen_at": "listings.first_seen_at",
    "title": "listings.title",
    "current_price": "listings.current_price",
    "score": "latest_eval.score",
    "evaluated_at": "latest_eval.evaluated_at",
    "listing_kind": "latest_eval.listing_kind",
}


@router.get("", response_model=PagedResponse[ListingRow])
def list_listings(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    # text search
    title: str | None = Query(None, description="Case-insensitive title search"),
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
    sort_col = SORT_COLUMNS.get(sort_by, "listings.last_seen_at")
    direction = "ASC" if sort_dir == "asc" else "DESC"

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
            (latest_eval_sq.c.listing_id == Listing.id)
            & (latest_eval_sq.c.rn == 1),
        )
    )

    # Apply filters
    if title:
        base_q = base_q.where(Listing.title.ilike(f"%{title}%"))
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
    rows = db.execute(
        base_q.order_by(text(f"{sort_col} {direction}"))
        .offset((page - 1) * page_size)
        .limit(page_size)
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
                first_seen_at=r.first_seen_at,
                last_seen_at=r.last_seen_at,
                ai=ai,
            )
        )

    return PagedResponse(items=items, total=total, page=page, page_size=page_size)
