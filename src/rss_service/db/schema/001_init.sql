CREATE TABLE IF NOT EXISTS feeds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'rss',
  enabled INTEGER NOT NULL DEFAULT 1,
  priority INTEGER NOT NULL DEFAULT 50,
  etag TEXT,
  last_modified TEXT,
  last_checked_at TEXT,
  last_success_at TEXT,
  last_error TEXT,
  error_count INTEGER NOT NULL DEFAULT 0,
  fetch_interval_minutes INTEGER NOT NULL DEFAULT 60,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entries (
  id TEXT PRIMARY KEY,
  feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
  source_guid TEXT,
  canonical_url TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  published_at TEXT,
  updated_at TEXT,
  fetched_at TEXT NOT NULL,
  dedupe_key TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  category TEXT NOT NULL,
  report_eligible INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_feed_guid
ON entries(feed_id, source_guid)
WHERE source_guid IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_dedupe_key
ON entries(dedupe_key);

CREATE INDEX IF NOT EXISTS idx_entries_published_at
ON entries(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_entries_category
ON entries(category);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  report_type TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  markdown_path TEXT NOT NULL,
  sources_json_path TEXT NOT NULL,
  source_count INTEGER NOT NULL DEFAULT 0,
  item_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'completed',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_items (
  report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
  item_id TEXT NOT NULL,
  item_source TEXT NOT NULL,
  section_name TEXT NOT NULL,
  rank_in_section INTEGER NOT NULL,
  PRIMARY KEY (report_id, item_id, item_source)
);

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);
