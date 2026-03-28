"""Yukon Government Open Tenders spider — BidsandTenders CSV feed.

Yukon Government publishes open tender data via the BidsandTenders platform
as a downloadable CSV. This spider uses Scrapy's CSVFeedSpider to stream and
parse each row, mapping it to a TenderItem for the shared TenderPipeline.

D-01: Uses CSVFeedSpider — matches the CanadaBuys pattern for CSV sources.
D-02: Lenient: missing optional fields map to None (no DropItem).
D-04: DOWNLOAD_DELAY=1 — respectful access to third-party aggregator.
"""
import logging

from scrapy.spiders import CSVFeedSpider

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Yukon project status -> normalized status
YUKON_STATUS_MAP = {
    "open": "open",
    "closed": "closed",
    "awarded": "awarded",
    "cancelled": "cancelled",
}


class YukonSpider(CSVFeedSpider):
    """Scrapy CSVFeedSpider that ingests Yukon open tender data from BidsandTenders CSV.

    Downloads the open data CSV export and maps each row to a TenderItem
    for the shared TenderPipeline.
    """

    name = "yukon"
    source_slug = "yukon"

    # BidsandTenders open data CSV export for Yukon tenders
    start_urls = [
        "https://yukon.bidsandtenders.ca/Module/Tenders/en/OpenData/GenerateReport"
        "?report=OpenTenders"
    ]

    # Third-party aggregator — polite rate limiting (D-04)
    custom_settings = {
        "DOWNLOAD_DELAY": 1,
    }

    def parse_row(self, response, row):
        """Map one CSV row to a TenderItem.

        Called by CSVFeedSpider once per CSV data row. Handles:
        - Status normalization: case-insensitive lookup in YUKON_STATUS_MAP
        - Missing/empty optional fields mapped to None (D-02 lenient)
        """
        # Status normalization: lowercase -> lookup in map, fallback to raw or None
        status_raw = (row.get("Project Status") or "").strip().lower()
        status = YUKON_STATUS_MAP.get(status_raw, status_raw or None)

        yield TenderItem(
            source_slug="yukon",
            external_id=(row.get("Project Number") or "").strip(),
            title=row.get("Project Description") or None,
            title_fr=None,
            description=None,
            description_fr=None,
            buyer_org=row.get("Department") or None,
            buyer_id=None,
            status=status,
            published_date=row.get("Published Date") or None,
            closing_date=row.get("Closing Date") or None,
            province="YT",
            jurisdiction="prov",
            category=None,
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=row.get("Link") or row.get("URL") or (
                f"https://yukon.bidsandtenders.ca/Module/Tenders/en/Tender/Detail/{(row.get('Project Number') or '').strip()}"
                if (row.get("Project Number") or "").strip() else None
            ),
            raw_ocds=dict(row),
        )
