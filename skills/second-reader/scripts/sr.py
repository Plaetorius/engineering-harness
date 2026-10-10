#!/usr/bin/env python3
"""second-reader CLI. Every command that touches data is logged to the SQLite ledger."""
import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from srlib import brief as brief_mod          # noqa: E402
from srlib import engine, extract, quotes, report, rfq   # noqa: E402
from srlib.checks import clip as checks_clip  # noqa: E402
from srlib.ledger import Ledger, LedgerError   # noqa: E402


def parse_params(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        if not k or not _:
            raise LedgerError(f"bad --param {it!r}; use name=value")
        out[k] = v
    return out


def cmd_init(a, led):
    if a.offline:
        led.set_offline()
    print(f"ledger ready: {led.path}" + ("  [OFFLINE: no AI reader can touch this ledger]" if led.offline else ""))


def cmd_mode(a, led):
    if a.mode == "offline":
        led.set_offline()
    print("mode:", "offline (no AI)" if led.offline else "online (AI readers allowed)")


def cmd_run(a, led):
    if a.action == "start":
        print(f"run {led.start_run(a.goal)} started")
    else:
        rid = led.current_run()
        r = led.db.execute("SELECT * FROM runs WHERE run_id=?", (rid,)).fetchone()
        print(f"active run {rid}: goal={r['goal']!r} started {r['started_at']}")


def cmd_ingest(a, led):
    run = led.current_run(a.run)
    for p in a.files:
        d = engine.ingest_document(led, run, p, a.goal_tag, use_cache=not a.no_cache)
        prof = json.loads(d["profile_json"])
        if prof.get("kind") == "text":
            n_inj = led.db.execute("SELECT COUNT(*) FROM findings WHERE doc_id=? AND check_id LIKE 'inject.%'",
                                   (d["doc_id"],)).fetchone()[0]
            print(f"doc {d['doc_id']}  {Path(d['path']).name}  sha {d['sha256'][:10]}  text/{prof['source_kind']} "
                  f"{prof['chars']} chars" + (f"  ** {n_inj} injection/hidden-text flag(s) **" if n_inj else ""))
            for att in prof.get("meta", {}).get("attachments", []):
                print(f"  attachment NOT analysed: {att.get('filename')} ({att.get('content_type')})")
            continue
        print(f"doc {d['doc_id']}  {Path(d['path']).name}  sha {d['sha256'][:10]}")
        for sheet, s in prof["sheets"].items():
            print(f"  [{sheet}] {s['data_rows']} data rows (header at row {s['header_row']})")
            for r, t in s.get("preamble", []):
                print(f"    preamble R{r}: {t}")
            for c in s["columns"]:
                extra = ""
                if c["type"] == "numeric":
                    extra = f" range {c['min']}..{c['max']}"
                elif c["type"] == "date":
                    extra = f" range {c['date_min']}..{c['date_max']}"
                print(f"    {c['name']:<28} {c['type']:<8} nulls {c['null_rate']:.1%} "
                      f"distinct {c['distinct']}{'+' if c['distinct_capped'] else ''}{extra}")
        mapping = json.loads(d["mapping_json"] or "{}")
        print("  suggested mapping: " + (", ".join(f"{r}={m['col']} ({m['source']}{', dirty' if m.get('dirty') else ''})"
                                                   for r, m in mapping.items()) or "none - set with `sr map`"))
        for n in prof.get("mapping_notes", []):
            print(f"  note: {n['role']} not mapped - {n['reason']} ({n['col']})")


def cmd_map(a, led):
    run = led.current_run(a.run)
    m = engine.set_mapping(led, run, a.doc, a.set, a.unset)
    print(json.dumps(m, indent=2))


def cmd_check(a, led):
    run = led.current_run(a.run)
    docs = [a.doc] if a.doc else [str(r["doc_id"]) for r in led.db.execute(
        "SELECT doc_id FROM documents WHERE ingest_status='ingested' AND doc_type!='text'")]
    today = date.fromisoformat(a.today) if a.today else None
    for d in docs:
        if led.get_document(d)["doc_type"] == "text":
            raise LedgerError(f"document {d} is text: use `sr extract` and `sr qcheck`, not `sr check`")
        print(f"doc {d}")
        for r in engine.run_checks(led, run, d, a.only, today, parse_params(a.param), use_cache=not a.no_cache):
            extra = f"  ({r['reason']})" if r.get("reason") else ""
            print(f"  {r['check']:<26} {r['status']:<10} findings {r['findings']}{extra}")


def cmd_brief(a, led):
    run = led.current_run(a.run) if a.run or a.current else None
    text = brief_mod.render(led, run, a.top)
    if a.out:
        Path(a.out).write_text(text)
        print(f"brief written to {a.out}")
    else:
        print(text)


def cmd_findings(a, led):
    q = "SELECT * FROM findings"
    cond, args = [], []
    if a.status:
        cond.append("status=?"); args.append(a.status)
    if a.severity:
        cond.append("severity=?"); args.append(a.severity)
    rows = led.db.execute(q + (" WHERE " + " AND ".join(cond) if cond else ""), args).fetchall()
    rows.sort(key=brief_mod._rank)
    for f in rows:
        print(f"F{f['finding_id']:<4} {f['severity']:<6} {f['kind']:<7} {f['status']:<9} x{f['count']:<6} {f['claim'][:100]}")


def cmd_drill(a, led):
    f, doc, recs, blocks = engine.drill(led, a.finding, a.context)
    print(f"F{f['finding_id']} [{f['severity']} {f['kind']} conf {f['confidence']}] {f['claim']}")
    print(f"check {f['check_id']} v{f['check_version']} on {Path(doc['path']).name}; status {f['status']}")
    detail = json.loads(f["detail_json"] or "{}")
    if detail.get("rows"):
        trunc = " (list truncated; count is exact)" if detail.get("rows_truncated") else ""
        print(f"affected source rows ({f['count']}){trunc}: {detail['rows'][:40]}{' ...' if len(detail['rows']) > 40 else ''}")
    for b in blocks:
        if b["kind"] == "table":
            print(f"\n--- {b['sheet']} around row {b['row_no']} ---")
            for r in b["context"]:
                mark = ">>" if r["target"] else "  "
                print(f"{mark} R{r['row_no']}: " + " | ".join(f"{k}={checks_clip(v, 200)}" for k, v in r["cells"].items()))
        elif b["kind"] == "text":
            flag = "" if b["verified"] else "  [UNVERIFIED: " + (b["note"] or "?") + "]"
            print(f"\n--- {b['locator']} {('pass ' + b['pass'] + ' ') if b['pass'] else ''}{b['field']}={checks_clip(b['value'], 80)!r}{flag} ---")
            w = b.get("where")
            if w:
                print(f"    page {w['page']} ({w['method']})" + (f", bbox {w['bbox']}, lowest OCR word confidence {w['min_conf']:.0f}%"
                                                                  if w["bbox"] else "") + f"  -> `sr page {doc['doc_id']} {w['page']}` to see it")
            print(("..." + b["before"] + "[[" + b["quoted"] + "]]" + b["after"] + "...").replace("\n", "\n    "))
        else:
            print(f"\n--- {b['locator']} {b['field']}={checks_clip(b['value'], 200)!r} ---")



def _doc(led, ref):
    d = led.get_document(ref)
    if d["doc_type"] != "text":
        raise LedgerError("this command needs a text/email document (.txt .eml .html)")
    return d


def cmd_extract(a, led):
    run = led.current_run(a.run)
    d = _doc(led, a.doc)
    if a.action == "prepare":
        payloads = extract.prepare(led, run, d, a.pass_label, a.model, a.max_chars, use_cache=not a.no_cache)
        out = json.dumps(payloads[0] if len(payloads) == 1 else payloads, indent=1, ensure_ascii=False)
        if a.out:
            Path(a.out).write_text(out)
            print(f"{len(payloads)} payload(s) written to {a.out}" + ("  (cached: nothing to do)" if payloads[0].get("cached") else ""))
        else:
            print(out)
    elif a.action == "commit":
        raw = sys.stdin.read() if a.input in (None, "-") else Path(a.input).read_text()
        res = extract.commit(led, run, d, a.pass_label, a.model, a.role or a.model if (a.role or a.model) in
                             ("haiku", "sonnet", "opus") else "code", raw, a.tokens_in, a.tokens_out)
        print(f"pass {a.pass_label} ({a.model}): {res['facts']} facts, {res['verified']} verified, "
              f"{res['unverified']} unverified {res['reasons'] or ''}")
        for n in res["notes"]:
            print(f"  model note: {n}")
    elif a.action == "local":
        res = extract.local_extract(led, run, d, a.pass_label if a.pass_label != "A" else "L", a.qty)
        print(f"local rule-based pass: {res['facts']} facts, {res['verified']} verified, {res['unverified']} unverified"
              + "".join(f"\n  note: {n}" for n in res["notes"]))
    else:
        res = extract.compare(led, run, d, a.a, a.b)
        print(f"pass {a.a} vs {a.b}: {res['agree']} agree, {res['disagree']} disagree {res['disagreements']}, "
              f"{res['pass_a_only']} read only by {a.a} {res['a_only']}, {res['pass_b_only']} only by {a.b} {res['b_only']}")


def cmd_batch(a, led):
    run = led.current_run(a.run)
    docs = [_doc(led, r) for r in a.docs] if a.action == "prepare" else None
    if a.action == "prepare":
        res = extract.prepare_batch(led, run, docs, a.pass_label, a.model, a.budget, a.max_docs, use_cache=not a.no_cache)
        outdir = Path(a.out_dir or ".")
        outdir.mkdir(parents=True, exist_ok=True)
        for i, b in enumerate(res["batches"]):
            (outdir / f"batch_{a.pass_label}_{i:03d}.json").write_text(json.dumps(b, ensure_ascii=False))
        print(f"{len(res['batches'])} batch call(s) for docs per batch {res['docs_per_batch']}; "
              f"{len(res['cached'])} already extracted (skipped) {res['cached']}; oversize (use single-doc prepare): {res['oversize']}")
    else:
        raw = sys.stdin.read() if a.input in (None, "-") else Path(a.input).read_text()
        ids = [int(x) for x in a.ids]
        docs_by_id = {i: _doc(led, str(i)) for i in ids}
        res = extract.commit_batch(led, run, docs_by_id, a.pass_label, a.model,
                                   a.role or (a.model if a.model in ("haiku", "sonnet", "opus") else "code"),
                                   raw, a.tokens_in, a.tokens_out)
        for did, r in res.items():
            print(f"doc {did}: " + (f"ERROR {r['error']}" if "error" in r else
                                    f"{r['facts']} facts, {r['verified']} verified, {r['unverified']} unverified {r['reasons'] or ''}"))


def cmd_page(a, led):
    from srlib import pdfdoc
    d = _doc(led, a.doc)
    if not d["path"].lower().endswith(".pdf"):
        raise LedgerError("`sr page` renders PDF pages")
    if not Path(d["path"]).exists():
        raise LedgerError(f"the original file is gone: {d['path']}")
    out = Path(a.out or f"page_{d['doc_id']}_{a.page}.png")
    pdfdoc.render_page(d["path"], a.page, out)
    print(f"page {a.page} rendered to {out}")


def _fmt(x, nd=2):
    return "-" if x is None else f"{x:,.{nd}f}"


def cmd_rfq(a, led):
    run = led.current_run(a.run)
    if a.action == "set":
        with led.transaction():
            if a.order_date:
                date.fromisoformat(a.order_date)
                rfq.set_setting(led, "order_date", a.order_date)
            if a.base:
                rfq.set_setting(led, "base_currency", a.base.upper())
            for item in a.fx or []:
                k, _, v = item.partition("=")
                Decimal(v)
                rfq.set_setting(led, f"fx.{k.upper()}", v)
        print("settings:", {k: (str(v) if not isinstance(v, dict) else {c: str(r) for c, r in v.items()}) for k, v in rfq.settings(led).items()})
    elif a.action == "add":
        with led.transaction():
            lid = rfq.add_line(led, a.part, a.qty, a.need_by_days, a.need_by_date, a.bid_price, a.currency)
        print(f"RFQ line {lid}: {a.qty} x {a.part}")
    elif a.action == "load":
        with led.transaction():
            ids = rfq.load_csv(led, a.file)
        print(f"{len(ids)} RFQ line(s) loaded")
    elif a.action == "show":
        for r in rfq.lines(led):
            print(f"#{r['rfq_line_id']} {r['quantity']} x {r['part_number']}  need-by {r['need_by_days']} d  bid {r['bid_unit_price'] or '-'} {r['bid_currency'] or ''}")
        print("settings:", {k: str(v) for k, v in rfq.settings(led).items()})
    else:                                        # compare
        with led.action(run, "rfq.compare", rfq.RFQ_VERSION, args={"pass": a.pass_label}) as act:
            cmp = rfq.build_comparison(led, a.pass_label)
            ids = rfq.run_checks(led, run, cmp)
            act["output_refs"] = {"findings": ids}
        base = cmp["settings"]["base"]
        for ln in cmp["lines"]:
            print(f"\nRFQ {rfq.fmtq(ln['quantity'])} x {ln['part']}  (need within {ln['need_by_days']} d; bid total {_fmt(ln['bid_total'])} {base})")
            for i, q in enumerate(ln["quotes"], 1):
                tag = {"compliant": "OK ", "conditional": "?? ", "disqualified": "NO "}[q["status"]]
                best = " <== RECOMMENDED" if q is ln["best"] else ""
                print(f" {i}. {tag}{q['label'][:34]:<34} {q['currency'] or '?'} {_fmt(q['effective_unit_price'], 4)}/unit x {rfq.fmtq(q['qty'])} "
                      f"goods {_fmt(q['goods_base'])} + freight {_fmt(q['freight_base'])} = landed {_fmt(q['landed_base'])} {base}  "
                      f"lead {q['lead_time_days'] if q['lead_time_days'] is not None else '?'} d  margin {_fmt(q['margin'])} ({q['margin_pct'] or '-'}%){best}")
                for r in q["reasons"]:
                    print(f"        x {r}")
                for f in q["flags"]:
                    print(f"        ! {f}")
            if ln["best"]:
                b = ln["best"]
                print(f" -> recommended: {b['supplier']}; landed {_fmt(b['landed_base'])} {base}; margin {_fmt(b['margin'])} {base} ({b['margin_pct']}% of the bid)")
                if ln["cheapest"] is not ln["best"]:
                    print(f"    cheapest overall is {ln['cheapest']['supplier']} but it is not compliant/complete (see above)")
            else:
                print(" -> no fully compliant, fully costed quote: a human must decide")
        for n in cmp["notes"] + [f"RFQ line {p} got no usable quote" for p in cmp["unanswered"]]:
            print("note:", n)


def cmd_report(a, led):
    run = led.current_run(a.run) if a.run or a.current else None
    text = report.render(led, run, a.title, a.embed_pages)
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"HTML report written to {a.out} ({len(text) // 1024} KB, self-contained, no scripts or external loads)")


