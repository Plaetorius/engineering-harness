"""Orchestration: ingest, map, run checks (cached, logged), materialize findings with evidence records."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from . import checks as chk
from . import ingest as ing
from . import textdoc
from .ledger import LedgerError, cache_key, canonical_json
from .numparse import parse_date, parse_number

TOOL_VERSION = "0.1.0"
CONF_RANK = {"low": 0, "medium": 1, "high": 2}


def _load_doc(led, ref):
    doc = led.get_document(ref)
    profile = json.loads(doc["profile_json"]) if doc["profile_json"] else None
    mapping = json.loads(doc["mapping_json"]) if doc["mapping_json"] else {}
    return doc, profile, mapping


def _save_profile(led, doc_id, profile):
    led.db.execute("UPDATE documents SET profile_json=? WHERE doc_id=?", (canonical_json(profile), doc_id))


# ---- ingest ----------------------------------------------------------------------------------
def ingest_document(led, run_id, path, goal_tag=None, use_cache=True):
    path = Path(path)
    args = {"path": str(path), "goal_tag": goal_tag}
    with led.action(run_id, "ingest", TOOL_VERSION, args=args) as act:
        if not path.is_file():
            raise LedgerError(f"no such file: {path}")
        if path.suffix.lower() in textdoc.TEXT_SUFFIXES:
            return _ingest_text(led, run_id, path, goal_tag, use_cache, act)
        doc_type = ing.detect_type(path)
        if doc_type is None:
            raise LedgerError(f"{path.suffix or 'this'} files are not handled by the tabular path yet "
                              f"(supported: csv, tsv, xlsx, json)")
        doc_id, sha, created = led.register_document(path, doc_type, goal_tag)
        key = cache_key(sha, "ingest", ing.INGEST_VERSION)
        doc = led.get_document(doc_id)
        act["cache_key"] = key
        if use_cache and doc["ingest_status"] == "ingested" and led.cache_get(key) is not None:
            act["cache_hit"], act["status"] = True, "cache_hit"
        else:
            with led.transaction():
                headers = ing.ingest_rows(led.db, doc_id, path, doc_type)
                if not headers:
                    raise LedgerError("no tabular data found")
                profile = {"sheets": {}, "coverage": {}}
                for sheet, h in headers.items():
                    p = ing.profile_sheet(led.db, doc_id, sheet, h["columns"])
                    profile["sheets"][sheet] = {"header_row": h["header_row"], "data_rows": h["data_rows"],
                                                "columns": p["columns"], "preamble": h["preamble"]}
                suggested, notes = ing.suggest_mapping(profile["sheets"])
                profile["mapping_notes"] = notes
                _save_profile(led, doc_id, profile)
                if not doc["mapping_json"]:
                    led.db.execute("UPDATE documents SET mapping_json=? WHERE doc_id=?",
                                   (canonical_json(suggested), doc_id))
                led.db.execute("UPDATE documents SET ingest_status='ingested', goal_tag=COALESCE(?,goal_tag) "
                               "WHERE doc_id=?", (goal_tag, doc_id))
                led.cache_put(key, {"sheets": {s: h["data_rows"] for s, h in headers.items()}})
        act["output_refs"] = {"doc_id": doc_id, "sha256": sha}
    return led.get_document(doc_id)


def _ingest_text(led, run_id, path, goal_tag, use_cache, act):
    doc_id, sha, _ = led.register_document(path, "text", goal_tag)
    from . import pdfdoc
    key = cache_key(sha, "text-ingest", textdoc.TEXT_VERSION, pdfdoc.PDF_VERSION if path.suffix.lower() == ".pdf" else None)
    doc = led.get_document(doc_id)
    act["cache_key"] = key
    if use_cache and doc["ingest_status"] == "ingested" and led.cache_get(key) is not None:
        act["cache_hit"], act["status"] = True, "cache_hit"
    else:
        from . import pdfdoc
        try:
            built = textdoc.build(path)
        except pdfdoc.PdfError as exc:                       # a corrupt PDF or a missing tool is a clean error, not a traceback
            raise LedgerError(f"{path.name}: {exc}") from exc
        with led.transaction():
            led.db.execute("INSERT OR REPLACE INTO doc_text(doc_id,text,source_kind,meta_json) VALUES(?,?,?,?)",
                           (doc_id, built["text"], built["kind"], canonical_json(built["meta"])))
            led.db.execute("DELETE FROM doc_pages WHERE doc_id=?", (doc_id,))
            led.db.execute("DELETE FROM ocr_words WHERE doc_id=?", (doc_id,))
            if built.get("pdf"):
                led.db.executemany("INSERT INTO doc_pages VALUES(?,?,?,?,?,?)",
                                   [(doc_id, p["page"], p["char_start"], p["char_end"], p["method"], p["mean_conf"])
                                    for p in built["pdf"]["pages"]])
                led.db.executemany("INSERT INTO ocr_words VALUES(?,?,?,?,?,?,?,?,?,?)",
                                   [(doc_id,) + w for w in built["pdf"]["words"]])
            profile = {"kind": "text", "chars": len(built["text"]), "source_kind": built["kind"],
                       "meta": built["meta"], "sheets": {}, "coverage": {}}
            if built.get("pdf"):
                profile["pages"] = built["pdf"]["pages"]
            led.db.execute("UPDATE documents SET ingest_status='ingested', mapping_json='{}', profile_json=?, "
                           "goal_tag=COALESCE(?,goal_tag) WHERE doc_id=?", (canonical_json(profile), goal_tag, doc_id))
            _scan_findings(led, run_id, doc_id, built)
            led.cache_put(key, {"chars": len(built["text"]), "hits": len(built["hits"])})
    act["output_refs"] = {"doc_id": doc_id, "sha256": sha, "kind": "text"}
    return led.get_document(doc_id)


def pdfdoc_version():
    from . import pdfdoc
    return pdfdoc.PDF_VERSION


def _scan_findings(led, run_id, doc_id, built):
    text = built["text"]
    labels = {
        "ignore_instructions": "tells a reader to ignore / override its instructions",
        "addresses_ai": "addresses an AI system or assigns it a role",
        "system_prompt": "refers to a system prompt or hidden instructions",
        "fake_role_tag": "contains a fake system/assistant role marker",
        "exfiltration": "asks for secrets or credentials to be revealed or sent",
        "decision_steering": "tries to steer which quote/supplier is picked",
        "secrecy": "asks that the user / reviewer not be told",
        "invisible_characters": "contains invisible zero-width characters",
    }
    live = set()
    for label, start, end in built["hits"]:
        rec = led.upsert_record(doc_id, "injection", f"chars:{start}-{end}", text[start:end][:200], "sr.scan",
                                verified=True, verify_note=label)
        live.add(label)
        led.upsert_finding(run_id, doc_id, "inject.suspicious_text", textdoc.TEXT_VERSION, label, "high", "medium",
                           "concern", f"Text that {labels.get(label, label)}; it is treated as data and never followed. "
                           f"Read it in the source before trusting this document's content.", [rec])
    if built["hidden_text"]:
        rec = led.upsert_record(doc_id, "hidden_text", "hidden:html", built["hidden_text"][:200], "sr.scan",
                                verified=True, verify_note="html_hidden")
        live.add("html_hidden")
        hostile = bool(built.get("hidden_hits"))
        led.upsert_finding(run_id, doc_id, "inject.hidden_text", textdoc.TEXT_VERSION, "html_hidden",
                           "high" if hostile else "low", "high" if hostile else "medium", "concern",
                           f"{len(built['hidden_text'])} characters of text are hidden in the HTML (display:none, zero size "
                           f"or white text); a human reader would not see it but an automated one might. "
                           + ("The hidden text itself contains instruction-like wording." if hostile else
                              "It reads like ordinary hidden markup (e.g. a preheader), but it was excluded from the text."),
                           [rec], count=len(built["hidden_text"]))
    for pg in (built.get("pdf") or {}).get("pages", []):
        if pg["method"] == "ocr_unreadable":
            rec = led.upsert_record(doc_id, "ocr_page", f"page:{pg['page']}", f"mean OCR confidence {pg['mean_conf']}%",
                                    "sr.scan", verified=True, verify_note="ocr_unreadable")
            live.add(f"unreadable:{pg['page']}")
            led.upsert_finding(run_id, doc_id, "ocr.unreadable_page", pdfdoc_version(), f"unreadable:{pg['page']}", "high",
                               "high", "defect", f"Page {pg['page']} could not be read by OCR (mean word confidence "
                               f"{pg['mean_conf']}%); it was left out. Nothing on it has been checked: read it by eye or "
                               f"rescan it.", [rec])
    for row in led.db.execute("SELECT finding_id, check_id, dedupe_key FROM findings WHERE doc_id=? AND "
                              "check_id IN ('inject.suspicious_text','inject.hidden_text','ocr.unreadable_page') AND status='open'",
                              (doc_id,)).fetchall():
        if row["dedupe_key"] not in live:
            led.db.execute("DELETE FROM findings WHERE finding_id=?", (row["finding_id"],))


def set_mapping(led, run_id, ref, sets=(), unsets=()):
    doc, profile, mapping = _load_doc(led, ref)
    if profile is None:
        raise LedgerError("document not ingested")
    with led.action(run_id, "map", TOOL_VERSION, args={"set": list(sets), "unset": list(unsets)},
                    input_refs={"doc_id": doc["doc_id"]}, role="human") as act:
        for role in unsets:
            mapping.pop(role, None)
        for item in sets:
            role, _, target = item.partition("=")
            if role not in ing.ROLE_SYNONYMS or not target:
                raise LedgerError(f"bad mapping {item!r}; roles: {', '.join(ing.ROLE_SYNONYMS)}")
            sheet, _, col = target.rpartition("!") if "!" in target else (None, "", target)
            hits = [(s, c["name"]) for s, p in profile["sheets"].items() for c in p["columns"]
                    if c["name"] == col and (sheet is None or s == sheet)]
            if len(hits) != 1:
                raise LedgerError(f"column {target!r} not found (or ambiguous; use Sheet!Column)")
            mapping[role] = {"sheet": hits[0][0], "col": hits[0][1], "source": "user"}
        led.db.execute("UPDATE documents SET mapping_json=? WHERE doc_id=?", (canonical_json(mapping), doc["doc_id"]))
        act["output_refs"] = mapping
    return mapping


# ---- checks ----------------------------------------------------------------------------------
def _draft_json(d):
    return d.to_json()


def run_checks(led, run_id, ref, only=None, today=None, params=None, use_cache=True):
    doc, profile, mapping = _load_doc(led, ref)
    if profile is None:
        raise LedgerError("document not ingested; run `sr ingest` first")
    if profile.get("kind") == "text":
        raise LedgerError("text documents use `sr extract` and `sr qcheck`, not `sr check`")
    today = today or date.today()
    params = params or {}
    ctx = chk.Ctx(led.db, doc["doc_id"], mapping, profile, today, params)
    results = []
    for check_id, version, needs, fn, desc in chk.CHECKS:
        if only and check_id not in only:
            continue
        roles = chk.applicable(ctx, needs)
        if roles is None:
            reason = "needs roles: " + " or ".join("+".join(n) for n in needs)
            profile["coverage"][check_id] = {"version": version, "status": "skipped", "reason": reason}
            _prune_skipped(led, run_id, doc["doc_id"], check_id, version)
            results.append({"check": check_id, "status": "skipped", "reason": reason, "findings": 0})
            continue
        key = cache_key(doc["sha256"], check_id, version, params, {r: mapping[r] for r in sorted(mapping)},
                        str(today) if check_id.startswith("date.") else None)
        with led.action(run_id, f"check:{check_id}", version, args={"params": params},
                        input_refs={"doc_id": doc["doc_id"]}) as act:
            cached = led.cache_get(key) if use_cache else None
            act["cache_key"] = key
            if cached is not None:
                drafts = [chk.Draft.from_json(d) for d in cached]
                act["cache_hit"], act["status"] = True, "cache_hit"
            else:
                drafts = fn(ctx)
                led.cache_put(key, [_draft_json(d) for d in drafts])
            ids = _materialize(led, run_id, doc, ctx, check_id, version, drafts, act)
            act["output_refs"] = {"finding_ids": ids}
        profile["coverage"][check_id] = {"version": version, "status": "ran", "findings": len(ids),
                                         "cache_hit": cached is not None}
        results.append({"check": check_id, "status": "cache_hit" if cached is not None else "ran",
                        "findings": len(ids), "finding_ids": ids})
    _save_profile(led, doc["doc_id"], profile)
    return results


def _prune_skipped(led, run_id, doc_id, check_id, version):
    """A check that can no longer run must not leave its old unreviewed findings in the brief."""
    rows = led.db.execute("SELECT finding_id FROM findings WHERE doc_id=? AND check_id=? AND status='open' AND "
                          "NOT EXISTS (SELECT 1 FROM feedback b WHERE b.finding_id=findings.finding_id)",
                          (doc_id, check_id)).fetchall()
    if not rows:
        return
    ids = [r["finding_id"] for r in rows]
    with led.action(run_id, f"prune:{check_id}", version, input_refs={"doc_id": doc_id}) as act:
        with led.transaction():
            led.db.executemany("DELETE FROM findings WHERE finding_id=?", [(i,) for i in ids])
        act["output_refs"] = {"removed_finding_ids": ids, "reason": "check no longer applicable"}


def _materialize(led, run_id, doc, ctx, check_id, version, drafts, act):
    doc_id = doc["doc_id"]
    row_cache = {}
    ids, keys = [], []
    with led.transaction():
        for d in drafts:
            roles = [c[2] for e in d.examples for c in e.cols]
            conf = d.confidence
            if CONF_RANK[ctx.mapping_confidence(roles)] < CONF_RANK[conf]:
                conf = ctx.mapping_confidence(roles)
            rec_ids = []
            for e in d.examples:
                cells = row_cache.get((e.sheet, e.row_no))
                if cells is None:
                    r = led.db.execute("SELECT data FROM table_rows WHERE doc_id=? AND sheet=? AND row_no=?",
                                       (doc_id, e.sheet, e.row_no)).fetchone()
                    cells = row_cache[(e.sheet, e.row_no)] = json.loads(r["data"]) if r else []
                for name, idx, role in e.cols:
                    raw = chk.cell(cells, idx)
                    raw_text = "" if raw is None else str(raw)
                    norm = None
                    num, _ = parse_number(raw)
                    if num is not None:
                        norm = str(num)
                    elif raw is not None:
                        dt, _ = parse_date(raw)
                        norm = dt.isoformat() if dt else None
                    rec_ids.append(led.upsert_record(doc_id, role, f"{e.sheet}!R{e.row_no}C{idx + 1}", raw_text,
                                                     "sr.cell", value_norm=norm, action_id=act.get("action_id")))
            detail = dict(d.detail)
            detail.update({"rows": d.rows, "rows_truncated": d.count > len(d.rows) and len(d.rows) >= chk.MAX_ROWS_LISTED, "columns": {c[2]: c[0] for e in d.examples for c in e.cols},
                           "mapping_roles": sorted(set(roles))})
            fid = led.upsert_finding(run_id, doc_id, check_id, version, d.dedupe_key, d.severity, conf, d.kind,
                                     d.claim, rec_ids, count=d.count, impact_amount=d.impact, detail=detail)
            ids.append(fid)
            keys.append(d.dedupe_key)
        # drop stale open findings for this check that nobody has reviewed
        for row in led.db.execute("SELECT finding_id, dedupe_key FROM findings WHERE doc_id=? AND check_id=? "
                                  "AND status='open'", (doc_id, check_id)).fetchall():
            if row["dedupe_key"] not in keys and not led.db.execute(
                    "SELECT 1 FROM feedback WHERE finding_id=?", (row["finding_id"],)).fetchone():
                led.db.execute("DELETE FROM findings WHERE finding_id=?", (row["finding_id"],))
    return ids


# ---- drill-down ------------------------------------------------------------------------------
def drill(led, finding_id, context=2):
    """-> (finding, doc, evidence records, blocks). Tabular evidence: surrounding source rows.
    Text evidence: the surrounding source passage (+-200 chars)."""
    f = led.db.execute("SELECT * FROM findings WHERE finding_id=?", (finding_id,)).fetchone()
    if f is None:
        raise LedgerError(f"unknown finding {finding_id}")
    doc = led.get_document(f["doc_id"])
    profile = json.loads(doc["profile_json"])
    recs = led.db.execute("SELECT r.* FROM finding_evidence e JOIN records r USING(record_id) "
                          "WHERE e.finding_id=? ORDER BY r.record_id", (finding_id,)).fetchall()
    rows, passages = set(), []
    for r in recs:
        loc = r["locator"].split("#")[0]
        if "!R" in loc:
            rows.add((loc.split("!R")[0], int(loc.split("!R")[1].split("C")[0])))
        elif loc.startswith("chars:"):
            t = led.db.execute("SELECT text FROM doc_text WHERE doc_id=?", (r["doc_id"],)).fetchone()
            s0, e0 = map(int, loc[6:].split("-"))
            text = t["text"] if t else ""
            from . import pdfdoc
            where = pdfdoc.locate(led.db, r["doc_id"], s0, e0)
            passages.append({"kind": "text", "locator": loc, "field": r["field"], "value": r["raw_text"], "where": where,
                             "before": text[max(0, s0 - 200):s0], "quoted": text[s0:e0], "after": text[e0:e0 + 200],
                             "pass": r["pass_label"], "verified": bool(r["verified"]), "note": r["verify_note"]})
        else:
            passages.append({"kind": "other", "locator": loc, "field": r["field"], "value": r["raw_text"],
                             "pass": r["pass_label"], "verified": bool(r["verified"]), "note": r["verify_note"]})
    out = list(passages)
    for sheet, row_no in sorted(rows):
        header = [c["name"] for c in profile["sheets"][sheet]["columns"]]
        block = []
        for r in led.db.execute("SELECT row_no, data FROM table_rows WHERE doc_id=? AND sheet=? AND row_no "
                                "BETWEEN ? AND ? ORDER BY row_no", (doc["doc_id"], sheet, row_no - context,
                                                                    row_no + context)):
            block.append({"row_no": r["row_no"], "target": r["row_no"] == row_no,
                          "cells": dict(zip(header, json.loads(r["data"])))})
        out.append({"kind": "table", "sheet": sheet, "row_no": row_no, "context": block})
    return f, doc, recs, out
