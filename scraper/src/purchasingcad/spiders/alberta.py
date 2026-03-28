"""Alberta APC (Alberta Purchasing Connection) spider.

Uses scrapy-playwright with XHR interception to capture the Angular SPA's
JSON API response. The 1GX/APC portal renders tender data via an Angular
frontend that fetches from an internal API — exact endpoint unknown at
development time, so we intercept all matching XHR responses at runtime.

Per D-01 (XHR preferred), D-05 (30s timeout), D-06 (no stealth),
D-07 (skip if auth required).
"""
import logging

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Alberta Purchasing Connection search page
_AB_START_URL = "https://purchasing.alberta.ca/search"

# XHR URL substring patterns to match against API responses.
# Broad matching because exact Alberta 1GX API URL is unknown (RESEARCH Open Q1)
# — must be discovered at runtime. Log the matched URL when found.
_API_URL_PATTERNS = ["/api/", "/search", "/solicitation", "/tender", "/procurement"]


class AlbertaSpider(Spider):
    """Scrapy Spider that ingests Alberta APC tenders via XHR interception.

    Uses scrapy-playwright with playwright_include_page=True so we have
    access to the Playwright page object for registering XHR response
    listeners on the Angular SPA. Falls back to DOM scraping if XHR
    interception yields no data.
    """

    name = "alberta"
    source_slug = "alberta"

    # SPA settings: 30s timeout per D-05, conservative rate limiting
    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        """Yield the first request with Playwright page access for XHR interception."""
        yield scrapy.Request(
            url=_AB_START_URL,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_load_state", "networkidle"),
                ],
            },
            callback=self.parse,
            errback=self._errback,
        )

    async def parse(self, response):
        """Parse Alberta APC Angular SPA via XHR interception with DOM fallback.

        Strategy:
        1. Register XHR response listener before page interaction
        2. Wait for networkidle to ensure Angular has loaded
        3. If JSON data captured via XHR: yield TenderItems from parsed JSON
        4. If no XHR data: fall back to DOM scraping for rendered HTML
        5. If still 0 items: log warning per D-07

        Always closes the Playwright page in finally block to prevent leaks.
        """
        page = response.meta.get("playwright_page")
        captured_responses = []

        async def _capture_xhr(resp):
            """Capture XHR responses matching Alberta API URL patterns."""
            url = resp.url
            # Check URL patterns
            if not any(pattern in url for pattern in _API_URL_PATTERNS):
                return
            # Check content-type is JSON
            content_type = resp.headers.get("content-type", "")
            if "json" not in content_type.lower():
                return
            try:
                data = await resp.json()
                logger.info("Alberta spider: Captured XHR response from %s", url)
                captured_responses.append(data)
            except Exception as exc:
                logger.debug(
                    "Alberta spider: Failed to parse XHR response from %s — %s",
                    url,
                    exc,
                )

        try:
            if page:
                # Register XHR listener before re-triggering any page actions
                page.on("response", _capture_xhr)
                # Wait for networkidle again in case page needs settling
                await page.wait_for_load_state("networkidle")

            items_yielded = 0

            if captured_responses:
                # Process captured XHR JSON data
                for data in captured_responses:
                    records = self._extract_records_from_json(data, response.url)
                    for record in records:
                        yield self._json_to_item(record)
                        items_yielded += 1
                    # Pagination: check if captured URL had pageNumber param
                    # (handled via follow-up requests below if needed)
            else:
                # Fallback: DOM scraping for rendered Angular HTML
                logger.debug(
                    "Alberta spider: No XHR data captured at %s, trying DOM fallback",
                    response.url,
                )
                # Try Angular Material table rows and SPA listing patterns
                for row in response.css(
                    "table tbody tr, mat-row, [class*='solicitation'], [class*='bid-item']"
                ):
                    record = self._extract_from_dom_row(row, response)
                    if record:
                        yield self._json_to_item(record)
                        items_yielded += 1

            if items_yielded == 0:
                logger.warning(
                    "Alberta spider: No data captured via XHR or DOM at %s. "
                    "Check DevTools for actual API endpoint.",
                    response.url,
                )

        finally:
            # Always close the Playwright page to prevent resource leaks
            if page:
                await page.close()

    def _extract_records_from_json(self, data, source_url: str) -> list:
        """Extract list of tender records from captured JSON response data.

        Tries common API response envelope keys: 'results', 'items', 'data'.
        Falls back to treating data as a list directly.
        """
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("results", "items", "data", "solicitations", "tenders"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        logger.debug(
            "Alberta spider: Unexpected JSON structure from %s — %s",
            source_url,
            type(data).__name__,
        )
        return []

    def _extract_from_dom_row(self, row, response) -> dict | None:
        """Extract tender data from a DOM row element (fallback when XHR fails)."""
        link = row.css("a")
        if not link:
            return None
        title = link.css("::text").get("").strip() or row.css("::text").get("").strip()
        if not title:
            return None
        href = link.attrib.get("href", "")
        url = response.urljoin(href) if href else response.url
        external_id = href.rstrip("/").split("/")[-1] if href else None

        closing_date = row.css(
            "[class*='closing']::text, [class*='deadline']::text"
        ).get("").strip() or None
        status = row.css("[class*='status']::text").get("").strip().lower() or None

        return {
            "id": external_id,
            "title": title,
            "organizationName": None,
            "closingDate": closing_date,
            "publishDate": None,
            "status": status,
            "url": url,
        }

    def _json_to_item(self, record: dict) -> TenderItem:
        """Map Alberta JSON API record to TenderItem.

        Field names are best-guess based on typical Angular SPA API patterns
        for Alberta 1GX. Multiple key names checked gracefully for resilience.

        Fixed fields: province='AB', jurisdiction='prov', source_slug='alberta',
        value_currency='CAD', title_fr=None (Alberta portal is EN-only).
        """
        title = (
            record.get("title")
            or record.get("name")
            or record.get("solicitation_title")
        )
        external_id = str(
            record.get("id")
            or record.get("solicitation_id")
            or record.get("referenceNumber")
            or ""
        )
        buyer_org = (
            record.get("organizationName")
            or record.get("organization")
            or record.get("ministry")
        )
        status_raw = record.get("status", "") or ""
        status = status_raw.lower() if status_raw else None
        closing_date = record.get("closingDate") or record.get("closing_date")
        published_date = (
            record.get("publishDate")
            or record.get("published_date")
            or record.get("postedDate")
        )
        source_url = record.get("url") or (
            f"https://purchasing.alberta.ca/search/{record.get('id', '')}"
            if record.get("id")
            else _AB_START_URL
        )

        return TenderItem(
            source_slug="alberta",
            external_id=external_id,
            title=title,
            title_fr=None,
            description=None,
            description_fr=None,
            buyer_org=buyer_org,
            buyer_id=None,
            status=status,
            published_date=published_date,
            closing_date=closing_date,
            province="AB",
            jurisdiction="prov",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=source_url,
            raw_ocds=record,
        )

    async def _errback(self, failure):
        """Handle request errors gracefully — log and close page if available."""
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        logger.error(
            "Alberta spider: Request failed for %s — %s",
            failure.request.url,
            failure.value,
        )