OFFLINE_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xlsm", ".json", ".txt", ".md", ".eml", ".html", ".htm", ".pdf"}


def cmd_offline_run(a, led):
    """Whole pipeline with no AI and no network: ingest -> local read -> checks -> RFQ comparison -> HTML report."""
    led.set_offline()
    run = led.start_run(a.goal or "offline run")
    files, skipped = [], 0
    for item in a.inputs:
        p = Path(item)
        found = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file()) if p.is_dir() else []
        if not found:
            raise LedgerError(f"nothing to read at {item}")
        for q in found:
            if q.suffix.lower() in OFFLINE_SUFFIXES:
                files.append(q)
            else:
                skipped += 1
    if a.part or a.rfq_file or a.order_date or a.fx or a.base:
        with led.transaction():
            if a.order_date:
                rfq.set_setting(led, "order_date", a.order_date)
            if a.base:
                rfq.set_setting(led, "base_currency", a.base.upper())
            for item in a.fx or []:
                k, _, v = item.partition("=")
                Decimal(v)
                rfq.set_setting(led, f"fx.{k.upper()}", v)
            if a.rfq_file:
                rfq.load_csv(led, a.rfq_file)
            if a.part:
                rfq.add_line(led, a.part, a.qty, a.need_by_days, a.need_by_date, a.bid_price, a.currency)
    today = date.fromisoformat(a.today) if a.today else None
    stats = {"documents": 0, "tables": 0, "text": 0, "failed": 0, "findings": 0, "skipped_unsupported": skipped}
    failures = []
    for f in files:
        try:
            d = engine.ingest_document(led, run, f)
        except (LedgerError, SystemExit, Exception) as exc:      # one bad file must not stop the run
            stats["failed"] += 1
            failures.append(f"{f.name}: {str(exc)[:120]}")
            continue
        stats["documents"] += 1
        if d["doc_type"] == "text":
            stats["text"] += 1
            res = extract.local_extract(led, run, d)
            quotes.qcheck(led, run, d, today, "L")
        else:
            stats["tables"] += 1
            engine.run_checks(led, run, d["doc_id"], today=today)
    if rfq.lines(led):
        cmp = rfq.build_comparison(led, "L")
        rfq.run_checks(led, run, cmp)
    stats["findings"] = led.db.execute("SELECT COUNT(*) FROM findings WHERE status!='dismissed'").fetchone()[0]
    out = Path(a.out)
    out.write_text(report.render(led, None, a.title, a.embed_pages), encoding="utf-8")
    print(f"OFFLINE run complete: {stats['documents']} document(s) read ({stats['tables']} table, {stats['text']} text/PDF), "
          f"{stats['findings']} finding(s), {stats['failed']} failed, {stats['skipped_unsupported']} unsupported file(s) skipped")
    print(f"report: {out}\nledger: {led.path}")
    if not a.quiet:
        for x in failures:
            print("  failed:", x)


