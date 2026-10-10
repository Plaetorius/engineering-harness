"""Self-contained HTML report: one file, no JavaScript, no external resources, everything escaped.

Content comes from the ledger (findings with evidence, the RFQ comparison, coverage, audit trail). Text copied from source
documents is untrusted: it is HTML-escaped and clipped, and the page carries a CSP that forbids scripts and network loads.
"""
import base64
import html
import json
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import pdfdoc, rfq
from .checks import clip

SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
CSS = """
:root{--fg:#1b1f24;--muted:#5b6672;--line:#d8dee4;--bg:#fff;--soft:#f6f8fa;--high:#b42318;--medium:#b54708;--low:#175cd3;--info:#475467;--ok:#067647}
*{box-sizing:border-box}body{font:14px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:var(--fg);background:var(--bg);margin:0}
main{max-width:1080px;margin:0 auto;padding:24px 20px 64px}h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.muted{color:var(--muted)}.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600;border:1px solid currentColor}
.b-high{color:var(--high)}.b-medium{color:var(--medium)}.b-low{color:var(--low)}.b-info{color:var(--info)}.b-ok{color:var(--ok)}
.banner{border:1px solid var(--line);background:var(--soft);padding:10px 14px;border-radius:8px;margin:12px 0}
.card{border:1px solid var(--line);border-left:4px solid var(--info);border-radius:6px;padding:10px 14px;margin:10px 0;background:#fff;break-inside:avoid}
.card.high{border-left-color:var(--high)}.card.medium{border-left-color:var(--medium)}.card.low{border-left-color:var(--low)}
.card h3{font-size:14px;margin:0 0 4px}.meta{font-size:12px;color:var(--muted);margin:4px 0}
.ev{font-size:12.5px;background:var(--soft);border-radius:4px;padding:6px 8px;margin:4px 0;overflow-wrap:anywhere}
mark{background:#fde68a;padding:0 2px;border-radius:2px}code{font-family:ui-monospace,Menlo,monospace;font-size:12px}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:var(--soft)}td.num{text-align:right;font-variant-numeric:tabular-nums}tr.best td{background:#ecfdf3}tr.dq td{color:var(--muted)}
ul.flags{margin:2px 0 0 16px;padding:0;font-size:12px}img.page{max-width:100%;border:1px solid var(--line);margin:6px 0}
details{margin:6px 0}summary{cursor:pointer;color:var(--muted)}
@media print{.noprint{display:none}body{font-size:11.5px}main{padding:0}}
"""


def esc(x):
    return html.escape("" if x is None else str(x), quote=True)


def _fmt(x, nd=2):
    return "-" if x is None else f"{x:,.{nd}f}"


def evidence_items(led, finding_id, limit=4):
    recs = led.db.execute("SELECT r.* FROM finding_evidence e JOIN records r USING(record_id) WHERE e.finding_id=? "
                          "ORDER BY r.record_id", (finding_id,)).fetchall()
    items, rows = [], defaultdict(list)
    for r in recs:
        m = re.match(r"^(.*)!R(\d+)C(\d+)$", r["locator"])
        if m:
            rows[(m.group(1), int(m.group(2)))].append(r)
            continue
        item = {"kind": "other", "locator": r["locator"].split("#")[0], "field": r["field"], "value": r["raw_text"],
                "pass": r["pass_label"], "note": r["verify_note"], "verified": bool(r["verified"]), "doc_id": r["doc_id"]}
        if r["locator"].startswith("chars:"):
            t = led.db.execute("SELECT text FROM doc_text WHERE doc_id=?", (r["doc_id"],)).fetchone()
            s0, e0 = map(int, r["locator"][6:].split("#")[0].split("-"))
            if t:
                text = t["text"]
                item.update(kind="text", before=" ".join(text[max(0, s0 - 90):s0].split()), quoted=" ".join(text[s0:e0].split()),
                            after=" ".join(text[e0:e0 + 90].split()), where=pdfdoc.locate(led.db, r["doc_id"], s0, e0))
        items.append(item)
    for (sheet, row), rs in list(rows.items())[:limit]:
        items.append({"kind": "table", "locator": f"{sheet}!R{row}", "cells": {r["field"]: r["raw_text"] for r in rs}})
    return items[:limit + 2]


