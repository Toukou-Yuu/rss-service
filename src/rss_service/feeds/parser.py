from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser
from dateutil import parser as date_parser

from rss_service.feeds.normalizer import clean_summary


@dataclass(frozen=True)
class ParsedEntry:
    source_guid: str | None
    title: str
    url: str
    summary: str
    published_at: datetime | None
    updated_at: datetime | None
    summary_fallback: bool


@dataclass(frozen=True)
class ParsedFeed:
    title: str | None
    entries: list[ParsedEntry]
    warnings: list[str]


def _dict_get(mapping: Any, key: str) -> Any:
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, struct_time):
        return datetime(*value[:6], tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        parsed = date_parser.parse(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    return None


def _entry_summary(entry: Any) -> str:
    summary = _dict_get(entry, "summary") or _dict_get(entry, "description")
    if summary:
        return str(summary)
    content = _dict_get(entry, "content")
    if isinstance(content, list) and content:
        value = _dict_get(content[0], "value")
        if value:
            return str(value)
    return ""


def parse_feed_bytes(data: bytes, *, summary_max_length: int = 240) -> ParsedFeed:
    parsed = feedparser.parse(data)
    warnings: list[str] = []
    if getattr(parsed, "bozo", False):
        warnings.append(str(getattr(parsed, "bozo_exception", "bozo feed")))
    feed_title = _dict_get(getattr(parsed, "feed", {}), "title")
    entries: list[ParsedEntry] = []
    for entry in getattr(parsed, "entries", []):
        title = str(_dict_get(entry, "title") or "").strip()
        link = str(_dict_get(entry, "link") or "").strip()
        if not title or not link:
            continue
        raw_summary = _entry_summary(entry)
        summary_fallback = not bool(raw_summary.strip())
        summary = clean_summary(raw_summary or title, max_length=summary_max_length)
        source_guid = _dict_get(entry, "id") or _dict_get(entry, "guid")
        published = parse_datetime(
            _dict_get(entry, "published_parsed") or _dict_get(entry, "published")
        )
        updated = parse_datetime(_dict_get(entry, "updated_parsed") or _dict_get(entry, "updated"))
        entries.append(
            ParsedEntry(
                source_guid=str(source_guid) if source_guid else None,
                title=title,
                url=link,
                summary=summary,
                published_at=published,
                updated_at=updated,
                summary_fallback=summary_fallback,
            )
        )
    return ParsedFeed(
        title=str(feed_title) if feed_title else None,
        entries=entries,
        warnings=warnings,
    )