def cmd_facts(a, led):
    d = _doc(led, a.doc)
    text = extract.get_text(led, d["doc_id"])
    q = "SELECT * FROM records WHERE doc_id=? AND pass_label IS NOT NULL"
    args = [d["doc_id"]]
    if a.pass_label:
        q += " AND pass_label=?"; args.append(a.pass_label)
    if a.unverified:
        q += " AND verified=0"
    for r in led.db.execute(q + " ORDER BY pass_label, entity, record_id", args):
        span = ""
        if r["locator"].startswith("chars:"):
            s0, e0 = r["locator"][6:].split("#")[0].split("-")
            span = " | " + extract.clip_text(text[int(s0):int(e0)].replace("\n", " "), 70)
        flag = "OK " if r["verified"] else "BAD"
        print(f"{r['pass_label']} {r['entity']:<6} {r['field']:<22} {flag} {extract.clip_text(r['raw_text'], 30)!r:<34} "
              f"{r['locator']}{'  [' + r['verify_note'].split(':')[0] + ']' if r['verify_note'] else ''}{span}")


def _tbl(t):
    return {**{k: (str(v) if isinstance(v, Decimal) else v.isoformat() if hasattr(v, "isoformat") else v)
               for k, v in t.items() if k != "lines"},
            "lines": [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in l.items()} for l in t["lines"]]}


