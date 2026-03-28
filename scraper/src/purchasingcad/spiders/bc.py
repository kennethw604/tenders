"""BC Bid (ASP.NET + jQuery) Playwright spider.

BC Bid is an ASP.NET + Semantic UI + jQuery procurement portal operated by
the BC government. It is NOT Ivalua directly — the 2022 rebuild uses a custom
ASP.NET system. The portal has a reCAPTCHA v3 browser check gate that
auto-submits after 200ms when accessed by a real browser.

Design decisions followed:
- D-01: Server-rendered HTML after reCAPTCHA check — DOM scraping used.
- D-05: 30-second page load timeout — reCAPTCHA check + page render takes time.
- D-06: scrapy-playwright renders in real Chromium; reCAPTCHA v3 should pass
  with wait_for_load_state("networkidle") since it waits for the JS check
  to complete and the actual page to load.
- D-07: No auth required — public tender listings accessible without login.
  If reCAPTCHA detection fails (spider gets the verification page with no
  tender rows), log warning and yield nothing rather than crash.

Risk: reCAPTCHA v3 auto-submits after 200ms with real Chromium.
If Playwright headless mode specifically triggers detection failure,
add PageMethod("wait_for_timeout", 1500) before extraction.
"""
import logging

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# BC Bid public tender browse URL
_BC_START_URL = "https://www.bcbid.gov.bc.ca/page.aspx/en/rfp/request_browse_public"


class BcSpider(Spider):
    """Scrapy Spider that ingests BC tenders from BC Bid portal.

    Uses scrapy-playwright (playwright_include_page=False) to render the
    ASP.NET + jQuery page in Chromium. The networkidle wait state ensures
    the reCAPTCHA v3 browser check completes before extraction begins.

    Detects reCAPTCHA challenge page (bot check failed) and yields nothing
    with a warning rather than crashing or silently returning zero results.
    """

    name = "bc"
    source_slug = "bc"

    # Conservative settings for ASP.NET portal with reCAPTCHA (D-05, D-06)
    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,  # 30s per D-05
        "ROBOTSTXT_OBEY": False,  # Public procurement portal for suppliers
    }

    def start_requests(self):
        """Yield the first request with Playwright rendering enabled.

        networkidle waits for reCAPTCHA v3 to auto-resolve (200ms check)
        and for the actual tender list page to fully load.
        """
        yield scrapy.Request(
            url=_BC_START_URL,
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
        """Parse the Playwright-rendered BC Bid tender browse page.

        reCAPTCHA detection per D-07: if the response contains "recaptcha"
        text AND no tender rows are found, the bot check failed — log a
        warning and return early.

        Tries multiple HTML selector patterns for BC Bid ASP.NET tables:
        1. table tbody tr             (standard ASP.NET table)
        2. .rfp-listing tr, .request-row (BC Bid specific classes)
        3. [class*='pager'] ~ table tr (table near pager)

        Handles pagination via standard next-page link selectors.
        """
        page_text = response.text.lower()

        # Detect tender rows early to inform reCAPTCHA check
        tender_rows = (
            response.css("table tbody tr")
            or response.css(".rfp-listing tr, .request-row")
        )

        # reCAPTCHA detection per D-07: bot challenge page has "recaptcha"
        # text but zero tender rows — bail with warning
        if "recaptcha" in page_text and len(tender_rows) == 0:
            logger.warning(
                "BC spider: Bot challenge detected at %s — "
                "reCAPTCHA check may have failed. Yielding nothing. "
                "Playwright networkidle wait may need tuning.",
                response.url,
            )
            return

        items_yielded = 0

        # Pattern 1: Standard ASP.NET table
        rows = response.css("table tbody tr")
        if rows:
            for row in rows:
                record = self._extract_from_table_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        # Pattern 2: BC Bid specific CSS classes
        if items_yielded == 0:
            for row in response.css(".rfp-listing tr, .request-row"):
                record = self._extract_from_table_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        # Pattern 3: Table near pager
        if items_yielded == 0:
            for row in response.css("[class*='pager'] ~ table tr"):
                record = self._extract_from_table_row(row, response)
                if record:
                    yield self._record_to_item(record)
                    items_yielded += 1

        if items_yielded == 0:
            logger.warning(
                "BC spider: No tender rows found at %s — "
                "site structure may have changed or reCAPTCHA blocked access.",
                response.url,
            )

        # Pagination: look for next-page link
        next_page = response.css(
            "a[class*='next']::attr(href), "
            "li.active + li a::attr(href), "
            ".pager a:last-child::attr(href), "
            "[rel='next']::attr(href)"
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
        """Extract tender data from a BC Bid ASP.NET table row.

        BC Bid tables typically have columns:
        Title (linked) | Organization | Location | Published Date | Closing Date

        Returns None if no meaningful title link is found (skip header/empty rows).
        """
        cells = row.css("td")
        if not cells:
            return None

        # Find the linked title — it's usually in the first <td> with an <a>
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

        # Extract external_id from URL query params (purchasingGroupId param)
        external_id = None
        if href:
            if "purchasingGroupId=" in href:
                external_id = href.split("purchasingGroupId=")[-1].split("&")[0]
            elif "id=" in href:
                external_id = href.split("id=")[-1].split("&")[0]
            else:
                external_id = href.rstrip("/").split("/")[-1]

        # Extract remaining cells by position
        cell_texts = [c.css("::text").get("").strip() for c in cells]

        buyer_org = None
        closing_date = None
        published_date = None
        status = None

        for i, text in enumerate(cell_texts):
            if not text or text == title:
                continue
            # Date-like cells: contains "/" or is YYYY-MM-DD format
            if "/" in text or (len(text) == 10 and text.count("-") == 2):
                if published_date is None and closing_date is None:
                    # First date found is typically published date
                    published_date = text
                elif closing_date is None:
                    closing_date = text
            # Status-like short text
            elif text.lower() in ("open", "closed", "active", "pending", "awarded", "cancelled"):
                status = text.lower()
            # Longer text is likely org name
            elif len(text) > 5 and buyer_org is None and i > 0:
                buyer_org = text

        return {
            "title": title,
            "url": url,
            "external_id": external_id or "",
            "status": status,
            "published_date": published_date,
            "closing_date": closing_date,
            "buyer_org": buyer_org,
            "category": None,
        }

    def _record_to_item(self, record: dict) -> TenderItem:
        """Map an extracted record dict to a TenderItem.

        Fixed fields: province='BC', jurisdiction='prov', source_slug='bc',
        value_currency='CAD'. title_fr=None (BC portal is English-only).
        """
        return TenderItem(
            source_slug="bc",
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
            province="BC",
            jurisdiction="prov",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=record.get("url"),
            raw_ocds=record,
        )
