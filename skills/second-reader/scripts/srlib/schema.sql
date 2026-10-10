-- second-reader ledger, schema version 1.
-- Invariants: actions is append-only; every record belongs to a document;
-- every finding has a primary evidence record (NOT NULL FK).

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE runs (
  run_id     INTEGER PRIMARY KEY,
  goal       TEXT,
  started_at TEXT NOT NULL,
  notes      TEXT
);

CREATE TABLE documents (
  doc_id        INTEGER PRIMARY KEY,
  sha256        TEXT NOT NULL UNIQUE,
  path          TEXT NOT NULL,
  mime          TEXT,
  doc_type      TEXT,            -- csv | xlsx | json | text | pdf ...
  goal_tag      TEXT,            -- rfq | quote | list | invoice ...
  size_bytes    INTEGER,
  ingest_status TEXT NOT NULL CHECK (ingest_status IN ('registered','ingested','failed')),
  mapping_json  TEXT,            -- {role: {"sheet":..,"col":..,"source":"auto-exact|auto-fuzzy|user"}}
  profile_json  TEXT,
  first_seen_at TEXT NOT NULL
);

CREATE TABLE actions (
  action_id   INTEGER PRIMARY KEY,
  run_id      INTEGER REFERENCES runs(run_id),
  ts          TEXT NOT NULL,
  role        TEXT NOT NULL CHECK (role IN ('code','haiku','sonnet','opus','human')),
  model       TEXT,
  tool        TEXT NOT NULL,
  tool_version TEXT,
  args_hash   TEXT,
  args_json   TEXT,
  input_refs  TEXT,
  output_refs TEXT,
  status      TEXT NOT NULL CHECK (status IN ('ok','error','cache_hit','rejected')),
  error       TEXT,
  duration_ms INTEGER,
  tokens_in   INTEGER,
  tokens_out  INTEGER,
  cache_key   TEXT,
  cache_hit   INTEGER NOT NULL DEFAULT 0
);
CREATE TRIGGER actions_no_update BEFORE UPDATE ON actions
BEGIN SELECT RAISE(ABORT, 'actions is append-only'); END;
CREATE TRIGGER actions_no_delete BEFORE DELETE ON actions
BEGIN SELECT RAISE(ABORT, 'actions is append-only'); END;

-- Parsed rows of tabular documents (source of truth stays the file; this is the working copy).
CREATE TABLE table_rows (
  doc_id INTEGER NOT NULL REFERENCES documents(doc_id),
  sheet  TEXT NOT NULL,
  row_no INTEGER NOT NULL,       -- 1-based row number in the source (header = first non-empty row)
  data   TEXT NOT NULL,          -- JSON array of cell values
  PRIMARY KEY (doc_id, sheet, row_no)
) WITHOUT ROWID;

CREATE TABLE records (
  record_id  INTEGER PRIMARY KEY,
  doc_id     INTEGER NOT NULL REFERENCES documents(doc_id),
  field      TEXT NOT NULL,
  raw_text   TEXT,               -- verbatim source text
  value_norm TEXT,               -- normalized value (Decimal/ISO date as text)
  unit       TEXT,
  currency   TEXT,
  locator    TEXT NOT NULL,      -- e.g. "Sheet1!R12C3" | "p2:bbox(x0,y0,x1,y1)" | "chars:120-148"
  extractor  TEXT NOT NULL,      -- tool or model that produced it
  confidence REAL,
  verified   INTEGER NOT NULL DEFAULT 0,
  action_id  INTEGER REFERENCES actions(action_id),
  UNIQUE (doc_id, locator, field, extractor)
);

CREATE TABLE findings (
  finding_id        INTEGER PRIMARY KEY,
  run_id            INTEGER NOT NULL REFERENCES runs(run_id),
  doc_id            INTEGER REFERENCES documents(doc_id),
  check_id          TEXT NOT NULL,
  check_version     TEXT NOT NULL,
  dedupe_key        TEXT NOT NULL,
  severity          TEXT NOT NULL CHECK (severity IN ('high','medium','low','info')),
  confidence        TEXT NOT NULL CHECK (confidence IN ('high','medium','low')),
  kind              TEXT NOT NULL CHECK (kind IN ('defect','concern')),
  claim             TEXT NOT NULL,
  count             INTEGER NOT NULL DEFAULT 1,
  impact_amount     TEXT,
  impact_currency   TEXT,
  detail_json       TEXT,
  primary_record_id INTEGER NOT NULL REFERENCES records(record_id),
  status            TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','confirmed','dismissed')),
  created_at        TEXT NOT NULL,
  UNIQUE (doc_id, check_id, dedupe_key)
);

CREATE TABLE finding_evidence (
  finding_id INTEGER NOT NULL REFERENCES findings(finding_id) ON DELETE CASCADE,
  record_id  INTEGER NOT NULL REFERENCES records(record_id),
  PRIMARY KEY (finding_id, record_id)
);

CREATE TABLE feedback (
  feedback_id INTEGER PRIMARY KEY,
  finding_id  INTEGER NOT NULL REFERENCES findings(finding_id),
  label       TEXT NOT NULL CHECK (label IN ('useful','noise','already-known')),
  note        TEXT,
  ts          TEXT NOT NULL
);

CREATE TABLE cache (
  cache_key  TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  created_at TEXT NOT NULL,
  hits       INTEGER NOT NULL DEFAULT 0
);