def cmd_quotes(a, led):
    docs = [_doc(led, r) for r in a.docs] if a.docs else led.db.execute(
        "SELECT * FROM documents WHERE doc_type='text'").fetchall()
    tables = [quotes.build_table(led, d["doc_id"], a.pass_label) for d in docs]
    if a.json:
        print(json.dumps([_tbl(t) for t in tables], indent=1))
        return
    for t in tables:
        print(f"doc {t['doc_id']}  {t['supplier'] or '(supplier not extracted)'}  valid until {t['valid_until'] or '-'}  "
              f"incoterms {t['incoterms'] or '-'}  payment {t['payment_terms'] or '-'}")
        for l in t["lines"]:
            print(f"  {l['entity']:<5} {l['part_number'] or '-':<14} qty {l['quantity'] or '-':<6} price {l['unit_price'] or '-':<8} "
                  f"{l['currency_code'] or '?':<4} basis {l['price_basis_qty']} -> {l.get('effective_unit_price', '-')}  "
                  f"lead {l['lead_time_days'] if l['lead_time_days'] is not None else '?'}d  freight {l['freight_amount'] if l['freight_amount'] is not None else '?'}  "
                  f"goods {l.get('goods_total', '-')}  landed {l.get('landed_total', '-')}")
            for n in l["notes"] + ([f"freight: {l['freight_note']}"] if l["freight_note"] and l["freight_note"] != "included" else []):
                print(f"        note: {n}")
        for c in t["conflicts"]:
            print(f"  CONFLICT {c['entity']}.{c['field']}: {c['values']}")


