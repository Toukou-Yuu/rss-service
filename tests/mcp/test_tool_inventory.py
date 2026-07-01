from pathlib import Path

import pytest

from rss_service.mcp.server import create_mcp_server
from rss_service.mcp.tools import TOOL_SPECS, call_rss_tool

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TOOLS = {
    "rss_list_feeds",
    "rss_add_feed",
    "rss_remove_feed",
    "rss_test_feed",
    "rss_fetch",
    "rss_inject_search_items",
    "rss_generate_report",
    "rss_list_reports",
    "rss_read_report",
    "rss_get_report_sources",
}


@pytest.mark.asyncio
async def test_mcp_tool_inventory_matches_architecture_standard() -> None:
    server = create_mcp_server()

    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}

    assert tool_names == EXPECTED_TOOLS
    for tool in tools:
        assert tool.description
        assert tool.name in TOOL_SPECS
        assert TOOL_SPECS[tool.name].permission in {"read", "write", "admin"}


def test_tool_calls_return_standard_success_envelope(isolated_env: None) -> None:
    result = call_rss_tool("rss_list_feeds", {})

    assert result == {
        "ok": True,
        "summary": "Found 0 RSS feeds.",
        "data": {"feeds": [], "count": 0},
        "warnings": [],
    }


def test_tool_calls_return_standard_error_envelope(isolated_env: None) -> None:
    result = call_rss_tool("rss_read_report", {"report_id": "missing"})

    assert result["ok"] is False
    assert result["error"] == {
        "code": "REPORT_NOT_FOUND",
        "message": "Report not found: missing",
        "retryable": False,
        "suggested_action": "Call rss_list_reports first, then retry with an existing report_id.",
    }


def test_tool_calls_initialize_database_when_needed(tmp_path, monkeypatch) -> None:
    from rss_service.settings import reset_settings_cache

    monkeypatch.setenv("RSS_DB_PATH", str(tmp_path / "fresh.sqlite3"))
    monkeypatch.setenv("RSS_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("RSS_CONFIG_DIR", str(PROJECT_ROOT / "config"))
    reset_settings_cache()
    try:
        result = call_rss_tool("rss_list_feeds", {})
    finally:
        reset_settings_cache()

    assert result["ok"] is True
    assert result["data"] == {"feeds": [], "count": 0}
