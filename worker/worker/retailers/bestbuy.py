"""Best Buy (US) via the official Products API: https://bestbuy.github.io/api-documentation/"""

import hashlib
import json
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from worker.retailers.base import RawListing

BASE_URL = "https://api.bestbuy.com/v1/products"
SHOW_FIELDS = "sku,name,salePrice,onlineAvailability,url,condition,image"
PAGE_SIZE = 100
MAX_PAGES = 3
CACHE_TTL_SECONDS = 60 * 60

# Best Buy carries little true server gear; these target homelab-relevant retail items.
DEFAULT_QUERIES = ["mini pc", "nas", "xeon", "epyc", "ddr4 ecc", "ddr5 ecc", "server"]


class Cache(Protocol):
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: str, ex: int) -> Any: ...


class BestBuy:
    source = "bestbuy"

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        cache: Cache | None = None,
        queries: list[str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._cache = cache
        self._queries = queries or DEFAULT_QUERIES

    async def fetch(self) -> list[RawListing]:
        found: dict[str, RawListing] = {}
        for query in self._queries:
            for page in range(1, MAX_PAGES + 1):
                data = await self._get_page(query, page)
                for product in data.get("products", []):
                    listing = parse_product(product)
                    if listing is not None:
                        found[listing.external_id] = listing
                if page >= data.get("totalPages", 1):
                    break
        return list(found.values())

    async def _get_page(self, query: str, page: int) -> dict[str, Any]:
        # Multi-word queries become AND-ed search clauses: (search=ddr4&search=ecc)
        clause = "&".join(f"search={quote(word)}" for word in query.split())
        url = f"{BASE_URL}({clause})"
        params: dict[str, str | int] = {
            "apiKey": self._api_key,
            "format": "json",
            "show": SHOW_FIELDS,
            "pageSize": PAGE_SIZE,
            "page": page,
        }
        # Never include the API key in the cache key.
        cache_key = "retailer:bestbuy:" + hashlib.sha256(f"{url}|{page}".encode()).hexdigest()
        if self._cache is not None:
            cached = await self._cache.get(cache_key)
            if cached:
                result: dict[str, Any] = json.loads(cached)
                return result

        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        if self._cache is not None:
            await self._cache.set(cache_key, json.dumps(data), ex=CACHE_TTL_SECONDS)
        return data


def parse_product(product: dict[str, Any]) -> RawListing | None:
    price = product.get("salePrice")
    sku = product.get("sku")
    if price is None or sku is None or not product.get("name") or not product.get("url"):
        return None
    condition = str(product.get("condition") or "new").lower()
    return RawListing(
        source=BestBuy.source,
        external_id=str(sku),
        title=product["name"],
        url=product["url"],
        price=Decimal(str(price)),
        currency="USD",
        condition=condition if condition in {"new", "refurbished", "used"} else "new",
        in_stock=bool(product.get("onlineAvailability")),
        image_url=product.get("image"),
    )
