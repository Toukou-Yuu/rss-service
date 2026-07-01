from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from rss_service.api.deps import repository_dep, require_token, settings_dep
from rss_service.db.repository import Repository
from rss_service.feeds.parser import parse_feed_bytes
from rss_service.feeds.service import FeedService, run_fetch_sync
from rss_service.models import FeedCreate, FeedPatch, FetchRequest
from rss_service.settings import Settings

router = APIRouter(dependencies=[Depends(require_token)], tags=["feeds"])


@router.get("/feeds")
def list_feeds(repository: Annotated[Repository, Depends(repository_dep)]) -> list[dict[str, Any]]:
    return repository.list_feeds()


@router.post("/feeds")
def create_feed(
    payload: FeedCreate,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, Any]:
    feed = repository.create_feed(
        name=payload.name,
        url=str(payload.url),
        category=payload.category,
        source_type=payload.source_type,
        enabled=payload.enabled,
        priority=payload.priority,
    )
    repository.connection.commit()
    return feed


@router.get("/feeds/{feed_id}")
def get_feed(
    feed_id: int,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, Any]:
    feed = repository.get_feed(feed_id)
    if feed is None:
        raise HTTPException(status_code=404, detail="feed not found")
    return feed


@router.patch("/feeds/{feed_id}")
def patch_feed(
    feed_id: int,
    payload: FeedPatch,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if "enabled" in values:
        values["enabled"] = int(values["enabled"])
    feed = repository.update_feed(feed_id, values)
    repository.connection.commit()
    if feed is None:
        raise HTTPException(status_code=404, detail="feed not found")
    return feed


@router.delete("/feeds/{feed_id}")
def delete_feed(
    feed_id: int,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, bool]:
    deleted = repository.delete_feed(feed_id)
    repository.connection.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="feed not found")
    return {"deleted": True}


@router.post("/feeds/test")
def test_feed(
    payload: dict[str, str],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> dict[str, Any]:
    response = httpx.get(
        payload["url"],
        headers={"User-Agent": settings.user_agent},
        timeout=settings.fetch_timeout_seconds,
        follow_redirects=True,
        proxy=settings.fetch_proxy,
    )
    parsed = parse_feed_bytes(response.content, summary_max_length=settings.summary_max_length)
    return {
        "ok": True,
        "feed_title": parsed.title,
        "entry_count": len(parsed.entries),
        "sample_entries": [
            {"title": item.title, "url": item.url, "summary": item.summary}
            for item in parsed.entries[:3]
        ],
        "warnings": parsed.warnings,
    }


@router.post("/feeds/import")
def import_feeds(
    payload: dict[str, str],
    repository: Annotated[Repository, Depends(repository_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> dict[str, int]:
    service = FeedService(repository, settings)
    feeds = service.import_feeds(Path(payload["file"]))
    return {"imported": len(feeds)}


@router.get("/feeds/export")
def export_feeds(
    repository: Annotated[Repository, Depends(repository_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> dict[str, Any]:
    return FeedService(repository, settings).export_feeds()


@router.post("/fetch")
def fetch(
    payload: FetchRequest,
    repository: Annotated[Repository, Depends(repository_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> dict[str, Any]:
    return run_fetch_sync(
        repository,
        settings,
        feed_ids=payload.feed_ids,
        categories=payload.categories,
        force=payload.force,
    )


@router.get("/fetch-runs")
def list_fetch_runs(
    repository: Annotated[Repository, Depends(repository_dep)],
) -> list[dict[str, Any]]:
    return repository.list_fetch_runs()


@router.get("/fetch-runs/{run_id}")
def get_fetch_run(
    run_id: str,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, Any]:
    try:
        return repository.get_fetch_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="fetch run not found") from None
