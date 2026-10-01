"""Newegg.ca: no public product API (Newegg's API is seller-only), so we parse search pages.

Only plain search URLs (`/p/pl?d=...&page=N`) are requested; robots.txt disallows sort/order
variants and PoliteFetcher refuses anything it disallows.
"""

from bs4 import BeautifulSoup

from worker.retailers.base import RawListing
from worker.retailers.scrape import PoliteFetcher, crawl_search, detect_condition, parse_price

SEARCH_URL = "https://www.newegg.ca/p/pl"
MAX_PAGES = 3

DEFAULT_QUERIES = ["xeon", "epyc", "ecc ddr4", "mini pc", "nas", "server"]


class Newegg:
    source = "newegg"

    def __init__(self, fetcher: PoliteFetcher, queries: list[str] | None = None) -> None:
        self._fetcher = fetcher
        self._queries = queries or DEFAULT_QUERIES

    async def fetch(self) -> list[RawListing]:
        return await crawl_search(
            self._fetcher, self.source, SEARCH_URL, "d", self._queries, parse_search_page, MAX_PAGES
        )


def parse_search_page(html: str) -> list[RawListing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[RawListing] = []
    for container in soup.select(".item-cell .item-container"):
        item_id = container.get("id")
        title_link = container.select_one("a.item-title")
        price_el = container.select_one("li.price-current")
        if not item_id or title_link is None or price_el is None:
            continue
        strong = price_el.find("strong")
        if strong is None:
            continue  # e.g. "See price in cart"
        cents = price_el.find("sup")
        price = parse_price(
            strong.get_text(strip=True) + (cents.get_text(strip=True) if cents else "")
        )
        href = title_link.get("href")
        if price is None or not href:
            continue
        title = title_link.get_text(strip=True)
        image = container.select_one("a.item-img img")
        listings.append(
            RawListing(
                source=Newegg.source,
                external_id=str(item_id),
                title=title,
                url=str(href).split("?")[0],
                price=price,
                currency="CAD",
                condition=detect_condition(title),
                in_stock=container.select_one("button.btn-primary") is not None,
                image_url=str(image["src"]) if image is not None and image.get("src") else None,
            )
        )
    return listings
