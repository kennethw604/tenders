"""Ingest CanadaBuys CSV directly into Supabase with ALL fields.

Usage:
    cd scraper
    python scripts/ingest_canadabuys.py [--clear]

Pass --clear to wipe existing canadabuys tenders first.
"""
import csv
import os
import re
import sys
import uuid
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "canadabuys_open.csv")
BATCH_SIZE = 50

PROVINCE_MAP = {
    "Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB",
    "New Brunswick": "NB", "Newfoundland and Labrador": "NL",
    "Northwest Territories": "NT", "Nova Scotia": "NS", "Nunavut": "NU",
    "Ontario": "ON", "Prince Edward Island": "PE", "Quebec": "QC",
    "Saskatchewan": "SK", "Yukon": "YT",
    "National Capital Region": "ON", "National": None,
}

STATUS_MAP = {
    "open": "open", "closed": "closed", "awarded": "awarded",
    "cancelled": "cancelled", "amended": "open", "expired": "closed",
}

CATEGORY_MAP = {
    "*gd": "goods", "*srv": "services", "*cnst": "works", "*srvtgd": "services",
    "goods": "goods", "services": "services", "construction": "works",
    "gd": "goods", "srv": "services", "cnst": "works", "srvtgd": "services",
}

SMALL_WORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "yet", "so",
    "in", "on", "at", "to", "by", "of", "up", "as", "is", "if", "it",
}

PROCUREMENT_TYPE_PATTERNS = [
    (r'\bRFP\b', 'RFP'), (r'\bRFQ\b', 'RFQ'), (r'\bRFI\b', 'RFI'),
    (r'\bRFSO\b', 'RFSO'), (r'\bRFSA\b', 'RFSA'), (r'\bRFB\b', 'RFB'),
    (r'\bITT\b', 'ITT'), (r'\bITQ\b', 'ITQ'), (r'\bAOCI\b', 'AOCI'),
    (r'\bACANS?\b', 'ACAN'), (r'\bLOI\b', 'LOI'),
]


def clean_title(text):
    if not text:
        return text
    cleaned = re.sub(r'^[A-Za-z0-9]+-[A-Za-z0-9\-]+\s*[-–]\s*', '', text)
    cleaned = re.sub(r'^\d{2,}-\d+\s+', '', cleaned)
    return cleaned.strip() if cleaned.strip() else text


def title_case(text):
    if not text:
        return text
    words = text.split()
    result = []
    for i, word in enumerate(words):
        if (len(word) <= 4 and word.isupper() and len(word) >= 3) or any(c.isdigit() for c in word):
            result.append(word)
        elif not word.isupper() and not word.islower() and not word.istitle():
            result.append(word)
        else:
            lower = word.lower()
            result.append(word.capitalize() if i == 0 or lower not in SMALL_WORDS else lower)
    return " ".join(result)


def extract_procurement_type(title, source_ref=None):
    for text in [title or "", source_ref or ""]:
        for pattern, ptype in PROCUREMENT_TYPE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return ptype
    return None


def parse_datetime(value):
    if not value or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def normalize_category(raw):
    raw = (raw or "").strip().lower()
    cat = CATEGORY_MAP.get(raw)
    if not cat and raw:
        for part in raw.replace("\n", " ").split():
            part = part.lstrip("*")
            if part in CATEGORY_MAP:
                cat = CATEGORY_MAP[part]
                break
    return cat


