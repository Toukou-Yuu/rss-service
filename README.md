# rss-service

`rss-service` is a headless, Markdown-first RSS/Search briefing service for Hermes.

It fetches RSS/Atom/RSSHub feeds, accepts Hermes-injected Web Search items, keeps minimal
runtime state in SQLite, and generates daily, weekly, and monthly Markdown reports with a
matching `sources.json` index.

## What It Is Not

- Not an RSS reader UI.
- Not a knowledge base.
- Not a RAG ingestion service.
- Not a vector database writer.
- Not a Web Search client.
- Not an LLM summarizer.

## Architecture

```text
RSS / Atom / RSSHub
        │
        ▼
rss-service
  ├── fetch and parse feeds
  ├── accept Hermes Web Search results
  ├── dedupe and normalize entries
  ├── persist minimal SQLite state
  ├── write Markdown reports
  ├── write sources.json
  ├── expose REST API
  └── expose MCP tool functions
        │
        ▼
Hermes
  ├── reads reports
  ├── talks to the user
  ├── decides follow-up research
  └── decides retrieval-api ingestion
```

`rss-service` does not import or call `retrieval-api`, `embedding-api`, Web Search providers,
RAG schemas, or vector databases.

## Local Development

Local development does not require Docker.

```bash
uv sync
uv run rss-service init-db
uv run rss-service feeds import --file config/feeds.example.yaml
uv run rss-service fetch --fixture fixtures/feeds
uv run rss-service generate daily --at "2026-06-24T10:00:00+08:00"
uv run rss-service serve --host 127.0.0.1 --port 8787
```

Default local paths:

- SQLite: `data/rss.sqlite3`
- Reports: `reports/`
- Config: `config/`

Runtime state, generated reports, secrets, and backups are ignored by Git.

## Configuration

Copy `.env.example` to `.env` for local overrides.

Important variables:

- `RSS_SERVICE_API_TOKEN`: Bearer token for non-health API calls.
- `RSS_DB_PATH`: SQLite database path.
- `RSS_REPORTS_DIR`: output directory for Markdown and `sources.json`.
- `RSS_CONFIG_DIR`: config directory.
- `RSS_TIMEZONE`: report period timezone.
- `RSS_FETCH_CONCURRENCY`: global fetch concurrency.
- `RSS_PER_DOMAIN_CONCURRENCY`: per-domain fetch concurrency.

YAML config files:

- `config/feeds.example.yaml`: seed feed list.
- `config/categories.yaml`: category metadata and report limits.
- `config/report_profiles.yaml`: report profiles.
- `config/schedules.yaml`: schedule hints for Hermes.

Runtime feed state is stored in SQLite. Use import/export commands for backup and bootstrap:

```bash
uv run rss-service feeds import --file config/feeds.example.yaml
uv run rss-service feeds export --file feeds.backup.yaml
```

## Feed Management

```bash
uv run rss-service feeds list
uv run rss-service feeds add --name "OpenAI" --url "https://openai.com/news/rss.xml" --category ai_agent
uv run rss-service feeds remove --id 1
uv run rss-service feeds test --url "https://example.com/rss.xml"
```

Fixture fetch mode is offline:

```bash
uv run rss-service fetch --fixture fixtures/feeds
```

Real fetch mode uses `httpx`, ETag/Last-Modified, redirect following, retry for transient
HTTP failures, and per-domain concurrency limits.

## RSSHub

RSSHub routes are ordinary feed URLs. `rss-service` does not hard-code RSSHub as a runtime
dependency.

Example feed:

```yaml
feeds:
  - name: "RSSHub Example Route"
    url: "http://rsshub:1200/example/route"
    category: "dev_ecosystem"
    source_type: "rsshub"
    enabled: true
    priority: 50
```

In Docker, RSSHub is optional:

```bash
docker compose --profile rsshub up -d
```

## Web Search Injection

Hermes calls Web Search tools itself, then injects selected results:

```bash
curl -X POST http://127.0.0.1:8787/external-items \
  -H "Authorization: Bearer $RSS_SERVICE_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data @fixtures/external_search_items.json
```

`rss-service` stores the injected item metadata and can include those items in reports. It does
not call Web Search providers directly.

## Reports

