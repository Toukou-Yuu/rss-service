from datetime import datetime
from pathlib import Path
from typing import Any, cast

from rss_service.db.connection import open_connection
from rss_service.db.repository import Repository
from rss_service.external.search_items import ExternalItemService
from rss_service.feeds.service import run_fetch_sync
from rss_service.reports.generator import ReportGenerator
from rss_service.settings import get_settings


def rss_list_feeds() -> list[dict[str, Any]]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        return Repository(connection).list_feeds()


def rss_add_feed(
    *,
    name: str,
    url: str,
    category: str,
    source_type: str = "rss",
    enabled: bool = True,
    priority: int = 50,
) -> dict[str, Any]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        repository = Repository(connection)
        feed = repository.create_feed(
            name=name,
            url=url,
            category=category,
            source_type=source_type,
            enabled=enabled,
            priority=priority,
        )
        repository.connection.commit()
        return feed


def rss_remove_feed(*, feed_id: int) -> dict[str, bool]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        repository = Repository(connection)
        deleted = repository.delete_feed(feed_id)
        repository.connection.commit()
        return {"deleted": deleted}


def rss_test_feed(*, url: str) -> dict[str, Any]:
    settings = get_settings()
    import httpx

    from rss_service.feeds.parser import parse_feed_bytes

    response = httpx.get(
        url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.fetch_timeout_seconds,
        follow_redirects=True,
    )
    parsed = parse_feed_bytes(response.content, summary_max_length=settings.summary_max_length)
    return {
        "ok": True,
        "feed_title": parsed.title,
        "entry_count": len(parsed.entries),
        "sample_entries": [
            {"title": item.title, "url": item.url, "summary": item.summary}
            for item in parsed.entries[:3]
        ],
        "warnings": parsed.warnings,
    }


def rss_fetch(
    *,
    feed_ids: list[int] | None = None,
    categories: list[str] | None = None,
    force: bool = False,
    fixture: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        return run_fetch_sync(
            Repository(connection),
            settings,
            feed_ids=feed_ids,
            categories=categories,
            force=force,
            fixture_dir=Path(fixture) if fixture else None,
        )


def rss_inject_search_items(*, items: list[dict[str, Any]]) -> dict[str, int]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        service = ExternalItemService(
            Repository(connection),
            summary_max_length=settings.summary_max_length,
        )
        return service.inject_items(items)


def rss_generate_report(*, report_type: str, at: str, force: bool = False) -> dict[str, Any]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        return ReportGenerator(Repository(connection), settings).generate(
            report_type=report_type,
            at=datetime.fromisoformat(at),
            force=force,
        )


def rss_list_reports() -> list[dict[str, Any]]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        return Repository(connection).list_reports()


def rss_read_report(*, report_id: str, include_sources: bool = True) -> dict[str, Any]:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        report = Repository(connection).get_report(report_id)
    if report is None:
        raise KeyError(report_id)
    markdown = Path(str(report["markdown_path"])).read_text(encoding="utf-8")
    payload: dict[str, Any] = {"markdown": markdown}
    if include_sources:
        import json

        payload["sources"] = json.loads(
            Path(str(report["sources_json_path"])).read_text(encoding="utf-8")
        )
    return payload


def rss_get_report_sources(*, report_id: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        rss_read_report(report_id=report_id, include_sources=True)["sources"],
    )


TOOLS = {
    "rss_list_feeds": rss_list_feeds,
    "rss_add_feed": rss_add_feed,
    "rss_remove_feed": rss_remove_feed,
    "rss_test_feed": rss_test_feed,
    "rss_fetch": rss_fetch,
    "rss_inject_search_items": rss_inject_search_items,
    "rss_generate_report": rss_generate_report,
    "rss_list_reports": rss_list_reports,
    "rss_read_report": rss_read_report,
    "rss_get_report_sources": rss_get_report_sources,
}
