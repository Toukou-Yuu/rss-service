from pathlib import Path

from rss_service.feeds.parser import parse_feed_bytes

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_parse_atom_fixture_without_full_content() -> None:
    parsed = parse_feed_bytes((PROJECT_ROOT / "fixtures/feeds/ai_agent.atom").read_bytes())
    assert parsed.title == "AI Agent Fixture"
    assert len(parsed.entries) == 2
    assert parsed.entries[1].summary_fallback is True
    assert parsed.entries[1].summary == parsed.entries[1].title


def test_parse_malformed_feed_keeps_parseable_entries() -> None:
    parsed = parse_feed_bytes((PROJECT_ROOT / "fixtures/feeds/malformed.rss").read_bytes())
    assert parsed.warnings
    assert parsed.entries[0].title == "Malformed but parseable item"
