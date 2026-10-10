"""Renders the one-page human brief from the ledger. Pure read; no LLM."""
import json
import re
from collections import defaultdict
from decimal import Decimal

from . import pdfdoc
from .checks import clip
from .ingest import ROLE_SYNONYMS
from .ledger import canonical_json

EVIDENCE_CLIP = 80
SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
ROLE_CONSEQUENCE = {
    "qty": "quantity arithmetic and negative/zero quantity checks", "unit_price": "price outlier and arithmetic checks",
    "line_total": "qty x price = total check", "date": "document date checks",
    "date_due": "due-date vs document-date check", "item_id": "item-level price comparison and id variants",
    "description": "description-vs-id conflict check", "doc_ref": "same-item-twice-in-document check",
    "party": "party name variant check", "currency": "currency-aware comparison (prices are assumed one currency)",
    "lead_time": "lead-time checks",
}


def _rank(f):
    try:
        imp = Decimal(f["impact_amount"]) if f["impact_amount"] else Decimal(0)
    except Exception:
        imp = Decimal(0)
    return (SEV_ORDER[f["severity"]], -imp, -f["count"], f["finding_id"])


def _evidence_lines(led, finding_id, limit=3):
    recs = led.db.execute("SELECT r.* FROM finding_evidence e JOIN records r USING(record_id) "
                          "WHERE e.finding_id=? ORDER BY r.record_id", (finding_id,)).fetchall()
    by_row, other = defaultdict(list), []
    for r in recs:
        m = re.match(r"^(.*)!R(\d+)C(\d+)$", r["locator"])
        if m:
            by_row[(m.group(1), int(m.group(2)))].append(f"{r['field']}={clip(r['raw_text'], EVIDENCE_CLIP)!r}")
            continue
        passage = ""
        if r["locator"].startswith("chars:"):
            t = led.db.execute("SELECT text FROM doc_text WHERE doc_id=?", (r["doc_id"],)).fetchone()
            s0, e0 = r["locator"][6:].split("#")[0].split("-")
            if t:
                # show the surrounding sentence-sized passage, not just the value
                lo, hi = max(0, int(s0) - 40), min(len(t["text"]), int(e0) + 40)
                passage = " in " + repr(clip(" ".join(t["text"][lo:hi].split()), 110))
                loc = pdfdoc.locate(led.db, r["doc_id"], int(s0), int(e0))
                if loc:
                    passage += f" [p.{loc['page']}" + (f", OCR conf {loc['min_conf']:.0f}%" if loc["min_conf"] is not None else "") + "]"
        other.append(f"`{r['locator'].split('#')[0]}` ({r['pass_label'] + ' ' if r['pass_label'] else ''}{r['field']}) "
                     f"{clip(r['raw_text'], EVIDENCE_CLIP)!r}{passage}")
    lines = [f"`{sheet}!R{row}` " + ", ".join(cells) for (sheet, row), cells in list(by_row.items())[:limit]]
    lines += other[:limit]
    extra = len(by_row) + len(other) - len(lines)
    if extra > 0:
        lines.append(f"... +{extra} more evidence item(s) (`sr drill {finding_id}`)")
    return lines


