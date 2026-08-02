"""Supabase pipeline: validate -> dedup fingerprint -> Supabase REST upsert.

Replaces the original SQLAlchemy TenderPipeline. Writes directly to the
tenders Supabase table via PostgREST API using the service_role key.

Field mapping (purchasingcad -> tenders Supabase schema):
  source_slug     -> source
  external_id     -> source_reference
  title           -> title
  description     -> description
  buyer_org       -> contracting_entity_name
  province        -> contracting_entity_province
  category        -> category_primary
  value_amount    -> estimated_value_min
  value_currency  -> currency
  jurisdiction    -> delivery_location (repurposed, stores "fed"/"prov"/"muni")
  title_fr        -> stored in summary field as "[FR] title_fr" prefix when no EN title
  unspsc_codes    -> unspsc (comma-joined)
"""
import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx

from purchasingcad.pipelines.dedup import compute_dedup_fingerprint

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BATCH_SIZE = int(os.environ.get("UPSERT_BATCH_SIZE", "50"))

REQUIRED_FIELDS = ["title", "closing_date", "source_url"]

# Small words that stay lowercase in title case (unless first word)
_TITLE_SMALL_WORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "yet", "so",
    "in", "on", "at", "to", "by", "of", "up", "as", "is", "if", "it",
    "de", "du", "des", "le", "la", "les", "et", "en", "au", "aux",  # French
}


def _clean_title(text):
    """Strip leading reference/file numbers from titles."""
    if not text:
        return text
    # Remove patterns like "EF926-261314-2 - ", "W7701-268112 - ", "cb-935-18469485 - "
    # Pattern: alphanumeric+hyphens followed by " - " at the start
    cleaned = re.sub(r'^[A-Za-z0-9]+-[A-Za-z0-9\-]+\s*[-–]\s*', '', text)
    # Remove patterns like "25-58188 " (just numbers-numbers at start)
    cleaned = re.sub(r'^\d{2,}-\d+\s+', '', cleaned)
    return cleaned.strip() if cleaned.strip() else text


def _title_case(text):
    """Convert text to title case, handling ALL CAPS and mixed case."""
    if not text:
        return text
    words = text.split()
    result = []
    for i, word in enumerate(words):
        # Preserve acronyms/codes that are 3-4 uppercase letters or contain digits
        if (len(word) <= 4 and word.isupper() and len(word) >= 3) or any(c.isdigit() for c in word):
            result.append(word)
        # Preserve words with internal caps (e.g., "nVidia", "MacBook")
        elif not word.isupper() and not word.islower() and not word.istitle():
            result.append(word)
        else:
            lower = word.lower()
            if i == 0 or lower not in _TITLE_SMALL_WORDS:
                result.append(word.capitalize())
            else:
                result.append(lower)
    return " ".join(result)

# Patterns to detect procurement type from title or bid number.
# Order matters — first match wins. Patterns are case-insensitive.
_PROCUREMENT_TYPE_PATTERNS = [
    (r'\bRFP\b', 'RFP'),           # Request for Proposal
    (r'\bRFQ\b', 'RFQ'),           # Request for Quotation
    (r'\bRFI\b', 'RFI'),           # Request for Information
    (r'\bRFSO\b', 'RFSO'),         # Request for Standing Offer
    (r'\bRFSA\b', 'RFSA'),         # Request for Supply Arrangement
    (r'\bRFB\b', 'RFB'),           # Request for Bids
    (r'\bITT\b', 'ITT'),           # Invitation to Tender
    (r'\bITQ\b', 'ITQ'),           # Invitation to Qualify
    (r'\bAOCI\b', 'AOCI'),         # Advance Contract Award Notice
    (r'\bACANS?\b', 'ACAN'),       # Advance Contract Award Notice (alt)
    (r'\bLOI\b', 'LOI'),           # Letter of Intent
    (r'\bSOW\b', 'SOW'),           # Statement of Work
    (r'\bRequest\s+for\s+Proposal', 'RFP'),
    (r'\bRequest\s+for\s+Quotation', 'RFQ'),
    (r'\bRequest\s+for\s+Information', 'RFI'),
    (r'\bRequest\s+for\s+Bids?\b', 'RFB'),
    (r'\bRequest\s+for\s+Standing\s+Offer', 'RFSO'),
    (r'\bRequest\s+for\s+Supply\s+Arrangement', 'RFSA'),
    (r'\bInvitation\s+to\s+Tender', 'ITT'),
    (r'\bInvitation\s+to\s+Qualify', 'ITQ'),
]


