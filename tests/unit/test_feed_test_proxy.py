from pathlib import Path
from typing import Any

import httpx

from rss_service.cli.main import feeds_test
from rss_service.mcp import tools
from rss_service.settings import reset_settings_cache

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROXY_URL = "http://proxy.example:8080"


class Response:
    content = (PROJECT_ROOT / "fixtures/feeds/ai_agent.atom").read_bytes()


def _enable_fetch_proxy(monkeypatch: Any) -> None:
    monkeypatch.setenv("RSS_FETCH_PROXY", PROXY_URL)
    reset_settings_cache()


def test_mcp_feed_test_uses_configured_proxy(isolated_env: None, monkeypatch: Any) -> None:
    captured = {}

    def fake_get(*_: Any, **kwargs: Any) -> Response:
        captured.update(kwargs)
        return Response()

    _enable_fetch_proxy(monkeypatch)
    monkeypatch.setattr(httpx, "get", fake_get)

    result = tools.rss_test_feed(url="https://example.com/rss.xml")

    assert result["ok"] is True
    assert captured["proxy"] == PROXY_URL


def test_cli_feed_test_uses_configured_proxy(isolated_env: None, monkeypatch: Any) -> None:
    captured = {}

    def fake_get(*_: Any, **kwargs: Any) -> Response:
        captured.update(kwargs)
        return Response()

    _enable_fetch_proxy(monkeypatch)
    monkeypatch.setattr(httpx, "get", fake_get)

    feeds_test("https://example.com/rss.xml")

    assert captured["proxy"] == PROXY_URL
