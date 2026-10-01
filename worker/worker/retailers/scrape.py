"""Shared plumbing for scraped retailers: robots.txt, rate limiting, caching, price parsing."""

import asyncio
import hashlib
import logging
import re
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from worker.retailers.base import RawListing

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60 * 60
_REFURB_RE = re.compile(r"\b(refurbished|renewed|open[- ]box)\b", re.I)
_USED_RE = re.compile(r"\bused\b", re.I)


class Cache(Protocol):
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: str, ex: int) -> Any: ...


class RobotsDisallowed(Exception):
    """Raised instead of fetching a URL that robots.txt disallows for us."""


class BlockedByChallenge(Exception):
    """The site served a bot challenge / 403. We stop rather than try to get around it."""


class PoliteFetcher:
    """GETs HTML pages: honours robots.txt, spaces requests out, caches in Redis."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        user_agent: str,
        delay_seconds: float,
        cache: Cache | None = None,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._delay = delay_seconds
        self._cache = cache
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request = 0.0

    async def get_html(self, url: str, params: dict[str, str] | None = None) -> str:
        request = self._client.build_request(
            "GET", url, params=params, headers={"User-Agent": self._user_agent}
        )
        full_url = str(request.url)
        cache_key = "scrape:" + hashlib.sha256(full_url.encode()).hexdigest()
        if self._cache is not None:
            cached = await self._cache.get(cache_key)
            if cached:
                return cached.decode() if isinstance(cached, bytes) else str(cached)

        if not await self._allowed(full_url):
            raise RobotsDisallowed(full_url)
        response = await self._throttled_get(request)
        if response.status_code in (403, 429, 503):
            raise BlockedByChallenge(f"{response.status_code} from {urlsplit(full_url).netloc}")
        response.raise_for_status()
        if self._cache is not None:
            await self._cache.set(cache_key, response.text, ex=CACHE_TTL_SECONDS)
        return response.text

    async def _throttled_get(self, request: httpx.Request) -> httpx.Response:
        wait = self._last_request + self._delay - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await self._client.send(request, follow_redirects=True)
        finally:
            self._last_request = time.monotonic()

    async def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = RobotFileParser()
            response = await self._throttled_get(
                self._client.build_request(
                    "GET", f"{origin}/robots.txt", headers={"User-Agent": self._user_agent}
                )
            )
            if response.status_code in (401, 403):
                parser.parse(
                    ["User-agent: *", "Disallow: /"]
                )  # blocked robots.txt: assume no access
            elif response.status_code >= 400:
                parser.parse(["User-agent: *", "Allow: /"])
            else:
                parser.parse(response.text.splitlines())
            self._robots[origin] = parser
        return self._robots[origin].can_fetch(self._user_agent, url)


def parse_price(text: str) -> Decimal | None:
    """'$1,249.99' -> Decimal('1249.99'). None if no price is present."""
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    return Decimal(match.group(0).replace(",", "")) if match else None


def detect_condition(title: str) -> str:
    if _REFURB_RE.search(title):
        return "refurbished"
    if _USED_RE.search(title):
        return "used"
    return "new"


async def crawl_search(
    fetcher: PoliteFetcher,
    source: str,
    url: str,
    query_param: str,
    queries: list[str],
    parse: Callable[[str], list[RawListing]],
    max_pages: int,
) -> list[RawListing]:
    """Run each query across result pages, keeping whatever was collected if something fails.

    A failing query is skipped; a bot challenge or robots.txt refusal stops the whole source.
    """
    found: dict[str, RawListing] = {}
    for query in queries:
        try:
            for page in range(1, max_pages + 1):
                html = await fetcher.get_html(url, {query_param: query, "page": str(page)})
                listings = parse(html)
                if not listings:
                    break
                for listing in listings:
                    found[listing.external_id] = listing
        except (BlockedByChallenge, RobotsDisallowed) as error:
            logger.warning("%s: stopping, access refused (%s)", source, error)
            break
        except httpx.HTTPError:
            logger.exception("%s: query %r failed, continuing", source, query)
    return list(found.values())
