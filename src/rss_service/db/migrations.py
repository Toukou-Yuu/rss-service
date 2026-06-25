import logging
import sqlite3
from pathlib import Path

from rss_service.logging import log_extra

LOGGER = logging.getLogger(__name__)
SCHEMA_DIR = Path(__file__).parent / "schema"


def run_migrations(connection: sqlite3.Connection, schema_dir: Path = SCHEMA_DIR) -> list[str]:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied = {
        row["version"]
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    applied_now: list[str] = []
    for path in sorted(schema_dir.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        with connection:
            connection.executescript(sql)
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
                (version,),
            )
        applied_now.append(version)
        log_extra(LOGGER, logging.INFO, "db_migration_applied", version=version)
    return applied_now
