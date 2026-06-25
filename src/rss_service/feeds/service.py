import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml

from rss_service.db.repository import Repository, utc_now
from rss_service.feeds.dedupe import content_hash, dedupe_key, iso_date_or_none, stable_item_id
from rss_service.feeds.fetcher import FeedFetcher, FetchRequest
from rss_service.feeds.normalizer import canonicalize_url, is_http_url
from rss_service.feeds.parser import ParsedFeed, parse_feed_bytes
from rss_service.logging import log_extra
from rss_service.settings import Settings

LOGGER = logging.getLogger(__name__)


class FeedService:
    def __init__(self, repository: Repository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def import_feeds(self, path: Path) -> list[dict[str, Any]]:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        feeds = data.get("feeds", [])
        created = self.repository.create_many_feeds(feeds)
        self.repository.connection.commit()
        return created

    def export_feeds(self, path: Path | None = None) -> dict[str, Any]:
        feeds = self.repository.list_feeds()
        payload = {
            "feeds": [
                {
                    "name": feed["name"],
                    "url": feed["url"],
                    "category": feed["category"],
                    "source_type": feed["source_type"],
                    "enabled": bool(feed["enabled"]),
                    "priority": feed["priority"],
                }
                for feed in feeds
            ]
        }
        if path:
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        return payload

    async def fetch(
        self,
        *,
        feed_ids: list[int] | None = None,
        categories: list[str] | None = None,
        force: bool = False,
        fixture_dir: Path | None = None,
    ) -> dict[str, Any]:
        feeds = self.repository.list_feeds(enabled=True, categories=categories, feed_ids=feed_ids)
        run_id = self.repository.start_fetch_run(len(feeds))
        self.repository.connection.commit()
        log_extra(
            LOGGER,
            logging.INFO,
            "feed_fetch_run_started",
            run_id=run_id,
            feed_count=len(feeds),
        )

        if fixture_dir:
            results = [self._fetch_fixture_feed(run_id, feed, fixture_dir) for feed in feeds]
        else:
            results = await self._fetch_real_feeds(run_id, feeds, force=force)

        success_count = sum(1 for result in results if result["status"] == "success")
        error_count = sum(1 for result in results if result["status"] == "error")
        new_entry_count = sum(int(result["new_entry_count"]) for result in results)
        status = "completed" if error_count == 0 else "completed_with_errors"
        run = self.repository.finish_fetch_run(
            run_id,
            status=status,
            success_count=success_count,
            error_count=error_count,
            new_entry_count=new_entry_count,
            log={"results": results},
        )
        self.repository.connection.commit()
        log_extra(
            LOGGER,
            logging.INFO,
            "feed_fetch_run_completed",
            run_id=run_id,
            status=status,
            new_entry_count=new_entry_count,
        )
        return run

    async def _fetch_real_feeds(
        self,
        run_id: str,
        feeds: list[dict[str, Any]],
        *,
        force: bool,
    ) -> list[dict[str, Any]]:
        fetcher = FeedFetcher(
            user_agent=self.settings.user_agent,
            timeout_seconds=self.settings.fetch_timeout_seconds,
            retry_times=self.settings.fetch_retry_times,
            per_domain_concurrency=self.settings.per_domain_concurrency,
        )
        semaphore = asyncio.Semaphore(self.settings.fetch_concurrency)

        async def run_one(feed: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await self._fetch_one_real(run_id, feed, fetcher, force=force)

        return await asyncio.gather(*(run_one(feed) for feed in feeds))

    async def _fetch_one_real(
        self,
        run_id: str,
        feed: dict[str, Any],
        fetcher: FeedFetcher,
        *,
        force: bool,
    ) -> dict[str, Any]:
        checked_at = utc_now()
        try:
            response = await fetcher.fetch(
                FetchRequest(
                    url=str(feed["url"]),
                    etag=None if force else feed.get("etag"),
                    last_modified=None if force else feed.get("last_modified"),
                )
            )
            if response.not_modified:
                self.repository.update_feed_success(
                    int(feed["id"]),
                    etag=response.etag,
                    last_modified=response.last_modified,
                    checked_at=checked_at,
                )
                self.repository.add_fetch_result(
                    run_id=run_id,
                    feed_id=int(feed["id"]),
                    status="not_modified",
                    http_status=response.status_code,
                    elapsed_ms=response.elapsed_ms,
                    checked_at=checked_at,
                )
                self.repository.connection.commit()
                return {"feed_id": feed["id"], "status": "not_modified", "new_entry_count": 0}
            parsed = parse_feed_bytes(
                response.content,
                summary_max_length=self.settings.summary_max_length,
            )
            new_count = self._store_parsed_entries(feed, parsed, fetched_at=checked_at)
            self.repository.update_feed_success(
                int(feed["id"]),
                etag=response.etag,
                last_modified=response.last_modified,
                checked_at=checked_at,
            )
            self.repository.add_fetch_result(
                run_id=run_id,
                feed_id=int(feed["id"]),
                status="success",
                http_status=response.status_code,
                elapsed_ms=response.elapsed_ms,
                new_entry_count=new_count,
                checked_at=checked_at,
            )
            self.repository.connection.commit()
            return {"feed_id": feed["id"], "status": "success", "new_entry_count": new_count}
        except Exception as exc:
            self.repository.update_feed_failure(
                int(feed["id"]),
                error=str(exc),
                checked_at=checked_at,
            )
            self.repository.add_fetch_result(
                run_id=run_id,
                feed_id=int(feed["id"]),
                status="error",
                http_status=None,
                elapsed_ms=None,
                error=str(exc),
                checked_at=checked_at,
            )
            self.repository.connection.commit()
            log_extra(
                LOGGER,
                logging.ERROR,
                "feed_fetch_failed",
                feed_id=feed["id"],
                feed_name=feed["name"],
                error=str(exc),
            )
            return {
                "feed_id": feed["id"],
                "status": "error",
                "new_entry_count": 0,
                "error": str(exc),
            }

    def _fetch_fixture_feed(
        self,
        run_id: str,
        feed: dict[str, Any],
        fixture_dir: Path,
    ) -> dict[str, Any]:
        checked_at = utc_now()
        try:
            path = self._fixture_path_for_feed(feed, fixture_dir)
            parsed = parse_feed_bytes(
                path.read_bytes(),
                summary_max_length=self.settings.summary_max_length,
            )
            new_count = self._store_parsed_entries(feed, parsed, fetched_at=checked_at)
            self.repository.update_feed_success(
                int(feed["id"]),
                etag=None,
                last_modified=None,
                checked_at=checked_at,
            )
            self.repository.add_fetch_result(
                run_id=run_id,
                feed_id=int(feed["id"]),
                status="success",
                http_status=200,
                elapsed_ms=0,
                new_entry_count=new_count,
                checked_at=checked_at,
            )
            self.repository.connection.commit()
            return {"feed_id": feed["id"], "status": "success", "new_entry_count": new_count}
        except Exception as exc:
            self.repository.update_feed_failure(
                int(feed["id"]),
                error=str(exc),
                checked_at=checked_at,
            )
            self.repository.add_fetch_result(
                run_id=run_id,
                feed_id=int(feed["id"]),
                status="error",
                http_status=None,
                elapsed_ms=0,
                error=str(exc),
                checked_at=checked_at,
            )
            self.repository.connection.commit()
            return {
                "feed_id": feed["id"],
                "status": "error",
                "new_entry_count": 0,
                "error": str(exc),
            }

    def _fixture_path_for_feed(self, feed: dict[str, Any], fixture_dir: Path) -> Path:
        candidates = [
            fixture_dir / f"{feed['category']}.rss",
            fixture_dir / f"{feed['category']}.atom",
            fixture_dir / f"{feed['source_type']}.rss",
            fixture_dir / f"{feed['source_type']}.atom",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        fixture_files = sorted([*fixture_dir.glob("*.rss"), *fixture_dir.glob("*.atom")])
        if fixture_files:
            index = (int(feed["id"]) - 1) % len(fixture_files)
            return fixture_files[index]
        raise FileNotFoundError(f"no fixture feed files in {fixture_dir}")

    def _store_parsed_entries(
        self,
        feed: dict[str, Any],
        parsed: ParsedFeed,
        *,
        fetched_at: str,
    ) -> int:
        new_count = 0
        for entry in parsed.entries:
            if not is_http_url(entry.url):
                continue
            canonical_url = canonicalize_url(entry.url)
            published_at = iso_date_or_none(entry.published_at)
            updated_at = iso_date_or_none(entry.updated_at)
            key = dedupe_key(entry.title, canonical_url, published_at)
            inserted = self.repository.insert_entry(
                entry_id=stable_item_id("rss", key),
                feed_id=int(feed["id"]),
                source_guid=entry.source_guid,
                canonical_url=canonical_url,
                title=entry.title,
                summary=entry.summary,
                published_at=published_at,
                updated_at=updated_at,
                fetched_at=fetched_at,
                dedupe_key=key,
                content_hash=content_hash(entry.title, entry.summary),
                category=str(feed["category"]),
            )
            if inserted:
                new_count += 1
        return new_count


def run_fetch_sync(
    repository: Repository,
    settings: Settings,
    *,
    feed_ids: list[int] | None = None,
    categories: list[str] | None = None,
    force: bool = False,
    fixture_dir: Path | None = None,
) -> dict[str, Any]:
    service = FeedService(repository, settings)
    return asyncio.run(
        service.fetch(
            feed_ids=feed_ids,
            categories=categories,
            force=force,
            fixture_dir=fixture_dir,
        )
    )
