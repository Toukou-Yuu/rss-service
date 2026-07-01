from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from rss_service.db.connection import open_connection
from rss_service.db.migrations import run_migrations
from rss_service.db.repository import Repository
from rss_service.external.search_items import ExternalItemService
from rss_service.feeds.service import run_fetch_sync
from rss_service.reports.generator import ReportGenerator
from rss_service.settings import get_settings

Permission = Literal["read", "write", "admin"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    permission: Permission
    description: str


ToolResult = dict[str, Any]
RawTool = Callable[..., Any]


def open_repository() -> Any:
    settings = get_settings()
    connection_cm = open_connection(settings.db_path)
    connection = connection_cm.__enter__()
    run_migrations(connection)
    return settings, Repository(connection), connection_cm


def success(
    summary: str, data: dict[str, Any] | None = None, warnings: list[str] | None = None
) -> ToolResult:
    return {
        "ok": True,
        "summary": summary,
        "data": data or {},
        "warnings": warnings or [],
    }


def error(
    *,
    code: str,
    message: str,
    retryable: bool = False,
    suggested_action: str,
) -> ToolResult:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "suggested_action": suggested_action,
        },
    }


def rss_list_feeds() -> ToolResult:
    _, repository, connection_cm = open_repository()
    try:
        feeds = repository.list_feeds()
    finally:
        connection_cm.__exit__(None, None, None)
    return success(
        f"Found {len(feeds)} RSS feeds.",
        {"feeds": feeds, "count": len(feeds)},
    )


def rss_add_feed(
    *,
    name: str,
    url: str,
    category: str,
    source_type: str = "rss",
    enabled: bool = True,
    priority: int = 50,
) -> ToolResult:
    _, repository, connection_cm = open_repository()
    try:
        feed = repository.create_feed(
            name=name,
            url=url,
            category=category,
            source_type=source_type,
            enabled=enabled,
            priority=priority,
        )
        repository.connection.commit()
    finally:
        connection_cm.__exit__(None, None, None)
    return success(f"Added feed {feed['id']}: {feed['name']}.", {"feed": feed})


def rss_remove_feed(*, feed_id: int) -> ToolResult:
    _, repository, connection_cm = open_repository()
    try:
        deleted = repository.delete_feed(feed_id)
        repository.connection.commit()
    finally:
        connection_cm.__exit__(None, None, None)
    if not deleted:
        return error(
            code="FEED_NOT_FOUND",
            message=f"Feed not found: {feed_id}",
            suggested_action="Call rss_list_feeds first, then retry with an existing feed_id.",
        )
    return success(f"Removed feed {feed_id}.", {"deleted": True, "feed_id": feed_id})


def rss_test_feed(*, url: str) -> ToolResult:
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
    sample_entries = [
        {"title": item.title, "url": item.url, "summary": item.summary}
        for item in parsed.entries[:3]
    ]
    return success(
        f"Feed test completed with {len(parsed.entries)} entries.",
        {
            "feed_title": parsed.title,
            "entry_count": len(parsed.entries),
            "sample_entries": sample_entries,
        },
        parsed.warnings,
    )


def rss_fetch(
    *,
    feed_ids: list[int] | None = None,
    categories: list[str] | None = None,
    force: bool = False,
    fixture: str | None = None,
) -> ToolResult:
    settings, repository, connection_cm = open_repository()
    try:
        fetch_run = run_fetch_sync(
            repository,
            settings,
            feed_ids=feed_ids,
            categories=categories,
            force=force,
            fixture_dir=Path(fixture) if fixture else None,
        )
    finally:
        connection_cm.__exit__(None, None, None)
    return success(
        (
            f"Fetch run {fetch_run['id']} {fetch_run['status']}: "
            f"{fetch_run['new_entry_count']} new entries, {fetch_run['error_count']} errors."
        ),
        {"fetch_run": fetch_run},
    )


def rss_inject_search_items(*, items: list[dict[str, Any]]) -> ToolResult:
    settings, repository, connection_cm = open_repository()
    try:
        service = ExternalItemService(
            repository,
            summary_max_length=settings.summary_max_length,
        )
        result = service.inject_items(items)
    finally:
        connection_cm.__exit__(None, None, None)
    return success(
        f"Injected {result['inserted']} new external items and updated {result['updated']}.",
        result,
    )


