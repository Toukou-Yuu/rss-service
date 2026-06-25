import logging
from datetime import datetime
from typing import Any

from rss_service.db.repository import Repository
from rss_service.feeds.dedupe import content_hash, dedupe_key, iso_date_or_none, stable_item_id
from rss_service.feeds.normalizer import canonicalize_url, clean_summary, is_http_url
from rss_service.logging import log_extra

LOGGER = logging.getLogger(__name__)


class ExternalItemService:
    def __init__(self, repository: Repository, *, summary_max_length: int = 240) -> None:
        self.repository = repository
        self.summary_max_length = summary_max_length

    def inject_items(self, items: list[dict[str, Any]]) -> dict[str, int]:
        accepted = 0
        inserted = 0
        updated = 0
        skipped = 0
        for item in items:
            url = str(item["url"])
            if not is_http_url(url):
                skipped += 1
                continue
            accepted += 1
            canonical_url = canonicalize_url(url)
            title = str(item["title"]).strip()
            summary = clean_summary(str(item["summary"]), self.summary_max_length)
            published_at = _iso_datetime(item.get("published_at"))
            retrieved_at = _iso_datetime(item["retrieved_at"])
            key = dedupe_key(title, canonical_url, published_at or retrieved_at)
            result = self.repository.insert_external_item(
                item_id=stable_item_id("external", key),
                provider=item.get("provider"),
                query=item.get("query"),
                title=title,
                canonical_url=canonical_url,
                summary=summary,
                category=str(item["category"]),
                published_at=published_at,
                retrieved_at=retrieved_at,
                dedupe_key=key,
                content_hash=content_hash(title, summary),
            )
            if result == "inserted":
                inserted += 1
            else:
                updated += 1
        self.repository.connection.commit()
        log_extra(
            LOGGER,
            logging.INFO,
            "external_items_injected",
            accepted=accepted,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
        )
        return {"accepted": accepted, "inserted": inserted, "updated": updated, "skipped": skipped}


def _iso_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return iso_date_or_none(value) or ""
    return str(value)