def _evidence_html(items, embed=None):
    out = []
    for it in items:
        if it["kind"] == "table":
            cells = ", ".join(f"{esc(k)}=<code>{esc(clip(v, 80))}</code>" for k, v in it["cells"].items())
            out.append(f'<div class="ev"><code>{esc(it["locator"])}</code> {cells}</div>')
        elif it["kind"] == "text":
            w = it.get("where")
            page = ""
            if w:
                page = f" · page {w['page']}" + (f" · OCR confidence {w['min_conf']:.0f}%" if w["min_conf"] is not None else "")
                if embed is not None:
                    embed.add((it["doc_id"], w["page"]))
            flag = "" if it["verified"] else ' <span class="badge b-high">unverified</span>'
            note = f' <span class="muted">[{esc(it["note"])}]</span>' if it.get("note") else ""
            out.append(f'<div class="ev"><span class="muted">{esc(it["pass"] + " " if it["pass"] else "")}{esc(it["field"])}</span>'
                       f'{flag}{note}{esc(page)}<br>…{esc(clip(it["before"], 90))} <mark>{esc(clip(it["quoted"], 160))}</mark> '
                       f'{esc(clip(it["after"], 90))}…</div>')
        else:
            out.append(f'<div class="ev"><code>{esc(it["locator"])}</code> {esc(it["field"])}={esc(clip(it["value"], 100))}</div>')
    return "".join(out)


