"""SEAO REST API spider for PurchasingCAD.

Ingests Quebec public body tenders from the SEAO live search API
(api.seao.gouv.qc.ca). Returns real-time data with ~2200 active tenders.

Pagination: API returns max ~250 per request with total count.
Uses offset parameter to paginate through all results.

SEAO is French-only: title stored in both title and title_fr fields.
"""
import json
import logging
from urllib.parse import urlencode

from scrapy import Spider, Request

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# SEAO status IDs -> normalized status
# statIds: 6=published/open, other values may exist
SEAO_STAT_MAP = {
    6: "open",
    7: "closed",
    8: "awarded",
    9: "cancelled",
}

# All notice type IDs and category IDs (comprehensive coverage)
_BASE_PARAMS = {
    "statIds": "6",
    "tpIds": "2,3,5,6,7,8,10,14,15,17,18",
    "catIds": "52,53,51,54,1,20,4,27,5,18,7,21,9,26,8,22,28,10,2,24,3,12,16,17,13,25,19,23,6,29,14,31,15,30,11,56,55,57,58,38,34,39,50,46,42,43,32,33,41,47,35,44,49,40,48,45,36,37",
}

_API_BASE = "https://api.seao.gouv.qc.ca/prod/api/recherche"
_DETAIL_BASE = "https://seao.gouv.qc.ca/avis-resultat-recherche/consulter"
_PAGE_SIZE = 2000
_MAX_PAGES = 20


class SeaoJsonSpider(Spider):
    """Spider for SEAO live REST API.

    Fetches all open Quebec public body tenders via paginated API calls.
    Each tender is mapped to a TenderItem for the shared TenderPipeline.
    """

    name = "seao"
    source_slug = "seao"

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": False,  # API endpoint, no robots.txt
    }

    def start_requests(self):
        yield Request(
            url=f"{_API_BASE}?{urlencode(_BASE_PARAMS)}",
            callback=self.parse_page,
            cb_kwargs={"page": 0},
        )

    def parse_page(self, response, page: int):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("SEAO API: Failed to parse JSON from %s", response.url)
            return

        api_data = data.get("apiData", data)
        tenders = api_data.get("results", api_data.get("listeAvis", []))
        total = api_data.get("total", 0)

        if isinstance(tenders, list):
            logger.info(
                "SEAO API: Page %d — %d tenders (total: %d)",
                page, len(tenders), total,
            )
            for tender in tenders:
                item = self._tender_to_item(tender)
                if item is not None:
                    yield item

            # Paginate if more results
            fetched = (page + 1) * _PAGE_SIZE
            if len(tenders) >= _PAGE_SIZE and fetched < total and page < _MAX_PAGES:
                params = dict(_BASE_PARAMS)
                params["offset"] = str(fetched)
                yield Request(
                    url=f"{_API_BASE}?{urlencode(params)}",
                    callback=self.parse_page,
                    cb_kwargs={"page": page + 1},
                )
        else:
            # Try to handle response as a flat list
            if isinstance(data, list):
                for tender in data:
                    item = self._tender_to_item(tender)
                    if item is not None:
                        yield item

    def _tender_to_item(self, tender: dict) -> "TenderItem | None":
        uuid = tender.get("uuid") or tender.get("id")
        if not uuid:
            return None

        numero = tender.get("numero") or str(uuid)
        titre = tender.get("titre")
        buyer_org = tender.get("nomDonneurOuvrage")
        published = tender.get("datePublicationUtc")
        closing = tender.get("dateFermetureUtc")

        stat_id = tender.get("statutAvisId")
        status = SEAO_STAT_MAP.get(stat_id, "open")

        source_url = f"{_DETAIL_BASE}?ItemId={uuid}" if uuid else None

        return TenderItem(
            source_slug="seao",
            external_id=str(numero),
            title=titre,
            title_fr=titre,
            description=None,
            description_fr=None,
            buyer_org=buyer_org,
            buyer_id=tender.get("donneurOuvrageUUID"),
            status=status,
            published_date=published,
            closing_date=closing,
            province="QC",
            jurisdiction="prov",
            category=None,
            unspsc_codes=None,
            value_amount=None,
            value_currency="CAD",
            source_url=source_url,
            raw_ocds=tender,
        )
