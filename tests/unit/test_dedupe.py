from rss_service.feeds.dedupe import dedupe_key, stable_item_id


def test_dedupe_key_uses_title_domain_and_day() -> None:
    key = dedupe_key("Hello Agent!", "https://example.com/a", "2026-06-24T08:00:00+08:00")
    assert key == "title:example.com:2026-06-24:hello agent"


def test_stable_item_id_is_prefixed() -> None:
    assert stable_item_id("rss", "abc").startswith("rss:")