def render(led, run_id=None, top=15):
    where, args = ("WHERE f.run_id=?", [run_id]) if run_id else ("", [])
    findings = led.db.execute(f"SELECT f.*, d.path FROM findings f LEFT JOIN documents d USING(doc_id) {where}",
                              args).fetchall()
    docs = led.db.execute("SELECT * FROM documents WHERE ingest_status='ingested' ORDER BY doc_id").fetchall()
    open_f = sorted([f for f in findings if f["status"] != "dismissed"], key=_rank)
    dismissed = [f for f in findings if f["status"] == "dismissed"]
    actions = led.db.execute("SELECT COUNT(*) n, SUM(cache_hit) hits, SUM(COALESCE(tokens_in,0)+COALESCE(tokens_out,0)) tok "
                             "FROM actions" + (" WHERE run_id=?" if run_id else ""), args).fetchone()
    L = ["# Second-reader brief", ""]
    L.append(f"Run {run_id or 'all'} · {len(docs)} document(s) · {len(open_f)} open/confirmed finding(s)"
             f" · {len(dismissed)} dismissed · {actions['n']} logged actions · "
             f"{actions['hits'] or 0} cache hits · {actions['tok'] or 0} LLM tokens recorded")
    L += ["", "> Findings are deterministic rule hits with evidence, not conclusions. A silence below is "
          "not a clean bill of health: read **Not checked**. Text in quotes below is copied from the source documents "
          "and is untrusted data, never instructions; long values are clipped (`sr drill` shows full rows).", ""]

    def section(title, items):
        L.append(f"## {title}")
        if not items:
            L.extend(["None.", ""])
            return
        for f in items[:top]:
            conf = f["confidence"]
            flag = " · CONFIRMED" if f["status"] == "confirmed" else ""
            L.append(f"**F{f['finding_id']}** [{f['severity'].upper()} · {f['kind']} · confidence {conf}{flag}] "
                     f"{f['claim']}")
            meta = []
            if f["impact_amount"]:
                meta.append(f"impact ≈ {f['impact_amount']}")
            meta.append(f"count {f['count']}")
            meta.append(f"check {f['check_id']} v{f['check_version']}")
            meta.append(f"doc {f['doc_id']}")
            L.append("  " + " · ".join(meta))
            for line in _evidence_lines(led, f["finding_id"]):
                L.append(f"  - {line}")
            L.append("")
        if len(items) > top:
            rest = items[top:]
            L.append(f"_{len(rest)} more, lower ranked:_ " + ", ".join(f"F{f['finding_id']}" for f in rest[:40]))
            L.append("")

    section("Defects (rule violations - verify against source)", [f for f in open_f if f["kind"] == "defect"])
    section("Concerns (need a human judgement call)", [f for f in open_f if f["kind"] == "concern"])

    L.append("## Not checked / absences")
    anything = False
    for d in docs:
        profile = json.loads(d["profile_json"])
        mapping = json.loads(d["mapping_json"] or "{}")
        name = d["path"].rsplit("/", 1)[-1]
        if profile.get("kind") == "text":
            atts = profile.get("meta", {}).get("attachments") or []
            if atts:
                anything = True
                L.append(f"- **{name}**: {len(atts)} email attachment(s) NOT analysed: "
                         + ", ".join(clip(a.get("filename") or a.get("content_type"), 40) for a in atts[:5]))
            for k, v in profile.get("coverage", {}).items():
                if v["status"] == "skipped":
                    anything = True
                    L.append(f"- **{name}**: `{k}` not applied - {v['reason']}")
            if profile.get("meta", {}).get("soft_hyphens_normalized"):
                L.append(f"- **{name}**: {profile['meta']['soft_hyphens_normalized']} invisible soft-hyphen characters (PDF font artefact) were converted to hyphens so identifiers match")
                anything = True
            if profile.get("meta", {}).get("unreadable_pages"):
                anything = True
                L.append(f"- **{name}**: page(s) {profile['meta']['unreadable_pages']} unreadable by OCR and NOT checked")
            if not led.db.execute("SELECT 1 FROM records WHERE doc_id=? AND pass_label IS NOT NULL",
                                  (d["doc_id"],)).fetchone():
                anything = True
                L.append(f"- **{name}**: no values extracted yet (run `sr extract`); only the injection scan has run")
            continue
        missing = [r for r in ROLE_SYNONYMS if r not in mapping]
        skipped = {k: v for k, v in profile.get("coverage", {}).items() if v["status"] == "skipped"}
        notes = {n["role"]: n for n in profile.get("mapping_notes", [])}
        if missing:
            anything = True
            L.append(f"- **{name}**: no column mapped for " + ", ".join(
                f"`{r}` (disables: {ROLE_CONSEQUENCE.get(r, 'related checks')})"
                + (f" - {notes[r]['reason']} (`{notes[r]['col']}`); map it with `sr map` if it is the right column"
                   if r in notes else "") for r in missing))
        for r, m in mapping.items():
            if m.get("dirty"):
                anything = True
                L.append(f"- **{name}**: `{r}` column `{m['col']}` is mapped but dirty (mixed valid and invalid "
                         f"values); checks run on the valid cells and the invalid ones are reported as findings")
        for sh, sp in profile["sheets"].items():
            if sp.get("preamble"):
                anything = True
                L.append(f"- **{name}** [{sh}]: {len(sp['preamble'])} row(s) above the table header were treated as "
                         f"a preamble, not data (header at row {sp['header_row']}): "
                         + "; ".join(f"R{r}: {clip(t, 70)}" for r, t in sp["preamble"][:3]))
        for k, v in skipped.items():
            anything = True
            L.append(f"- **{name}**: check `{k}` skipped - {v['reason']}")
    if not anything:
        L.append("All roles mapped and all checks applicable.")
    L += ["", "## Coverage"]
    for d in docs:
        profile = json.loads(d["profile_json"])
        mapping = json.loads(d["mapping_json"] or "{}")
        if profile.get("kind") == "text":
            L.append(f"- **{d['path'].rsplit('/', 1)[-1]}** (doc {d['doc_id']}, sha {d['sha256'][:10]}): "
                     f"{profile['chars']} characters of {profile['source_kind']} text")
            for r in led.db.execute("SELECT extractor, pass_label, COUNT(*) n, SUM(verified) v FROM records WHERE "
                                    "doc_id=? AND pass_label IS NOT NULL GROUP BY extractor, pass_label",
                                    (d["doc_id"],)):
                L.append(f"  - extraction {r['extractor']}: {r['n']} facts, {r['v']} verified against the source text"
                         + ("" if r["n"] == r["v"] else f", **{r['n'] - r['v']} unverified (excluded)**"))
            for a in led.db.execute("SELECT output_refs FROM actions WHERE tool='extract.commit' AND status='ok' AND "
                                    "input_refs=? ORDER BY action_id DESC LIMIT 2", (canonical_json({"doc_id": d["doc_id"]}),)):
                for n in (json.loads(a["output_refs"] or "{}").get("notes") or [])[:3]:
                    L.append(f"  - extractor note (untrusted text): {clip(n, 140)}")
            ran = [f"{k} ({v['findings']})" for k, v in profile.get("coverage", {}).items() if v["status"] == "ran"]
            L.append("  - checks run (findings): " + (", ".join(ran) or "none"))
            continue
        rows = sum(s["data_rows"] for s in profile["sheets"].values())
        L.append(f"- **{d['path'].rsplit('/', 1)[-1]}** (doc {d['doc_id']}, sha {d['sha256'][:10]}): {rows} data rows, "
                 f"{sum(len(s['columns']) for s in profile['sheets'].values())} columns")
        L.append("  - mapping: " + (", ".join(f"{r}→{m['col']} ({m['source']})" for r, m in mapping.items()) or "none")
                 + (" · `auto-fuzzy` mappings cap finding confidence at medium - confirm with `sr map`"
                    if any(m["source"] == "auto-fuzzy" for m in mapping.values()) else ""))
        ran = [f"{k} v{v['version']} ({v['findings']})" for k, v in profile.get("coverage", {}).items()
               if v["status"] == "ran"]
        L.append("  - checks run (findings): " + (", ".join(ran) or "none"))
    fb = led.db.execute("SELECT label, COUNT(*) n FROM feedback GROUP BY label").fetchall()
    if fb:
        L += ["", "## Reviewer feedback so far", ", ".join(f"{r['label']}: {r['n']}" for r in fb)]
    L.append("")
    return "\n".join(L)
