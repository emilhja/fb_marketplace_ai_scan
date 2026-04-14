"""SQLAlchemy ORM models mirroring the schema created by pg_cache.ensure_database()."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    marketplace: Mapped[str] = mapped_column(Text, nullable=False)
    marketplace_listing_id: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_post_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    current_price: Mapped[str] = mapped_column(Text, nullable=False)
    original_price: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    last_content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    skick: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    availability: Mapped[str] = mapped_column(Text, nullable=False, server_default="Till Salu")
    is_tradera: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    contacted_seller: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    user_note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    user_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    vram_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    ai_evaluations: Mapped[list[AIEvaluation]] = relationship(
        "AIEvaluation", back_populates="listing", lazy="noload"
    )
    price_history: Mapped[list[ListingPriceHistory]] = relationship(
        "ListingPriceHistory", back_populates="listing", lazy="noload"
    )
    availability_history: Mapped[list[ListingAvailabilityHistory]] = relationship(
        "ListingAvailabilityHistory", back_populates="listing", lazy="noload"
    )
    notification_events: Mapped[list[NotificationEvent]] = relationship(
        "NotificationEvent", back_populates="listing", lazy="noload"
    )


class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    item_config_hash: Mapped[str] = mapped_column(Text, nullable=False)
    marketplace_config_hash: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(Text, nullable=False)
    listing_price: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    response_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    listing_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    evaluated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    listing: Mapped[Listing] = relationship("Listing", back_populates="ai_evaluations")


class ListingPriceHistory(Base):
    __tablename__ = "listing_price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    listing: Mapped[Listing] = relationship("Listing", back_populates="price_history")


class ListingAvailabilityHistory(Base):
    __tablename__ = "listing_availability_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    availability: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    listing: Mapped[Listing] = relationship("Listing", back_populates="availability_history")


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    user_name: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    listing: Mapped[Listing] = relationship("Listing", back_populates="notification_events")


class ListingRerunQueue(Base):
    __tablename__ = "listing_rerun_queue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
