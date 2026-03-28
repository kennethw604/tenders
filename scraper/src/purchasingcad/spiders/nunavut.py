"""Nunavut HTML spider for PurchasingCAD.

Scrapes tender listings from nunavuttenders.ca, a static HTML portal with
three sections: Currently Open RFTs/RFPs, Unawarded Notices, Recently Awarded.
Section membership determines the normalized status for each tender.

D-04: DOWNLOAD_DELAY=2 — conservative rate limiting for HTML source.
D-02: Lenient validation — missing fields stay None; all linked rows yielded.
"""
import logging
from urllib.parse import urljoin

from scrapy import Spider

from purchasingcad.items import TenderItem

logger = logging.getLogger(__name__)

# Section heading keywords -> normalized status
# Matched by checking if the heading contains these keywords (case-insensitive)
SECTION_STATUS_MAP = {
    "open": "open",
    "unawarded": "closed",
    "awarded": "awarded",
}


def _heading_to_status(heading_text: str) -> str:
    """Map a section heading to a normalized status string.

    Checks heading keywords in priority order: 'open' first (before 'awarded'),
    then 'unawarded', then 'awarded'.
    """
    lower = heading_text.lower()
    if "open" in lower:
        return "open"
    if "unawarded" in lower:
        return "closed"
    if "awarded" in lower:
        return "awarded"
    return "open"  # Default: treat unknown sections as open


class NunavutSpider(Spider):
    """Scrapy Spider that scrapes tender listings from nunavuttenders.ca.

    The page contains multiple HTML tables, each preceded by an <h2> section
    heading. The spider tracks the current section heading as it walks through
    the page elements to assign the correct status to each tender row.

    Column layout per row: Ref# (linked), Description, FOB Point, Issued Date,
    Contact, Phone/Email, Closing Date, Submit button.
    """

    name = "nunavut"
    source_slug = "nunavut"

    start_urls = ["https://www.nunavuttenders.ca/Default.aspx"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "ROBOTSTXT_OBEY": True,
    }

    def parse(self, response):
        """Parse all sections of the nunavuttenders.ca page.

        Walks through h2 headings and tables in document order. Each h2 updates
        the current section status. Each table row in the following table is
        parsed with that status.
        """
        parsed_count = 0

        # Walk through all h2 and table elements in document order
        # Use XPath to get these elements in order
        elements = response.xpath("//h2 | //table")

        current_status = "open"  # Default before first heading

        for element in elements:
            tag = element.root.tag if hasattr(element.root, "tag") else element.xpath("name()").get("")

            if tag == "h2":
                heading_text = element.css("::text").get("").strip()
                current_status = _heading_to_status(heading_text)
                logger.debug("NunavutSpider: section '%s' -> status '%s'", heading_text, current_status)

            elif tag == "table":
                for row in element.css("tr"):
                    cells = row.css("td")
                    if len(cells) < 7:
                        continue  # Skip header rows

                    # First cell: Ref# with link
                    ref_link = cells[0].css("a")
                    if not ref_link:
                        continue

                    ref = ref_link.css("::text").get("").strip()
                    href = ref_link.attrib.get("href", "")
                    source_url = urljoin(response.url, href) if href else None

                    description = cells[1].css("::text").get("").strip() or None
                    fob_point = cells[2].css("::text").get("").strip() or None
                    issued_date = cells[3].css("::text").get("").strip() or None
                    contact = cells[4].css("::text").get("").strip() or None
                    phone = cells[5].css("::text").get("").strip() or None
                    closing_date = cells[6].css("::text").get("").strip() or None

                    raw = {
                        "ref": ref,
                        "description": description or "",
                        "fob_point": fob_point or "",
                        "issued_date": issued_date or "",
                        "contact": contact or "",
                        "phone": phone or "",
                        "closing_date": closing_date or "",
                        "section_status": current_status,
                    }

                    yield TenderItem(
                        source_slug="nunavut",
                        external_id=ref,
                        title=description,
                        title_fr=None,
                        description=None,
                        description_fr=None,
                        buyer_org=None,
                        buyer_id=None,
                        status=current_status,
                        published_date=issued_date,
                        closing_date=closing_date,
                        province="NU",
                        jurisdiction="prov",
                        category=None,
                        unspsc_codes=None,
                        value_amount=None,
                        value_currency="CAD",
                        source_url=source_url,
                        raw_ocds=raw,
                    )
                    parsed_count += 1

        logger.info("NunavutSpider: parsed %d tenders from %s", parsed_count, response.url)
