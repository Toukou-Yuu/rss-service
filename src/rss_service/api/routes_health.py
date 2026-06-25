from fastapi import APIRouter

from rss_service import __version__

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "rss-service"}


@router.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready", "service": "rss-service"}


@router.get("/version")
def version() -> dict[str, str]:
    return {"service": "rss-service", "version": __version__}
