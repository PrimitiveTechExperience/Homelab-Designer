from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.listing import Listing, PriceSnapshot
from app.models.user import utcnow
from worker.retailers.base import RawListing

# Unchanged prices are still re-snapshotted this often so charts show the listing is alive.
HEARTBEAT = timedelta(days=1)


def _changed(last: PriceSnapshot, raw: RawListing, now: datetime) -> bool:
    # SQLite (tests) returns naive datetimes; Postgres returns aware ones.
    age = now - last.captured_at.replace(tzinfo=now.tzinfo)
    return age >= HEARTBEAT or last.price != raw.price or last.in_stock != raw.in_stock


def store_listings(db: Session, raw_listings: list[RawListing]) -> int:
    """Upsert listings; add a price snapshot if price/stock changed. Returns snapshots added."""
    now = utcnow()
    added = 0
    for raw in raw_listings:
        listing = db.scalar(
            select(Listing).where(
                Listing.source == raw.source, Listing.external_id == raw.external_id
            )
        )
        if listing is None:
            listing = Listing(source=raw.source, external_id=raw.external_id, first_seen_at=now)
            db.add(listing)
        listing.title = raw.title
        listing.url = raw.url
        listing.condition = raw.condition
        listing.currency = raw.currency
        listing.image_url = raw.image_url
        listing.last_seen_at = now
        db.flush()

        last = db.scalar(
            select(PriceSnapshot)
            .where(PriceSnapshot.listing_id == listing.id)
            .order_by(PriceSnapshot.captured_at.desc())
            .limit(1)
        )
        if last is None or _changed(last, raw, now):
            db.add(
                PriceSnapshot(
                    listing_id=listing.id,
                    price=raw.price,
                    in_stock=raw.in_stock,
                    captured_at=now,
                )
            )
            added += 1
    db.commit()
    return added
