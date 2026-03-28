"""New Brunswick NBON Playwright spider — nbon-rpanb.gnb.ca.

The New Brunswick NBON (NB Open Procurement Network) portal loads tender data
inside iframes via jQuery/AJAX. Plain Scrapy requests return only the outer
shell page without the tender content. This spider uses scrapy-playwright with
playwright_include_page=True to render the full page including iframe content,
then extracts tender listings from the dynamically loaded HTML.

D-01: One spider file per source.
D-02: Accept everything — tenders with minimal fields are still valuable.
D-04: DOWNLOAD_DELAY=2, CONCURRENT_REQUESTS=1 — conservative for iframe JS portal.
"""
import logging

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# NBON welcome page — English entry point
_NB_START_URL = "https://nbon-rpanb.gnb.ca/welcome?Language=En"


class NewBrunswickSpider(Spider):
    """Scrapy Spider that ingests New Brunswick NBON tenders.

    Uses scrapy-playwright with playwright_include_page=True to render the
    iframe-based NBON portal. After rendering, extracts tender listings from
    the dynamically loaded iframe content. Handles iframe src following and
    Playwright page lifecycle management.
    """

    name = "new_brunswick"
    source_slug = "new_brunswick"

    # Conservative settings for iframe-based JS portal (D-04)
    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        """Yield the first request with Playwright rendering and page access enabled.

        playwright_include_page=True is required because we may need to interact
        with iframes and close the page after extraction.
        """
        yield scrapy.Request(
            url=_NB_START_URL,
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
        """Parse the Playwright-rendered NBON page.

        NBON uses iframe-based content loading. After Playwright renders the page:
        1. Check if tender content is in the main frame
        2. If iframes found, follow the tender-relevant iframe src URL
        3. Extract tender listings from rendered content

        Always closes the Playwright page at the end to prevent resource leaks.
        """
        page = response.meta.get("playwright_page")

        try:
            # Check if the main response already contains tender rows
            items_yielded = 0
            for row in response.css("table tbody tr, .tender-row, .procurement-row"):
                cells = row.css("td")
                if not cells:
                    continue
                record = self._extract_from_table_row(row, cells, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

            # If no items in main frame, look for iframe with tender content
            if items_yielded == 0:
                iframes = response.css("iframe")
                for iframe in iframes:
                    iframe_src = iframe.attrib.get("src", "")
                    if not iframe_src:
                        continue
                    iframe_url = response.urljoin(iframe_src)
                    # Follow iframe content as a new Playwright request
                    yield scrapy.Request(
                        url=iframe_url,
                        meta={
                            "playwright": True,
                            "playwright_include_page": False,
                            "playwright_page_methods": [
                                PageMethod("wait_for_load_state", "networkidle"),
                            ],
                        },
                        callback=self.parse_tenders,
                    )

            # If still no content found, log warning
            if items_yielded == 0 and not response.css("iframe"):
                logger.warning(
                    "NB spider: No tender rows or iframes found at %s — "
                    "site structure may have changed.",
                    response.url,
                )

        finally:
            # Always close the Playwright page to prevent resource leaks (D-playwright)
            if page:
                await page.close()

    def parse_tenders(self, response):
        """Parse a Playwright-rendered iframe or redirected tender listing page.

        Called when the main NBON page uses iframes to load tender content.
        Extracts tender rows from the rendered iframe HTML.
        """
        items_yielded = 0

        # Common table-based listing patterns
        for row in response.css("table tbody tr"):
            cells = row.css("td")
            if not cells:
                continue
            record = self._extract_from_table_row(row, cells, response)
            if record:
                yield self._record_to_item(record)
                items_yielded += 1

        # Fallback: div-based listing patterns
        if items_yielded == 0:
            for row in response.css(".tender-item, .procurement-item, [class*='tender']"):
                record = self._extract_from_div_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        if items_yielded == 0:
            logger.warning(
                "NB spider: No tender rows found in iframe content at %s",
                response.url,
            )

        # Pagination: follow next page link if present
        next_page = response.css(
            "a.next-page::attr(href), "
            "[class*='next']::attr(href), "
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
                callback=self.parse_tenders,
            )

    def _extract_from_table_row(self, row, cells, response) -> dict | None:
        """Extract tender data from an HTML table row.

        Expected column order (NBON typical):
        0: Reference/ID (may be linked)
        1: Title/Description
        2: Organization/Department
        3: Closing Date
        4: Status (optional)
        """
        # Reference number from first cell (may be a link)
        first_cell = cells[0]
        link = first_cell.css("a")
        if link:
            external_id = link.css("::text").get("").strip()
            href = link.attrib.get("href", "")
            url = response.urljoin(href) if href else None
        else:
            external_id = first_cell.css("::text").get("").strip() or None
            url = None

        # Title from second cell (or linked text in first cell)
        if len(cells) > 1:
            title = cells[1].css("::text").get("").strip() or None
        elif link:
            title = link.css("::text").get("").strip() or None
        else:
            title = None

        # If first cell has both ID and title (common pattern), use it as title fallback
        if not title and external_id:
            title = external_id
            external_id = None

        # Buyer org from third cell
        buyer_org = cells[2].css("::text").get("").strip() if len(cells) > 2 else None

        # Closing date from fourth cell
        closing_date = cells[3].css("::text").get("").strip() if len(cells) > 3 else None

        # Status from fifth cell (if present)
        status = cells[4].css("::text").get("").strip().lower() if len(cells) > 4 else None

        return {
            "title": title,
            "url": url,
            "external_id": external_id or "",
            "status": status or None,
            "published_date": None,
            "closing_date": closing_date or None,
            "buyer_org": buyer_org or None,
            "category": None,
        }

    def _extract_from_div_row(self, row, response) -> dict | None:
        """Extract tender data from a div-based listing row (fallback)."""
        link = row.css("a")
        if not link:
            return None

        title = link.css("::text").get("").strip() or row.css("::text").getall()[0].strip() if row.css("::text") else None
        href = link.attrib.get("href", "")
        url = response.urljoin(href) if href else None
        external_id = href.rstrip("/").split("/")[-1] if href else None

        closing_date = row.css("[class*='closing'], [class*='deadline']::text").get("").strip() or None
        status = row.css("[class*='status']::text").get("").strip().lower() or None

        return {
            "title": title,
            "url": url,
            "external_id": external_id or "",
            "status": status,
            "published_date": None,
            "closing_date": closing_date,
            "buyer_org": None,
            "category": None,
        }

    def _record_to_item(self, record: dict) -> TenderItem:
        """Map an extracted record dict to a TenderItem.

        Fixed fields: province='NB', jurisdiction='prov',
        source_slug='new_brunswick', value_currency='CAD'.
        NB NBON is bilingual but French fields not reliably extractable
        from dynamic content — title_fr set to None.
        """
        return TenderItem(
            source_slug="new_brunswick",
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
            province="NB",
            jurisdiction="prov",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=record.get("url"),
            raw_ocds=record,
        )

    async def _errback(self, failure):
        """Handle request errors gracefully — log and close page if available."""
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        logger.error(
            "NB spider: Request failed for %s — %s",
            failure.request.url,
            failure.value,
        )
