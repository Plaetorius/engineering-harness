"""SQLite ledger: action log (append-only), document/record/finding store, cache."""
import contextlib
import hashlib
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 3
# Forward-only migrations applied after the v1 base schema (fresh DBs) or on open (older DBs), in one transaction.
MIGRATIONS = {
    2: """
CREATE TABLE doc_text (
  doc_id     INTEGER PRIMARY KEY REFERENCES documents(doc_id),
  text       TEXT NOT NULL,           -- canonical text; records.locator 'chars:S-E' indexes into this
  source_kind TEXT NOT NULL,          -- txt | eml | html
  meta_json  TEXT
);
ALTER TABLE records ADD COLUMN entity TEXT;        -- 'doc' or a line id such as 'L1'
ALTER TABLE records ADD COLUMN verify_note TEXT;   -- why a fact is unverified (or an advisory flag)
ALTER TABLE records ADD COLUMN pass_label TEXT;    -- extraction pass: A, B ...
""",
    3: """
CREATE TABLE doc_pages (
  doc_id     INTEGER NOT NULL REFERENCES documents(doc_id),
  page       INTEGER NOT NULL,
  char_start INTEGER NOT NULL,
  char_end   INTEGER NOT NULL,
  method     TEXT NOT NULL,          -- text | ocr
  mean_conf  REAL,                   -- mean OCR word confidence (ocr pages)
  PRIMARY KEY (doc_id, page)
);
CREATE TABLE ocr_words (
  doc_id     INTEGER NOT NULL REFERENCES documents(doc_id),
  page       INTEGER NOT NULL,
  char_start INTEGER NOT NULL,
  char_end   INTEGER NOT NULL,
  text       TEXT NOT NULL,
  conf       REAL NOT NULL,
  x INTEGER NOT NULL, y INTEGER NOT NULL, w INTEGER NOT NULL, h INTEGER NOT NULL
);
CREATE INDEX ocr_words_pos ON ocr_words(doc_id, char_start);
CREATE TABLE rfq_lines (
  rfq_line_id    INTEGER PRIMARY KEY,
  label          TEXT,
  part_number    TEXT NOT NULL,
  norm_part      TEXT NOT NULL,
  quantity       TEXT NOT NULL,
  need_by_days   INTEGER,            -- calendar days after the order date
  need_by_date   TEXT,
  bid_unit_price TEXT,               -- what we bid to our customer, per unit
  bid_currency   TEXT,
  src_doc_id     INTEGER REFERENCES documents(doc_id),
  created_at     TEXT NOT NULL
);
""",
}
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB = ".second-reader/ledger.db"
ROLES = ("code", "haiku", "sonnet", "opus", "human")


class LedgerError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_key(*parts):
    """Stable key from heterogeneous parts (doc sha, tool, tool version, params, model, prompt hash...)."""
    return sha256_text(canonical_json(list(parts)))


