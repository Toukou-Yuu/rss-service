from fastapi import FastAPI

from rss_service import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="rss-service", version=__version__)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "rss-service"}

    @app.get("/readyz", tags=["health"])
    def readyz() -> dict[str, str]:
        return {"status": "ready", "service": "rss-service"}

    @app.get("/version", tags=["health"])
    def version() -> dict[str, str]:
        return {"service": "rss-service", "version": __version__}

    return app


app = create_app()
