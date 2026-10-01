from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class RawListing:
    """A retailer product normalized to the fields we store, before DB upsert."""

    source: str
    external_id: str
    title: str
    url: str
    price: Decimal
    currency: str
    condition: str  # new | refurbished | used
    in_stock: bool
    image_url: str | None = None


class Retailer(Protocol):
    source: str

    async def fetch(self) -> list[RawListing]:
        """Fetch current listings for all configured queries."""
        ...
