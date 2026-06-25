from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from rss_service.api.deps import repository_dep, require_token
from rss_service.db.repository import Repository

router = APIRouter(dependencies=[Depends(require_token)], tags=["entries"])


@router.get("/entries")
def list_entries(
    repository: Annotated[Repository, Depends(repository_dep)],
    limit: int = 100,
    category: str | None = None,
) -> list[dict[str, Any]]:
    return repository.list_entries(limit=limit, category=category)


@router.get("/entries/{entry_id}")
def get_entry(
    entry_id: str,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, Any]:
    entry = repository.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    return entry