def _extract_contact_info(description):
    """Extract contact name, email, phone from description text and return cleaned description."""
    if not description:
        return {}, description

    contact = {}

    # Extract email
    email_match = re.search(r'[Ee]-?[Mm]ail[:\s]*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', description)
    if not email_match:
        email_match = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.gc\.ca)', description)
    if email_match:
        contact['contact_email'] = email_match.group(1)

    # Extract phone
    phone_match = re.search(r'[Pp]hone\s*(?:[Nn]umber)?[:\s]*(\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})', description)
    if not phone_match:
        phone_match = re.search(r'[Tt]el(?:ephone)?[:\s]*(\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})', description)
    if phone_match:
        contact['contact_phone'] = phone_match.group(1)

    # Extract contracting authority / contact name
    name_match = re.search(r'[Cc]ontracting\s+[Aa]uthority[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', description)
    if not name_match:
        name_match = re.search(r'[Cc]ontact[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', description)
    if name_match:
        contact['contact_name'] = name_match.group(1).strip()

    # Clean description: remove the contact/boilerplate block
    # Match from "File Number:" or "Contracting Authority:" through end of contact block
    cleaned = description
    # Remove contact block patterns
    cleaned = re.sub(
        r'(?:File\s+Number:.*?\n)?'
        r'(?:Contracting\s+Authority:.*?\n)?'
        r'(?:Phone\s+Number:.*?\n)?'
        r'(?:E-?Mail:.*?\n)?'
        r'(?:SOLICITATION\s+CLOSES.*?\n)?'
        r'(?:At\s+\d{1,2}:\d{2}\s+(?:AM|PM|am|pm).*?(?:EST|PST|MST|CST|EDT|PDT|MDT|CDT|ET|PT).*?\n)?',
        '', cleaned, flags=re.IGNORECASE
    )
    # Remove "NOTE TO BIDDER" boilerplate section
    cleaned = re.sub(
        r'NOTE\s+TO\s+BIDDER[S]?:.*$',
        '', cleaned, flags=re.IGNORECASE | re.DOTALL
    )
    # Clean up excessive whitespace
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

    return contact, cleaned


def _extract_procurement_type(title, source_ref=None):
    """Extract procurement type from title text and/or source reference number."""
    for text in [title or '', source_ref or '']:
        for pattern, ptype in _PROCUREMENT_TYPE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return ptype
    return None


