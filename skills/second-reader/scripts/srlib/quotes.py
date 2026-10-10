"""Quote table: verified facts -> one row per offered line with deterministic derivations, plus single-document
quote checks. Derived values are computed by code from verified facts only and always carry a note when an
assumption was needed (business-day conversion, assumed price basis, ...)."""
import re
from datetime import date, timedelta
from decimal import Decimal

from .extract import (EXTRACT_VERSION, LINE_ENTITY, canon, canon_currency, clip_text, derive_basis, derive_freight,
                      derive_lead, norm_cmp)
from .numparse import parse_date

QCHECK_VERSION = "2"
QUOTE_CUE = re.compile(r"\b(quot\w*|offer\w*|price\w*|pricing|rfq|inquiry|enquiry|angebot\w*|preis\w*|anfrage|unit price|per piece|each|lead time|delivery)\b", re.I)
REQUIRED = [("part_number", "medium"), ("unit_price", "high"), ("quantity", "high"), ("currency", "high"), ("lead_time", "medium"),
            ("valid_until", "medium"), ("freight", "medium")]
MONEY = Decimal("0.01")


def _first(rows):
    return rows[0] if rows else None


def build_table(led, doc_id, pass_label="A"):
    recs = led.db.execute("SELECT * FROM records WHERE doc_id=? AND pass_label=? AND verified=1 ORDER BY record_id",
                          (doc_id, pass_label)).fetchall()
    by = {}
    for r in recs:
        by.setdefault((r["entity"], r["field"]), []).append(r)
    conflicts = []
    for (ent, field), rows in by.items():
        if len({canon(field, r["raw_text"], r["value_norm"]) for r in rows}) > 1:
            conflicts.append({"entity": ent, "field": field, "records": [r["record_id"] for r in rows],
                              "values": [r["raw_text"] for r in rows]})
    doc_facts = {f: _first(rows) for (ent, f), rows in by.items() if ent == "doc"}
    lines = []
    for ent in sorted({e for (e, _) in by if e and LINE_ENTITY.match(e)}, key=lambda e: (len(e), e)):
        got = {f: _first(rows) for (e, f), rows in by.items() if e == ent}
        pick = lambda f: got.get(f) or doc_facts.get(f)              # line value wins, else document-level
        row = {"entity": ent, "records": {f: r["record_id"] for f, r in got.items()}, "notes": []}
        for f in ("part_number", "alternate_part_number", "currency", "price_basis", "lead_time", "freight"):
            r = pick(f)
            row[f] = r["raw_text"] if r else None
            if r and f not in got:
                row["records"][f] = r["record_id"]
        qty, price = _first(by.get((ent, "quantity"), [])), _first(by.get((ent, "unit_price"), []))
        row["quantity"] = Decimal(qty["value_norm"]) if qty else None
        row["unit_price"] = Decimal(price["value_norm"]) if price else None
        mq = pick("min_order_qty")
        row["min_order_qty"] = Decimal(mq["value_norm"]) if mq else None
        row["currency_code"] = canon_currency(row["currency"]) if row["currency"] else None
        basis, note = derive_basis(row["price_basis"])
        row["price_basis_qty"] = basis
        if note:
            row["notes"].append(note)
        if row["unit_price"] is not None and basis:
            row["effective_unit_price"] = (row["unit_price"] / basis).quantize(Decimal("0.0001"))
            if row["quantity"] is not None:
                row["goods_total"] = (row["effective_unit_price"] * row["quantity"]).quantize(MONEY)
        days, note = derive_lead(row["lead_time"])
        row["lead_time_days"] = days
        if note and row["lead_time"] is not None:
            row["notes"].append(f"lead time: {note}")
        freight, note = derive_freight(row["freight"])
        row["freight_amount"], row["freight_note"] = freight, note
        if row.get("goods_total") is not None and freight is not None:
            row["landed_total"] = (row["goods_total"] + freight).quantize(MONEY)
        lines.append(row)
    vu = doc_facts.get("valid_until")
    return {"doc_id": doc_id, "pass": pass_label, "supplier": doc_facts["supplier_name"]["raw_text"]
            if "supplier_name" in doc_facts else None,
            "valid_until": date.fromisoformat(vu["value_norm"]) if vu else None,
            "validity_period": doc_facts["validity_period"]["raw_text"] if "validity_period" in doc_facts else None,
            "incoterms": doc_facts["incoterms"]["raw_text"] if "incoterms" in doc_facts else None,
            "payment_terms": doc_facts["payment_terms"]["raw_text"] if "payment_terms" in doc_facts else None,
            "doc_records": {f: r["record_id"] for f, r in doc_facts.items()}, "lines": lines, "conflicts": conflicts}


