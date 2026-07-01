from __future__ import annotations

import json
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.types import ASGIApp

from rss_service.mcp.tools import TOOL_SPECS, call_rss_tool


def create_mcp_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8788,
    path: str = "/mcp",
) -> FastMCP:
    server = FastMCP(
        "rss-service",
        instructions=(
            "Agent-facing tools for hikari's rss-service. Use these tools to manage feeds, "
            "fetch RSS/search items, generate Markdown reports, and read report sources."
        ),
        host=host,
        port=port,
        streamable_http_path=path,
        stateless_http=True,
        json_response=True,
    )
    _register_tools(server)
    return server


def create_mcp_http_app(
    *,
    host: str = "127.0.0.1",
    port: int = 8788,
    path: str = "/mcp",
) -> ASGIApp:
    return create_mcp_server(host=host, port=port, path=path).streamable_http_app()


def run_stdio_server() -> None:
    create_mcp_server().run("stdio")


def run_streamable_http_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8788,
    path: str = "/mcp",
) -> None:
    create_mcp_server(host=host, port=port, path=path).run("streamable-http")


def call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Compatibility helper for older tests/scripts that called the legacy JSON loop."""
    return call_rss_tool(tool_name, arguments)


def run_legacy_json_stdio_server() -> None:
    """Run the pre-MCP line-delimited JSON protocol for local backwards compatibility."""
    for line in sys.stdin:
        request = json.loads(line)
        tool_name = request["tool"]
        arguments = request.get("arguments", {})
        result = call_rss_tool(tool_name, arguments)
        sys.stdout.write(json.dumps({"result": result}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _register_tools(server: FastMCP) -> None:
    server.tool(
        name="rss_list_feeds",
        description=TOOL_SPECS["rss_list_feeds"].description,
    )(rss_list_feeds_tool)
    server.tool(
        name="rss_add_feed",
        description=TOOL_SPECS["rss_add_feed"].description,
    )(rss_add_feed_tool)
    server.tool(
        name="rss_remove_feed",
        description=TOOL_SPECS["rss_remove_feed"].description,
    )(rss_remove_feed_tool)
    server.tool(
        name="rss_test_feed",
        description=TOOL_SPECS["rss_test_feed"].description,
    )(rss_test_feed_tool)
    server.tool(
        name="rss_fetch",
        description=TOOL_SPECS["rss_fetch"].description,
    )(rss_fetch_tool)
    server.tool(
        name="rss_inject_search_items",
        description=TOOL_SPECS["rss_inject_search_items"].description,
    )(rss_inject_search_items_tool)
    server.tool(
        name="rss_generate_report",
        description=TOOL_SPECS["rss_generate_report"].description,
    )(rss_generate_report_tool)
    server.tool(
        name="rss_list_reports",
        description=TOOL_SPECS["rss_list_reports"].description,
    )(rss_list_reports_tool)
    server.tool(
        name="rss_read_report",
        description=TOOL_SPECS["rss_read_report"].description,
    )(rss_read_report_tool)
    server.tool(
        name="rss_get_report_sources",
        description=TOOL_SPECS["rss_get_report_sources"].description,
    )(rss_get_report_sources_tool)


def rss_list_feeds_tool() -> dict[str, Any]:
    return call_rss_tool("rss_list_feeds", {})


def rss_add_feed_tool(
    name: str,
    url: str,
    category: str,
    source_type: str = "rss",
    enabled: bool = True,
    priority: int = 50,
) -> dict[str, Any]:
    return call_rss_tool(
        "rss_add_feed",
        {
            "name": name,
            "url": url,
            "category": category,
            "source_type": source_type,
            "enabled": enabled,
            "priority": priority,
        },
    )


def rss_remove_feed_tool(feed_id: int) -> dict[str, Any]:
    return call_rss_tool("rss_remove_feed", {"feed_id": feed_id})


def rss_test_feed_tool(url: str) -> dict[str, Any]:
    return call_rss_tool("rss_test_feed", {"url": url})


def rss_fetch_tool(
    feed_ids: list[int] | None = None,
    categories: list[str] | None = None,
    force: bool = False,
    fixture: str | None = None,
) -> dict[str, Any]:
    return call_rss_tool(
        "rss_fetch",
        {
            "feed_ids": feed_ids,
            "categories": categories,
            "force": force,
            "fixture": fixture,
        },
    )


def rss_inject_search_items_tool(items: list[dict[str, Any]]) -> dict[str, Any]:
    return call_rss_tool("rss_inject_search_items", {"items": items})


def rss_generate_report_tool(report_type: str, at: str, force: bool = False) -> dict[str, Any]:
    return call_rss_tool(
        "rss_generate_report",
        {"report_type": report_type, "at": at, "force": force},
    )


def rss_list_reports_tool(limit: int = 100) -> dict[str, Any]:
    return call_rss_tool("rss_list_reports", {"limit": limit})


def rss_read_report_tool(report_id: str, include_sources: bool = True) -> dict[str, Any]:
    return call_rss_tool(
        "rss_read_report",
        {"report_id": report_id, "include_sources": include_sources},
    )


def rss_get_report_sources_tool(report_id: str) -> dict[str, Any]:
    return call_rss_tool("rss_get_report_sources", {"report_id": report_id})
