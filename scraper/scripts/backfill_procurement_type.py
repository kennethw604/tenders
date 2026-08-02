"""One-time backfill: parse procurement_type from existing tender titles and source_references.

Usage:
    cd scraper
    python scripts/backfill_procurement_type.py

Requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars (or .env file).
"""
import os
import re
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

PROCUREMENT_TYPE_PATTERNS = [
    (r'\bRFP\b', 'RFP'),
    (r'\bRFQ\b', 'RFQ'),
    (r'\bRFI\b', 'RFI'),
    (r'\bRFSO\b', 'RFSO'),
    (r'\bRFSA\b', 'RFSA'),
    (r'\bRFB\b', 'RFB'),
    (r'\bITT\b', 'ITT'),
    (r'\bITQ\b', 'ITQ'),
    (r'\bAOCI\b', 'AOCI'),
    (r'\bACANS?\b', 'ACAN'),
    (r'\bLOI\b', 'LOI'),
    (r'\bSOW\b', 'SOW'),
    (r'\bRequest\s+for\s+Proposal', 'RFP'),
    (r'\bRequest\s+for\s+Quotation', 'RFQ'),
    (r'\bRequest\s+for\s+Information', 'RFI'),
    (r'\bRequest\s+for\s+Bids?\b', 'RFB'),
    (r'\bRequest\s+for\s+Standing\s+Offer', 'RFSO'),
    (r'\bRequest\s+for\s+Supply\s+Arrangement', 'RFSA'),
    (r'\bInvitation\s+to\s+Tender', 'ITT'),
    (r'\bInvitation\s+to\s+Qualify', 'ITQ'),
]


def extract_procurement_type(title, source_ref=None):
    for text in [title or '', source_ref or '']:
        for pattern, ptype in PROCUREMENT_TYPE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return ptype
    return None


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def main():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        sys.exit(1)

    client = httpx.Client(timeout=30.0)

    # Fetch all tenders where procurement_type is null
    offset = 0
    page_size = 1000
    total_updated = 0
    total_scanned = 0

    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/tenders",
            params={
                "procurement_type": "is.null",
                "select": "id,title,source_reference",
                "limit": page_size,
                "offset": offset,
            },
            headers=headers(),
        )

        if resp.status_code != 200:
            print(f"ERROR fetching tenders: {resp.status_code} {resp.text[:200]}")
            sys.exit(1)

        rows = resp.json()
        if not rows:
            break

        total_scanned += len(rows)
        updates = []

        for row in rows:
            ptype = extract_procurement_type(row.get("title"), row.get("source_reference"))
            if ptype:
                updates.append({"id": row["id"], "procurement_type": ptype})

        # Batch update
        for update in updates:
            resp = client.patch(
                f"{SUPABASE_URL}/rest/v1/tenders",
                params={"id": f"eq.{update['id']}"},
                json={"procurement_type": update["procurement_type"]},
                headers=headers(),
            )
            if resp.status_code not in (200, 204):
                print(f"  WARN: Failed to update {update['id']}: {resp.status_code}")

        total_updated += len(updates)
        print(f"  Scanned {total_scanned} | Updated {total_updated} so far...")

        if len(rows) < page_size:
            break
        offset += page_size

    print(f"\nDone. Scanned {total_scanned} tenders, updated {total_updated} with procurement_type.")
    client.close()


if __name__ == "__main__":
    main()
