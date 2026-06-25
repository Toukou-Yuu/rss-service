CREATE TABLE IF NOT EXISTS fetch_runs (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  feed_count INTEGER NOT NULL DEFAULT 0,
  success_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  new_entry_count INTEGER NOT NULL DEFAULT 0,
  log_json TEXT
);

CREATE TABLE IF NOT EXISTS feed_fetch_results (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES fetch_runs(id) ON DELETE CASCADE,
  feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  http_status INTEGER,
  elapsed_ms INTEGER,
  new_entry_count INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  checked_at TEXT NOT NULL
);
