"""Winnipeg Municipal Tenders spider via MERX (merx.com/mbgov/cityofwinnipeg).

Server-rendered HTML with ?pageNumber=N pagination. MERX is a commercial
SaaS (Mediagrif) — extra conservative rate limiting required to avoid
triggering anti-bot measures or 429 responses.

Per D-03 (extra MERX rate limiting), D-05 (30s timeout), D-06 (no stealth).

Key facts from research:
- Portal: https://www.merx.com/mbgov/cityofwinnipeg
- Winnipeg moved to MERX as of March 1, 2025 (same platform as Manitoba)
- Pagination: ?pageNumber=N (non-AJAX, paginationOptions.ajax = false)
- Detail link pattern: href contains purchasingGroupId=<ID>
- MERX is server-rendered — playwright_include_page=False is sufficient
- jurisdiction="muni" (NOT "prov") — Winnipeg is a municipal government
- Note: merx.com/mbgov/cityofwinnipeg uses a tabbed interface (Open/Closed/Results/Awarded)
  but defaults to the Open tab — start URL is valid for open bids
"""
import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Winnipeg MERX open bids listing (defaults to Open tab)
_WPG_START_URL = "https://www.merx.com/mbgov/cityofwinnipeg"

# Safety bound to prevent infinite pagination
_MAX_PAGE = 20


class WinnipegSpider(Spider):
    """Scrapy Spider that ingests Winnipeg municipal tenders from MERX (merx.com/mbgov/cityofwinnipeg).

    MERX is a commercial platform with strict rate limits. Uses extra conservative
    settings: DOWNLOAD_DELAY=3, AUTOTHROTTLE_ENABLED=True. Pagination via
    ?pageNumber=N query parameter (server-rendered, not AJAX).

    Yields TenderItems with jurisdiction="muni" and province="MB".
    """

    name = "winnipeg"
    source_slug = "winnipeg"

    # Extra conservative for MERX commercial platform (D-03)
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
            url=_WPG_START_URL,
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
        """Parse a MERX Winnipeg tender listing page.

        Detects captcha/block and returns early. Tries multiple CSS patterns
        for MERX div-based listings, extracting external_id from
        purchasingGroupId URL param. Handles ?pageNumber=N pagination.
        """
        # Detect block / captcha response
        page_text_lower = response.text.lower()
        if "captcha" in page_text_lower or response.status == 429:
            logger.warning(
                "Winnipeg spider: Captcha or rate-limit detected at %s (status=%s) — "
                "skipping page.",
                response.url,
                response.status,
            )
            return

        items_yielded = 0

        # Pattern 1: MERX solicitation/bid link patterns (div-based, not table)
        tender_links = (
            response.css("[class*='solicitation'] a, [class*='bid-item'] a")
            or response.css(".search-results-item a, .result-item a")
            or response.css("a[href*='purchasingGroupId']")
        )

        for link in tender_links:
            href = link.attrib.get("href", "")
            if not href:
                continue

            title = link.css("::text").get("").strip()
            if not title:
                # Try parent element text
                title = link.xpath("../text()").get("").strip() or None

            # Extract external_id from purchasingGroupId query param
            external_id = self._extract_purchasing_group_id(href)
            source_url = response.urljoin(href)

            # Extract buyer_org and closing_date from sibling/parent elements
            parent = link.xpath("..")
            buyer_org = (
                parent.css("[class*='organization']::text, [class*='ministry']::text").get("").strip()
                or parent.xpath("..//*[contains(@class, 'org')]//text()").get("").strip()
                or None
            )
            closing_date = (
                parent.css("[class*='closing']::text, [class*='deadline']::text, [class*='close']::text").get("").strip()
                or parent.xpath("..//time/@datetime").get("").strip()
                or None
            )
            published_date = (
                parent.css("[class*='publish']::text, [class*='posted']::text").get("").strip()
                or None
            )

            record = {
                "title": title or None,
                "url": source_url,
                "external_id": external_id or "",
                "status": None,
                "published_date": published_date or None,
                "closing_date": closing_date or None,
                "buyer_org": buyer_org or None,
                "category": None,
            }
            yield self._record_to_item(record)
            items_yielded += 1

        if items_yielded == 0:
            logger.warning(
                "Winnipeg spider: No tender links found at %s — "
                "MERX HTML structure may have changed.",
                response.url,
            )

        # Pagination: MERX uses ?pageNumber=N (non-AJAX, per research)
        current_page = self._get_current_page(response.url)
        if items_yielded > 0 and current_page < _MAX_PAGE:
            # Check if a next page link exists explicitly
            next_page_url = self._build_next_page_url(response.url, current_page + 1)
            has_next = bool(
                response.css(
                    f"a[href*='pageNumber={current_page + 1}'], "
                    f"[class*='next'] a, "
                    f"a[rel='next']"
                ).get()
            )
            if has_next or (items_yielded > 0 and current_page == 1):
                # On page 1 with results: speculatively try page 2
                # On subsequent pages: only continue if explicit next-page link found
                if current_page == 1 or has_next:
                    yield scrapy.Request(
                        url=next_page_url,
                        meta={
                            "playwright": True,
                            "playwright_include_page": False,
                            "playwright_page_methods": [
                                PageMethod("wait_for_load_state", "networkidle"),
                            ],
                        },
                        callback=self.parse,
                    )

    def _extract_purchasing_group_id(self, href: str) -> str | None:
        """Extract purchasingGroupId value from MERX URL query string."""
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        ids = params.get("purchasingGroupId", [])
        return ids[0] if ids else None

    def _get_current_page(self, url: str) -> int:
        """Parse current pageNumber from URL, defaulting to 1."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        pages = params.get("pageNumber", ["1"])
        try:
            return int(pages[0])
        except (ValueError, IndexError):
            return 1

    def _build_next_page_url(self, current_url: str, next_page: int) -> str:
        """Build URL with pageNumber=next_page query parameter."""
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        params["pageNumber"] = [str(next_page)]
        # Flatten list values for urlencode
        flat_params = {k: v[0] for k, v in params.items()}
        new_query = urlencode(flat_params)
        return urlunparse(parsed._replace(query=new_query))

    def _record_to_item(self, record: dict) -> TenderItem:
        """Map an extracted record dict to a TenderItem.

        Fixed fields: province='MB', jurisdiction='muni',
        source_slug='winnipeg', value_currency='CAD', title_fr=None
        (Winnipeg MERX portal is English-only).
        """
        return TenderItem(
            source_slug="winnipeg",
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
            province="MB",
            jurisdiction="muni",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=record.get("url"),
            raw_ocds=record,
        )
