"""Toronto municipal tenders spider via City of Toronto public API.

Toronto exposes a public OData-style JSON API for procurement solicitations
at secure.toronto.ca. Returns structured JSON with all active tenders.

No Playwright/Ariba needed — direct JSON API, much more reliable.

Source: MapleTenders project (github.com/FuJacob/mapletenders)
"""
import json
import logging

from scrapy import Spider, Request

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

_TORONTO_API_BASE = (
    "https://secure.toronto.ca/c3api_data/v2/DataAccess.svc/"
    "pmmd_solicitations/feis_solicitation"
    "?$format=application/json;odata.metadata=none"
    "&$count=true&$top=500"
    "&$orderby=Closing_Date%20desc,Issue_Date%20desc"
)
_PAGE_SIZE = 500

_TORONTO_DETAIL_BASE = "https://www.toronto.ca/business-economy/doing-business-with-the-city/searching-bidding-on-city-contracts/"


class TorontoSpider(Spider):
    """Spider for Toronto municipal tenders via city public API."""

    name = "toronto"
    source_slug = "toronto"

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": False,  # API endpoint
    }

    def start_requests(self):
        yield Request(
            url=f"{_TORONTO_API_BASE}&$skip=0",
            callback=self.parse,
            cb_kwargs={"skip": 0},
        )

    def parse(self, response, skip: int):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Toronto API: Failed to parse JSON from %s", response.url)
            return

        tenders = data.get("value", [])
        total = data.get("@odata.count", 0)
        logger.info("Toronto API: %d tenders at skip=%d (total: %s)", len(tenders), skip, total)

        for tender in tenders:
            item = self._tender_to_item(tender)
            if item is not None:
                yield item

        # Paginate if more results
        next_skip = skip + _PAGE_SIZE
        if len(tenders) == _PAGE_SIZE and next_skip < total:
            yield Request(
                url=f"{_TORONTO_API_BASE}&$skip={next_skip}",
                callback=self.parse,
                cb_kwargs={"skip": next_skip},
            )

    def _tender_to_item(self, tender: dict) -> "TenderItem | None":
        doc_id = tender.get("Solicitation_Document_Number") or tender.get("id")
        if not doc_id:
            return None

        title = tender.get("Posting_Title")
        status_raw = (tender.get("Status") or "").lower()
        if status_raw in ("open", "active"):
            status = "open"
        elif status_raw in ("closed", "complete"):
            status = "closed"
        elif status_raw == "awarded":
            status = "awarded"
        elif status_raw == "cancelled":
            status = "cancelled"
        else:
            status = status_raw or "open"

        # Category from High_Level_Category
        cat_raw = (tender.get("High_Level_Category") or "").lower()
        if "goods" in cat_raw or "supply" in cat_raw:
            category = "goods"
        elif "service" in cat_raw:
            category = "services"
        elif "construction" in cat_raw:
            category = "works"
        else:
            category = None

        # Use Ariba posting link if available, otherwise general page
        source_url = tender.get("Ariba_Discovery_Posting_Link") or _TORONTO_DETAIL_BASE

        # Client division (first item if list)
        division = tender.get("Client_Division")
        if isinstance(division, list):
            division = division[0] if division else None
        buyer_org = f"City of Toronto — {division}" if division else "City of Toronto"

        return TenderItem(
            source_slug="toronto",
            external_id=str(doc_id),
            title=title,
            title_fr=None,
            description=tender.get("Solicitation_Document_Description"),
            description_fr=None,
            buyer_org=buyer_org,
            buyer_id=None,
            status=status,
            published_date=tender.get("Issue_Date"),
            closing_date=tender.get("Closing_Date"),
            province="ON",
            jurisdiction="muni",
            category=category,
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=source_url,
            raw_ocds=tender,
        )
