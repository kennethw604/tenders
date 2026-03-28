"""Newfoundland and Labrador Government Tenders spider via MERX (merx.com/govnl).

gov.nl.ca/ppa routes all procurement to merx.com/govnl. Same MERX platform
as Manitoba — server-rendered HTML with ?pageNumber=N pagination. Extra
conservative rate limiting for commercial SaaS platform.

Key facts:
- Portal: https://www.merx.com/govnl/solicitations/open-bids
- Pagination: ?pageNumber=N (server-rendered, not AJAX)
- Detail link pattern: href contains purchasingGroupId=<ID>
"""
import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import scrapy
from scrapy import Spider
from scrapy_playwright.page import PageMethod

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

_NL_START_URL = "https://www.merx.com/govnl/solicitations/open-bids"

_MAX_PAGE = 20


class NewfoundlandSpider(Spider):
    """Scrapy Spider that ingests Newfoundland tenders from MERX (merx.com/govnl).

    MERX is a commercial platform with strict rate limits. Uses extra conservative
    settings: DOWNLOAD_DELAY=3, AUTOTHROTTLE_ENABLED=True. Pagination via
    ?pageNumber=N query parameter (server-rendered, not AJAX).
    """

    name = "newfoundland"
    source_slug = "newfoundland"

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        yield scrapy.Request(
            url=_NL_START_URL,
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
        """Parse a MERX Newfoundland tender listing page."""
        page_text_lower = response.text.lower()
        if "captcha" in page_text_lower or response.status == 429:
            logger.warning(
                "Newfoundland spider: Captcha or rate-limit detected at %s (status=%s) — "
                "skipping page.",
                response.url,
                response.status,
            )
            return

        items_yielded = 0

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
                title = link.xpath("../text()").get("").strip() or None

            external_id = self._extract_purchasing_group_id(href)
            source_url = response.urljoin(href)

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
                "Newfoundland spider: No tender links found at %s — "
                "MERX HTML structure may have changed.",
                response.url,
            )

        current_page = self._get_current_page(response.url)
        if items_yielded > 0 and current_page < _MAX_PAGE:
            next_page_url = self._build_next_page_url(response.url, current_page + 1)
            has_next = bool(
                response.css(
                    f"a[href*='pageNumber={current_page + 1}'], "
                    f"[class*='next'] a, "
                    f"a[rel='next']"
                ).get()
            )
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
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        ids = params.get("purchasingGroupId", [])
        return ids[0] if ids else None

    def _get_current_page(self, url: str) -> int:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        pages = params.get("pageNumber", ["1"])
        try:
            return int(pages[0])
        except (ValueError, IndexError):
            return 1

    def _build_next_page_url(self, current_url: str, next_page: int) -> str:
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        params["pageNumber"] = [str(next_page)]
        flat_params = {k: v[0] for k, v in params.items()}
        new_query = urlencode(flat_params)
        return urlunparse(parsed._replace(query=new_query))

    def _record_to_item(self, record: dict) -> TenderItem:
        return TenderItem(
            source_slug="newfoundland",
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
            province="NL",
            jurisdiction="prov",
            category=record.get("category"),
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=record.get("url"),
            raw_ocds=record,
        )
