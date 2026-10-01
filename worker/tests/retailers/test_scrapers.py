from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from worker.retailers import canadacomputers, newegg
from worker.retailers.scrape import (
    BlockedByChallenge,
    PoliteFetcher,
    RobotsDisallowed,
    detect_condition,
    parse_price,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
UA = "TestBot/1.0 (+test)"


def test_parse_price() -> None:
    assert parse_price("$1,249.99") == Decimal("1249.99")
    assert parse_price(" $3.88 ") == Decimal("3.88")
    assert parse_price("See price in cart") is None


def test_detect_condition() -> None:
    assert detect_condition("Dell R730 Refurbished Server") == "refurbished"
    assert detect_condition("Lenovo M920q (Open Box)") == "refurbished"
    assert detect_condition("Used 8TB drive") == "used"
    assert detect_condition("Intel Xeon Silver") == "new"


def test_canadacomputers_parse() -> None:
    listings = canadacomputers.parse_search_page(
        (FIXTURES / "canadacomputers_search.html").read_text(encoding="utf8")
    )
    assert len(listings) == 3
    first = listings[0]
    assert first.source == "canadacomputers"
    assert first.currency == "CAD"
    assert first.price > 0
    assert "?" not in first.url  # tracking query string stripped
    assert first.external_id.isdigit()


def test_newegg_parse() -> None:
    listings = newegg.parse_search_page(
        (FIXTURES / "newegg_search.html").read_text(encoding="utf8")
    )
    assert len(listings) == 3
    first = listings[0]
    assert first.source == "newegg"
    assert first.external_id == "0XM-009Y-001R8"
    assert first.price == Decimal("1249.99")
    assert first.currency == "CAD"
    assert first.url == "https://www.newegg.ca/p/0XM-009Y-001R8"


def test_parsers_tolerate_garbage() -> None:
    assert canadacomputers.parse_search_page("<html></html>") == []
    assert newegg.parse_search_page("<html></html>") == []


def _fetcher(handler: httpx.MockTransport) -> tuple[PoliteFetcher, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    return PoliteFetcher(client, UA, delay_seconds=0), client


async def test_fetcher_respects_robots_and_sends_user_agent() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, text="<html>ok</html>")

    fetcher, client = _fetcher(httpx.MockTransport(handler))
    async with client:
        assert await fetcher.get_html("https://shop.test/search", {"s": "x"}) == "<html>ok</html>"
        with pytest.raises(RobotsDisallowed):
            await fetcher.get_html("https://shop.test/private/page")
    assert all(request.headers["user-agent"] == UA for request in seen)
    assert sum(request.url.path == "/robots.txt" for request in seen) == 1  # fetched once


async def test_fetcher_stops_on_challenge_instead_of_bypassing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(403, text="Just a moment...")

    fetcher, client = _fetcher(httpx.MockTransport(handler))
    async with client:
        with pytest.raises(BlockedByChallenge):
            await fetcher.get_html("https://shop.test/search")


async def test_fetcher_treats_blocked_robots_as_disallow_all() -> None:
    fetcher, client = _fetcher(httpx.MockTransport(lambda request: httpx.Response(403)))
    async with client:
        with pytest.raises(RobotsDisallowed):
            await fetcher.get_html("https://shop.test/search")


async def test_scraper_paginates_until_empty_page() -> None:
    page1 = (FIXTURES / "newegg_search.html").read_text(encoding="utf8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        page = request.url.params["page"]
        return httpx.Response(200, text=page1 if page == "1" else "<html></html>")

    fetcher, client = _fetcher(httpx.MockTransport(handler))
    async with client:
        listings = await newegg.Newegg(fetcher, queries=["xeon"]).fetch()
    assert len(listings) == 3


async def test_failed_query_keeps_earlier_results_and_continues() -> None:
    page = (FIXTURES / "newegg_search.html").read_text(encoding="utf8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        query = request.url.params["d"]
        if query == "bad":
            return httpx.Response(500)
        return httpx.Response(200, text=page if request.url.params["page"] == "1" else "")

    fetcher, client = _fetcher(httpx.MockTransport(handler))
    async with client:
        listings = await newegg.Newegg(fetcher, queries=["xeon", "bad", "epyc"]).fetch()
    assert len(listings) == 3  # xeon and epyc succeeded (same fixture items), "bad" skipped


async def test_challenge_stops_source_but_keeps_results() -> None:
    page = (FIXTURES / "newegg_search.html").read_text(encoding="utf8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.params["d"] == "blocked":
            return httpx.Response(403)
        return httpx.Response(200, text=page if request.url.params["page"] == "1" else "")

    fetcher, client = _fetcher(httpx.MockTransport(handler))
    async with client:
        listings = await newegg.Newegg(fetcher, queries=["xeon", "blocked", "epyc"]).fetch()
    assert len(listings) == 3
