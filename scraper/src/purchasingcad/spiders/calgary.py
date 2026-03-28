"""Calgary municipal tenders spider via SAP Ariba Discovery.

Calgary exposes a public buyer profile page on SAP Ariba Discovery
(service.ariba.com/Discovery.aw) with server-rendered RJS listings.
This is different from the Alberta APC spider (Angular SPA with XHR) —
Ariba Discovery profile pages are server-rendered and do not require
XHR interception.

Pagination uses session-based tokens on Ariba; clicking the next-page
DOM element is required (URL construction fails per Research Pitfall 3).

Rate limiting: DOWNLOAD_DELAY=3 + AUTOTHROTTLE (conservative municipal rate).

ROBOTSTXT_OBEY=False: Ariba's robots.txt uses a whitelist approach that
default-denies unlisted user-agents, but profile pages are intentionally
public-facing buyer directories designed to be found by suppliers. The
portal itself has no login gate for viewing.
"""
import logging

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Calgary's public Ariba Discovery buyer profile page
_CALGARY_PROFILE_URL = "https://service.ariba.com/Discovery.aw/ad/profile?key=AN11042088414"

# Safety bound to prevent infinite pagination on session-based Ariba pages
_MAX_PAGES = 20


class CalgarySpider(Spider):
    """Scrapy Spider that ingests Calgary municipal tenders from SAP Ariba Discovery.

    Uses playwright_include_page=True to enable pagination via DOM clicks.
    Ariba Discovery uses session-based pagination tokens that expire if URLs
    are constructed manually (Research Pitfall 3) — only DOM click works.

    ROBOTSTXT_OBEY=False because Ariba's robots.txt default-denies generic
    crawlers but profile pages are designed as public-facing buyer directories.
    """

    name = "calgary"
    source_slug = "calgary"

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
        "AUTOTHROTTLE_ENABLED": True,
        # Ariba robots.txt uses whitelist approach — default-denies unlisted agents.
        # Profile pages are intentionally public-facing buyer directories for suppliers.
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        """Yield initial request with Playwright page access for pagination clicks."""
        yield scrapy.Request(
            url=_CALGARY_PROFILE_URL,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_load_state", "networkidle"),
                ],
                "page_num": 1,
            },
            callback=self.parse,
            errback=self._errback,
        )

    async def parse(self, response, **kwargs):
        """Parse Calgary Ariba Discovery profile page for tender listings.

        Extracts tender rows from server-rendered RJS table. Handles
        Ariba session-based pagination via DOM clicks. Always closes the
        Playwright page in finally block to prevent resource leaks.
        """
        page = response.meta.get("playwright_page")
        page_num = response.meta.get("page_num", 1)
        items_yielded = 0

        try:
            # Ariba Discovery server-rendered RJS table rows
            # Row classes alternate: 'rowOdd' and 'rowEven' per Research
            rows = response.css(
                "tr[class*='rowOdd'], tr[class*='rowEven'], table.dataTable tbody tr"
            )

            for row in rows:
                record = self._extract_from_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

            if items_yielded == 0:
                logger.warning(
                    "Calgary spider: No tender rows found at %s (page %d). "
                    "Ariba HTML structure may have changed.",
                    response.url,
                    page_num,
                )

            # Pagination: click next-page link in DOM (session tokens expire if URL constructed)
            if page and page_num < _MAX_PAGES and items_yielded > 0:
                next_btn = await page.query_selector(
                    "a[class*='next'], a[rel='next'], [class*='pagination'] a:last-child, "
                    "img[class*='next'], a:has(img[src*='next'])"
                )
                if next_btn:
                    logger.debug(
                        "Calgary spider: Clicking next-page (page %d -> %d)",
                        page_num,
                        page_num + 1,
                    )
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle")
                    # Re-parse the updated page content
                    content = await page.content()
                    new_response = response.replace(body=content.encode())
                    new_response.meta["page_num"] = page_num + 1
                    new_response.meta["playwright_page"] = page
                    # Yield from recursive parse (page stays open for pagination)
                    async for item in self.parse(new_response):
                        yield item
                    return  # Page closed in recursive call's finally block

        finally:
            if page:
                await page.close()

    def _extract_from_row(self, row, response) -> dict | None:
        """Extract tender record from a server-rendered Ariba table row.

        Returns None if row lacks a title link (likely a header or spacer row).
        source_url uses the profile page URL — individual bid URLs contain
        encrypted AuthTokens that expire.
        """
        # Title comes from the first linked cell (per Research DOM selectors)
        link = row.css("a[href*='ViewSourcingEvent'], a[href*='Event']") or row.css("td a")
        if not link:
            return None

        title = link.css("::text").get("").strip()
        if not title:
            return None

        # Reference/external_id: td containing a numeric pattern
        # Ariba typically puts the reference number in the 2nd or 3rd column
        cells = row.css("td")
        external_id = None
        closing_date = None
        category = None
        value_amount = None

        for cell in cells:
            cell_text = cell.css("::text").get("").strip()
            # Numeric patterns: reference numbers like "COC-2024-001" or "12345"
            if not external_id and cell_text and any(c.isdigit() for c in cell_text):
                # Prefer cells that look like ref numbers (not dates or currency)
                if not any(month in cell_text for month in [
                    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
                ]) and "$" not in cell_text and "/" not in cell_text[:4]:
                    external_id = cell_text

            # Date pattern: closing date
            if not closing_date and ("/" in cell_text or "-" in cell_text):
                # Simple heuristic: cells with date-like content
                if any(month in cell_text for month in [
                    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                    "2024", "2025", "2026",
                ]):
                    closing_date = cell_text

        return {
            "title": title,
            "external_id": external_id or "",
            "url": _CALGARY_PROFILE_URL,
            "closing_date": closing_date,
            "published_date": None,
            "status": "open",
            "buyer_org": "City of Calgary",
            "category": category,
            "value_amount": value_amount,
        }

    def _record_to_item(self, record: dict) -> TenderItem:
        """Map extracted record to TenderItem.

        Fixed fields: province='AB', jurisdiction='muni',
        source_slug='calgary', value_currency='CAD', title_fr=None
        (Ariba Discovery Calgary portal is EN-only).
        """
        return TenderItem(
            source_slug="calgary",
            external_id=record.get("external_id") or "",
            title=record.get("title"),
            title_fr=None,
            description=None,
            description_fr=None,
            buyer_org=record.get("buyer_org", "City of Calgary"),
            buyer_id=None,
            status=record.get("status"),
            published_date=record.get("published_date"),
            closing_date=record.get("closing_date"),
            province="AB",
            jurisdiction="muni",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=record.get("value_amount"),
            value_currency="CAD",
            source_url=record.get("url", _CALGARY_PROFILE_URL),
            raw_ocds=record,
        )

    async def _errback(self, failure):
        """Handle request errors — log and close Playwright page if available."""
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        logger.error(
            "Calgary spider: Request failed for %s — %s",
            failure.request.url,
            failure.value,
        )
