import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utcnow


class Listing(Base):
    """A product as listed by one source (a retailer, eventually eBay). One row per source+id."""

    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32))  # e.g. "bestbuy"
    external_id: Mapped[str] = mapped_column(String(128))  # the source's SKU / item id
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    condition: Mapped[str] = mapped_column(String(16))  # new | refurbished | used
    currency: Mapped[str] = mapped_column(String(3))
    image_url: Mapped[str | None] = mapped_column(Text, default=None)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Catalog linkage (part_id) is added once the canonical parts catalog exists.


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (Index("ix_price_snapshots_listing_captured", "listing_id", "captured_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    in_stock: Mapped[bool]
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
