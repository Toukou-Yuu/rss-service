import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rss_service.db.connection import open_connection
from rss_service.db.repository import Repository
from rss_service.logging import log_extra
from rss_service.settings import Settings, get_settings

LOGGER = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def settings_dep() -> Settings:
    return get_settings()


def require_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        log_extra(LOGGER, logging.WARNING, "api_auth_failed", reason="missing_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    if credentials.credentials != settings.api_token:
        log_extra(LOGGER, logging.WARNING, "api_auth_failed", reason="invalid_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")


def repository_dep(settings: Annotated[Settings, Depends(settings_dep)]) -> Iterator[Repository]:
    with open_connection(settings.db_path) as connection:
        yield Repository(connection)
