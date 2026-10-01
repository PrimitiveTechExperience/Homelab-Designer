from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Listing, PriceSnapshot
from worker.ingest import store_listings
from worker.retailers.base import RawListing

RAW = RawListing(
    source="bestbuy",
    external_id="1",
    title="Mini PC",
    url="https://example.com/1",
    price=Decimal("100.00"),
    currency="USD",
    condition="new",
    in_stock=True,
)


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    engine.dispose()


def _snapshots(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(PriceSnapshot)) or 0


def test_first_run_creates_listing_and_snapshot(db: Session) -> None:
    assert store_listings(db, [RAW]) == 1
    assert db.scalar(select(func.count()).select_from(Listing)) == 1
    assert _snapshots(db) == 1


def test_unchanged_price_adds_no_snapshot(db: Session) -> None:
    store_listings(db, [RAW])
    assert store_listings(db, [RAW]) == 0
    assert _snapshots(db) == 1


def test_changed_price_or_stock_adds_snapshot_without_duplicating_listing(db: Session) -> None:
    store_listings(db, [RAW])
    store_listings(db, [replace(RAW, price=Decimal("90.00"))])
    store_listings(db, [replace(RAW, price=Decimal("90.00"), in_stock=False)])
    assert db.scalar(select(func.count()).select_from(Listing)) == 1
    assert _snapshots(db) == 3


def test_old_snapshot_gets_heartbeat(db: Session) -> None:
    store_listings(db, [RAW])
    snapshot = db.scalars(select(PriceSnapshot)).one()
    snapshot.captured_at -= timedelta(days=2)
    db.commit()
    assert store_listings(db, [RAW]) == 1
