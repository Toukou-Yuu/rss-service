from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rss_service.app import create_app
from rss_service.db.connection import open_connection
from rss_service.db.migrations import run_migrations
from rss_service.settings import get_settings, reset_settings_cache

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("RSS_DB_PATH", str(tmp_path / "rss.sqlite3"))
    monkeypatch.setenv("RSS_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("RSS_CONFIG_DIR", str(PROJECT_ROOT / "config"))
    monkeypatch.setenv("RSS_SERVICE_API_TOKEN", "test-token")
    reset_settings_cache()
    with open_connection(get_settings().db_path) as connection:
        run_migrations(connection)
    yield
    reset_settings_cache()


@pytest.fixture()
def client(isolated_env: None) -> TestClient:
    return TestClient(create_app())
