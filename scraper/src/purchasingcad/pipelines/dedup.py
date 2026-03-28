import hashlib
import re
import unicodedata


def normalize_title(title: str) -> str:
    """Lowercase, strip accents, strip punctuation, collapse whitespace (per D-08)."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    stripped = re.sub(r"[^\w\s]", "", ascii_title)
    return re.sub(r"\s+", " ", stripped).strip().lower()


def compute_dedup_fingerprint(
    title: str,
    buyer_org: str,
    province: str,
    published_date: str,
) -> str:
    """SHA256 of normalized_title|buyer_org|province|published_date (per D-06)."""
    normalized = normalize_title(title)
    payload = f"{normalized}|{buyer_org.lower().strip()}|{province.lower().strip()}|{published_date}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