def cmd_qcheck(a, led):
    run = led.current_run(a.run)
    d = _doc(led, a.doc)
    res = quotes.qcheck(led, run, d, date.fromisoformat(a.today) if a.today else None, a.pass_label)
    prof = json.loads(d["profile_json"])
    prof.setdefault("coverage", {})["quote_checks"] = (
        {"version": quotes.QCHECK_VERSION, "status": "skipped", "reason": res["note"]} if res.get("not_a_quote") else
        {"version": quotes.QCHECK_VERSION, "status": "ran", "findings": len(res["findings"])})
    led.db.execute("UPDATE documents SET profile_json=? WHERE doc_id=?", (json.dumps(prof), d["doc_id"]))
    print(f"quote checks: {len(res['findings'])} finding(s)" + (f" ({res['note']})" if res.get("note") else ""))


def _human(led, a, tool, status=None, label=None):
    run = led.current_run(a.run)
    with led.action(run, tool, role="human", args={"finding": a.finding, "label": label, "note": a.note}) as act:
        if status:
            led.set_finding_status(a.finding, status)
        if label:
            led.add_feedback(a.finding, label, a.note)
        act["output_refs"] = {"finding": a.finding, "status": status, "label": label}
    print(f"F{a.finding}: {status or ''} {label or ''}".strip())


