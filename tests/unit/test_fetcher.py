import asyncio

import pytest

from rss_service.feeds.fetcher import FeedFetcher, FetchRequest
from rss_service.feeds.service import exception_message


def test_fetcher_passes_configured_proxy_to_httpx(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        url = "https://example.com/feed.xml"
        content = b"<rss></rss>"
        headers = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("rss_service.feeds.fetcher.httpx.AsyncClient", FakeAsyncClient)

    fetcher = FeedFetcher(
        user_agent="test-agent",
        timeout_seconds=1.0,
        retry_times=0,
        per_domain_concurrency=1,
        proxy_url="http://proxy.example:8080",
    )
    response = asyncio.run(fetcher.fetch(FetchRequest("https://example.com/feed.xml")))

    assert response.status_code == 200
    assert captured["proxy"] == "http://proxy.example:8080"


def test_exception_message_uses_type_name_when_message_is_empty():
    assert exception_message(Exception()) == "builtins.Exception"
    assert exception_message(RuntimeError("network failed")) == "network failed"


def test_fetcher_raises_on_failed_http_status(monkeypatch):
    class Response:
        status_code = 429
        url = "https://example.com/feed.xml"
        content = b"rate limited"
        headers = {}

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("rss_service.feeds.fetcher.httpx.AsyncClient", FakeAsyncClient)

    fetcher = FeedFetcher(
        user_agent="test-agent",
        timeout_seconds=1.0,
        retry_times=0,
        per_domain_concurrency=1,
    )

    with pytest.raises(RuntimeError, match="HTTP 429"):
        asyncio.run(fetcher.fetch(FetchRequest("https://example.com/feed.xml")))
