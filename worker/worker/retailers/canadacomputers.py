"""Canada Computers & Electronics (canadacomputers.com): no public API, so we parse search pages."""

from bs4 import BeautifulSoup

from worker.retailers.base import RawListing
from worker.retailers.scrape import PoliteFetcher, crawl_search, detect_condition, parse_price

SEARCH_URL = "https://www.canadacomputers.com/en/search"
MAX_PAGES = 3

DEFAULT_QUERIES = ["xeon", "epyc", "ecc ddr4", "mini pc", "nas", "server"]


class CanadaComputers:
    source = "canadacomputers"

    def __init__(self, fetcher: PoliteFetcher, queries: list[str] | None = None) -> None:
        self._fetcher = fetcher
        self._queries = queries or DEFAULT_QUERIES

    async def fetch(self) -> list[RawListing]:
        return await crawl_search(
            self._fetcher, self.source, SEARCH_URL, "s", self._queries, parse_search_page, MAX_PAGES
        )


def parse_search_page(html: str) -> list[RawListing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[RawListing] = []
    for card in soup.select("article.product-miniature"):
        description = card.select_one(".product-description")
        link = card.select_one("h2.product-title a")
        product_id = card.get("data-id-product")
        if description is None or link is None or not product_id:
            continue
        price = parse_price(str(description.get("data-final_price") or ""))
        href = link.get("href")
        if price is None or not href:
            continue
        title = link.get_text(strip=True)
        availability = card.select_one(".available-tag")
        in_stock = availability is not None and bool(
            availability.get("data-stock_availability_online")
            or availability.get("data-stock_availability_retail")
        )
        image = card.select_one("img[data-cc-src]")
        listings.append(
            RawListing(
                source=CanadaComputers.source,
                external_id=str(product_id),
                title=title,
                url=str(href).split("?")[0],
                price=price,
                currency="CAD",
                condition=detect_condition(title),
                in_stock=in_stock,
                image_url=str(image["data-cc-src"]) if image is not None else None,
            )
        )
    return listings
