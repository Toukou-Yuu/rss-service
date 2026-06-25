from datetime import datetime
from pathlib import Path

from rss_service.db.connection import open_connection
from rss_service.db.repository import Repository
from rss_service.feeds.service import FeedService, run_fetch_sync
from rss_service.reports.generator import ReportGenerator
from rss_service.settings import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_daily_report_snapshot(isolated_env: None) -> None:
    markdown, sources = _generate("daily", "2026-06-24T10:00:00+08:00")
    assert "report_id: daily-2026-06-24" in markdown
    assert "knowledge_base_write: false" in markdown
    assert markdown.index("## 今日概览") < markdown.index("## 要闻")
    assert markdown.index("## 要闻") < markdown.index("## AI 与 Agent")
    assert markdown.index("## AI 与 Agent") < markdown.index("## 来源索引")
    assert "content:" not in markdown
    assert sources["items"][0]["sources"]


def _generate(report_type: str, at: str) -> tuple[str, dict[str, object]]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        repository = Repository(connection)
        FeedService(repository, settings).import_feeds(PROJECT_ROOT / "config/feeds.example.yaml")
        run_fetch_sync(repository, settings, fixture_dir=PROJECT_ROOT / "fixtures/feeds")
        report = ReportGenerator(repository, settings).generate(
            report_type=report_type,
            at=datetime.fromisoformat(at),
            force=True,
        )
    import json

    markdown = Path(str(report["markdown_path"])).read_text(encoding="utf-8")
    sources = json.loads(Path(str(report["sources_json_path"])).read_text(encoding="utf-8"))
    return markdown, sources
