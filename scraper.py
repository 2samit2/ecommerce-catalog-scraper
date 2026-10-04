import asyncio
import re
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

import config

RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
RE_PRICE = re.compile(r"[\d.]+")


@dataclass(slots=True)
class Product:
    title: str
    category: str
    price: Decimal
    rating: int
    in_stock: bool
    image_url: str
    product_url: str

    def to_row(self):
        return [
            self.title,
            self.category,
            float(self.price),
            self.rating,
            "In stock" if self.in_stock else "Out of stock",
            self.image_url,
            self.product_url,
        ]


@dataclass
class ScrapingStats:
    pages_parsed: int = 0
    products_found: int = 0
    product_pages_parsed: int = 0
    errors: list = field(default_factory=list)


def parse_rating(tag):
    for cls in tag.get("class", []):
        if cls in RATING_MAP:
            return RATING_MAP[cls]
    return 0


def parse_stock(availability_text):
    return "in stock" in availability_text.lower()


def parse_price(price_text):
    match = RE_PRICE.search(price_text)
    return Decimal(match.group()) if match else Decimal("0")


class BooksScraper:
    def __init__(
        self,
        base_url=config.BASE_URL,
        max_concurrent=config.MAX_CONCURRENT_REQUESTS,
        headers=None,
        request_delay=config.REQUEST_DELAY,
        max_retries=config.MAX_RETRIES,
        retry_delay=config.RETRY_DELAY,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))
        self.headers = headers or config.DEFAULT_HEADERS
        self.request_delay = request_delay
        self.max_retries = max(1, int(max_retries))
        self.retry_delay = retry_delay
        self.stats = ScrapingStats()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=httpx.Timeout(
                    connect=config.CONNECT_TIMEOUT,
                    read=config.READ_TIMEOUT,
                    write=config.READ_TIMEOUT,
                    pool=config.READ_TIMEOUT,
                ),
                follow_redirects=True,
            )
        return self._client

    async def fetch(self, url):
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self.semaphore:
                    response = await self.client.get(url)
                    response.raise_for_status()
                if self.request_delay > 0:
                    await asyncio.sleep(self.request_delay)
                return response.text
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (404, 410):
                    return None
                logger.warning("HTTP {} on {} ({}/{})", exc.response.status_code, url, attempt, self.max_retries)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning("{} on {} ({}/{})", type(exc).__name__, url, attempt, self.max_retries)

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)

        self.stats.errors.append(url)
        return None

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def parse_product_page(self, html, product_url):
        soup = BeautifulSoup(html, "lxml")

        title_tag = soup.select_one(".product_main h1")
        if title_tag is None:
            return None

        category_tag = soup.select_one("ul.breadcrumb li:nth-of-type(3) a")
        price_tag = soup.select_one(".product_main .price_color")
        rating_tag = soup.select_one(".product_main .star-rating")
        availability_tag = soup.select_one(".product_main .availability")
        image_tag = soup.select_one("#product_gallery img")

        return Product(
            title=title_tag.get_text(strip=True),
            category=category_tag.get_text(strip=True) if category_tag else "",
            price=parse_price(price_tag.get_text(strip=True)) if price_tag else Decimal("0"),
            rating=parse_rating(rating_tag) if rating_tag else 0,
            in_stock=parse_stock(availability_tag.get_text(strip=True)) if availability_tag else False,
            image_url=urljoin(product_url, image_tag["src"]) if image_tag else "",
            product_url=product_url,
        )

    async def count_catalog_pages(self):
        html = await self.fetch(self.base_url)
        if html is None:
            raise RuntimeError("cannot load catalog page")
        current = BeautifulSoup(html, "lxml").select_one(".pager li.current")
        if not current:
            return 1
        match = re.search(r"Page \d+ of (\d+)", current.get_text(strip=True))
        return int(match.group(1)) if match else 1

    async def collect_product_urls(self, max_pages=0):
        urls = []
        page_url = self.base_url
        pages = 0

        while page_url and (max_pages <= 0 or pages < max_pages):
            html = await self.fetch(page_url)
            if html is None:
                break
            soup = BeautifulSoup(html, "lxml")
            for article in soup.select("article.product_pod"):
                a = article.select_one("h3 a")
                if a is not None:
                    urls.append(urljoin(page_url, a["href"]))
            self.stats.pages_parsed += 1
            pages += 1
            next_link = soup.select_one("li.next a")
            page_url = urljoin(page_url, next_link["href"]) if next_link else None
            logger.info("catalog page {}/{} done, {} links", pages, max_pages or "all", len(urls))

        return urls

    async def fetch_product(self, product_url):
        html = await self.fetch(product_url)
        if html is None:
            return None
        self.stats.product_pages_parsed += 1
        return self.parse_product_page(html, product_url)

    async def scrape(self, max_pages=0):
        logger.info("starting scraper: {}", self.base_url)
        total_pages = await self.count_catalog_pages()
        if max_pages > 0:
            total_pages = min(total_pages, max_pages)
        logger.info("pages to parse: {}", total_pages)

        product_urls = await self.collect_product_urls(max_pages)
        self.stats.products_found = len(product_urls)
        logger.success("product links: {}", len(product_urls))

        products = await asyncio.gather(*[self.fetch_product(u) for u in product_urls])
        products = [p for p in products if p is not None]
        logger.success("products parsed: {}/{}", len(products), len(product_urls))
        return products

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        await self.close()