def cmd_confirm(a, led):
    _human(led, a, "confirm", status="confirmed", label=a.label)


def cmd_dismiss(a, led):
    _human(led, a, "dismiss", status="dismissed", label=a.label or "noise")


def cmd_feedback(a, led):
    _human(led, a, "feedback", label=a.label)


def cmd_log(a, led):
    rows = led.db.execute("SELECT * FROM actions ORDER BY action_id DESC LIMIT ?", (a.n,)).fetchall()
    for r in reversed(rows):
        print(f"#{r['action_id']:<5} {r['ts']} run{r['run_id']} {r['role']:<6} {r['tool']:<28} {r['status']:<9} "
              f"{r['duration_ms'] or 0}ms{' CACHE' if r['cache_hit'] else ''}{' ' + r['error'] if r['error'] else ''}")


def cmd_export(a, led):
    out = Path(a.out)
    with out.open("w") as f:
        for r in led.db.execute("SELECT * FROM actions ORDER BY action_id"):
            f.write(json.dumps(dict(r)) + "\n")
    print(f"{out} written")


def cmd_verify(a, led):
    problems = led.verify()
    print("ledger OK" if not problems else "PROBLEMS:\n  " + "\n  ".join(problems))
    return 1 if problems else 0


def cmd_cache(a, led):
    r = led.db.execute("SELECT COUNT(*) n, COALESCE(SUM(hits),0) h FROM cache").fetchone()
    print(f"{r['n']} cache entries, {r['h']} hits")