def rss_generate_report(*, report_type: str, at: str, force: bool = False) -> ToolResult:
    settings, repository, connection_cm = open_repository()
    try:
        report = ReportGenerator(repository, settings).generate(
            report_type=report_type,
            at=datetime.fromisoformat(at),
            force=force,
        )
    finally:
        connection_cm.__exit__(None, None, None)
    return success(
        f"Generated {report_type} report {report['id']} with {report['item_count']} items.",
        {"report": report},
    )


def rss_list_reports(limit: int = 100) -> ToolResult:
    _, repository, connection_cm = open_repository()
    try:
        reports = repository.list_reports(limit=limit)
    finally:
        connection_cm.__exit__(None, None, None)
    return success(
        f"Found {len(reports)} reports.",
        {"reports": reports, "count": len(reports)},
    )


def rss_read_report(*, report_id: str, include_sources: bool = True) -> ToolResult:
    _, repository, connection_cm = open_repository()
    try:
        report = repository.get_report(report_id)
    finally:
        connection_cm.__exit__(None, None, None)
    if report is None:
        return error(
            code="REPORT_NOT_FOUND",
            message=f"Report not found: {report_id}",
            suggested_action="Call rss_list_reports first, then retry with an existing report_id.",
        )
    markdown = Path(str(report["markdown_path"])).read_text(encoding="utf-8")
    data: dict[str, Any] = {
        "report_id": report_id,
        "markdown": markdown,
        "metadata": report,
        "truncated": False,
    }
    if include_sources:
        import json

        data["sources"] = json.loads(
            Path(str(report["sources_json_path"])).read_text(encoding="utf-8")
        )
    return success(f"Read report {report_id}.", data)


def rss_get_report_sources(*, report_id: str) -> ToolResult:
    result = rss_read_report(report_id=report_id, include_sources=True)
    if not result.get("ok"):
        return result
    data = cast(dict[str, Any], result["data"])
    return success(
        f"Read sources for report {report_id}.",
        {"report_id": report_id, "sources": data["sources"]},
    )


TOOL_SPECS: dict[str, ToolSpec] = {
    "rss_list_feeds": ToolSpec(
        "rss_list_feeds",
        "read",
        "List configured RSS, Atom, and RSSHub feeds. Use before adding or "
        "removing feeds. Read-only.",
    ),
    "rss_add_feed": ToolSpec(
        "rss_add_feed",
        "write",
        "Add a feed to rss-service. Side effect: writes feed configuration to SQLite.",
    ),
    "rss_remove_feed": ToolSpec(
        "rss_remove_feed",
        "write",
        "Remove a feed by id. Side effect: deletes the feed row from SQLite.",
    ),
    "rss_test_feed": ToolSpec(
        "rss_test_feed",
        "read",
        "Fetch and parse a candidate feed URL without saving it. Read-only network operation.",
    ),
    "rss_fetch": ToolSpec(
        "rss_fetch",
        "write",
        "Fetch enabled feeds and store new entries. Side effect: writes fetch run and entry state.",
    ),
    "rss_inject_search_items": ToolSpec(
        "rss_inject_search_items",
        "write",
        "Inject Hermes-provided web search results as external report items. "
        "Side effect: writes external items.",
    ),
    "rss_generate_report": ToolSpec(
        "rss_generate_report",
        "write",
        "Generate a daily, weekly, or monthly Markdown report. Side effect: "
        "writes report files and metadata.",
    ),
    "rss_list_reports": ToolSpec(
        "rss_list_reports",
        "read",
        "List generated reports and their metadata. Read-only.",
    ),
    "rss_read_report": ToolSpec(
        "rss_read_report",
        "read",
        "Read a generated report's Markdown and optionally its sources. "
        "Read-only; can return long text.",
    ),
    "rss_get_report_sources": ToolSpec(
        "rss_get_report_sources",
        "read",
        "Read sources.json for a generated report. Use when checking report provenance. Read-only.",
    ),
}

TOOLS: dict[str, RawTool] = {
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


def call_rss_tool(tool_name: str, arguments: dict[str, Any]) -> ToolResult:
    if tool_name not in TOOLS:
        return error(
            code="TOOL_NOT_FOUND",
            message=f"Unknown RSS MCP tool: {tool_name}",
            suggested_action="Call MCP list_tools and retry with a supported rss_* tool name.",
        )
    try:
        result = TOOLS[tool_name](**arguments)
    except Exception as exc:
        return error(
            code="TOOL_CALL_FAILED",
            message=str(exc),
            retryable=True,
            suggested_action="Inspect the tool arguments and rss-service logs, then retry.",
        )
    if isinstance(result, dict) and "ok" in result:
        return cast(ToolResult, result)
    return success(f"{tool_name} completed.", {"result": result})
