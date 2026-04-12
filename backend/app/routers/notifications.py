"""GET /api/notification-events."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Listing, NotificationEvent
from ..schemas import NotificationEventRow, PagedResponse

router = APIRouter(prefix="/api/notification-events", tags=["notifications"])


@router.get("", response_model=PagedResponse[NotificationEventRow])
def list_notification_events(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    listing_id: int | None = Query(None),
    channel: str | None = Query(None),
    status: str | None = Query(None),
    sent_from: datetime | None = Query(None),
    sent_to: datetime | None = Query(None),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
):
    q = (
        select(
            NotificationEvent.id,
            NotificationEvent.listing_id,
            Listing.title.label("listing_title"),
            Listing.canonical_post_url,
            NotificationEvent.user_name,
            NotificationEvent.channel,
            NotificationEvent.status,
            NotificationEvent.details,
            NotificationEvent.sent_at,
        )
        .join(Listing, Listing.id == NotificationEvent.listing_id)
    )

    if listing_id is not None:
        q = q.where(NotificationEvent.listing_id == listing_id)
    if channel:
        q = q.where(NotificationEvent.channel == channel)
    if status:
        q = q.where(NotificationEvent.status == status)
    if sent_from:
        q = q.where(NotificationEvent.sent_at >= sent_from)
    if sent_to:
        q = q.where(NotificationEvent.sent_at <= sent_to)

    count_sq = q.subquery("count_sq")
    total: int = db.execute(select(func.count()).select_from(count_sq)).scalar_one()

    order = (
        NotificationEvent.sent_at.asc()
        if sort_dir == "asc"
        else NotificationEvent.sent_at.desc()
    )
    rows = db.execute(
        q.order_by(order).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        NotificationEventRow(
            id=r.id,
            listing_id=r.listing_id,
            listing_title=r.listing_title,
            canonical_post_url=r.canonical_post_url,
            user_name=r.user_name,
            channel=r.channel,
            status=r.status,
            details=r.details,
            sent_at=r.sent_at,
        )
        for r in rows
    ]
    return PagedResponse(items=items, total=total, page=page, page_size=page_size)
