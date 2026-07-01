import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from rss_service.logging import log_extra

LOGGER = logging.getLogger(__name__)
RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class FetchRequest:
    url: str
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True)
class FetchResponse:
    status_code: int
    final_url: str
    content: bytes
    etag: str | None
    last_modified: str | None
    not_modified: bool
    elapsed_ms: int


class FeedFetcher:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        retry_times: int,
        per_domain_concurrency: int,
        proxy_url: str | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.retry_times = retry_times
        self.proxy_url = proxy_url
        self.domain_limiters: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(per_domain_concurrency)
        )

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        domain = urlsplit(request.url).netloc.lower()
        async with self.domain_limiters[domain]:
            return await self._fetch_with_retries(request)

    async def _fetch_with_retries(self, request: FetchRequest) -> FetchResponse:
        headers = {"User-Agent": self.user_agent}
        if request.etag:
            headers["If-None-Match"] = request.etag
        if request.last_modified:
            headers["If-Modified-Since"] = request.last_modified

        timeout = httpx.Timeout(self.timeout_seconds)
        start = time.monotonic()
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            proxy=self.proxy_url,
        ) as client:
            for attempt in range(self.retry_times + 1):
                response = await client.get(request.url, headers=headers)
                if response.status_code not in RETRY_STATUSES or attempt == self.retry_times:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    log_extra(
                        LOGGER,
                        logging.INFO,
                        "feed_http_fetch_completed",
                        url=request.url,
                        status_code=response.status_code,
                        elapsed_ms=elapsed_ms,
                    )
                    if response.status_code >= 400:
                        raise RuntimeError(f"feed fetch returned HTTP {response.status_code}")
                    return FetchResponse(
                        status_code=response.status_code,
                        final_url=str(response.url),
                        content=response.content,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        not_modified=response.status_code == 304,
                        elapsed_ms=elapsed_ms,
                    )
                await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError("unreachable fetch loop")
