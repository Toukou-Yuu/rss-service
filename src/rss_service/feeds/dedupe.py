import hashlib
from datetime import datetime
from urllib.parse import urlsplit

from rss_service.feeds.normalizer import normalize_title


def content_hash(title: str, summary: str) -> str:
    return hashlib.sha256(f"{title}\n{summary}".encode()).hexdigest()


def published_day(value: str | None) -> str:
    if not value:
        return "unknown-day"
    return value[:10]


def title_domain_key(title: str, canonical_url: str, published_at: str | None) -> str:
    domain = urlsplit(canonical_url).netloc.lower()
    return f"title:{domain}:{published_day(published_at)}:{normalize_title(title)}"


def dedupe_key(title: str, canonical_url: str, published_at: str | None) -> str:
    return title_domain_key(title, canonical_url, published_at)


def stable_item_id(prefix: str, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{digest}"


def iso_date_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
