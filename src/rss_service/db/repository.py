import json
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class Repository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_feeds(
        self,
        *,
        enabled: bool | None = None,
        categories: list[str] | None = None,
        feed_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if enabled is not None:
            clauses.append("enabled = ?")
            params.append(1 if enabled else 0)
        if categories:
            placeholders = ",".join("?" for _ in categories)
            clauses.append(f"category IN ({placeholders})")
            params.extend(categories)
        if feed_ids:
            placeholders = ",".join("?" for _ in feed_ids)
            clauses.append(f"id IN ({placeholders})")
            params.extend(feed_ids)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.connection.execute(
            f"SELECT * FROM feeds {where} ORDER BY priority DESC, id ASC", params
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_feed(self, feed_id: int) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        return row_to_dict(row) if row else None

    def create_feed(
        self,
        *,
        name: str,
        url: str,
        category: str,
        source_type: str = "rss",
        enabled: bool = True,
        priority: int = 50,
    ) -> dict[str, Any]:
        now = utc_now()
        cursor = self.connection.execute(
            """
            INSERT INTO feeds (
              name, url, category, source_type, enabled, priority, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
              name = excluded.name,
              category = excluded.category,
              source_type = excluded.source_type,
              enabled = excluded.enabled,
              priority = excluded.priority,
              updated_at = excluded.updated_at
            RETURNING *
            """,
            (name, url, category, source_type, int(enabled), priority, now, now),
        )
        return row_to_dict(cursor.fetchone())

    def update_feed(self, feed_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        if not values:
            return self.get_feed(feed_id)
        assignments = [f"{key} = ?" for key in values]
        params = list(values.values())
        assignments.append("updated_at = ?")
        params.append(utc_now())
        params.append(feed_id)
        self.connection.execute(
            f"UPDATE feeds SET {', '.join(assignments)} WHERE id = ?",
            params,
        )
        return self.get_feed(feed_id)

    def delete_feed(self, feed_id: int) -> bool:
        cursor = self.connection.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        return cursor.rowcount > 0

    def update_feed_success(
        self,
        feed_id: int,
        *,
        etag: str | None,
        last_modified: str | None,
        checked_at: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE feeds
            SET last_checked_at = ?,
                last_success_at = ?,
                last_error = NULL,
                error_count = 0,
                etag = COALESCE(?, etag),
                last_modified = COALESCE(?, last_modified),
                updated_at = ?
            WHERE id = ?
            """,
            (checked_at, checked_at, etag, last_modified, checked_at, feed_id),
        )

    def update_feed_failure(self, feed_id: int, *, error: str, checked_at: str) -> None:
        self.connection.execute(
            """
            UPDATE feeds
            SET last_checked_at = ?,
                last_error = ?,
                error_count = error_count + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (checked_at, error, checked_at, feed_id),
        )

    def start_fetch_run(self, feed_count: int) -> str:
        run_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO fetch_runs (id, started_at, status, feed_count)
            VALUES (?, ?, 'running', ?)
            """,
            (run_id, utc_now(), feed_count),
        )
        return run_id

    def add_fetch_result(
        self,
        *,
        run_id: str,
        feed_id: int,
        status: str,
        http_status: int | None,
        elapsed_ms: int | None,
        new_entry_count: int = 0,
        error: str | None = None,
        checked_at: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO feed_fetch_results (
              id, run_id, feed_id, status, http_status, elapsed_ms,
              new_entry_count, error, checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                run_id,
                feed_id,
                status,
                http_status,
                elapsed_ms,
                new_entry_count,
                error,
                checked_at or utc_now(),
            ),
        )

    def finish_fetch_run(
        self,
        run_id: str,
        *,
        status: str,
        success_count: int,
        error_count: int,
        new_entry_count: int,
        log: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.connection.execute(
            """
            UPDATE fetch_runs
            SET finished_at = ?,
                status = ?,
                success_count = ?,
                error_count = ?,
                new_entry_count = ?,
                log_json = ?
            WHERE id = ?
            """,
            (
                utc_now(),
                status,
                success_count,
                error_count,
                new_entry_count,
                json.dumps(log or {}, ensure_ascii=False),
                run_id,
            ),
        )
        return self.get_fetch_run(run_id)

    def get_fetch_run(self, run_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM fetch_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return row_to_dict(row)

    def list_fetch_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM fetch_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def insert_entry(
        self,
        *,
        entry_id: str,
        feed_id: int,
        source_guid: str | None,
        canonical_url: str,
        title: str,
        summary: str,
        published_at: str | None,
        updated_at: str | None,
        fetched_at: str,
        dedupe_key: str,
        content_hash: str,
        category: str,
    ) -> bool:
        try:
            self.connection.execute(
                """
                INSERT INTO entries (
                  id, feed_id, source_guid, canonical_url, title, summary,
                  published_at, updated_at, fetched_at, dedupe_key, content_hash,
                  category, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    feed_id,
                    source_guid,
                    canonical_url,
                    title,
                    summary,
                    published_at,
                    updated_at,
                    fetched_at,
                    dedupe_key,
                    content_hash,
                    category,
                    fetched_at,
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def list_entries(
        self,
        *,
        limit: int = 100,
        category: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["report_eligible = 1"]
        params: list[Any] = []
        if category:
            clauses.append("entries.category = ?")
            params.append(category)
        if period_start:
            clauses.append("COALESCE(published_at, fetched_at) >= ?")
            params.append(period_start)
        if period_end:
            clauses.append("COALESCE(published_at, fetched_at) < ?")
            params.append(period_end)
        params.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT entries.*, feeds.name AS feed_name, feeds.url AS feed_url,
                   feeds.source_type AS feed_source_type, feeds.priority AS feed_priority
            FROM entries
            JOIN feeds ON feeds.id = entries.feed_id
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(published_at, fetched_at) DESC, feeds.priority DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT entries.*, feeds.name AS feed_name, feeds.url AS feed_url,
                   feeds.source_type AS feed_source_type, feeds.priority AS feed_priority
            FROM entries
            JOIN feeds ON feeds.id = entries.feed_id
            WHERE entries.id = ?
            """,
            (entry_id,),
        ).fetchone()
        return row_to_dict(row) if row else None

    def insert_external_item(
        self,
        *,
        item_id: str,
        provider: str | None,
        query: str | None,
        title: str,
        canonical_url: str,
        summary: str,
        category: str,
        published_at: str | None,
        retrieved_at: str,
        dedupe_key: str,
        content_hash: str,
    ) -> str:
        now = utc_now()
        cursor = self.connection.execute(
            "SELECT id FROM external_items WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
        if cursor:
            self.connection.execute(
                """
                UPDATE external_items
                SET provider = ?,
                    query = ?,
                    title = ?,
                    canonical_url = ?,
                    summary = ?,
                    category = ?,
                    published_at = ?,
                    retrieved_at = ?,
                    content_hash = ?
                WHERE dedupe_key = ?
                """,
                (
                    provider,
                    query,
                    title,
                    canonical_url,
                    summary,
                    category,
                    published_at,
                    retrieved_at,
                    content_hash,
                    dedupe_key,
                ),
            )
            return "updated"
        self.connection.execute(
            """
            INSERT INTO external_items (
              id, provider, query, title, canonical_url, summary, category,
              published_at, retrieved_at, dedupe_key, content_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                provider,
                query,
                title,
                canonical_url,
                summary,
                category,
                published_at,
                retrieved_at,
                dedupe_key,
                content_hash,
                now,
            ),
        )
        return "inserted"

    def list_external_items(
        self,
        *,
        limit: int = 100,
        category: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["report_eligible = 1"]
        params: list[Any] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if period_start:
            clauses.append("COALESCE(published_at, retrieved_at) >= ?")
            params.append(period_start)
        if period_end:
            clauses.append("COALESCE(published_at, retrieved_at) < ?")
            params.append(period_end)
        params.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT * FROM external_items
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(published_at, retrieved_at) DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def get_external_item(self, item_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM external_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        return row_to_dict(row) if row else None

    def delete_external_item(self, item_id: str) -> bool:
        cursor = self.connection.execute("DELETE FROM external_items WHERE id = ?", (item_id,))
        return cursor.rowcount > 0

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return row_to_dict(row) if row else None

    def list_reports(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM reports ORDER BY generated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]

    def save_report(
        self,
        *,
        report_id: str,
        report_type: str,
        period_start: str,
        period_end: str,
        generated_at: str,
        markdown_path: str,
        sources_json_path: str,
        source_count: int,
        item_count: int,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connection:
            self.connection.execute("DELETE FROM report_items WHERE report_id = ?", (report_id,))
            self.connection.execute("DELETE FROM reports WHERE id = ?", (report_id,))
            self.connection.execute(
                """
                INSERT INTO reports (
                  id, report_type, period_start, period_end, generated_at,
                  markdown_path, sources_json_path, source_count, item_count,
                  status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
                """,
                (
                    report_id,
                    report_type,
                    period_start,
                    period_end,
                    generated_at,
                    markdown_path,
                    sources_json_path,
                    source_count,
                    item_count,
                    now,
                ),
            )
            for item in items:
                self.connection.execute(
                    """
                    INSERT INTO report_items (
                      report_id, item_id, item_source, section_name, rank_in_section
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        report_id,
                        item["item_id"],
                        item["item_source"],
                        item["section_name"],
                        item["rank_in_section"],
                    ),
                )
        report = self.get_report(report_id)
        if report is None:
            raise KeyError(report_id)
        return report

    def delete_report(self, report_id: str) -> bool:
        cursor = self.connection.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        return cursor.rowcount > 0

    def list_categories(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT DISTINCT category FROM feeds ORDER BY category"
        ).fetchall()
        return [str(row["category"]) for row in rows]

    def create_many_feeds(self, feeds: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for feed in feeds:
            created.append(
                self.create_feed(
                    name=str(feed["name"]),
                    url=str(feed["url"]),
                    category=str(feed["category"]),
                    source_type=str(feed.get("source_type", "rss")),
                    enabled=bool(feed.get("enabled", True)),
                    priority=int(feed.get("priority", 50)),
                )
            )
        return created
