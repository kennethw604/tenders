"""Ontario Tenders Portal (Jaggaer) Playwright spider.

Ontario Tenders Portal is powered by Jaggaer, a Java-based procurement SaaS
platform. The opportunity listing page uses server-rendered JSP HTML (`.do`
extension — Struts/Spring MVC) rather than a modern React SPA. Playwright is
still required to execute JavaScript and bypass any session/cookie setup.

Design decisions followed:
- D-01: XHR interception preferred; this portal is server-rendered HTML, so
  DOM scraping is used directly.
- D-05: 30-second page load timeout — SPAs and legacy Java portals are slow.
- D-06: scrapy-playwright renders in real Chromium; no stealth plugins needed.
- D-07: No auth required — public opportunity list accessible without login.
  If login redirect detected, log warning and yield nothing.
"""
import logging

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Ontario Tenders Portal — Jaggaer public opportunity list
_ONTARIO_START_URL = (
    "https://ontariotenders.app.jaggaer.com/esop/toolkit/opportunity/"
    "opportunityList.do?oppList=CURRENT&reset=true&resetstored=true"
)


class OntarioSpider(Spider):
    """Scrapy Spider that ingests Ontario tenders from Jaggaer portal.

    Uses scrapy-playwright (playwright_include_page=False) to render the
    Jaggaer JSP page in Chromium, then extracts tender listings from the
    server-rendered HTML table. Handles pagination via next-page links.

    The portal uses Jaggaer's legacy JSP UI — the `.do` URL extension
    indicates Java Struts/Spring MVC server rendering, not a React SPA.
    Playwright is still required to execute JavaScript before extraction.
    """

    name = "ontario"
    source_slug = "ontario"

    # Conservative settings for JS-heavy Jaggaer portal (D-05, D-06)
    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        """Yield the first request with Playwright rendering enabled."""
        yield scrapy.Request(
            url=_ONTARIO_START_URL,
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
        """Parse the Playwright-rendered Ontario Jaggaer opportunity list.

        Detects login/redirect pages and bails early. Tries multiple HTML
        selector patterns for Jaggaer tables in order:
        1. table.table tbody tr  (standard Jaggaer table with Bootstrap class)
        2. table tbody tr        (generic table fallback)
        3. .listbox_data tr, .opportunity-row (Jaggaer-specific classes)

        Handles pagination via standard next-page link selectors.
        """
        page_text = response.text.lower()

        # Detect login redirect per D-07 — if we get a login page, bail
        is_login_page = (
            "sign in" in page_text
            or "login" in response.url.lower()
            or ("username" in page_text and "password" in page_text)
        )
        if is_login_page:
            logger.warning(
                "Ontario spider: Login page detected at %s — "
                "public opportunity list not accessible. Yielding nothing.",
                response.url,
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

        # Pattern 3: Jaggaer-specific CSS classes
        if items_yielded == 0:
            for row in response.css(".listbox_data tr, .opportunity-row"):
                record = self._extract_from_table_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        if items_yielded == 0:
            logger.warning(
                "Ontario spider: No tender rows found at %s — "
                "site structure may have changed or no current tenders.",
                response.url,
            )

        # Pagination: look for next-page link
        next_page = response.css(
            "a.next::attr(href), "
            "[rel='next']::attr(href), "
            "a[title*='Next']::attr(href), "
            "li.pager__item--next a::attr(href)"
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
        """Extract tender data from a Jaggaer table row.

        Jaggaer tables typically have columns:
        Reference Number | Title (linked) | Organization | Closing Date | Status

        Returns None if no meaningful title link is found (skip header/empty rows).
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

        url = response.urljoin(href) if href else None

        # Extract external_id from URL query params or path segment
        external_id = None
        if href:
            # Try opportunityId param first
            if "opportunityId=" in href:
                external_id = href.split("opportunityId=")[-1].split("&")[0]
            elif "id=" in href:
                external_id = href.split("id=")[-1].split("&")[0]
            else:
                external_id = href.rstrip("/").split("/")[-1]

        # Extract text from remaining cells by position
        # Typical Jaggaer column order: Ref# | Title | Org | Closing | Status
        # We look for cells that look like dates or org names
        cell_texts = [c.css("::text").get("").strip() for c in cells]

        buyer_org = None
        closing_date = None
        published_date = None
        status = None
        ref_number = None

        for i, text in enumerate(cell_texts):
            if not text:
                continue
            # Reference number cell (short alphanumeric, no spaces usually)
            if i == 0 and len(text) < 30 and not " " in text:
                ref_number = text
                if not external_id:
                    external_id = text
            # Date-like cells
            elif "/" in text or (len(text) == 10 and text.count("-") == 2):
                if closing_date is None:
                    closing_date = text
                else:
                    published_date = text
            # Status-like short text
            elif text.lower() in ("open", "closed", "active", "pending", "awarded", "cancelled"):
                status = text.lower()
            # Longer text is likely org name (after the title cell)
            elif len(text) > 5 and text != title and buyer_org is None:
                if i > 0:  # Skip first cell which might be ref number
                    buyer_org = text

        return {
            "title": title,
            "url": url,
            "external_id": external_id or ref_number or "",
            "status": status,
            "published_date": published_date,
            "closing_date": closing_date,
            "buyer_org": buyer_org,
            "category": None,
        }

    def _record_to_item(self, record: dict) -> TenderItem:
        """Map an extracted record dict to a TenderItem.

        Fixed fields: province='ON', jurisdiction='prov', source_slug='ontario',
        value_currency='CAD'. title_fr=None (Ontario portal is EN-only for
        tender listings).
        """
        return TenderItem(
            source_slug="ontario",
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
            province="ON",
            jurisdiction="prov",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=record.get("url"),
            raw_ocds=record,
        )
