from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rss_service import __version__
from rss_service.api.routes_entries import router as entries_router
from rss_service.api.routes_external import router as external_router
from rss_service.api.routes_feeds import router as feeds_router
from rss_service.api.routes_health import router as health_router
from rss_service.api.routes_reports import router as reports_router
from rss_service.errors import RssServiceError


def create_app() -> FastAPI:
    app = FastAPI(title="rss-service", version=__version__)

    @app.exception_handler(RssServiceError)
    def handle_service_error(_: Request, exc: RssServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": exc.__class__.__name__, "detail": str(exc)},
        )

    app.include_router(health_router)
    app.include_router(feeds_router)
    app.include_router(entries_router)
    app.include_router(external_router)
    app.include_router(reports_router)

    return app


app = create_app()
