"""Pydantic v2 response and query parameter schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Listings + latest AI evaluation
# ---------------------------------------------------------------------------


class LatestAIEval(BaseModel):
    eval_id: int | None = None
    score: int | None = None
    conclusion: str | None = None
    comment: str | None = None
    listing_kind: str | None = None
    model: str | None = None
    response_model: str | None = None
    evaluated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ListingRow(BaseModel):
    id: int
    listing_key: str
    marketplace: str
    marketplace_listing_id: str
    canonical_post_url: str
    title: str
    current_price: str
    original_price: str
    description: str
    location: str
    skick: str
    availability: str
    is_tradera: bool
    message_sent: bool
    vram: str | None = None
    vram_override: str | None = None
    contacted_seller: bool
    user_note: str
    user_feedback: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    # latest AI evaluation (may be absent for newly seen listings)
    ai: LatestAIEval | None = None

    model_config = ConfigDict(from_attributes=True)


class ListingUpdateRequest(BaseModel):
    user_note: str | None = None
    user_feedback: str | None = None
    vram_override: str | None = None
    contacted_seller: bool | None = None


class ListingRerunRequest(BaseModel):
    listing_ids: list[int]


class ListingRerunResult(BaseModel):
    listing_id: int
    canonical_post_url: str | None = None
    target_item: str | None = None
    success: bool
    message: str


class ListingRerunResponse(BaseModel):
    results: list[ListingRerunResult]


# ---------------------------------------------------------------------------
# Price history
# ---------------------------------------------------------------------------


class PriceHistoryRow(BaseModel):
    id: int
    listing_id: int
    listing_title: str | None = None
    canonical_post_url: str | None = None
    price: str
    previous_price: str | None = None
    changed_by: int | None = None
    observed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Notification events
# ---------------------------------------------------------------------------


class NotificationEventRow(BaseModel):
    id: int
    listing_id: int
    listing_title: str | None = None
    canonical_post_url: str | None = None
    user_name: str
    channel: str
    status: str
    details: Any | None = None
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)
