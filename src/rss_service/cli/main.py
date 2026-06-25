import sqlite3
import subprocess
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import httpx
import typer
import uvicorn

from rss_service.backup import create_backup, restore_backup
from rss_service.db.connection import open_connection
from rss_service.db.migrations import run_migrations
from rss_service.db.repository import Repository
from rss_service.feeds.parser import parse_feed_bytes
from rss_service.feeds.service import FeedService, run_fetch_sync
from rss_service.logging import configure_logging
from rss_service.mcp.server import run_stdio_server
from rss_service.reports.generator import ReportGenerator
from rss_service.settings import get_settings

app = typer.Typer(no_args_is_help=True)
feeds_app = typer.Typer(no_args_is_help=True)
generate_app = typer.Typer(no_args_is_help=True)
reports_app = typer.Typer(no_args_is_help=True)
app.add_typer(feeds_app, name="feeds")
app.add_typer(generate_app, name="generate")
app.add_typer(reports_app, name="reports")


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


def _parse_at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _generate(report_type: str, at: str, force: bool) -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        report = ReportGenerator(Repository(connection), settings).generate(
            report_type=report_type,
            at=_parse_at(at),
            force=force,
        )
    typer.echo(
        f"{report['id']} {report['status']} "
        f"{report['item_count']} items -> {report['markdown_path']}"
    )


@generate_app.command("daily")
def generate_daily(
    at: Annotated[str, typer.Option("--at")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    _generate("daily", at, force)


@generate_app.command("weekly")
def generate_weekly(
    at: Annotated[str, typer.Option("--at")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    _generate("weekly", at, force)


@generate_app.command("monthly")
def generate_monthly(
    at: Annotated[str, typer.Option("--at")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    _generate("monthly", at, force)


@reports_app.command("list")
def reports_list() -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        reports = Repository(connection).list_reports()
    for report in reports:
        typer.echo(
            f"{report['id']}\t{report['report_type']}\t"
            f"{report['item_count']}\t{report['markdown_path']}"
        )


@reports_app.command("read")
def reports_read(report_id: str) -> None:
    settings = get_settings()
    with open_connection(settings.db_path) as connection:
        report = Repository(connection).get_report(report_id)
    if report is None:
        raise typer.Exit(code=1)
    markdown = Path(str(report["markdown_path"])).read_text(encoding="utf-8")
    typer.echo(markdown)


@app.command()
def backup(output: Annotated[Path, typer.Option("--output")]) -> None:
    settings = get_settings()
    path = create_backup(settings, output)
    typer.echo(f"backup written: {path}")


@app.command()
def restore(
    input_path: Annotated[Path, typer.Option("--input")],
    yes: Annotated[bool, typer.Option("--yes")] = False,
) -> None:
    if not yes:
        typer.echo("restore requires --yes")
        raise typer.Exit(code=1)
    restore_backup(get_settings(), input_path)
    typer.echo("restore completed")


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
def mcp() -> None:
    run_stdio_server()


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
