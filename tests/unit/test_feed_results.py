import json
from pathlib import Path

from rss_service.db.connection import open_connection
from rss_service.db.repository import Repository
from rss_service.feeds.service import feed_source_slug, run_fetch_sync
from rss_service.settings import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_feed_source_slug_uses_feed_name() -> None:
    assert feed_source_slug({"name": "Reddit - OpenAI - Agent"}) == "reddit-openai-agent"
    assert feed_source_slug({"name": "Reddit - ClaudeAI - MCP"}) == "reddit-claudeai-mcp"


def test_fetch_run_results_include_source_names(isolated_env: None) -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        repository = Repository(connection)
        repository.create_feed(
            name="Reddit - OpenAI - Agent",
            url="https://example.com/rss.xml",
            category="ai_agent",
            source_type="rss",
            enabled=True,
            priority=60,
        )
        connection.commit()

        run = run_fetch_sync(repository, settings, fixture_dir=PROJECT_ROOT / "fixtures/feeds")

    results = json.loads(str(run["log_json"]))["results"]
    assert results[0]["source"] == "reddit-openai-agent"
    assert results[0]["source_name"] == "Reddit - OpenAI - Agent"
    assert results[0]["feed_id"]


def test_failed_fetch_run_results_include_source_names(isolated_env: None, tmp_path: Path) -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        repository = Repository(connection)
        repository.create_feed(
            name="Reddit - ClaudeAI - MCP",
            url="https://example.com/rss.xml",
            category="ai_agent",
            source_type="rss",
            enabled=True,
            priority=60,
        )
        connection.commit()

        run = run_fetch_sync(repository, settings, fixture_dir=tmp_path)

    results = json.loads(str(run["log_json"]))["results"]
    assert run["status"] == "completed_with_errors"
    assert results[0]["source"] == "reddit-claudeai-mcp"
    assert results[0]["source_name"] == "Reddit - ClaudeAI - MCP"
    assert results[0]["error"]