```bash
uv run rss-service generate daily --at "2026-06-24T10:00:00+08:00"
uv run rss-service generate weekly --at "2026-06-29T10:00:00+08:00"
uv run rss-service generate monthly --at "2026-07-01T10:00:00+08:00"
uv run rss-service reports list
uv run rss-service reports read daily-2026-06-24
```

Output paths:

```text
reports/daily/YYYY-MM-DD.md
reports/daily/YYYY-MM-DD.sources.json
reports/weekly/YYYY-Www.md
reports/weekly/YYYY-Www.sources.json
reports/monthly/YYYY-MM.md
reports/monthly/YYYY-MM.sources.json
```

Reports include:

- YAML frontmatter.
- `knowledge_base_write: false`.
- category sections.
- source links and source type.
- pointer to the matching `sources.json`.

## REST API

Only `/healthz` is public. Other endpoints require:

```http
Authorization: Bearer <RSS_SERVICE_API_TOKEN>
```

Health:

- `GET /healthz`
- `GET /readyz`
- `GET /version`

Feeds and fetch:

- `GET /feeds`
- `POST /feeds`
- `GET /feeds/{feed_id}`
- `PATCH /feeds/{feed_id}`
- `DELETE /feeds/{feed_id}`
- `POST /feeds/test`
- `POST /feeds/import`
- `GET /feeds/export`
- `POST /fetch`
- `GET /fetch-runs`
- `GET /fetch-runs/{run_id}`

Entries and external items:

- `GET /entries`
- `GET /entries/{entry_id}`
- `POST /external-items`
- `GET /external-items`
- `DELETE /external-items/{item_id}`

Reports:

- `POST /reports/generate`
- `GET /reports`
- `GET /reports/{report_id}`
- `GET /reports/{report_id}/markdown`
- `GET /reports/{report_id}/sources`
- `DELETE /reports/{report_id}`

## MCP Tools

`rss-service` exposes native MCP tools backed by the same service layer as the REST API.

Local stdio development:

```bash
uv run rss-service mcp
```

Production HTTP / Streamable HTTP:

```bash
uv run rss-service mcp-http --host 127.0.0.1 --port 8788 --path /mcp
```

See [docs/mcp.md](docs/mcp.md) for Hermes configuration, response envelope, permissions, and tests.

Tool names:

- `rss_list_feeds`
- `rss_add_feed`
- `rss_remove_feed`
- `rss_test_feed`
- `rss_fetch`
- `rss_inject_search_items`
- `rss_generate_report`
- `rss_list_reports`
- `rss_read_report`
- `rss_get_report_sources`

MCP tools call the same service layer used by REST and CLI. They return a stable `{ok, summary, data, warnings}` envelope for Agent consumption.

## Docker Deployment

Create `.env.prod` with at least:

```env
RSS_SERVICE_API_TOKEN=change-me-to-a-real-token
```

Run:

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

The service binds to `127.0.0.1:8787` on the host by default. Put Tailscale, ZeroTier,
reverse proxy rules, or host firewall policy outside this service.

## Watchtower

For automatic updates, point Watchtower at the same Docker host and image tag:

```yaml
environment:
  WATCHTOWER_POLL_INTERVAL: 300
  WATCHTOWER_CLEANUP: "true"
```

Pushes to `main` publish Docker Hub images through GitHub Actions when
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository secrets are configured.
Release tags `v*.*.*` also publish the matching version tag.

## Backup And Restore

Backups include a SQLite online backup, reports, and config.

```bash
uv run rss-service backup --output backups/rss-service-$(date +%Y%m%d).tar.gz
uv run rss-service restore --input backups/rss-service-YYYYMMDD.tar.gz --yes
```

Restore replaces the configured database, reports directory, and config directory.

## Tests And Checks

```bash
uv run ruff check .
uv run mypy src
uv run pytest
docker build -t rss-service:local .
docker compose -f docker-compose.prod.yml config
uv run pytest tests/mcp -q
```

Tests use fixtures and do not require Docker or public network access.

## Hermes Boundary

Hermes owns orchestration:

1. Trigger feed fetch.
2. Call Web Search MCP when needed.
3. Inject search results into `rss-service`.
4. Generate reports.
5. Read reports and talk to the user.
6. Decide whether any item should be sent to `retrieval-api`.

`rss-service` remains intentionally narrow:

```text
rss-service = information source and report layer
Hermes = orchestration and user-facing decision layer
retrieval-api = ingestion and retrieval layer
embedding-api = vectorization layer
```
