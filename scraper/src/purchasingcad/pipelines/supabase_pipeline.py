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
    title = item.get("title") or item.get("title_fr") or "Untitled"
    description = item.get("description") or item.get("description_fr") or ""
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

    return {
        "id": existing_id or str(uuid.uuid4()),
        "title": title,
        "description": description,
        "source": source,
        "source_url": item.get("source_url"),
        "source_reference": source_ref,
        "status": item.get("status"),
        "category_primary": item.get("category"),
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
