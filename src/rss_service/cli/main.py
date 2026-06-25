import sqlite3
import subprocess
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Annotated

import httpx
import typer
import uvicorn

from rss_service.db.connection import open_connection
from rss_service.db.migrations import run_migrations
from rss_service.db.repository import Repository
from rss_service.feeds.parser import parse_feed_bytes
from rss_service.feeds.service import FeedService, run_fetch_sync
from rss_service.logging import configure_logging
from rss_service.settings import get_settings

app = typer.Typer(no_args_is_help=True)
feeds_app = typer.Typer(no_args_is_help=True)
app.add_typer(feeds_app, name="feeds")


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


def _repository() -> tuple[Repository, AbstractContextManager[sqlite3.Connection]]:
    settings = get_settings()
    connection_cm = open_connection(settings.db_path)
    connection = connection_cm.__enter__()
    return Repository(connection), connection_cm


@feeds_app.command("list")
def feeds_list() -> None:
    repository, connection_cm = _repository()
    try:
        for feed in repository.list_feeds():
            enabled = "enabled" if feed["enabled"] else "disabled"
            typer.echo(
                f"{feed['id']}\t{enabled}\t{feed['category']}\t"
                f"{feed['priority']}\t{feed['name']}\t{feed['url']}"
            )
    finally:
        connection_cm.__exit__(None, None, None)


@feeds_app.command("add")
def feeds_add(
    name: Annotated[str, typer.Option("--name")],
    url: Annotated[str, typer.Option("--url")],
    category: Annotated[str, typer.Option("--category")],
    source_type: Annotated[str, typer.Option("--source-type")] = "rss",
    priority: Annotated[int, typer.Option("--priority")] = 50,
    disabled: Annotated[bool, typer.Option("--disabled")] = False,
) -> None:
    repository, connection_cm = _repository()
    try:
        feed = repository.create_feed(
            name=name,
            url=url,
            category=category,
            source_type=source_type,
            enabled=not disabled,
            priority=priority,
        )
        repository.connection.commit()
        typer.echo(f"feed saved: {feed['id']} {feed['name']}")
    finally:
        connection_cm.__exit__(None, None, None)


@feeds_app.command("remove")
def feeds_remove(feed_id: Annotated[int, typer.Option("--id")]) -> None:
    repository, connection_cm = _repository()
    try:
        deleted = repository.delete_feed(feed_id)
        repository.connection.commit()
        if not deleted:
            raise typer.Exit(code=1)
        typer.echo(f"feed removed: {feed_id}")
    finally:
        connection_cm.__exit__(None, None, None)


@feeds_app.command("import")
def feeds_import(file: Annotated[Path, typer.Option("--file")]) -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        service = FeedService(Repository(connection), settings)
        feeds = service.import_feeds(file)
    typer.echo(f"imported feeds: {len(feeds)}")


@feeds_app.command("export")
def feeds_export(file: Annotated[Path, typer.Option("--file")]) -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        service = FeedService(Repository(connection), settings)
        service.export_feeds(file)
    typer.echo(f"exported feeds: {file}")


@feeds_app.command("test")
def feeds_test(url: Annotated[str, typer.Option("--url")]) -> None:
    settings = get_settings()
    response = httpx.get(
        url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.fetch_timeout_seconds,
        follow_redirects=True,
    )
    parsed = parse_feed_bytes(response.content, summary_max_length=settings.summary_max_length)
    typer.echo("ok: true")
    typer.echo(f"feed_title: {parsed.title or ''}")
    typer.echo(f"entry_count: {len(parsed.entries)}")
    for entry in parsed.entries[:3]:
        typer.echo(f"- {entry.title} {entry.url}")
    for warning in parsed.warnings:
        typer.echo(f"warning: {warning}")


@app.command("fetch")
def fetch(
    fixture: Annotated[Path | None, typer.Option("--fixture")] = None,
    category: Annotated[list[str] | None, typer.Option("--category")] = None,
    feed_id: Annotated[list[int] | None, typer.Option("--feed-id")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        run = run_fetch_sync(
            Repository(connection),
            settings,
            feed_ids=feed_id,
            categories=category,
            force=force,
            fixture_dir=fixture,
        )
    typer.echo(
        f"fetch run {run['id']} {run['status']}: "
        f"{run['new_entry_count']} new entries, {run['error_count']} errors"
    )


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
