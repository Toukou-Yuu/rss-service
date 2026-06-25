CREATE TABLE IF NOT EXISTS external_items (
  id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL DEFAULT 'web_search',
  query TEXT,
  provider TEXT,
  title TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  summary TEXT NOT NULL,
  category TEXT NOT NULL,
  published_at TEXT,
  retrieved_at TEXT NOT NULL,
  dedupe_key TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  report_eligible INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_external_items_dedupe_key
ON external_items(dedupe_key);

CREATE INDEX IF NOT EXISTS idx_external_items_category
ON external_items(category);

CREATE INDEX IF NOT EXISTS idx_external_items_retrieved_at
ON external_items(retrieved_at DESC);