def _headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def _parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def _map_tender(item, existing_ids):
    """Map a purchasingcad TenderItem to the tenders Supabase schema."""
    title = _title_case(_clean_title(item.get("title") or item.get("title_fr") or "Untitled"))
    raw_description = item.get("description") or item.get("description_fr") or ""
    contact_info, description = _extract_contact_info(raw_description)
    source = item.get("source_slug") or "unknown"
    source_ref = item.get("external_id") or ""

    # Check if this tender already exists (preserve UUID for bookmarks)
    lookup_key = f"{source}:{source_ref}"
    existing_id = existing_ids.get(lookup_key)

    value_amount = None
    if item.get("value_amount") is not None:
        try:
            value_amount = float(Decimal(str(item["value_amount"])))
        except (InvalidOperation, ValueError):
            value_amount = None

    unspsc = None
    if item.get("unspsc_codes"):
        unspsc = ",".join(item["unspsc_codes"])

    province = item.get("province")
    # Map jurisdiction to a recognizable format in delivery_location
    jurisdiction = item.get("jurisdiction") or ""
    jurisdiction_map = {"fed": "Federal", "prov": f"Provincial ({province or ''})", "muni": f"Municipal ({province or ''})"}
    delivery_loc = jurisdiction_map.get(jurisdiction, jurisdiction)

    procurement_type = _extract_procurement_type(title, source_ref) or item.get("notice_type")

    # Normalize category
    _CATEGORY_MAP = {
        "*srv": "services", "*gd": "goods", "*cnst": "works", "*srvtgd": "services",
        "construction": "works", "goods": "goods", "services": "services",
    }
    raw_cat = (item.get("category") or "").strip().lower()
    category = _CATEGORY_MAP.get(raw_cat)
    if not category and raw_cat:
        for part in raw_cat.replace("\n", " ").split():
            if part in _CATEGORY_MAP:
                category = _CATEGORY_MAP[part]
                break

    return {
        "id": existing_id or str(uuid.uuid4()),
        "title": title,
        "description": description,
        "source": source,
        "source_url": item.get("source_url"),
        "source_reference": source_ref,
        "status": item.get("status"),
        "category_primary": category,
        "procurement_type": procurement_type,
        "closing_date": _parse_datetime(item.get("closing_date")),
        "published_date": _parse_datetime(item.get("published_date")),
        "estimated_value_min": value_amount,
        "currency": item.get("value_currency") or "CAD",
        "contracting_entity_name": item.get("buyer_org"),
        "contracting_entity_province": province,
        "contracting_entity_country": "Canada",
        "delivery_location": delivery_loc,
        "unspsc": unspsc,
        "gsin": None,
        "contact_name": item.get("contact_name") or contact_info.get("contact_name"),
        "contact_email": item.get("contact_email") or contact_info.get("contact_email"),
        "contact_phone": item.get("contact_phone") or contact_info.get("contact_phone"),
        "contracting_entity_city": item.get("buyer_city"),
        "procurement_method": item.get("procurement_method"),
        "contract_start_date": _parse_datetime(item.get("contract_start_date")),
        "delivery_location": item.get("delivery_regions") or delivery_loc,
        "last_scraped_at": datetime.now(timezone.utc).isoformat(),
    }


class SupabasePipeline:
    """Pipeline that upserts tenders to Supabase via REST API."""

    def __init__(self):
        self._batch = []
        self._items_processed = 0
        self._items_warned = 0
        self._existing_ids = {}
        self._client = None

    async def open_spider(self, spider):
        self._client = httpx.AsyncClient(timeout=30.0)
        source_slug = getattr(spider, "source_slug", spider.name)

        # Pre-fetch existing tender IDs for this source to preserve UUIDs
        try:
            resp = await self._client.get(
                f"{SUPABASE_URL}/rest/v1/tenders",
                params={
                    "source": f"eq.{source_slug}",
                    "select": "id,source,source_reference",
                },
                headers=_headers(),
            )
            if resp.status_code == 200:
                for row in resp.json():
                    key = f"{row['source']}:{row.get('source_reference', '')}"
                    self._existing_ids[key] = row["id"]
                logger.info(
                    "Loaded %d existing tender IDs for source %s",
                    len(self._existing_ids),
                    source_slug,
                )
        except Exception as e:
            logger.warning("Could not pre-fetch existing IDs: %s", e)

    async def process_item(self, item, spider):
        # Lenient validation
        missing = [f for f in REQUIRED_FIELDS if not item.get(f)]
        if missing:
            logger.warning(
                "Spider %s item %s missing fields: %s — inserting anyway",
                spider.name,
                item.get("external_id", "?"),
                ", ".join(missing),
            )
            self._items_warned += 1

        mapped = _map_tender(item, self._existing_ids)
        self._batch.append(mapped)

        if len(self._batch) >= BATCH_SIZE:
            await self._flush_batch(spider)

        return item

    async def close_spider(self, spider):
        if self._batch:
            await self._flush_batch(spider)
        if self._client:
            await self._client.aclose()
        logger.info(
            "Spider %s pipeline done: %d items processed, %d warnings",
            spider.name,
            self._items_processed,
            self._items_warned,
        )

    async def _flush_batch(self, spider):
        if not self._batch:
            return

        try:
            resp = await self._client.post(
                f"{SUPABASE_URL}/rest/v1/tenders",
                json=self._batch,
                headers=_headers(),
            )
            if resp.status_code in (200, 201):
                self._items_processed += len(self._batch)
                logger.info(
                    "Upserted %d tenders for %s", len(self._batch), spider.name
                )
            else:
                logger.error(
                    "Supabase upsert failed (%d): %s",
                    resp.status_code,
                    resp.text[:500],
                )
        except Exception as e:
            logger.error("Supabase upsert error: %s", e)

        self._batch = []