def _anchor(table, line=None):
    """A record to cite when the finding is about something absent."""
    if line:
        for f in ("part_number", "unit_price", "quantity"):
            if f in line["records"]:
                return line["records"][f]
    for f in ("supplier_name", "valid_until"):
        if f in table["doc_records"]:
            return table["doc_records"][f]
    return next(iter(table["doc_records"].values()), None) or next(
        (v for l in table["lines"] for v in l["records"].values()), None)


def qcheck(led, run_id, doc, today=None, pass_label="A"):
    """Single-document quote checks. Returns list of finding ids. Idempotent per (check, key)."""
    today = today or date.today()
    t = build_table(led, doc["doc_id"], pass_label)
    drafts = []        # (check_id, key, severity, confidence, kind, claim, anchor_record, count, detail)
    text = (led.db.execute("SELECT text FROM doc_text WHERE doc_id=?", (doc["doc_id"],)).fetchone() or {"text": ""})["text"]
    if not any(l["unit_price"] is not None for l in t["lines"]) and not QUOTE_CUE.search(text):
        # not a quotation (e.g. a test certificate): applying quote checks would only produce noise
        with led.transaction():
            led.db.execute("DELETE FROM findings WHERE doc_id=? AND check_id LIKE 'quote.%' AND status='open'", (doc["doc_id"],))
        return {"findings": [], "table": t, "not_a_quote": True,
                "note": "not recognised as a quotation: no quote checks applied, and no extraction schema exists for this document type"}
    if not t["lines"] and not t["doc_records"]:
        return {"findings": [], "table": t, "note": "no verified facts: nothing to check"}
    if not any(l["unit_price"] is not None for l in t["lines"]):
        anchor = _anchor(t)
        if anchor is not None:
            drafts.append(("quote.no_offer", "no_priced_line", "info", "medium", "concern",
                           "no priced offer was found in this document (a decline, a question, or a quote the "
                           "extractor could not read): it contributes nothing to a comparison", anchor, 1, {}))
        t["lines"] = [] if not t["lines"] else t["lines"]
        required = []
    else:
        required = REQUIRED
    for field, sev in required:
        if field == "valid_until":
            missing = [] if t["valid_until"] else [None]
        elif field == "freight":
            missing = [l for l in t["lines"] if l["freight"] is None]
        elif field in ("currency", "lead_time"):
            missing = [l for l in t["lines"] if l[field] is None]
        else:
            missing = [l for l in t["lines"] if l.get(field) is None]
        if missing and (t["lines"] or field == "valid_until"):
            what = ("the quote's validity is relative (" + repr(t["validity_period"]) + "), so its expiry date is unknown"
                    if t.get("validity_period") else "the quote has no validity date") if field == "valid_until" else \
                f"{len(missing)} of {len(t['lines'])} quoted lines have no {field.replace('_', ' ')} stated"
            drafts.append(("quote.missing", field, sev, "high", "concern", what, (t["doc_records"].get("validity_period") if field == "valid_until" and t.get("validity_period") else
                                                                 _anchor(t, missing[0] if missing and missing[0] else None)),
                           len(missing), {"field": field, "entities": [l["entity"] for l in missing if l]}))
    if t["valid_until"]:
        vu = t["valid_until"]
        rec = t["doc_records"]["valid_until"]
        if vu < today:
            drafts.append(("quote.expired", "valid_until", "high", "high", "defect",
                           f"the quote expired on {vu.isoformat()} ({(today - vu).days} days before {today})", rec, 1, {}))
        elif vu <= today + timedelta(days=7):
            drafts.append(("quote.expiring", "valid_until", "medium", "high", "concern",
                           f"the quote expires on {vu.isoformat()} ({(vu - today).days} days away)", rec, 1, {}))
    odd = [l for l in t["lines"] if l["price_basis_qty"] != 1]
    if odd:
        unk = [l for l in odd if l["price_basis_qty"] is None]
        drafts.append(("quote.price_basis", "not_per_unit", "high", "high", "concern",
                       f"{len(odd)} line(s) are not priced per single unit "
                       + ("(" + "; ".join(f"{l['entity']}: {l['price_basis'] or ''} -> per {l['price_basis_qty']}"
                                        for l in odd[:3]) + ")") + (f"; {len(unk)} basis unrecognised" if unk else "")
                       + " - comparing raw unit prices would be wrong",
                       odd[0]["records"].get("price_basis") or _anchor(t, odd[0]), len(odd), {}))
    alt = [l for l in t["lines"] if l["alternate_part_number"]]
    if alt:
        drafts.append(("quote.substitute", "alternate_part", "medium", "high", "concern",
                       f"{len(alt)} line(s) offer a substitute / superseding part number "
                       f"(e.g. {clip_text(alt[0]['alternate_part_number'], 40)}); needs buyer approval",
                       alt[0]["records"]["alternate_part_number"], len(alt), {}))
    unclear = [l for l in t["lines"] if l["freight"] is not None and l["freight_amount"] is None]
    if unclear:
        drafts.append(("quote.freight_unclear", "freight", "medium", "medium", "concern",
                       f"freight is mentioned but its cost is unclear for {len(unclear)} line(s): landed cost unknown",
                       unclear[0]["records"]["freight"], len(unclear), {}))
    badlead = [l for l in t["lines"] if l["lead_time"] is not None and l["lead_time_days"] is None]
    if badlead:
        drafts.append(("quote.lead_time_unreadable", "lead_time", "low", "medium", "concern",
                       f"lead time text could not be read as a duration for {len(badlead)} line(s): "
                       f"{clip_text(badlead[0]['lead_time'], 50)!r}", badlead[0]["records"]["lead_time"], len(badlead), {}))
    for c in t["conflicts"]:
        drafts.append(("quote.conflict", f"{c['entity']}:{c['field']}", "high", "high", "concern",
                       f"the document gives different values for {c['field']} on {c['entity']}: "
                       + " vs ".join(clip_text(v, 30) for v in c["values"][:3]), c["records"][0], 1, {}))
    amb = led.db.execute("SELECT record_id, field, raw_text FROM records WHERE doc_id=? AND pass_label=? AND verified=1 "
                         "AND verify_note LIKE '%ambiguous_sep%'", (doc["doc_id"], pass_label)).fetchall()
    if amb:
        drafts.append(("quote.ambiguous_number", "ambiguous_sep", "medium", "medium", "concern",
                       f"{len(amb)} number(s) like {amb[0]['raw_text']!r} could be a thousands or a decimal separator",
                       amb[0]["record_id"], len(amb), {}))
    low = led.db.execute("SELECT record_id, field, raw_text, verify_note, locator FROM records WHERE doc_id=? AND pass_label=? "
                         "AND verified=1 AND verify_note LIKE '%low_ocr_confidence%' ORDER BY record_id",
                         (doc["doc_id"], pass_label)).fetchall()
    if low:
        def conf(r):
            return int(re.search(r"low_ocr_confidence:(\d+)", r["verify_note"]).group(1))
        shown = "; ".join(f"{r['field']} {r['raw_text']!r} ({conf(r)}%)" for r in low[:3])
        drafts.append(("ocr.low_confidence", "low_conf", "high", "high", "concern",
                       f"{len(low)} value(s) were read from a scanned page with low OCR confidence: {shown}. "
                       f"Confirm against the page image (`sr page`) before relying on them",
                       low[0]["record_id"], len(low), {"records": [r["record_id"] for r in low]}))
    ids, keep = [], {}
    with led.transaction():
        for check_id, key, sev, conf, kind, claim, rec, count, detail in drafts:
            if rec is None:
                continue
            keep.setdefault(check_id, set()).add(key)
            ids.append(led.upsert_finding(run_id, doc["doc_id"], check_id, QCHECK_VERSION, key, sev, conf, kind,
                                          f"[{t['supplier'] or 'supplier unknown'}] {claim}", [rec], count=count,
                                          detail=detail))
        for row in led.db.execute("SELECT finding_id, check_id, dedupe_key FROM findings WHERE doc_id=? AND "
                                  "(check_id LIKE 'quote.%' OR check_id LIKE 'ocr.%') AND status='open'", (doc["doc_id"],)).fetchall():
            if row["dedupe_key"] not in keep.get(row["check_id"], set()) and not led.db.execute(
                    "SELECT 1 FROM feedback WHERE finding_id=?", (row["finding_id"],)).fetchone():
                led.db.execute("DELETE FROM findings WHERE finding_id=?", (row["finding_id"],))
    return {"findings": ids, "table": t}
