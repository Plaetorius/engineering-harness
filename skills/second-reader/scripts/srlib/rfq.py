"""RFQ model + quote comparison (S4). Everything here is deterministic code over verified facts.

An RFQ line is what the buyer asked for (part, quantity, need-by) plus what we bid our own customer per unit. Each
supplier quote line is matched to it, checked (part, quantity, lead time, validity, currency, freight), costed to a
landed total in the base currency, ranked, and the margin against the bid is computed.

Status per quote line:  compliant | conditional (usable, but a human must resolve a stated issue) | disqualified.
The cheapest quote is never silently the best: when they differ, a finding says why.
"""
import csv
import re
import statistics
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from . import quotes
from .ingest import _norm_header
from .ledger import LedgerError, now

RFQ_VERSION = "1"
Q2 = Decimal("0.01")


def fmtq(d):
    return format(Decimal(d).normalize(), "f")


def norm_part(p):
    return re.sub(r"[^a-z0-9]", "", (p or "").lower())


def match_part(rfq_norm, q_norm):
    """-> 'exact' | 'variant' | None. A variant is a different revision/own number that CONTAINS or EXTENDS ours."""
    if not rfq_norm or not q_norm:
        return None
    if rfq_norm == q_norm:
        return "exact"
    shorter, longer = sorted((rfq_norm, q_norm), key=len)
    if shorter in longer and len(shorter) >= 5:
        return "variant"
    common = 0
    for a, b in zip(rfq_norm, q_norm):
        if a != b:
            break
        common += 1
    if common >= max(5, int(0.8 * len(shorter))) and len(longer) - common <= 2:
        return "variant"
    return None


# ---- settings / lines ---------------------------------------------------------------------------------------------
def get_setting(led, key, default=None):
    row = led.db.execute("SELECT value FROM meta WHERE key=?", (f"rfq.{key}",)).fetchone()
    return row["value"] if row else default


def set_setting(led, key, value):
    led.db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (f"rfq.{key}", str(value)))


def settings(led):
    fx = {r["key"].split(".", 2)[2].upper(): Decimal(r["value"]) for r in led.db.execute(
        "SELECT key, value FROM meta WHERE key LIKE 'rfq.fx.%'")}
    od = get_setting(led, "order_date")
    return {"base": (get_setting(led, "base_currency") or "EUR").upper(), "fx": fx,
            "order_date": date.fromisoformat(od) if od else date.today()}


def add_line(led, part, quantity, need_by_days=None, need_by_date=None, bid_unit_price=None, bid_currency=None,
             label=None, src_doc_id=None):
    if not part or not str(part).strip():
        raise LedgerError("an RFQ line needs a part number")
    q = Decimal(str(quantity))
    if q <= 0:
        raise LedgerError("quantity must be positive")
    if need_by_date and need_by_days is None:
        need_by_days = (date.fromisoformat(need_by_date) - settings(led)["order_date"]).days
    cur = led.db.execute(
        "INSERT INTO rfq_lines(label,part_number,norm_part,quantity,need_by_days,need_by_date,bid_unit_price,bid_currency,"
        "src_doc_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (label, str(part).strip(), norm_part(part), str(q), need_by_days, need_by_date,
         None if bid_unit_price is None else str(Decimal(str(bid_unit_price))), (bid_currency or "").upper() or None,
         src_doc_id, now()))
    return cur.lastrowid


def load_csv(led, path):
    rows = list(csv.reader(open(path, newline="", encoding="utf-8-sig")))
    if len(rows) < 2:
        raise LedgerError("RFQ file needs a header and at least one line")
    head = [_norm_header(h) for h in rows[0]]

    def col(*names):
        for n in names:
            if n in head:
                return head.index(n)
        return None
    ci = {"part": col("partnumber", "partno", "part", "sku", "pn", "itemid", "article"),
          "qty": col("quantity", "qty", "menge"), "days": col("needbydays", "leaddays", "maxleaddays"),
          "date": col("needbydate", "needby", "requireddate", "duedate", "deliverydate"),
          "bid": col("bidprice", "bidunitprice", "bid", "sellprice", "saleprice"), "ccy": col("currency", "bidcurrency", "ccy")}
    if ci["part"] is None or ci["qty"] is None:
        raise LedgerError("RFQ file needs a part-number column and a quantity column")
    ids = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        g = lambda k: r[ci[k]].strip() if ci[k] is not None and ci[k] < len(r) and r[ci[k]].strip() else None
        ids.append(add_line(led, g("part"), g("qty"), int(g("days")) if g("days") else None, g("date"), g("bid"), g("ccy")))
    return ids


