from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AIEvaluation, Listing
from ..schemas import ListingRerunResult


def rerun_listings(db: Session, listing_ids: list[int]) -> list[ListingRerunResult]:
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
    # Release the read transaction before the slow browser/AI work starts so
    # dashboard schema checks are not blocked by an idle session.
    db.rollback()

    listings_by_id = {row.id: row for row in rows}
    logger = logging.getLogger("dashboard_rerun")
    results: list[ListingRerunResult] = []

    try:
        from ai_marketplace_monitor.monitor import MarketplaceMonitor
        from ai_marketplace_monitor.utils import CacheType, cache
    except Exception as exc:
        return [
            ListingRerunResult(
                listing_id=listing_id,
                success=False,
                message=f"Failed to load rerun dependencies: {exc}",
            )
            for listing_id in unique_listing_ids
        ]

    monitor = MarketplaceMonitor(config_files=None, headless=True, logger=logger)

    try:
        try:
            monitor.load_config_file()
        except Exception as exc:
            return [
                ListingRerunResult(
                    listing_id=listing_id,
                    success=False,
                    message=f"Failed to load monitor config: {exc}",
                )
                for listing_id in unique_listing_ids
            ]
        expected_items = list(monitor.config.item.keys()) if monitor.config else []

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

            target_item = row.listing_kind or "unknown"
            if target_item not in expected_items:
                if len(expected_items) == 1:
                    target_item = expected_items[0]
                else:
                    results.append(
                        ListingRerunResult(
                            listing_id=listing_id,
                            canonical_post_url=row.canonical_post_url,
                            target_item=target_item,
                            success=False,
                            message="Could not resolve item config for rerun",
                        )
                    )
                    continue

            clean_url = row.canonical_post_url.split("?")[0]
            cache.delete((CacheType.LISTING_DETAILS.value, clean_url))

            try:
                monitor.check_items(items=[clean_url], for_item=target_item)
            except Exception as exc:
                results.append(
                    ListingRerunResult(
                        listing_id=listing_id,
                        canonical_post_url=row.canonical_post_url,
                        target_item=target_item,
                        success=False,
                        message=str(exc),
                    )
                )
                continue

            results.append(
                ListingRerunResult(
                    listing_id=listing_id,
                    canonical_post_url=row.canonical_post_url,
                    target_item=target_item,
                    success=True,
                    message="Rerun completed",
                )
            )
    finally:
        monitor.stop_monitor()

    return results
