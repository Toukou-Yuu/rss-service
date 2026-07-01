# rss-service MCP Tools

`rss-service` exposes native MCP tools for Alice/Hermes. MCP is an Agent-facing adapter over the same service layer used by the REST API and CLI.

## Transports

### stdio, local development

```bash
uv run rss-service mcp
```

### HTTP / Streamable HTTP, production

```bash
uv run rss-service mcp-http --host 127.0.0.1 --port 8788 --path /mcp
```

Docker deployments should normally run REST and MCP as separate containers from the same image:

```text
rss-service       -> REST API on 127.0.0.1:8787
rss-service-mcp   -> MCP HTTP on 127.0.0.1:8788/mcp
```

## Hermes configuration

Store secrets in `/opt/data/.env` and reference them from `/opt/data/config.yaml` when authentication is enabled. For localhost-only development, no header is required.

```yaml
mcp_servers:
  rss:
    url: http://127.0.0.1:8788/mcp
    timeout: 120
    connect_timeout: 60
```

Verify after deployment:

```bash
hermes mcp list
hermes mcp test rss
```

Current Hermes sessions may need `/reload-mcp`, `/new`, or a process restart before new tools appear.

## Tool inventory

| Tool | Permission | Side effect |
| --- | --- | --- |
| `rss_list_feeds` | read | none |
| `rss_add_feed` | write | creates a feed row |
| `rss_remove_feed` | write | deletes a feed row |
| `rss_test_feed` | read | network fetch only; does not save |
| `rss_fetch` | write | stores fetch run and new entries |
| `rss_inject_search_items` | write | stores Hermes-provided search result items |
| `rss_generate_report` | write | writes Markdown report, sources JSON, and report metadata |
| `rss_list_reports` | read | none |
| `rss_read_report` | read | reads report Markdown and optional sources |
| `rss_get_report_sources` | read | reads report sources JSON |

## Response envelope

All tools return a stable envelope:

```json
{
  "ok": true,
  "summary": "Found 3 reports.",
  "data": {},
  "warnings": []
}
```

Errors use:

```json
{
  "ok": false,
  "error": {
    "code": "REPORT_NOT_FOUND",
    "message": "Report not found: daily-2026-06-30",
    "retryable": false,
    "suggested_action": "Call rss_list_reports first, then retry with an existing report_id."
  }
}
```

## Tests

```bash
uv run pytest tests/mcp -q
uv run pytest -q
uv run ruff check .
uv run mypy src
```