def main(argv=None):
    p = argparse.ArgumentParser(prog="sr", description=__doc__)
    p.add_argument("--db", help="ledger path (default $SR_DB or ./.second-reader/ledger.db)")
    p.add_argument("--run", type=int, help="run id (default: active run)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("--offline", action="store_true", help="declare this ledger AI-free (one-way)")
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("mode"); s.add_argument("mode", nargs="?", choices=["offline"]); s.set_defaults(fn=cmd_mode)
    s = sub.add_parser("run"); s.add_argument("action", choices=["start", "show"]); s.add_argument("--goal")
    s.set_defaults(fn=cmd_run)
    s = sub.add_parser("ingest"); s.add_argument("files", nargs="+"); s.add_argument("--goal-tag")
    s.add_argument("--no-cache", action="store_true"); s.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("map"); s.add_argument("doc"); s.add_argument("--set", action="append", default=[],
                                                                      metavar="role=Column")
    s.add_argument("--unset", action="append", default=[]); s.set_defaults(fn=cmd_map)
    s = sub.add_parser("check"); s.add_argument("doc", nargs="?"); s.add_argument("--only", action="append")
    s.add_argument("--today", help="YYYY-MM-DD reference date"); s.add_argument("--param", action="append")
    s.add_argument("--no-cache", action="store_true"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("brief"); s.add_argument("--out"); s.add_argument("--top", type=int, default=15)
    s.add_argument("--current", action="store_true", help="only the active run's findings"); s.set_defaults(fn=cmd_brief)
    s = sub.add_parser("report", help="self-contained HTML report"); s.add_argument("--out", required=True); s.add_argument("--title")
    s.add_argument("--current", action="store_true"); s.add_argument("--embed-pages", action="store_true", help="embed cited PDF pages as images")
    s.set_defaults(fn=cmd_report)
    s = sub.add_parser("offline-run", help="no-AI, no-network pipeline: read -> check -> compare -> HTML report")
    s.add_argument("inputs", nargs="+", help="files and/or folders"); s.add_argument("--out", required=True)
    s.add_argument("--title"); s.add_argument("--goal"); s.add_argument("--today"); s.add_argument("--embed-pages", action="store_true")
    s.add_argument("--quiet", action="store_true", help="print counts and paths only (nothing derived from the documents)")
    s.add_argument("--rfq-file"); s.add_argument("--part"); s.add_argument("--qty"); s.add_argument("--need-by-days", type=int)
    s.add_argument("--need-by-date"); s.add_argument("--bid-price"); s.add_argument("--currency"); s.add_argument("--order-date")
    s.add_argument("--base"); s.add_argument("--fx", action="append"); s.set_defaults(fn=cmd_offline_run)
    s = sub.add_parser("findings"); s.add_argument("--status", choices=["open", "confirmed", "dismissed"])
    s.add_argument("--severity", choices=["high", "medium", "low", "info"]); s.set_defaults(fn=cmd_findings)
    s = sub.add_parser("drill"); s.add_argument("finding", type=int); s.add_argument("--context", type=int, default=2)
    s.set_defaults(fn=cmd_drill)
    for name, fn in (("confirm", cmd_confirm), ("dismiss", cmd_dismiss), ("feedback", cmd_feedback)):
        s = sub.add_parser(name); s.add_argument("finding", type=int); s.add_argument("--note")
        s.add_argument("--label", choices=["useful", "noise", "already-known"], required=(name == "feedback"))
        s.set_defaults(fn=fn)
    s = sub.add_parser("extract", help="LLM extraction contract: prepare a payload, commit the doer's JSON, compare passes")
    s.add_argument("action", choices=["prepare", "commit", "compare", "local"]); s.add_argument("doc")
    s.add_argument("--pass", dest="pass_label", default="A"); s.add_argument("--model", default="haiku")
    s.add_argument("--role", choices=["haiku", "sonnet", "opus", "code"]); s.add_argument("--input")
    s.add_argument("--out"); s.add_argument("--max-chars", type=int, default=extract.MAX_CHUNK)
    s.add_argument("--tokens-in", type=int); s.add_argument("--tokens-out", type=int)
    s.add_argument("--a", default="A"); s.add_argument("--b", default="B")
    s.add_argument("--qty", type=float, help="local reader: the quantity the buyer asked for (selects a price-break row)")
    s.add_argument("--no-cache", action="store_true"); s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("batch", help="several documents per doer call: prepare batches / commit a batch answer")
    s.add_argument("action", choices=["prepare", "commit"]); s.add_argument("docs", nargs="*")
    s.add_argument("--ids", nargs="*", default=[], help="commit: the doc ids that were in the batch")
    s.add_argument("--pass", dest="pass_label", default="A"); s.add_argument("--model", default="haiku")
    s.add_argument("--role", choices=["haiku", "sonnet", "opus", "code"]); s.add_argument("--input")
    s.add_argument("--out-dir"); s.add_argument("--budget", type=int, default=extract.BATCH_BUDGET)
    s.add_argument("--max-docs", type=int, default=extract.BATCH_MAX_DOCS)
    s.add_argument("--tokens-in", type=int); s.add_argument("--tokens-out", type=int)
    s.add_argument("--no-cache", action="store_true"); s.set_defaults(fn=cmd_batch)
    s = sub.add_parser("page", help="render a PDF page to a PNG so a human can check the evidence"); s.add_argument("doc")
    s.add_argument("page", type=int); s.add_argument("--out"); s.set_defaults(fn=cmd_page)
    s = sub.add_parser("rfq", help="the buyer's request + quote comparison")
    s.add_argument("action", choices=["set", "add", "load", "show", "compare"])
    s.add_argument("--part"); s.add_argument("--qty"); s.add_argument("--need-by-days", type=int); s.add_argument("--need-by-date")
    s.add_argument("--bid-price", help="what we bid our own customer per unit"); s.add_argument("--currency", help="currency of the bid price")
    s.add_argument("--order-date"); s.add_argument("--base", help="base currency, default EUR")
    s.add_argument("--fx", action="append", help="CCY=rate, units of CCY per 1 base (1 EUR = 1.08 USD -> USD=1.08)")
    s.add_argument("--file"); s.add_argument("--pass", dest="pass_label"); s.set_defaults(fn=cmd_rfq)
    s = sub.add_parser("facts"); s.add_argument("doc"); s.add_argument("--pass", dest="pass_label")
    s.add_argument("--unverified", action="store_true"); s.set_defaults(fn=cmd_facts)
    s = sub.add_parser("quotes"); s.add_argument("docs", nargs="*"); s.add_argument("--pass", dest="pass_label", default="A")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_quotes)
    s = sub.add_parser("qcheck"); s.add_argument("doc"); s.add_argument("--today")
    s.add_argument("--pass", dest="pass_label", default="A"); s.set_defaults(fn=cmd_qcheck)
    s = sub.add_parser("log"); s.add_argument("-n", type=int, default=30); s.set_defaults(fn=cmd_log)
    s = sub.add_parser("export"); s.add_argument("out"); s.set_defaults(fn=cmd_export)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    sub.add_parser("cache").set_defaults(fn=cmd_cache)

    a = p.parse_args(argv)
    try:
        if a.cmd == "offline-run" and not a.db and not os.environ.get("SR_DB"):
            a.db = str(Path(a.out).with_suffix(".ledger.db"))
        led = Ledger(a.db)
        rc = a.fn(a, led)
        led.close()
        return rc or 0
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