def lines(led):
    return led.db.execute("SELECT * FROM rfq_lines ORDER BY rfq_line_id").fetchall()


# ---- comparison -----------------------------------------------------------------------------------------------------
def to_base(amount, ccy, cfg):
    if amount is None or not ccy:
        return None
    if ccy == cfg["base"]:
        return amount
    rate = cfg["fx"].get(ccy)
    return (amount / rate) if rate else None


def build_comparison(led, pass_label=None, doc_ids=None):
    cfg = settings(led)
    rfq = lines(led)
    if not rfq:
        raise LedgerError("no RFQ lines: add them with `sr rfq add` or `sr rfq load`")
    docs = [d for d in led.db.execute("SELECT * FROM documents WHERE doc_type='text' ORDER BY doc_id")
            if not doc_ids or d["doc_id"] in doc_ids]
    entries, notes = [], []
    for d in docs:
        passes = [r["pass_label"] for r in led.db.execute(
            "SELECT DISTINCT pass_label FROM records WHERE doc_id=? AND pass_label IS NOT NULL AND verified=1", (d["doc_id"],))]
        use = pass_label if pass_label in passes else next((p for p in ("A", "L", "B") if p in passes), None)
        if use is None:
            notes.append(f"doc {d['doc_id']} ({Path(d['path']).name}) has no verified extraction yet")
            continue
        t = quotes.build_table(led, d["doc_id"], use)
        entries.append((d, t, use))
    rows = []
    for rl in rfq:
        rq = Decimal(rl["quantity"])
        for d, t, use in entries:
            priced = [l for l in t["lines"] if l["unit_price"] is not None]
            for l in priced:
                kind = match_part(rl["norm_part"], norm_part(l["part_number"]))
                reasons, flags = [], []
                status = "compliant"
                if kind is None and not l["part_number"] and (len(priced) == 1 or len(rfq) == 1):
                    kind = "assumed"
                    flags.append("part number not stated: assumed to be the RFQ item")
                    status = "conditional"
                if kind is None:
                    continue
                if kind == "variant":
                    flags.append(f"different part number ({l['part_number']} vs RFQ {rl['part_number']}): substitute or "
                                 f"revision, needs buyer approval")
                    status = "conditional"
                elif kind == "exact" and l["part_number"] and l["part_number"] != rl["part_number"]:
                    flags.append(f"written {l['part_number']!r}, RFQ {rl['part_number']!r}: same after ignoring punctuation")
                qty = l["quantity"]
                if qty is None:
                    qty_used = rq
                    flags.append("quantity not stated: assumed to be the RFQ quantity")
                    status = "conditional" if status == "compliant" else status
                else:
                    qty_used = qty
                partial = qty_used < rq
                over = qty_used > rq
                if over:
                    flags.append(f"price is quoted for {fmtq(qty_used)} pcs but {fmtq(rq)} are needed: a "
                                 f"minimum quantity or price tier may not apply")
                    status = "conditional" if status == "compliant" else status
                    qty_used = rq                      # cost what we would actually buy
                if partial:
                    reasons.append(f"covers only {fmtq(qty_used)} of {fmtq(rq)} pcs")
                    status = "disqualified"
                eff = l.get("effective_unit_price")
                if eff is None:
                    continue
                goods_native = (eff * qty_used).quantize(Q2, ROUND_HALF_UP)
                goods = to_base(goods_native, l["currency_code"], cfg)
                freight = to_base(l["freight_amount"], l["currency_code"], cfg) if l["freight_amount"] is not None else None
                if l["currency_code"] is None:
                    flags.append("currency not stated")
                    status = "conditional" if status == "compliant" else status
                elif goods is None:
                    flags.append(f"no FX rate for {l['currency_code']} (set with `sr rfq set --fx {l['currency_code']}=<per 1 {cfg['base']}>`)")
                    status = "conditional" if status == "compliant" else status
                if l["freight_amount"] is None:
                    flags.append("freight cost unknown: landed cost is a lower bound")
                    status = "conditional" if status == "compliant" else status
                landed = (goods + freight).quantize(Q2, ROUND_HALF_UP) if goods is not None and freight is not None else None
                lead = l["lead_time_days"]
                if rl["need_by_days"] is not None:
                    if lead is None:
                        flags.append("lead time unknown")
                        status = "conditional" if status == "compliant" else status
                    elif lead > rl["need_by_days"]:
                        reasons.append(f"lead time {lead} d exceeds the required {rl['need_by_days']} d")
                        status = "disqualified"
                if t["valid_until"] is not None and t["valid_until"] < cfg["order_date"]:
                    reasons.append(f"quote expired {t['valid_until'].isoformat()}")
                    status = "disqualified"
                elif t["valid_until"] is None:
                    flags.append("validity unknown" + (f" ({t['validity_period']})" if t.get("validity_period") else ""))
                for n in l["notes"]:
                    if n.startswith("lead time:"):
                        flags.append(n)
                bid = Decimal(rl["bid_unit_price"]) * rq if rl["bid_unit_price"] else None
                bid_base = to_base(bid, rl["bid_currency"] or cfg["base"], cfg) if bid is not None else None
                cost_for_margin = landed if landed is not None else goods
                margin = (bid_base - cost_for_margin).quantize(Q2, ROUND_HALF_UP) if bid_base is not None and cost_for_margin is not None else None
                rows.append({
                    "rfq_line_id": rl["rfq_line_id"], "rfq_part": rl["part_number"], "doc_id": d["doc_id"],
                    "supplier": t["supplier"] or Path(d["path"]).stem, "entity": l["entity"], "pass": use,
                    "label": (t["supplier"] or Path(d["path"]).stem) + (f" [{l['entity']}]" if len(priced) > 1 else ""),
                    "match": kind, "quote_part": l["part_number"], "qty": qty_used, "unit_price": l["unit_price"],
                    "currency": l["currency_code"], "basis": l["price_basis_qty"], "effective_unit_price": eff,
                    "goods_native": goods_native, "goods_base": goods.quantize(Q2) if goods is not None else None,
                    "freight_base": freight.quantize(Q2) if freight is not None else None, "landed_base": landed,
                    "lead_time_days": lead, "valid_until": t["valid_until"].isoformat() if t["valid_until"] else None,
                    "status": status, "reasons": reasons, "flags": flags, "margin": margin,
                    "margin_pct": (margin / bid_base * 100).quantize(Decimal("0.1")) if margin is not None and bid_base else None,
                    "records": l["records"], "freight_incomplete": l["freight_amount"] is None})
    # rank within each RFQ line
    result = []
    for rl in rfq:
        mine = [r for r in rows if r["rfq_line_id"] == rl["rfq_line_id"]]
        key = lambda r: (r["landed_base"] if r["landed_base"] is not None else (r["goods_base"] if r["goods_base"] is not None else Decimal("1e18")))
        order = {"compliant": 0, "conditional": 1, "disqualified": 2}
        mine.sort(key=lambda r: (order[r["status"]], key(r)))
        comp = [r for r in mine if r["status"] == "compliant" and r["landed_base"] is not None]
        best = comp[0] if comp else None
        costed = [r for r in mine if (r["goods_base"] is not None)]
        cheapest = min(costed, key=lambda r: ((r["landed_base"] if r["landed_base"] is not None else r["goods_base"]) / r["qty"]),
                       default=None)
        bid = Decimal(rl["bid_unit_price"]) * Decimal(rl["quantity"]) if rl["bid_unit_price"] else None
        result.append({"rfq_line_id": rl["rfq_line_id"], "part": rl["part_number"], "quantity": Decimal(rl["quantity"]),
                       "need_by_days": rl["need_by_days"], "bid_total": to_base(bid, rl["bid_currency"] or cfg["base"], cfg) if bid else None,
                       "quotes": mine, "best": best, "cheapest": cheapest})
    unanswered = [r["part"] for r in result if not r["quotes"]]
    return {"settings": cfg, "lines": result, "unanswered": unanswered, "notes": notes,
            "documents_considered": len(entries)}