class Ledger:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("SR_DB") or DEFAULT_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    # ---- schema -------------------------------------------------------
    def _init_schema(self):
        # Single IMMEDIATE transaction so two processes initializing at once can't both create tables.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise LedgerError(f"ledger schema v{version} is newer than this tool (v{SCHEMA_VERSION})")
            if version == 0:
                for stmt in _split_sql(SCHEMA_PATH.read_text()):
                    self.db.execute(stmt)
                version = 1
            for target in range(version + 1, SCHEMA_VERSION + 1):
                for stmt in _split_sql(MIGRATIONS[target]):
                    self.db.execute(stmt)
            self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()

    # ---- offline mode: no AI reader may touch this ledger ----------------------------------------
    @property
    def offline(self):
        return os.environ.get("SR_OFFLINE", "").lower() in ("1", "true", "yes") or self._meta_get("mode") == "offline"

    def require_online(self, what):
        if self.offline:
            raise LedgerError(f"offline mode: {what} is disabled. This ledger never produces payloads for, or accepts "
                              f"data from, an AI reader. Use `sr extract local` (rule-based) instead.")

    def set_offline(self):
        """One-way: a ledger that has held AI-read data cannot be declared offline, and an offline ledger never goes back."""
        ai = self.db.execute("SELECT 1 FROM actions WHERE role IN ('haiku','sonnet','opus') LIMIT 1").fetchone()
        if ai:
            raise LedgerError("this ledger already contains AI-read data; start a new ledger for offline work")
        self._meta_set("mode", "offline")

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    # ---- meta / runs --------------------------------------------------
    def _meta_get(self, key):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def _meta_set(self, key, value):
        self.db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, str(value)))

    def start_run(self, goal=None, notes=None):
        with self.transaction():
            cur = self.db.execute("INSERT INTO runs(goal,started_at,notes) VALUES(?,?,?)", (goal, now(), notes))
            self._meta_set("active_run", cur.lastrowid)
        return cur.lastrowid

    def current_run(self, run_id=None):
        if run_id:
            if not self.db.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
                raise LedgerError(f"unknown run {run_id}")
            return int(run_id)
        active = self._meta_get("active_run")
        return int(active) if active else self.start_run(goal="(auto)")

    # ---- action log ---------------------------------------------------
    def log_action(self, run_id, tool, role="code", status="ok", model=None, tool_version=None, args=None,
                   input_refs=None, output_refs=None, error=None, duration_ms=None, tokens_in=None,
                   tokens_out=None, cache_key=None, cache_hit=False):
        if role not in ROLES:
            raise LedgerError(f"unknown role {role!r}")
        if role in ("haiku", "sonnet", "opus"):
            self.require_online(f"recording an action by the {role} model")
        args_json = canonical_json(args) if args is not None else None
        cur = self.db.execute(
            """INSERT INTO actions(run_id,ts,role,model,tool,tool_version,args_hash,args_json,input_refs,
               output_refs,status,error,duration_ms,tokens_in,tokens_out,cache_key,cache_hit)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, now(), role, model, tool, tool_version,
             sha256_text(args_json) if args_json else None, args_json,
             canonical_json(input_refs) if input_refs is not None else None,
             canonical_json(output_refs) if output_refs is not None else None,
             status, error, duration_ms, tokens_in, tokens_out, cache_key, int(bool(cache_hit))))
        return cur.lastrowid

    @contextlib.contextmanager
    def action(self, run_id, tool, tool_version=None, role="code", args=None, input_refs=None, **kw):
        """Logs one action row on exit (ok, or error with message). Yields a dict; set ['output_refs']."""
        state = {"output_refs": None, "status": "ok", "cache_key": None, "cache_hit": False, "action_id": None}
        t0 = time.monotonic()
        try:
            yield state
        except BaseException as exc:
            state["action_id"] = self.log_action(
                run_id, tool, role=role, status="rejected" if state["status"] == "rejected" else "error",
                tool_version=tool_version, args=args,
                input_refs=input_refs, error=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - t0) * 1000), **kw)
            raise
        state["action_id"] = self.log_action(
            run_id, tool, role=role, status=state["status"], tool_version=tool_version, args=args,
            input_refs=input_refs, output_refs=state["output_refs"], cache_key=state["cache_key"],
            cache_hit=state["cache_hit"], duration_ms=int((time.monotonic() - t0) * 1000), **kw)

    # ---- cache --------------------------------------------------------
    def cache_get(self, key):
        row = self.db.execute("SELECT value FROM cache WHERE cache_key=?", (key,)).fetchone()
        if row is None:
            return None
        self.db.execute("UPDATE cache SET hits=hits+1 WHERE cache_key=?", (key,))
        return json.loads(row["value"])

    def cache_peek(self, key):
        """Read without counting a hit."""
        row = self.db.execute("SELECT value FROM cache WHERE cache_key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else None

    def cache_put(self, key, value):
        self.db.execute(
            "INSERT INTO cache(cache_key,value,created_at) VALUES(?,?,?) "
            "ON CONFLICT(cache_key) DO UPDATE SET value=excluded.value, created_at=excluded.created_at",
            (key, canonical_json(value), now()))

    # ---- documents / records / findings -------------------------------
    def register_document(self, path, doc_type, goal_tag=None, mime=None):
        path = Path(path)
        sha = sha256_file(path)
        row = self.db.execute("SELECT doc_id FROM documents WHERE sha256=?", (sha,)).fetchone()
        if row:
            return row["doc_id"], sha, False
        cur = self.db.execute(
            "INSERT INTO documents(sha256,path,mime,doc_type,goal_tag,size_bytes,ingest_status,first_seen_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (sha, str(path.resolve()), mime, doc_type, goal_tag, path.stat().st_size, "registered", now()))
        return cur.lastrowid, sha, True

    def get_document(self, ref):
        """ref: doc_id (digits), sha256 prefix (>=6 hex chars) or file path. Ambiguity is an error, never a guess."""
        ref = str(ref)
        if ref.isdigit():
            rows = self.db.execute("SELECT * FROM documents WHERE doc_id=?", (int(ref),)).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM documents WHERE path=?", (str(Path(ref).resolve()),)).fetchall()
            if not rows and re.fullmatch(r"[0-9a-f]{6,64}", ref.lower()):
                rows = self.db.execute("SELECT * FROM documents WHERE substr(sha256,1,?)=?",
                                       (len(ref), ref.lower())).fetchall()
        if not rows:
            raise LedgerError(f"unknown document {ref!r}")
        if len(rows) > 1:
            raise LedgerError(f"{ref!r} matches {len(rows)} documents; use the numeric doc id")
        return rows[0]

    def upsert_record(self, doc_id, field, locator, raw_text, extractor, value_norm=None, unit=None,
                      currency=None, confidence=None, verified=False, action_id=None, entity=None,
                      verify_note=None, pass_label=None):
        self.db.execute(
            """INSERT INTO records(doc_id,field,raw_text,value_norm,unit,currency,locator,extractor,confidence,
               verified,action_id,entity,verify_note,pass_label) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(doc_id,locator,field,extractor) DO UPDATE SET raw_text=excluded.raw_text,
               value_norm=excluded.value_norm, unit=excluded.unit, currency=excluded.currency,
               confidence=excluded.confidence, verified=excluded.verified, action_id=excluded.action_id,
               entity=excluded.entity, verify_note=excluded.verify_note, pass_label=excluded.pass_label""",
            (doc_id, field, raw_text, value_norm, unit, currency, locator, extractor, confidence,
             int(bool(verified)), action_id, entity, verify_note, pass_label))
        return self.db.execute(
            "SELECT record_id FROM records WHERE doc_id=? AND locator=? AND field=? AND extractor=?",
            (doc_id, locator, field, extractor)).fetchone()["record_id"]

    def upsert_finding(self, run_id, doc_id, check_id, check_version, dedupe_key, severity, confidence, kind,
                       claim, evidence_record_ids, count=1, impact_amount=None, impact_currency=None, detail=None):
        """Idempotent per (doc, check, dedupe_key): refreshes content, keeps human status and feedback."""
        if not evidence_record_ids:
            raise LedgerError("a finding needs at least one evidence record")
        ids = list(dict.fromkeys(evidence_record_ids))
        existing = self.db.execute("SELECT finding_id FROM findings WHERE doc_id IS ? AND check_id=? AND dedupe_key=?",
                                   (doc_id, check_id, dedupe_key)).fetchone()
        vals = (run_id, check_version, severity, confidence, kind, claim, count,
                None if impact_amount is None else str(impact_amount), impact_currency,
                canonical_json(detail) if detail is not None else None, ids[0])
        if existing:
            fid = existing["finding_id"]
            self.db.execute(
                """UPDATE findings SET run_id=?,check_version=?,severity=?,confidence=?,kind=?,claim=?,count=?,
                   impact_amount=?,impact_currency=?,detail_json=?,primary_record_id=? WHERE finding_id=?""",
                vals + (fid,))
            self.db.execute("DELETE FROM finding_evidence WHERE finding_id=?", (fid,))
        else:
            cur = self.db.execute(
                """INSERT INTO findings(run_id,check_version,severity,confidence,kind,claim,count,impact_amount,
                   impact_currency,detail_json,primary_record_id,doc_id,check_id,dedupe_key,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                vals + (doc_id, check_id, dedupe_key, now()))
            fid = cur.lastrowid
        self.db.executemany("INSERT INTO finding_evidence(finding_id,record_id) VALUES(?,?)",
                            [(fid, r) for r in ids])
        return fid

    def set_finding_status(self, finding_id, status):
        cur = self.db.execute("UPDATE findings SET status=? WHERE finding_id=?", (status, finding_id))
        if cur.rowcount == 0:
            raise LedgerError(f"unknown finding {finding_id}")

    def add_feedback(self, finding_id, label, note=None):
        if not self.db.execute("SELECT 1 FROM findings WHERE finding_id=?", (finding_id,)).fetchone():
            raise LedgerError(f"unknown finding {finding_id}")
        self.db.execute("INSERT INTO feedback(finding_id,label,note,ts) VALUES(?,?,?,?)",
                        (finding_id, label, note, now()))

    # ---- integrity ----------------------------------------------------
    def verify(self):
        """Returns a list of problems (empty = healthy)."""
        problems = []
        if self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            problems.append("sqlite integrity_check failed")
        for row in self.db.execute("PRAGMA foreign_key_check").fetchall():
            problems.append(f"foreign key violation in {row[0]} rowid {row[1]}")
        for trig in ("actions_no_update", "actions_no_delete"):
            if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?", (trig,)).fetchone():
                problems.append(f"missing trigger {trig}")
        for row in self.db.execute(
                """SELECT f.finding_id FROM findings f LEFT JOIN finding_evidence e
                   ON e.finding_id=f.finding_id AND e.record_id=f.primary_record_id WHERE e.finding_id IS NULL"""):
            problems.append(f"finding {row[0]} lacks its primary evidence link")
        return problems


def _strip_comment(line):
    """Cut a trailing `-- comment`, ignoring `--` inside single-quoted literals."""
    quoted = False
    for i, ch in enumerate(line):
        if ch == "'":
            quoted = not quoted
        elif ch == "-" and not quoted and line[i:i + 2] == "--":
            return line[:i].rstrip()
    return line


def _split_sql(script):
    """Split a script into statements, keeping CREATE TRIGGER ... END; bodies intact."""
    statements, buf, in_trigger = [], [], False
    for line in script.splitlines():
        line = _strip_comment(line)
        stripped = line.strip()
        if not stripped:
            continue
        buf.append(line)
        if stripped.upper().startswith("CREATE TRIGGER"):
            in_trigger = True
        if (in_trigger and stripped.upper().rstrip(";").endswith("END")) or (not in_trigger and stripped.endswith(";")):
            statements.append("\n".join(buf))
            buf, in_trigger = [], False
    if buf:
        statements.append("\n".join(buf))
    return statements
