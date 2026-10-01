from decimal import Decimal
from typing import Any

import httpx

from worker.retailers.bestbuy import BestBuy, parse_product

PRODUCT = {
    "sku": 123,
    "name": "Mini PC",
    "salePrice": 199.99,
    "onlineAvailability": True,
    "url": "https://www.bestbuy.com/site/123.p",
    "condition": "New",
    "image": "https://img/123.jpg",
}


class DictCache:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> Any:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.data[key] = value


def test_parse_product() -> None:
    listing = parse_product(PRODUCT)
    assert listing is not None
    assert listing.external_id == "123"
    assert listing.price == Decimal("199.99")
    assert listing.condition == "new"
    assert listing.currency == "USD"
    assert listing.in_stock is True


def test_parse_product_skips_unpriced() -> None:
    assert parse_product({**PRODUCT, "salePrice": None}) is None


async def test_fetch_paginates_dedupes_and_caches() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page"])
        return httpx.Response(
            200, json={"totalPages": 2, "products": [{**PRODUCT, "sku": 100 + page}, PRODUCT]}
        )

    cache = DictCache()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        retailer = BestBuy("KEY", client, cache=cache, queries=["ddr4 ecc"])
        listings = await retailer.fetch()
        assert sorted(item.external_id for item in listings) == ["101", "102", "123"]
        assert len(requests) == 2
        assert "search=ddr4&search=ecc" in str(requests[0].url)
        assert all("KEY" not in key for key in cache.data)

        await retailer.fetch()
        assert len(requests) == 2  # second run served from cache
