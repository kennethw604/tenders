"""NWT (Northwest Territories) spider for PurchasingCAD.

Scrapes tender listings from contracts.opennwt.ca, a Django-based procurement
portal. The site supports a CSV export endpoint (?format=csv) for bulk download.

Strategy:
1. First try CSV export: https://contracts.opennwt.ca/tenders/?format=csv&ps=1000
2. If CSV is unavailable (403, non-CSV response): fall back to HTML table parsing

Note: The site returned 403 during research from certain IPs. During production
use, respectful rate limiting and user-agent headers are applied.

D-04: DOWNLOAD_DELAY=3 — extra conservative due to 403 risk observed in research.
D-02: Lenient validation — missing fields stay None.
"""
import csv
import io
import logging
from urllib.parse import urljoin

from scrapy import Spider, Request

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

NWT_STATUS_MAP = {
    "open": "open",
    "closed": "closed",
    "awarded": "awarded",
    "cancelled": "cancelled",
    "active": "open",
    "complete": "closed",
    "completed": "closed",
}

CSV_URL = "https://contracts.opennwt.ca/tenders/?format=csv&ps=1000"
HTML_URL = "https://contracts.opennwt.ca/tenders/"


class NwtSpider(Spider):
    """Spider for Northwest Territories contracts.opennwt.ca portal.

    Attempts CSV export first for bulk access; falls back to HTML table parsing
    if the CSV endpoint returns a non-CSV response or error code.

    The site uses Django's standard URL patterns. CSV column names may vary
    between deployments — the spider handles multiple known field name variants.
    """

    name = "nwt"
    source_slug = "nwt"

    start_urls = [CSV_URL]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "ROBOTSTXT_OBEY": True,
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": "Mozilla/5.0 (compatible; PurchasingCAD/1.0; +https://github.com/purchasingcad)"
        },
    }

    def parse(self, response):
        """Route response to CSV or HTML parser based on Content-Type."""
        content_type = response.headers.get("Content-Type", b"").decode("utf-8", errors="ignore").lower()

        if "text/csv" in content_type or "application/csv" in content_type:
            yield from self.parse_csv_response(response)
        elif response.status == 200 and self._looks_like_csv(response.text):
            yield from self.parse_csv_response(response)
        else:
            logger.warning(
                "NwtSpider: CSV endpoint returned non-CSV response (status=%d, content-type=%s). "
                "Falling back to HTML listing.",
                response.status,
                content_type,
            )
            # Fall back to HTML listing
            yield Request(HTML_URL, callback=self.parse_html_response)

    def _looks_like_csv(self, text: str) -> bool:
        """Heuristic: first line should contain commas and no HTML tags."""
        first_line = text.strip().split("\n")[0] if text.strip() else ""
        return "," in first_line and "<" not in first_line

    def parse_csv_response(self, response):
        """Parse a CSV export response from contracts.opennwt.ca.

        The CSV export is undocumented — field names are inferred from the
        OCDS-based Django model. Handles multiple known column name variants.
        """
        text = response.text
        if not text.strip():
            logger.warning("NwtSpider: empty CSV response from %s", response.url)
            return

        try:
            reader = csv.DictReader(io.StringIO(text))
            count = 0
            for row in reader:
                item = self._csv_row_to_item(row)
                if item is not None:
                    yield item
                    count += 1
            logger.info("NwtSpider: parsed %d tenders from CSV at %s", count, response.url)
        except csv.Error as e:
            logger.error("NwtSpider: CSV parsing error: %s — falling back to HTML", e)
            yield Request(HTML_URL, callback=self.parse_html_response)

    def _csv_row_to_item(self, row: dict) -> "TenderItem | None":
        """Convert one CSV row dict to a TenderItem.

        Handles multiple possible column name variants from the OpenNWT Django app.
        Returns None if no usable identifier can be found.
        """
        # External ID: try multiple column name variants
        external_id = (
            row.get("ocid")
            or row.get("id")
            or row.get("reference")
            or row.get("tender_id")
            or ""
        ).strip()

        # Title: try multiple column name variants
        title = (
            row.get("title")
            or row.get("description")
            or row.get("tender_title")
            or row.get("name")
            or None
        )
        if title:
            title = title.strip() or None

        # Buyer org
        buyer_org = (
            row.get("buyer")
            or row.get("organization")
            or row.get("entity")
            or row.get("contracting_authority")
            or None
        )
        if buyer_org:
            buyer_org = buyer_org.strip() or None

        # Dates
        published_date = (row.get("published") or row.get("start_date") or row.get("issue_date") or None)
        closing_date = (row.get("closing") or row.get("close_date") or row.get("end_date") or None)

        # Status normalization
        status_raw = (row.get("status") or "").strip().lower()
        status = NWT_STATUS_MAP.get(status_raw, status_raw or None)

        # Source URL
        source_url = (row.get("url") or row.get("link") or row.get("detail_url") or None)
        if source_url:
            source_url = source_url.strip() or None
            if source_url and not source_url.startswith("http"):
                source_url = urljoin(HTML_URL, source_url)

        return TenderItem(
            source_slug="nwt",
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
            province="NT",
            jurisdiction="prov",
            category=None,
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=source_url,
            raw_ocds=dict(row),
        )

    def parse_html_response(self, response):
        """Fallback HTML table parser for contracts.opennwt.ca listing page.

        The OpenNWT site uses a standard Django list view with an HTML table.
        Column order: Title (linked), Buyer, Reference, Published, Closing, Status.
        Handles Django-style pagination by following 'next' page links.
        """
        rows = response.css("table tr")
        parsed_count = 0

        for row in rows:
            cells = row.css("td")
            if not cells:
                continue

            link = cells[0].css("a") if len(cells) >= 1 else None

            # Get title from link or plain text
            if link:
                title = link.css("::text").get("").strip() or None
                href = link.attrib.get("href", "")
                source_url = urljoin(response.url, href) if href else None
            else:
                title = cells[0].css("::text").get("").strip() or None
                source_url = None

            if not title and not source_url:
                continue

            buyer_org = cells[1].css("::text").get("").strip() if len(cells) > 1 else None
            external_id = cells[2].css("::text").get("").strip() if len(cells) > 2 else ""
            published_date = cells[3].css("::text").get("").strip() if len(cells) > 3 else None
            closing_date = cells[4].css("::text").get("").strip() if len(cells) > 4 else None
            status_raw = (cells[5].css("::text").get("").strip() if len(cells) > 5 else "").lower()
            status = NWT_STATUS_MAP.get(status_raw, status_raw or None)

            raw = {
                "title": title or "",
                "buyer": buyer_org or "",
                "external_id": external_id or "",
                "published_date": published_date or "",
                "closing_date": closing_date or "",
                "status": status_raw,
                "source_url": source_url or "",
            }

            yield TenderItem(
                source_slug="nwt",
                external_id=external_id or "",
                title=title,
                title_fr=None,
                description=None,
                description_fr=None,
                buyer_org=buyer_org or None,
                buyer_id=None,
                status=status,
                published_date=published_date or None,
                closing_date=closing_date or None,
                province="NT",
                jurisdiction="prov",
                category=None,
                unspsc_codes=None,
                value_amount=None,
                value_currency="CAD",
                source_url=source_url,
                raw_ocds=raw,
            )
            parsed_count += 1

        logger.info("NwtSpider: parsed %d tenders from HTML at %s", parsed_count, response.url)

        # Django-style pagination: follow 'next' page link
        next_link = response.css("a[rel='next']::attr(href), .next a::attr(href)").get()
        if next_link:
            yield Request(urljoin(response.url, next_link), callback=self.parse_html_response)
