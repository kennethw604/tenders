"""Saskatchewan HTML spider for PurchasingCAD.

Scrapes tender listings from SaskTenders (sasktenders.ca), a server-side
ASP.NET portal with sortable HTML tables. No authentication required.

D-04: DOWNLOAD_DELAY=2 — conservative rate limiting for HTML source.
D-02: Lenient validation — missing fields stay None; all rows with a link yielded.
"""
import logging
from urllib.parse import urljoin

from scrapy import Spider

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Saskatchewan SaskTenders status text -> normalized status
SK_STATUS_MAP = {
    "open": "open",
    "closed": "closed",
    "awarded": "awarded",
    "cancelled": "cancelled",
}


class SaskatchewanSpider(Spider):
    """Scrapy Spider that scrapes tender listings from sasktenders.ca.

    Targets the public search page which returns a server-side rendered HTML
    table. Each row contains: Competition Name (linked), Organization,
    Competition Number, Open Date, Close Date, Status.

    Pagination: The site supports a ?ps=100 parameter to show up to 100 results
    per page. We use this to maximize rows per request and handle pagination
    via ASP.NET page controls if present.
    """

    name = "saskatchewan"
    source_slug = "saskatchewan"

    # All active tenders listing — first page with 100 per page
    start_urls = ["https://sasktenders.ca/Content/Public/Search.aspx"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "ROBOTSTXT_OBEY": True,
    }

    def parse(self, response):
        """Parse the HTML table rows from a SaskTenders listing page.

        Selects all table rows, skips header rows (no <a> in first cell),
        and yields one TenderItem per data row.
        """
        rows = response.css("table tr")
        parsed_count = 0

        for row in rows:
            cells = row.css("td")
            if not cells:
                continue  # Skip header rows (th-only rows)

            # First cell must have a link — that's the Competition Name
            link = cells[0].css("a") if len(cells) >= 1 else None
            if not link:
                continue  # Skip rows without a competition name link

            title = link.css("::text").get("").strip() or None
            detail_href = link.attrib.get("href", "")
            source_url = urljoin(response.url, detail_href) if detail_href else None

            # Column order: Name, Organization, Competition Number, Open Date, Close Date, Status
            org = cells[1].css("::text").get("").strip() if len(cells) > 1 else None
            comp_num = cells[2].css("::text").get("").strip() if len(cells) > 2 else None
            open_date = cells[3].css("::text").get("").strip() if len(cells) > 3 else None
            close_date = cells[4].css("::text").get("").strip() if len(cells) > 4 else None
            status_raw = cells[5].css("::text").get("").strip() if len(cells) > 5 else ""

            # Normalize status — lowercase key lookup, fall through to raw if unknown
            status = SK_STATUS_MAP.get(status_raw.lower(), status_raw.lower() or None)

            raw = {
                "title": title,
                "organization": org or "",
                "competition_number": comp_num or "",
                "open_date": open_date or "",
                "close_date": close_date or "",
                "status": status_raw,
                "source_url": source_url or "",
            }

            yield TenderItem(
                source_slug="saskatchewan",
                external_id=comp_num or "",
                title=title,
                title_fr=None,
                description=None,
                description_fr=None,
                buyer_org=org or None,
                buyer_id=None,
                status=status,
                published_date=open_date or None,
                closing_date=close_date or None,
                province="SK",
                jurisdiction="prov",
                category=None,
                unspsc_codes=None,
                value_amount=None,
                value_currency="CAD",
                source_url=source_url,
                raw_ocds=raw,
            )
            parsed_count += 1

        logger.info("SaskatchewanSpider: parsed %d tenders from %s", parsed_count, response.url)
