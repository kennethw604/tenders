"""PEI Tenders Playwright spider — princeedwardisland.ca.

The PEI government tender listing is a Drupal-based site protected by Radware
bot detection. Plain Scrapy requests are redirected to a JavaScript challenge
at validate.perfdrive.com. This spider uses scrapy-playwright to render the
page through a real Chromium browser, bypassing the bot challenge.

D-01: One spider file per source.
D-02: Accept everything — tenders with minimal fields are still valuable.
D-04: DOWNLOAD_DELAY=2, CONCURRENT_REQUESTS=1 — conservative for JS portal.
"""
import logging

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# PEI tender listing URL — items_per_page=100 reduces pagination requests
_PEI_START_URL = (
    "https://www.princeedwardisland.ca/en/tenders?items_per_page=100"
)


class PeiSpider(Spider):
    """Scrapy Spider that ingests PEI tenders from princeedwardisland.ca.

    Uses scrapy-playwright to bypass Radware bot detection. After Playwright
    renders the page, extracts tender listings from the Drupal Views HTML.
    Handles pagination via Drupal's `?page=N` parameter.
    """

    name = "pei"
    source_slug = "pei"

    # Conservative settings for JS-heavy, bot-protected portal (D-04)
    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        """Yield the first request with Playwright rendering enabled."""
        yield scrapy.Request(
            url=_PEI_START_URL,
            meta={
                "playwright": True,
                "playwright_include_page": False,
                "playwright_page_methods": [
                    PageMethod("wait_for_load_state", "networkidle"),
                ],
            },
            callback=self.parse,
        )

    def parse(self, response):
        """Parse the Playwright-rendered PEI tender listing page.

        Tries multiple Drupal HTML patterns in order:
        1. .views-row (Drupal Views default row wrapper)
        2. article.node--type-tender (Drupal node listing)
        3. table tbody tr (table display fallback)

        Handles pagination via Drupal's pager links.
        """
        # Detect Radware challenge — if we still got a challenge page, bail
        page_text = response.text.lower()
        if "validate.perfdrive.com" in page_text or "bot challenge" in page_text:
            logger.warning(
                "PEI spider: Radware bot challenge not bypassed at %s — "
                "yielding nothing. Try updating user agent or playwright settings.",
                response.url,
            )
            return

        items_yielded = 0

        # Pattern 1: Drupal Views .views-row elements
        for row in response.css(".views-row"):
            record = self._extract_from_views_row(row, response)
            if record:
                yield self._record_to_item(record)
                items_yielded += 1

        # Pattern 2: Drupal node article listing (if .views-row not found)
        if items_yielded == 0:
            for article in response.css("article.node--type-tender, article[class*='tender']"):
                record = self._extract_from_article(article, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        # Pattern 3: Table display fallback
        if items_yielded == 0:
            for row in response.css("table tbody tr"):
                cells = row.css("td")
                if not cells:
                    continue
                record = self._extract_from_table_row(row, cells, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        if items_yielded == 0:
            logger.warning(
                "PEI spider: No tender rows found at %s — "
                "site structure may have changed.",
                response.url,
            )

        # Pagination: Drupal pager next link
        next_page = response.css(
            "li.pager__item--next a::attr(href), "
            ".pager-next a::attr(href), "
            "a[rel='next']::attr(href)"
        ).get()
        if next_page:
            yield scrapy.Request(
                url=response.urljoin(next_page),
                meta={
                    "playwright": True,
                    "playwright_include_page": False,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                    ],
                },
                callback=self.parse,
            )

    def _extract_from_views_row(self, row, response) -> dict | None:
        """Extract tender data from a Drupal .views-row element."""
        link = row.css("a")
        if not link:
            return None
        title = link.css("::text").get("").strip()
        if not title:
            # Try heading elements
            title = row.css("h2::text, h3::text, .views-field-title::text").get("").strip()
        href = link.attrib.get("href", "")
        url = response.urljoin(href) if href else None

        # Try to extract dates from common Drupal field classes
        closing_date = (
            row.css(".views-field-field-closing-date::text, .field-closing-date::text").get("").strip()
            or None
        )
        published_date = (
            row.css(".views-field-created::text, .field-created::text, .date-display-single::text").get("").strip()
            or None
        )
        status = (
            row.css(".views-field-field-status::text, .field-status::text").get("").strip().lower()
            or None
        )

        # Extract external_id from URL slug (last path segment)
        external_id = href.rstrip("/").split("/")[-1] if href else None

        return {
            "title": title or None,
            "url": url,
            "external_id": external_id,
            "status": status,
            "published_date": published_date,
            "closing_date": closing_date,
            "buyer_org": None,
            "category": None,
        }

    def _extract_from_article(self, article, response) -> dict | None:
        """Extract tender data from a Drupal article element."""
        link = article.css("a")
        if not link:
            return None
        title = link.css("::text").get("").strip() or article.css("h2::text, h3::text").get("").strip()
        href = link.attrib.get("href", "")
        url = response.urljoin(href) if href else None
        external_id = href.rstrip("/").split("/")[-1] if href else None

        closing_date = article.css("[class*='closing']::text, [class*='deadline']::text").get("").strip() or None
        status = article.css("[class*='status']::text").get("").strip().lower() or None

        return {
            "title": title or None,
            "url": url,
            "external_id": external_id,
            "status": status,
            "published_date": None,
            "closing_date": closing_date,
            "buyer_org": None,
            "category": None,
        }

    def _extract_from_table_row(self, row, cells, response) -> dict | None:
        """Extract tender data from a table row (fallback pattern)."""
        # Expect columns: Title, Status, Closing Date (order may vary)
        link = cells[0].css("a")
        if not link:
            return None
        title = link.css("::text").get("").strip()
        href = link.attrib.get("href", "")
        url = response.urljoin(href) if href else None
        external_id = href.rstrip("/").split("/")[-1] if href else None

        status = cells[1].css("::text").get("").strip().lower() if len(cells) > 1 else None
        closing_date = cells[2].css("::text").get("").strip() if len(cells) > 2 else None

        return {
            "title": title or None,
            "url": url,
            "external_id": external_id,
            "status": status or None,
            "published_date": None,
            "closing_date": closing_date or None,
            "buyer_org": None,
            "category": None,
        }

    def _record_to_item(self, record: dict) -> TenderItem:
        """Map an extracted record dict to a TenderItem.

        Fixed fields: province='PE', jurisdiction='prov', source_slug='pei',
        value_currency='CAD'. All French fields are None (PEI is English-only portal).
        """
        return TenderItem(
            source_slug="pei",
            external_id=record.get("external_id") or "",
            title=record.get("title"),
            title_fr=None,
            description=None,
            description_fr=None,
            buyer_org=record.get("buyer_org"),
            buyer_id=None,
            status=record.get("status"),
            published_date=record.get("published_date"),
            closing_date=record.get("closing_date"),
            province="PE",
            jurisdiction="prov",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=record.get("url"),
            raw_ocds=record,
        )