def clean_description(desc):
    """Remove contact block and boilerplate from description."""
    if not desc:
        return desc
    cleaned = desc
    cleaned = re.sub(
        r'(?:File\s+Number:.*?\n)?'
        r'(?:Contracting\s+Authority:.*?\n)?'
        r'(?:Phone\s+Number:.*?\n)?'
        r'(?:E-?Mail:.*?\n)?'
        r'(?:SOLICITATION\s+CLOSES.*?\n)?'
        r'(?:At\s+\d{1,2}:\d{2}\s+(?:AM|PM|am|pm).*?(?:EST|PST|MST|CST|EDT|PDT|MDT|CDT|ET|PT).*?\n)?',
        '', cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r'NOTE\s+TO\s+BIDDER[S]?:.*$', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def map_row(row, existing_ids):
    """Map a CSV row to a tenders DB record."""
    # Clean column names (BOM defense)
    row = {k.lstrip("\ufeff").strip('"'): v for k, v in row.items()}

    source_ref = (row.get("referenceNumber-numeroReference") or "").strip()
    raw_title = row.get("title-titre-eng") or row.get("title-titre-fra") or "Untitled"
    title = title_case(clean_title(raw_title))

    description = clean_description(
        row.get("tenderDescription-descriptionAppelOffres-eng")
        or row.get("tenderDescription-descriptionAppelOffres-fra")
        or ""
    )

    province_raw = (row.get("contractingEntityAddressProvince-entiteContractanteAdresseProvince-eng") or "").strip()
    province = PROVINCE_MAP.get(province_raw) if province_raw else None

    status_raw = (row.get("tenderStatus-appelOffresStatut-eng") or "").strip().lower()
    status = STATUS_MAP.get(status_raw, status_raw or None)

    category = normalize_category(row.get("procurementCategory-categorieApprovisionnement"))

    # UNSPSC codes
    unspsc_raw = row.get("unspsc") or ""
    unspsc_codes = [c.lstrip("*").strip() for c in unspsc_raw.split("\n") if c.strip()]
    unspsc = ",".join(unspsc_codes) if unspsc_codes else None

    # Procurement type: from title first, fallback to notice_type column
    notice_type = (row.get("noticeType-avisType-eng") or "").strip()
    procurement_type = extract_procurement_type(title, source_ref) or notice_type or None

    # Existing ID preservation
    lookup_key = f"canadabuys:{source_ref}"
    existing_id = existing_ids.get(lookup_key)

    return {
        "id": existing_id or str(uuid.uuid4()),
        "title": title,
        "description": description,
        "source": "canadabuys",
        "source_url": (row.get("noticeURL-URLavis-eng") or "").strip() or None,
        "source_reference": source_ref,
        "status": status,
        "category_primary": category,
        "procurement_type": procurement_type,
        "procurement_method": (row.get("procurementMethod-methodeApprovisionnement-eng") or "").strip() or None,
        "closing_date": parse_datetime(row.get("tenderClosingDate-appelOffresDateCloture")),
        "published_date": parse_datetime(row.get("publicationDate-datePublication")),
        "contract_start_date": parse_datetime(row.get("expectedContractStartDate-dateDebutContratPrevue")),
        "estimated_value_min": None,
        "currency": "CAD",
        "contracting_entity_name": (row.get("contractingEntityName-nomEntitContractante-eng") or "").strip() or None,
        "contracting_entity_city": (row.get("contractingEntityAddressCity-entiteContractanteAdresseVille-eng") or "").strip() or None,
        "contracting_entity_province": province,
        "contracting_entity_country": "Canada",
        "contact_name": (row.get("contactInfoName-informationsContactNom") or "").strip() or None,
        "contact_email": (row.get("contactInfoEmail-informationsContactCourriel") or "").strip() or None,
        "contact_phone": (row.get("contactInfoPhone-contactInfoTelephone") or "").strip() or None,
        "delivery_location": (row.get("regionsOfDelivery-regionsLivraison-eng") or "").strip() or None,
        "unspsc": unspsc,
        "gsin": (row.get("gsin-nibs") or "").strip() or None,
        "last_scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        sys.exit(1)

    client = httpx.Client(timeout=60.0)

    # Clear existing canadabuys tenders if --clear flag
    if "--clear" in sys.argv:
        print("Clearing existing canadabuys tenders...")
        r = client.delete(f"{SUPABASE_URL}/rest/v1/tenders",
            params={"source": "eq.canadabuys"},
            headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"})
        print(f"  Cleared: {r.status_code}")

    # Pre-fetch existing IDs
    print("Loading existing tender IDs...")
    existing_ids = {}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/tenders",
        params={"source": "eq.canadabuys", "select": "id,source,source_reference", "limit": 50000},
        headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"})
    if resp.status_code == 200:
        for row in resp.json():
            key = f"{row['source']}:{row.get('source_reference', '')}"
            existing_ids[key] = row["id"]
    print(f"  Found {len(existing_ids)} existing records")

    # Read and process CSV
    print(f"Reading CSV: {CSV_PATH}")
    batch = []
    total = 0
    errors = 0

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                mapped = map_row(row, existing_ids)
                batch.append(mapped)
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  ERROR mapping row: {e}")
                continue

            if len(batch) >= BATCH_SIZE:
                resp = client.post(f"{SUPABASE_URL}/rest/v1/tenders",
                    json=batch, headers=headers())
                if resp.status_code not in (200, 201):
                    print(f"  UPSERT ERROR ({resp.status_code}): {resp.text[:200]}")
                total += len(batch)
                batch = []
                if total % 1000 == 0:
                    print(f"  Processed {total}...")

    # Flush remaining
    if batch:
        resp = client.post(f"{SUPABASE_URL}/rest/v1/tenders", json=batch, headers=headers())
        if resp.status_code not in (200, 201):
            print(f"  UPSERT ERROR ({resp.status_code}): {resp.text[:200]}")
        total += len(batch)

    print(f"\nDone. Ingested {total} tenders, {errors} errors.")
    client.close()


if __name__ == "__main__":
    main()
