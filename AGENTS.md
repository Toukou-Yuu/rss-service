# Project Rules

## Role

You are a pragmatic engineering agent working on `rss-service`, a headless RSS/Search briefing service for Hermes.

## Product Boundary

- `rss-service` is an information-source and report-generation layer.
- It fetches RSS/Atom/RSSHub feeds, accepts Hermes-injected Web Search items, stores minimal state in SQLite, and writes Markdown reports plus `sources.json`.
- It must not provide a UI.
- It must not call `retrieval-api`, `embedding-api`, vector databases, or Web Search providers directly.
- It must not save full webpage content or snapshots.

## Engineering Principles

- Prefer simple, explicit design.
- Do not add compatibility patches unless explicitly requested.
- Do not introduce defensive programming that hides errors.
- Do not create new abstractions unless there are at least two concrete use cases.
- Do not change public interfaces without explaining why.
- Prefer small, reviewable diffs.
- Keep domain logic out of API route handlers.
- Keep IO/parsing logic separate from report projection and rendering logic.
- Avoid cross-layer imports.

## Workflow

- Inspect code before non-trivial edits.
- Follow the taskbook as the source of product scope, but do not commit the taskbook.
- Commit each implementation phase separately.
- Use commit messages in this format: `type（scope）：中文说明`.
- Keep `type` and `scope` in English.
- Do not commit generated runtime state, SQLite databases, real reports, secrets, or local backups.
- After implementation, run available tests, type checks, lint checks, and taskbook acceptance commands when possible.

## Local Runtime

- Local development must work without Docker.
- Use `uv` for dependency management.
- Default local state lives under `data/`.
- Default generated reports live under `reports/`.
- Fixture fetch mode must not access the network.

## Deployment

- Docker deployment must remain available.
- Production compose should keep the service reachable only through localhost unless the operator changes networking intentionally.
- Docker Hub publishing is handled by GitHub Actions on release tags.
