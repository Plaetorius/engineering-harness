"""Field-level scoring of the quote table against an answer key (shared by eval_s2, eval_heldout, run_eval).

Rules: a key value of null means 'the document does not state it', so a tool value there is a hallucination and counts
as a miss. A tool line with a price that matches no key line is a spurious line (a miss). valid_until is skipped when
the tool reports a relative validity period (the key may have derived a date from the email date)."""
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from srlib import quotes  # noqa: E402


def norm(p):
    return re.sub(r"[^a-z0-9]", "", (p or "").lower())


def dec(x):
    return None if x is None else Decimal(str(x))


def evaluate(led, doc_ids, expected, pass_label="A"):
    """-> dict(passed, total, misses, by_field={field: [passed, total]}, per_doc={key: [passed, total]})"""
    res = {"passed": 0, "total": 0, "misses": [], "by_field": {}, "per_doc": {}}

    def check(key, field, ok, label=None):
        res["total"] += 1
        res["passed"] += bool(ok)
        f = res["by_field"].setdefault(field, [0, 0])
        f[1] += 1
        f[0] += bool(ok)
        d = res["per_doc"].setdefault(key, [0, 0])
        d[1] += 1
        d[0] += bool(ok)
        if not ok:
            res["misses"].append(label or f"{key}.{field}")

    for key, exp in expected.items():
        t = quotes.build_table(led, doc_ids[key], pass_label)
        priced = [l for l in t["lines"] if l["unit_price"] is not None]
        used = set()
        if exp.get("supplier_name"):
            got = norm(t["supplier"])
            check(key, "supplier", got.startswith(norm(exp["supplier_name"])[:8]) or norm(exp["supplier_name"])[:8] in got)
        for j, el in enumerate(exp["lines"]):
            cand = [l for l in priced if norm(l["part_number"]) == norm(el["part_number"]) and l["entity"] not in used]
            line = cand[0] if cand else None
            if line is None:
                spare = [l for l in priced if l["entity"] not in used]
                line = spare[0] if spare and len(exp["lines"]) == len(priced) else None
            check(key, "part_number", bool(cand), f"{key}.L{j + 1}.part_number")
            if line:
                used.add(line["entity"])
            for f in ("quantity", "unit_price"):
                if f in el:
                    check(key, f, line is not None and line[f] == dec(el[f]), f"{key}.L{j + 1}.{f}")
            if "currency" in el:
                check(key, "currency", line is not None and line["currency_code"] == el["currency"], f"{key}.L{j + 1}.currency")
            if el.get("price_basis_qty"):
                check(key, "price_basis", line is not None and line["price_basis_qty"] == el["price_basis_qty"], f"{key}.L{j + 1}.price_basis")
        for l in priced:
            if l["entity"] not in used:
                check(key, "spurious_line", False, f"{key}.{l['entity']}.spurious_line")
        first = (priced or t["lines"] or [None])[0]
        if exp["lines"]:
            if "lead_time_days" in exp:
                check(key, "lead_time", first is not None and first["lead_time_days"] == exp["lead_time_days"])
            if "freight_amount" in exp:
                check(key, "freight", first is not None and first["freight_amount"] == dec(exp["freight_amount"]))
        if "valid_until" in exp and not t.get("validity_period"):
            got = t["valid_until"].isoformat() if t["valid_until"] else None
            check(key, "valid_until", got == exp["valid_until"])
        if not exp["lines"]:
            check(key, "no_offer", not priced, f"{key}.no_offer")
    return res


def summary(res):
    pct = lambda a, b: f"{a}/{b} ({a / b:.0%})" if b else "n/a"
    lines = [f"overall {pct(res['passed'], res['total'])}"]
    lines.append("by field: " + ", ".join(f"{f} {pct(*v)}" for f, v in sorted(res["by_field"].items())))
    return "\n".join(lines)
