"""Nova Scotia Awarded Public Tenders spider — Socrata SODA API.

Nova Scotia publishes all awarded tender contracts via the Socrata open data
platform. The dataset (m6ps-8j6u) is available as a paginated JSON API.
This spider fetches all records using $limit/$offset pagination and maps each
record to a TenderItem for the shared TenderPipeline.

All records in this dataset are awarded contracts — status is hardcoded to
"awarded" (no status field exists in the source data).

D-01: Spider follows Scrapy Spider base class pattern (not CSVFeedSpider).
D-02: Lenient: missing optional fields map to None.
D-04: DOWNLOAD_DELAY=0.5, CONCURRENT_REQUESTS=1 — respectful API access.
"""
import logging

from scrapy import Spider
from scrapy.http import Request

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

PAGE_SIZE = 1000

# Socrata resource ID for Nova Scotia awarded tenders
_NS_API_URL = (
    "https://data.novascotia.ca/resource/m6ps-8j6u.json"
    "?$limit={limit}&$offset={offset}"
)


class NovascotiaSpider(Spider):
    """Scrapy Spider that ingests Nova Scotia awarded tenders from Socrata SODA API.

    Paginates using $limit/$offset. Stops when a page returns fewer than
    PAGE_SIZE records (indicating the last page).
    """

    name = "nova_scotia"
    source_slug = "nova_scotia"

    # Socrata API — polite rate limiting (D-04)
    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS": 1,
    }

    def start_requests(self):
        """Yield the first page request."""
        yield self._page_request(offset=0)

    def _page_request(self, offset: int) -> Request:
        """Build a paginated request for the given offset."""
        url = _NS_API_URL.format(limit=PAGE_SIZE, offset=offset)
        return Request(
            url=url,
            callback=self.parse_page,
            cb_kwargs={"offset": offset},
        )

    def parse_page(self, response, offset: int):
        """Parse one page of JSON records, yield TenderItems, paginate if needed."""
        records = response.json()

        for record in records:
            yield self._record_to_item(record)

        # If page was full, there may be more records
        if len(records) == PAGE_SIZE:
            yield self._page_request(offset=offset + PAGE_SIZE)

    def _record_to_item(self, record: dict) -> TenderItem:
        """Map one Socrata JSON record to a TenderItem.

        Category is derived from boolean flags in the record:
        - goods='Y'        -> 'goods'
        - service='Y'      -> 'services'
        - construction='Y' -> 'works'
        - all 'N'          -> None
        """
        # Category derivation from boolean flag columns
        if record.get("goods") == "Y":
            category = "goods"
        elif record.get("service") == "Y":
            category = "services"
        elif record.get("construction") == "Y":
            category = "works"
        else:
            category = None

        return TenderItem(
            source_slug="nova_scotia",
            external_id=record.get("tender_id") or "",
            title=record.get("tender_description"),
            title_fr=None,
            description=None,
            description_fr=None,
            buyer_org=record.get("entity"),
            buyer_id=None,
            # This dataset is awarded contracts only — status is hardcoded
            status="awarded",
            published_date=record.get("tender_start_date"),
            closing_date=record.get("tender_close_date"),
            province="NS",
            jurisdiction="prov",
            category=category,
            unspsc_codes=None,
            value_amount=record.get("awarded_amount"),
            value_currency="CAD",
            source_url="https://data.novascotia.ca/d/m6ps-8j6u",
            raw_ocds=record,
        )
