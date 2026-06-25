from typing import Any


def build_sources_json(
    *,
    report_id: str,
    report_type: str,
    period_start: str,
    period_end: str,
    generated_at: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "report_type": report_type,
        "period_start": period_start,
        "period_end": period_end,
        "generated_at": generated_at,
        "items": [_source_item(item) for item in items],
    }


def _source_item(item: dict[str, Any]) -> dict[str, Any]:
    if item["item_source"] == "rss":
        sources = [
            {
                "feed_id": item["feed_id"],
                "feed_name": item["source_name"],
                "feed_url": item["feed_url"],
                "entry_url": item["primary_url"],
                "published_at": item["published_at"],
            }
        ]
    else:
        sources = [
            {
                "provider": item["provider"],
                "query": item["query"],
                "entry_url": item["primary_url"],
                "published_at": item["published_at"],
                "retrieved_at": item["retrieved_at"],
            }
        ]
    return {
        "item_id": item["item_id"],
        "section": item["section_name"],
        "rank": item["rank_in_section"],
        "title": item["title"],
        "summary": item["summary"],
        "primary_url": item["primary_url"],
        "source_type": item["source_type"],
        "sources": sources,
    }
