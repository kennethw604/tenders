"""CanadaBuys CSV spider — ingests federal tenders from open data CSV.

CanadaBuys publishes all tender notices as a single open data CSV that is
refreshed every 2 hours. This spider downloads the all-time historical CSV
and yields one TenderItem per row. The shared TenderPipeline handles
deduplication and upsert.

D-04: No date cutoff — process all rows (pipeline fingerprints duplicates).
D-08: GSIN->UNSPSC mapping preloaded into memory to avoid per-row DB queries.
D-09: Store whatever bilingual content is available; missing fields stay None.
"""
import logging

from scrapy.spiders import CSVFeedSpider

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Full province/territory name -> ISO 3166-2 CA 2-letter code
PROVINCE_MAP = {
    "Alberta": "AB",
    "British Columbia": "BC",
    "Manitoba": "MB",
    "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL",
    "Northwest Territories": "NT",
    "Nova Scotia": "NS",
    "Nunavut": "NU",
    "Ontario": "ON",
    "Prince Edward Island": "PE",
    "Quebec": "QC",
    "Saskatchewan": "SK",
    "Yukon": "YT",
    # Special cases
    "National Capital Region": "ON",
    "National": None,
}

# CanadaBuys status values (lowercase) -> normalized status
STATUS_MAP = {
    "open": "open",
    "closed": "closed",
    "awarded": "awarded",
    "cancelled": "cancelled",
    "amended": "open",
}

# Procurement category -> normalized category
# CSV values can be full text ("Goods") or coded ("*gd", "*srv", "*cnst")
# Multi-value entries like "*srvtgd" or "*srv\n*gd" also occur
CATEGORY_MAP = {
    "goods": "goods",
    "services": "services",
    "construction": "works",
    # Coded variants from CSV
    "*gd": "goods",
    "*srv": "services",
    "*cnst": "works",
    "*srvtgd": "services",  # services + goods combo → primary is services
    "*gd\n*srv": "goods",
    "*srv\n*gd": "services",
    "*gd\n*srvtgd": "goods",
}


def parse_codes(raw: str | None) -> list[str]:
    """Parse '*CODE1\\n*CODE2' multi-value format into ['CODE1', 'CODE2'].

    CanadaBuys encodes multi-value commodity codes as newline-separated
    values prefixed with '*'. Empty/None input returns an empty list.
    """
    if not raw:
        return []
    return [c.lstrip("*").strip() for c in raw.split("\n") if c.strip()]


