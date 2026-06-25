from rss_service.reports.sources import build_sources_json


def test_sources_json_serializes_rss_item() -> None:
    payload = build_sources_json(
        report_id="daily-2026-06-24",
        report_type="daily",
        period_start="2026-06-23T10:00:00+08:00",
        period_end="2026-06-24T10:00:00+08:00",
        generated_at="2026-06-24T10:00:02+08:00",
        items=[
            {
                "item_id": "rss:1",
                "item_source": "rss",
                "section_name": "AI 与 Agent",
                "rank_in_section": 1,
                "title": "Title",
                "summary": "Summary",
                "primary_url": "https://example.com",
                "source_type": "RSS",
                "feed_id": 1,
                "source_name": "Feed",
                "feed_url": "https://example.com/rss.xml",
                "published_at": "2026-06-24T09:00:00+08:00",
            }
        ],
    )
    assert payload["items"][0]["sources"][0]["feed_name"] == "Feed"
