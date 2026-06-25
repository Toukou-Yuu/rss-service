import subprocess

import typer
import uvicorn

from rss_service.db.connection import open_connection
from rss_service.db.migrations import run_migrations
from rss_service.logging import configure_logging
from rss_service.settings import get_settings

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


@app.command("init-db")
def init_db() -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        applied = run_migrations(connection)
    typer.echo(f"database initialized: {settings.db_path}")
    if applied:
        typer.echo("applied migrations: " + ", ".join(applied))


@app.command()
def serve(
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
) -> None:
    settings = get_settings()
    uvicorn.run(
        "rss_service.app:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=False,
    )


@app.command()
def healthcheck() -> None:
    settings = get_settings()
    subprocess.run(
        [
            "python",
            "-c",
            (
                "import urllib.request; "
                f"urllib.request.urlopen('http://127.0.0.1:{settings.port}/healthz', timeout=3)"
            ),
        ],
        check=True,
    )
