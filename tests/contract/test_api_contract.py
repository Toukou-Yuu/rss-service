from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rss_service.db.connection import open_connection
from rss_service.db.repository import Repository
from rss_service.feeds.service import FeedService, run_fetch_sync
from rss_service.reports.generator import ReportGenerator
from rss_service.settings import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def seed_feed_data() -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        repository = Repository(connection)
        FeedService(repository, settings).import_feeds(PROJECT_ROOT / "config/feeds.example.yaml")
        run_fetch_sync(repository, settings, fixture_dir=PROJECT_ROOT / "fixtures/feeds")


def test_healthz_is_public(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200


def test_reports_requires_token(client: TestClient) -> None:
    assert client.get("/reports").status_code == 401


def test_feeds_crud_contract(client: TestClient) -> None:
    payload = {
        "name": "Example",
        "url": "https://example.com/rss.xml",
        "category": "ai_agent",
        "source_type": "rss",
        "enabled": True,
        "priority": 50,
    }
    created = client.post("/feeds", headers=auth(), json=payload)
    assert created.status_code == 200
    feed_id = created.json()["id"]
    assert client.get("/feeds", headers=auth()).status_code == 200
    assert client.get(f"/feeds/{feed_id}", headers=auth()).status_code == 200
    patched = client.patch(f"/feeds/{feed_id}", headers=auth(), json={"priority": 70})
    assert patched.json()["priority"] == 70
    assert client.delete(f"/feeds/{feed_id}", headers=auth()).json() == {"deleted": True}


def test_feeds_test_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        content = (PROJECT_ROOT / "fixtures/feeds/ai_agent.atom").read_bytes()

    def fake_get(*_: Any, **__: Any) -> Response:
        return Response()

    monkeypatch.setattr("rss_service.api.routes_feeds.httpx.get", fake_get)
    response = client.post(
        "/feeds/test",
        headers=auth(),
        json={"url": "https://example.com/rss.xml"},
    )
    assert response.status_code == 200
    assert response.json()["entry_count"] == 2


def test_fetch_contract_with_empty_db(client: TestClient) -> None:
    response = client.post(
        "/fetch",
        headers=auth(),
        json={"feed_ids": None, "categories": ["ai_agent"], "force": False},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_entries_category_filter_contract(client: TestClient) -> None:
    seed_feed_data()
    response = client.get("/entries?category=ai_agent&limit=10", headers=auth())
    assert response.status_code == 200
    entries = response.json()
    assert entries
    assert {entry["category"] for entry in entries} == {"ai_agent"}


def test_external_items_contract(client: TestClient) -> None:
    payload = {
        "items": [
            {
                "provider": "tavily",
                "query": "agent release",
                "title": "Agent runtime release",
                "url": "https://example.com/agent-runtime",
                "summary": "Search result summary.",
                "category": "ai_agent",
                "published_at": None,
                "retrieved_at": "2026-06-24T09:30:00+08:00",
            }
        ]
    }
    response = client.post("/external-items", headers=auth(), json=payload)
    assert response.status_code == 200
    assert response.json()["inserted"] == 1
    listed = client.get("/external-items", headers=auth()).json()
    assert listed[0]["title"] == "Agent runtime release"


def test_reports_contract(client: TestClient) -> None:
    seed_feed_data()
    generated = client.post(
        "/reports/generate",
        headers=auth(),
        json={
            "report_type": "daily",
            "at": "2026-06-24T10:00:00+08:00",
            "force": True,
        },
    )
    assert generated.status_code == 200
    report_id = generated.json()["id"]
    report = client.get(f"/reports/{report_id}", headers=auth())
    assert report.status_code == 200
    assert "knowledge_base_write: false" in report.json()["markdown"]
    assert client.get(f"/reports/{report_id}/sources", headers=auth()).status_code == 200
    markdown = client.get(f"/reports/{report_id}/markdown", headers=auth())
    assert markdown.status_code == 200
    assert "# Hikari Daily Briefing" in markdown.text


def test_report_generation_is_idempotent(isolated_env: None) -> None:
    seed_feed_data()
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        generator = ReportGenerator(Repository(connection), settings)
        first = generator.generate(
            report_type="daily",
            at=datetime.fromisoformat("2026-06-24T10:00:00+08:00"),
            force=True,
        )
        second = generator.generate(
            report_type="daily",
            at=datetime.fromisoformat("2026-06-24T10:00:00+08:00"),
            force=False,
        )
    assert first["id"] == second["id"]
