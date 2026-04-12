"""GET /api/listing-price-history."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Listing, ListingPriceHistory
from ..schemas import PagedResponse, PriceHistoryRow

router = APIRouter(prefix="/api/listing-price-history", tags=["price-history"])


@router.get("", response_model=PagedResponse[PriceHistoryRow])
def list_price_history(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    listing_id: int | None = Query(None),
    observed_from: datetime | None = Query(None),
    observed_to: datetime | None = Query(None),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
):
    q = (
        select(
            ListingPriceHistory.id,
            ListingPriceHistory.listing_id,
            Listing.title.label("listing_title"),
            Listing.canonical_post_url,
            ListingPriceHistory.price,
            ListingPriceHistory.observed_at,
        )
        .join(Listing, Listing.id == ListingPriceHistory.listing_id)
    )

    if listing_id is not None:
        q = q.where(ListingPriceHistory.listing_id == listing_id)
    if observed_from:
        q = q.where(ListingPriceHistory.observed_at >= observed_from)
    if observed_to:
        q = q.where(ListingPriceHistory.observed_at <= observed_to)

    count_sq = q.subquery("count_sq")
    total: int = db.execute(select(func.count()).select_from(count_sq)).scalar_one()

    order = (
        ListingPriceHistory.observed_at.asc()
        if sort_dir == "asc"
        else ListingPriceHistory.observed_at.desc()
    )
    rows = db.execute(
        q.order_by(order).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        PriceHistoryRow(
            id=r.id,
            listing_id=r.listing_id,
            listing_title=r.listing_title,
            canonical_post_url=r.canonical_post_url,
            price=r.price,
            observed_at=r.observed_at,
        )
        for r in rows
    ]
    return PagedResponse(items=items, total=total, page=page, page_size=page_size)
