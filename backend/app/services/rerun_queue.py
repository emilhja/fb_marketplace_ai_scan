from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AIEvaluation, Listing, ListingRerunQueue
from ..schemas import ListingRerunResult


def enqueue_listing_reruns(db: Session, listing_ids: list[int]) -> list[ListingRerunResult]:
    unique_listing_ids = list(dict.fromkeys(listing_ids))
    if not unique_listing_ids:
        return []

    latest_eval_sq = (
        select(
            AIEvaluation.listing_id,
            AIEvaluation.listing_kind,
            func.row_number()
            .over(
                partition_by=AIEvaluation.listing_id,
                order_by=[AIEvaluation.evaluated_at.desc(), AIEvaluation.id.desc()],
            )
            .label("rn"),
        )
    ).subquery("latest_eval")

    rows = db.execute(
        select(
            Listing.id,
            Listing.canonical_post_url,
            latest_eval_sq.c.listing_kind,
        )
        .select_from(Listing)
        .outerjoin(
            latest_eval_sq,
            (latest_eval_sq.c.listing_id == Listing.id) & (latest_eval_sq.c.rn == 1),
        )
        .where(Listing.id.in_(unique_listing_ids))
    ).all()

    listings_by_id = {row.id: row for row in rows}
    active_listing_ids = set(
        db.execute(
            select(ListingRerunQueue.listing_id).where(
                ListingRerunQueue.listing_id.in_(unique_listing_ids),
                ListingRerunQueue.status.in_(("pending", "running")),
            )
        ).scalars()
    )

    results: list[ListingRerunResult] = []
    for listing_id in unique_listing_ids:
        row = listings_by_id.get(listing_id)
        if row is None:
            results.append(
                ListingRerunResult(
                    listing_id=listing_id,
                    success=False,
                    message="Listing not found",
                )
            )
            continue

        if listing_id in active_listing_ids:
            results.append(
                ListingRerunResult(
                    listing_id=listing_id,
                    canonical_post_url=row.canonical_post_url,
                    target_item=row.listing_kind or "unknown",
                    success=True,
                    message="Already queued",
                )
            )
            continue

        db.add(ListingRerunQueue(listing_id=listing_id, status="pending"))
        results.append(
            ListingRerunResult(
                listing_id=listing_id,
                canonical_post_url=row.canonical_post_url,
                target_item=row.listing_kind or "unknown",
                success=True,
                message="Sent to scraping_run",
            )
        )

    db.commit()
    return results