class CanadaBuysCsvSpider(CSVFeedSpider):
    """Scrapy CSVFeedSpider that ingests the CanadaBuys open data CSV.

    Downloads the all-time historical CSV from the open data portal and
    maps each row to a TenderItem for the shared TenderPipeline.
    """

    name = "canadabuys"
    source_slug = "canadabuys"

    # All-time historical CSV — no date cutoff (D-04)
    start_urls = [
        "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"
    ]

    # CSV is open data — no robots.txt applies; no rate limit needed
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gsin_map: dict[str, str] = {}  # gsin_code -> unspsc_code

    async def _load_gsin_map(self) -> None:
        """GSIN->UNSPSC mapping placeholder. Mapping table not available in Supabase mode."""
        logger.info("GSIN->UNSPSC mapping skipped (no mapping table)")
        self._gsin_map = {}

    def parse_row(self, response, row):
        """Map one CSV row to a TenderItem.

        Called by CSVFeedSpider once per CSV data row. Handles:
        - BOM defense: strips \\ufeff from column name keys (Pitfall 1)
        - GSIN multi-value parsing: '*CODE1\\n*CODE2' format (Pitfall 2)
        - Province normalization: full name -> 2-letter ISO code
        - Status normalization: CSV value -> open/closed/awarded/cancelled
        - Category normalization: CSV value -> goods/services/works
        """
        # Strip BOM and quote-wrapping from column names defensively (Pitfall 1)
        row = {k.lstrip("\ufeff").strip('"'): v for k, v in row.items()}

        # Parse GSIN codes and resolve to UNSPSC (D-08)
        gsin_codes = parse_codes(row.get("gsin-nibs"))
        direct_unspsc = parse_codes(row.get("unspsc"))

        # Merge: direct UNSPSC + GSIN-mapped UNSPSC (dedup, preserve order)
        unspsc_from_gsin = [
            self._gsin_map[g] for g in gsin_codes if g in self._gsin_map
        ]
        all_unspsc = list(dict.fromkeys(direct_unspsc + unspsc_from_gsin))

        # Province mapping: full name -> 2-letter ISO code
        province_raw = (
            row.get(
                "contractingEntityAddressProvince-entiteContractanteAdresseProvince-eng"
            )
            or ""
        ).strip()
        # PROVINCE_MAP.get returns None for missing keys (unknown province)
        province = PROVINCE_MAP.get(province_raw) if province_raw else None

        # Status normalization: lowercase first, then map
        status_raw = (row.get("tenderStatus-appelOffresStatut-eng") or "").strip().lower()
        status = STATUS_MAP.get(status_raw, status_raw or None)

        # Category normalization: lookup coded or text values
        category_raw = (
            row.get("procurementCategory-categorieApprovisionnement") or ""
        ).strip().lower()
        category = CATEGORY_MAP.get(category_raw)
        if not category and category_raw:
            # Handle multi-value: pick first recognized code
            for part in category_raw.replace("\n", " ").split():
                if part in CATEGORY_MAP:
                    category = CATEGORY_MAP[part]
                    break
            if not category:
                category = category_raw  # preserve raw if no mapping

        yield TenderItem(
            source_slug="canadabuys",
            external_id=(row.get("referenceNumber-numeroReference") or "").strip(),
            title=row.get("title-titre-eng") or None,
            title_fr=row.get("title-titre-fra") or None,
            description=row.get("tenderDescription-descriptionAppelOffres-eng") or None,
            description_fr=row.get("tenderDescription-descriptionAppelOffres-fra") or None,
            buyer_org=row.get("contractingEntityName-nomEntitContractante-eng") or None,
            buyer_id=None,
            status=status,
            published_date=row.get("publicationDate-datePublication") or None,
            closing_date=row.get("tenderClosingDate-appelOffresDateCloture") or None,
            province=province,
            jurisdiction="fed",
            category=category,
            unspsc_codes=all_unspsc or None,
            value_amount=None,
            value_currency="CAD",
            source_url=row.get("noticeURL-URLavis-eng") or None,
            raw_ocds=dict(row),
            # Extended fields — directly from CSV columns
            notice_type=row.get("noticeType-avisType-eng") or None,
            procurement_method=row.get("procurementMethod-methodeApprovisionnement-eng") or None,
            contact_name=row.get("contactInfoName-informationsContactNom") or None,
            contact_email=row.get("contactInfoEmail-informationsContactCourriel") or None,
            contact_phone=row.get("contactInfoPhone-contactInfoTelephone") or None,
            buyer_city=(row.get("contractingEntityAddressCity-entiteContractanteAdresseVille-eng") or "").strip() or None,
            buyer_postal_code=(row.get("contractingEntityAddressPostalCode-entiteContractanteAdresseCodePostal") or "").strip() or None,
            delivery_regions=row.get("regionsOfDelivery-regionsLivraison-eng") or None,
            end_user_entity=row.get("endUserEntitiesName-nomEntitesUtilisateurFinal-eng") or None,
            contract_start_date=row.get("expectedContractStartDate-dateDebutContratPrevue") or None,
            contract_end_date=row.get("expectedContractEndDate-dateFinContratPrevue") or None,
            selection_criteria=row.get("selectionCriteria-criteresSelection-eng") or None,
            trade_agreements=row.get("tradeAgreements-accordsCommerciaux-eng") or None,
            solicitation_number=row.get("solicitationNumber-numeroSollicitation") or None,
        )