# ---- findings --------------------------------------------------------------------------------------------------------
def run_checks(led, run_id, comparison):
    """Upsert cross-document findings; returns the ids. Every finding cites a verified fact record."""
    ids, keep = [], set()

    def put(doc_id, key, sev, conf, kind, claim, rec, count=1, detail=None, check="rfq.compare"):
        if rec is None:
            return
        keep.add((doc_id, check, key))
        ids.append(led.upsert_finding(run_id, doc_id, check, RFQ_VERSION, key, sev, conf, kind, claim, [rec], count=count,
                                      detail=detail))

    with led.transaction():
        for ln in comparison["lines"]:
            cur = comparison["settings"]["base"]
            qs = ln["quotes"]
            if not qs:
                anchor = led.db.execute("SELECT record_id, doc_id FROM records WHERE pass_label IS NOT NULL AND verified=1 "
                                        "ORDER BY record_id LIMIT 1").fetchone()
                if anchor:
                    put(anchor["doc_id"], f"unquoted:{ln['rfq_line_id']}", "high", "high", "defect",
                        f"RFQ line {ln['part']} x{fmtq(ln['quantity'])} received no usable quote from any supplier",
                        anchor["record_id"], check="rfq.unquoted_line")
            for q in qs:
                rec = q["records"].get("unit_price") or next(iter(q["records"].values()), None)
                tag = f"[{q['supplier']}] "
                for reason in q["reasons"]:
                    sev = "high"
                    put(q["doc_id"], f"{ln['rfq_line_id']}:{q['entity']}:{reason[:24]}", sev, "high", "defect",
                        tag + f"cannot be used for {ln['part']}: {reason}", q["records"].get("quantity") if "pcs" in reason
                        else q["records"].get("lead_time") if "lead time" in reason else rec,
                        check="rfq.disqualified")
                if q["match"] == "variant":
                    put(q["doc_id"], f"{ln['rfq_line_id']}:{q['entity']}:substitute", "medium", "high", "concern",
                        tag + f"offers {q['quote_part']!r} instead of the requested {ln['part']!r}: a substitute or revision "
                        f"that needs buyer approval before it can be compared like-for-like",
                        q["records"].get("part_number") or rec, check="rfq.substitute")
                if q["currency"] and q["landed_base"] is None and q["goods_base"] is None:
                    put(q["doc_id"], f"{ln['rfq_line_id']}:{q['entity']}:fx", "high", "high", "concern",
                        tag + f"priced in {q['currency']} with no FX rate set: cannot be ranked against {cur} quotes",
                        rec, check="rfq.no_fx")
                if q["freight_incomplete"] and q["goods_base"] is not None:
                    put(q["doc_id"], f"{ln['rfq_line_id']}:{q['entity']}:freight", "medium", "high", "concern",
                        tag + "freight cost is unknown, so its landed cost is a lower bound and could change the ranking",
                        q["records"].get("freight") or rec, check="rfq.freight_unknown")
            ok = [q for q in qs if q["goods_base"] is not None and q["status"] != "disqualified"]
            if len(ok) >= 3:
                unit = [(q, q["goods_base"] / q["qty"]) for q in ok if q["qty"]]
                med = statistics.median(float(u) for _, u in unit)
                for q, u in unit:
                    r = float(u) / med if med else 1
                    if r < 0.6 or r > 1.6:
                        put(q["doc_id"], f"{ln['rfq_line_id']}:{q['entity']}:outlier", "medium", "medium", "concern",
                            f"[{q['supplier']}] unit price {float(u):.2f} {cur} is {r:.2f}x the median of the other quotes; "
                            f"check scope, price basis and part before treating it as a bargain or an error",
                            q["records"].get("unit_price"), check="rfq.price_outlier")
            if ln["cheapest"] and ln["best"] and ln["cheapest"] is not ln["best"]:
                c, b = ln["cheapest"], ln["best"]
                why = "; ".join(c["reasons"] + c["flags"])[:200] or "ranked after it"
                put(c["doc_id"], f"{ln['rfq_line_id']}:cheapest_not_best", "high", "high", "concern",
                    f"[{c['supplier']}] has the lowest cost but is not the recommended quote ({b['supplier']} is): {why}",
                    c["records"].get("unit_price"), check="rfq.cheapest_not_best")
        # one supplier, several documents
        by_sup = {}
        for ln in comparison["lines"]:
            for q in ln["quotes"]:
                by_sup.setdefault(re.sub(r"[^a-z0-9]", "", re.sub(r"\b(gmbh|ag|ltd|inc|llc|sa|bv|srl|spa)\b", "", (q["supplier"] or "").lower())), set()).add(q["doc_id"])
        for sup, docs in by_sup.items():
            if sup and len(docs) > 1:
                d = sorted(docs)[0]
                rec = led.db.execute("SELECT record_id FROM records WHERE doc_id=? AND pass_label IS NOT NULL LIMIT 1", (d,)).fetchone()
                put(d, f"dup_supplier:{sup}", "medium", "medium", "concern",
                    f"{len(docs)} documents look like they come from the same supplier ({sup}): a later one may supersede an earlier one",
                    rec["record_id"] if rec else None, count=len(docs), check="rfq.duplicate_supplier")
        for row in led.db.execute("SELECT finding_id, doc_id, check_id, dedupe_key FROM findings WHERE check_id LIKE 'rfq.%' "
                                  "AND status='open'").fetchall():
            if (row["doc_id"], row["check_id"], row["dedupe_key"]) not in keep and not led.db.execute(
                    "SELECT 1 FROM feedback WHERE finding_id=?", (row["finding_id"],)).fetchone():
                led.db.execute("DELETE FROM findings WHERE finding_id=?", (row["finding_id"],))
    return ids
