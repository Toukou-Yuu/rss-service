from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from rss_service.api.deps import repository_dep, require_token, settings_dep
from rss_service.db.repository import Repository
from rss_service.external.search_items import ExternalItemService
from rss_service.models import ExternalItemsRequest, ExternalItemsResponse
from rss_service.settings import Settings

router = APIRouter(dependencies=[Depends(require_token)], tags=["external"])


@router.post("/external-items")
def inject_external_items(
    payload: ExternalItemsRequest,
    repository: Annotated[Repository, Depends(repository_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> ExternalItemsResponse:
    service = ExternalItemService(repository, summary_max_length=settings.summary_max_length)
    result = service.inject_items([item.model_dump(mode="json") for item in payload.items])
    return ExternalItemsResponse(**result)


@router.get("/external-items")
def list_external_items(
    repository: Annotated[Repository, Depends(repository_dep)],
    limit: int = 100,
    category: str | None = None,
) -> list[dict[str, Any]]:
    return repository.list_external_items(limit=limit, category=category)


@router.delete("/external-items/{item_id}")
def delete_external_item(
    item_id: str,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, bool]:
    deleted = repository.delete_external_item(item_id)
    repository.connection.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="external item not found")
    return {"deleted": True}
