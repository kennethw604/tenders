"""Vancouver Municipal Tenders spider via Jaggaer/SciQuest portal.

Vancouver's bids portal (bids.vancouver.ca) redirects to bids.sciquest.com —
the same Jaggaer platform used by Ontario (ontariotenders.app.jaggaer.com).
Server-rendered HTML with jQuery + Kendo UI pagination.

Per D-03 (extra rate limiting), D-05 (30s timeout), D-06 (no stealth).

Key facts from research:
- Portal: https://bids.sciquest.com/apps/Router/PublicEvent?CustomerOrg=CityofVancouver
- Platform: Jaggaer (formerly SciQuest) — same as Ontario portal
- Rendering: server-rendered HTML + jQuery + Kendo UI (NOT Angular SPA)
- Table structure: HTML table with rows per opportunity
- Fields per row: Status badge, linked title, Open date, Close date,
  Procurement type (RFP/ITT/RFQ/RFEOI), Reference number, Contact
- IMPORTANT: Individual bid URLs use encrypted AuthToken params — do NOT store them.
  Use the listing page URL as source_url instead.
- jurisdiction="muni" — Vancouver is a municipal government
"""
import logging

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Vancouver Jaggaer/SciQuest public opportunity listing
_VAN_START_URL = "https://bids.sciquest.com/apps/Router/PublicEvent?CustomerOrg=CityofVancouver"

# Fixed buyer org for all Vancouver tenders
_BUYER_ORG = "City of Vancouver"


class VancouverSpider(Spider):
    """Scrapy Spider that ingests Vancouver municipal tenders from Jaggaer/SciQuest.

    Uses scrapy-playwright (playwright_include_page=False) to render the
    Jaggaer SciQuest page in Chromium, then extracts tender listings from the
    server-rendered HTML table. Handles pagination via next-page links.

    IMPORTANT: Individual bid detail URLs use encrypted AuthToken parameters
    that expire — they cannot be stored as source_url. The listing page URL
    is used as source_url fallback.

    Yields TenderItems with jurisdiction="muni" and province="BC".
    """

    name = "vancouver"
    source_slug = "vancouver"

    # Conservative settings for Jaggaer portal (D-03, D-05, D-06)
    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        """Yield the first request with Playwright rendering (server-rendered HTML)."""
        yield scrapy.Request(
            url=_VAN_START_URL,
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
        """Parse the Playwright-rendered Vancouver Jaggaer opportunity list.

        Detects captcha/block and returns early. Tries multiple HTML selector
        patterns for Jaggaer/SciQuest tables. Handles pagination via next-page
        link selectors.

        ANTI-PATTERN: Do NOT store AuthToken bid detail URLs as source_url —
        they use encrypted tokens that expire and will 403 when revisited.
        Use response.urljoin(href) for any stable reference, or fall back to
        the listing page URL.
        """
        # Detect block / captcha response
        page_text_lower = response.text.lower()
        if "captcha" in page_text_lower or response.status == 429:
            logger.warning(
                "Vancouver spider: Captcha or rate-limit detected at %s (status=%s) — "
                "skipping page.",
                response.url,
                response.status,
            )
            return

        items_yielded = 0

        # Pattern 1: Standard Jaggaer table with Bootstrap .table class
        rows = response.css("table.table tbody tr")
        if rows:
            for row in rows:
                record = self._extract_from_table_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        # Pattern 2: Generic table fallback
        if items_yielded == 0:
            for row in response.css("table tbody tr"):
                record = self._extract_from_table_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        # Pattern 3: Jaggaer/SciQuest specific classes
        if items_yielded == 0:
            for row in response.css(".listbox_data tr, .opportunity-row, .rfq-row"):
                record = self._extract_from_table_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        if items_yielded == 0:
            logger.warning(
                "Vancouver spider: No tender rows found at %s — "
                "site structure may have changed or no current tenders.",
                response.url,
            )

        # Pagination: look for next-page link (Jaggaer/Kendo UI pagination)
        next_page = response.css(
            "a.next::attr(href), "
            "[rel='next']::attr(href), "
            "a[title*='Next']::attr(href), "
            "li.pager__item--next a::attr(href), "
            ".k-pager-nav.k-pager-next::attr(href)"
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

    def _extract_from_table_row(self, row, response) -> dict | None:
        """Extract tender data from a Jaggaer/SciQuest table row.

        Vancouver Jaggaer tables typically have columns:
        Status | Title (linked) | Open Date | Close Date | Procurement Type | Reference # | Contact

        Returns None if no meaningful title link is found (skip header/empty rows).

        IMPORTANT: If the title link href contains 'AuthToken=', use the listing
        page URL (_VAN_START_URL) as source_url — AuthToken URLs expire and cannot
        be stored as permanent references.
        """
        cells = row.css("td")
        if not cells:
            return None

        # Find the linked title — it's usually in a <td> with an <a>
        link = None
        title = None
        href = ""
        for cell in cells:
            a = cell.css("a")
            if a:
                link = a
                title = a.css("::text").get("").strip()
                href = a.attrib.get("href", "")
                if title:
                    break

        # If no linked title found, try plain text in first cell
        if not title:
            title = cells[0].css("::text").get("").strip() if cells else ""

        if not title:
            return None

        # ANTI-PATTERN guard: AuthToken URLs expire — use listing page URL as fallback
        if href and "AuthToken=" in href:
            source_url = _VAN_START_URL
        elif href:
            source_url = response.urljoin(href)
        else:
            source_url = _VAN_START_URL

        # Extract cell texts for field mapping
        cell_texts = [c.css("::text").get("").strip() for c in cells]

        external_id = None
        closing_date = None
        published_date = None
        status = None

        for i, text in enumerate(cell_texts):
            if not text:
                continue
            # Status badge (first or last column typically)
            if text.lower() in ("open", "closed", "active", "pending", "awarded", "cancelled"):
                status = text.lower()
            # Date-like cells (DD/MM/YYYY or YYYY-MM-DD or MM/DD/YYYY)
            elif "/" in text or (len(text) == 10 and text.count("-") == 2):
                if closing_date is None:
                    closing_date = text
                else:
                    published_date = text
            # Reference number: short alphanumeric, no spaces, not the title
            elif text != title and len(text) < 30 and (
                any(c.isdigit() for c in text) and len(text) > 2
            ):
                if external_id is None:
                    external_id = text

        return {
            "title": title,
            "url": source_url,
            "external_id": external_id or "",
            "status": status,
            "published_date": published_date,
            "closing_date": closing_date,
            "buyer_org": _BUYER_ORG,
            "category": None,
        }

    def _record_to_item(self, record: dict) -> TenderItem:
        """Map an extracted record dict to a TenderItem.

        Fixed fields: province='BC', jurisdiction='muni',
        source_slug='vancouver', value_currency='CAD',
        buyer_org='City of Vancouver' (always fixed — single-buyer portal).
        title_fr=None (Vancouver portal is English-only).
        """
        return TenderItem(
            source_slug="vancouver",
            external_id=record.get("external_id") or "",
            title=record.get("title"),
            title_fr=None,
            description=None,
            description_fr=None,
            buyer_org="City of Vancouver",
            buyer_id=None,
            status=record.get("status"),
            published_date=record.get("published_date"),
            closing_date=record.get("closing_date"),
            province="BC",
            jurisdiction="muni",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=record.get("url"),
            raw_ocds=record,
        )