def render(led, run_id=None, title=None, embed_pages=False, max_findings=60):
    where, args = ("WHERE f.run_id=?", [run_id]) if run_id else ("", [])
    findings = led.db.execute(f"SELECT f.* FROM findings f {where}", args).fetchall()
    findings = [f for f in findings if f["status"] != "dismissed"]
    findings.sort(key=lambda f: (SEV_ORDER[f["severity"]], -f["count"], f["finding_id"]))
    docs = led.db.execute("SELECT * FROM documents WHERE ingest_status='ingested' ORDER BY doc_id").fetchall()
    roles = Counter(r["role"] for r in led.db.execute("SELECT role FROM actions"))
    models = sorted({r["model"] for r in led.db.execute("SELECT DISTINCT model FROM actions WHERE model IS NOT NULL")})
    offline = led.offline
    pages_needed = set() if embed_pages else None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    h = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:\">"
         f"<title>{esc(title or 'Second-reader report')}</title><style>{CSS}</style></head><body><main>",
         f"<h1>{esc(title or 'Second-reader report')}</h1><div class='muted'>Generated {now} · {len(docs)} document(s) · "
         f"{len(findings)} finding(s) to look at</div>"]
    if offline:
        h.append("<div class='banner'><span class='badge b-ok'>OFFLINE</span> Every value in this report was read by local rules and "
                 "checked by code on this machine. No AI model saw any document and nothing was sent to any service. Rule-based "
                 "reading covers common phrasings only: read the coverage notes and what is missing.</div>")
    else:
        used = ", ".join(esc(m) for m in models if m != "local") or "none"
        h.append(f"<div class='banner'><span class='badge b-info'>AI-ASSISTED</span> Values were read by: {used} (plus local rules); "
                 f"every value was verified against the source text by code. Document text was sent to those models.</div>")
    h.append("<div class='banner'>Findings are rule hits with evidence, not conclusions. Quoted text is copied from the source "
             "documents and is untrusted. Silence is not a clean bill of health.</div>")

    if rfq.lines(led):
        try:
            cmp = rfq.build_comparison(led)
        except Exception as exc:                                 # a report must still render
            cmp = None
            h.append(f"<p class='muted'>Quote comparison unavailable: {esc(exc)}</p>")
        if cmp:
            base = cmp["settings"]["base"]
            h.append("<h2>Quote comparison</h2>")
            h.append(f"<div class='muted'>Base currency {esc(base)} · FX (units per 1 {esc(base)}): "
                     f"{esc(', '.join(f'{k}={v}' for k, v in cmp['settings']['fx'].items()) or 'none set')} · order date "
                     f"{esc(cmp['settings']['order_date'])}</div>")
            for ln in cmp["lines"]:
                h.append(f"<h3>{esc(rfq.fmtq(ln['quantity']))} × {esc(ln['part'])} "
                         f"<span class='muted'>(needed within {esc(ln['need_by_days'])} days · bid {_fmt(ln['bid_total'])} {esc(base)})</span></h3>")
                if not ln["quotes"]:
                    h.append("<p><span class='badge b-high'>no usable quote</span></p>")
                    continue
                h.append("<table><tr><th>#</th><th>Supplier</th><th>Status</th><th>Unit price</th><th>Qty</th><th>Goods</th><th>Freight</th>"
                         f"<th>Landed ({esc(base)})</th><th>Lead</th><th>Margin</th><th>Notes</th></tr>")
                for i, q in enumerate(ln["quotes"], 1):
                    cls = "best" if q is ln["best"] else ("dq" if q["status"] == "disqualified" else "")
                    chip = {"compliant": "b-ok", "conditional": "b-medium", "disqualified": "b-high"}[q["status"]]
                    notes = "".join(f"<li>✗ {esc(r)}</li>" for r in q["reasons"]) + "".join(f"<li>! {esc(f)}</li>" for f in q["flags"])
                    h.append(f"<tr class='{cls}'><td>{i}</td><td>{esc(q['label'])}{' <b>★ recommended</b>' if q is ln['best'] else ''}</td>"
                             f"<td><span class='badge {chip}'>{esc(q['status'])}</span></td>"
                             f"<td class='num'>{esc(q['currency'] or '?')} {_fmt(q['effective_unit_price'], 4)}</td><td class='num'>{esc(rfq.fmtq(q['qty']))}</td>"
                             f"<td class='num'>{_fmt(q['goods_base'])}</td><td class='num'>{_fmt(q['freight_base'])}</td>"
                             f"<td class='num'><b>{_fmt(q['landed_base'])}</b></td><td class='num'>{esc(q['lead_time_days'] if q['lead_time_days'] is not None else '?')} d</td>"
                             f"<td class='num'>{_fmt(q['margin'])}<br><span class='muted'>{esc(q['margin_pct'] or '-')}%</span></td>"
                             f"<td><ul class='flags'>{notes}</ul></td></tr>")
                h.append("</table>")
                if ln["best"]:
                    b = ln["best"]
                    h.append(f"<p><b>Recommended: {esc(b['supplier'])}</b> — landed {_fmt(b['landed_base'])} {esc(base)}, margin "
                             f"<b>{_fmt(b['margin'])} {esc(base)} ({esc(b['margin_pct'])}% of the bid)</b>. "
                             + (f"The cheapest option, {esc(ln['cheapest']['supplier'])}, is not recommended (see notes)." if ln["cheapest"] is not ln["best"] else "")
                             + "</p>")
                else:
                    h.append("<p><span class='badge b-high'>no fully compliant, fully costed quote</span> A person must decide.</p>")

    h.append("<h2>Read this first</h2>")
    if not findings:
        h.append("<p class='muted'>No findings.</p>")
    for f in findings[:max_findings]:
        h.append(f"<div class='card {esc(f['severity'])}'><h3><span class='badge b-{esc(f['severity'])}'>{esc(f['severity'].upper())}</span> "
                 f"<span class='muted'>F{f['finding_id']} · {esc(f['kind'])} · confidence {esc(f['confidence'])}"
                 f"{' · CONFIRMED' if f['status'] == 'confirmed' else ''}</span><br>{esc(f['claim'])}</h3>")
        meta = [f"check {esc(f['check_id'])} v{esc(f['check_version'])}", f"count {f['count']}"]
        if f["impact_amount"]:
            meta.append(f"impact ≈ {esc(f['impact_amount'])}")
        if f["doc_id"]:
            meta.append(f"doc {f['doc_id']}")
        h.append(f"<div class='meta'>{' · '.join(meta)} · <code>sr drill {f['finding_id']}</code></div>")
        h.append(_evidence_html(evidence_items(led, f["finding_id"]), pages_needed))
        h.append("</div>")
    if len(findings) > max_findings:
        h.append(f"<p class='muted'>{len(findings) - max_findings} more findings not shown (lower ranked): "
                 f"{esc(', '.join('F' + str(f['finding_id']) for f in findings[max_findings:max_findings + 40]))}</p>")

    if pages_needed:
        h.append("<h2>Cited pages</h2><p class='muted'>Rendered locally so you can check the evidence by eye.</p>")
        for did, page in sorted(pages_needed)[:6]:
            d = led.get_document(did)
            if d["path"].lower().endswith(".pdf") and Path(d["path"]).exists():
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        png = pdfdoc.render_page(d["path"], page, Path(tmp) / "p.png", dpi=80)
                        b64 = base64.b64encode(Path(png).read_bytes()).decode()
                    h.append(f"<details><summary>{esc(Path(d['path']).name)} · page {page}</summary>"
                             f"<img class='page' alt='page {page}' src='data:image/png;base64,{b64}'></details>")
                except Exception:
                    h.append(f"<p class='muted'>page {page} of {esc(Path(d['path']).name)} could not be rendered</p>")

    h.append("<h2>Documents and coverage</h2><table><tr><th>Doc</th><th>File</th><th>Kind</th><th>Reading</th><th>Checks run</th><th>Caveats</th></tr>")
    for d in docs:
        prof = json.loads(d["profile_json"])
        caveats, reading = [], ""
        if prof.get("kind") == "text":
            kind = f"text/{prof['source_kind']} · {prof['chars']} chars"
            ex = led.db.execute("SELECT extractor, COUNT(*) n, SUM(verified) v FROM records WHERE doc_id=? AND pass_label IS NOT NULL "
                                "GROUP BY extractor", (d["doc_id"],)).fetchall()
            reading = "<br>".join(f"{esc(r['extractor'])}: {r['n']} facts, {r['v']} verified" for r in ex) or "not read yet"
            if prof.get("pages"):
                ocr = [p for p in prof["pages"] if p["method"].startswith("ocr")]
                if ocr:
                    reading += f"<br>OCR on {len(ocr)} page(s), mean confidence " + ", ".join(f"{p['mean_conf']:.0f}%" for p in ocr)
            for k, v in prof.get("coverage", {}).items():
                if v["status"] == "skipped":
                    caveats.append(f"{k} not applied: {v['reason']}")
            if prof.get("meta", {}).get("soft_hyphens_normalized"):
                caveats.append(f"{prof['meta']['soft_hyphens_normalized']} soft-hyphen characters converted to hyphens (PDF font artefact)")
            if prof.get("meta", {}).get("unreadable_pages"):
                caveats.append(f"page(s) {prof['meta']['unreadable_pages']} unreadable by OCR — NOT checked")
            for a in prof.get("meta", {}).get("attachments") or []:
                caveats.append(f"attachment not analysed: {clip(a.get('filename') or a.get('content_type'), 40)}")
        else:
            kind = f"table · {sum(s['data_rows'] for s in prof['sheets'].values())} rows"
            m = json.loads(d["mapping_json"] or "{}")
            reading = esc(", ".join(f"{r}→{v['col']}" for r, v in m.items()) or "no roles mapped")
            caveats += [f"{x['role']}: {x['reason']}" for x in prof.get("mapping_notes", [])]
        ran = [f"{k} ({v['findings']})" for k, v in prof.get("coverage", {}).items() if v["status"] == "ran"]
        h.append(f"<tr><td>{d['doc_id']}</td><td>{esc(Path(d['path']).name)}<br><span class='muted'><code>{esc(d['sha256'][:12])}</code></span></td>"
                 f"<td>{esc(kind)}</td><td>{reading}</td><td>{esc(', '.join(ran) or 'none')}</td>"
                 f"<td>{'<br>'.join(esc(c) for c in caveats) or '–'}</td></tr>")
    h.append("</table>")

    n_act = led.db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    hits = led.db.execute("SELECT COUNT(*) FROM actions WHERE cache_hit=1").fetchone()[0]
    fb = Counter(r["label"] for r in led.db.execute("SELECT label FROM feedback"))
    h.append("<h2>Audit trail</h2>")
    h.append(f"<p>{n_act} logged actions ({', '.join(f'{k}: {v}' for k, v in sorted(roles.items()))}); {hits} served from cache. "
             f"Ledger <code>{esc(led.path.name)}</code> is append-only; every finding opens to its source with <code>sr drill &lt;F&gt;</code>. "
             f"Reviewer feedback so far: {esc(', '.join(f'{k} {v}' for k, v in fb.items()) or 'none')}.</p>")
    h.append("</main></body></html>")
    return "".join(h)
