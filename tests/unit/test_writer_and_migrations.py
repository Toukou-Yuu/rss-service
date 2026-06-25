from pathlib import Path

from rss_service.db.connection import open_connection
from rss_service.db.migrations import run_migrations
from rss_service.reports.writer import atomic_write_text


def test_migration_runner_applies_schema(tmp_path: Path) -> None:
    with open_connection(tmp_path / "rss.sqlite3") as connection:
        applied = run_migrations(connection)
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "feeds" in tables
    assert "external_items" in tables
    assert applied


def test_atomic_write_text_replaces_file(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    atomic_write_text(path, "one")
    atomic_write_text(path, "two")
    assert path.read_text(encoding="utf-8") == "two"
    assert not path.with_suffix(".md.tmp").exists()
