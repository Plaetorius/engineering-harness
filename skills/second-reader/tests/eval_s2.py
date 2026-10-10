"""Scores the quote table against fixtures/s2/expected.json (field-level). Used by test_s2.py and runnable alone."""
import json, sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from srlib import quotes  # noqa: E402

EXPECTED = json.loads((ROOT / "tests/fixtures/s2/expected.json").read_text())


def dec(x):
    return None if x is None else Decimal(str(x))


def evaluate(led, doc_ids, pass_label="A"):
    """doc_ids: {'01_alpine': doc_id, ...} -> (passed, total, misses)"""
    passed, total, misses = 0, 0, []

    def check(label, ok):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        if not ok:
            misses.append(label)

    for key, exp in EXPECTED.items():
        t = quotes.build_table(led, doc_ids[key], pass_label)
        check(f"{key}.supplier", (t["supplier"] or "").lower().startswith(exp["supplier_name"].lower()[:10]))
        lines = list(t["lines"])
        for j, el in enumerate(exp["lines"]):
            cand = [l for l in lines if l["part_number"] == el["part_number"]]
            line = cand[0] if cand else None
            check(f"{key}.L{j + 1}.part_number", line is not None)
            if line is None:
                # fall back to the order of price-bearing lines so the other fields still get scored
                priced = [l for l in lines if l["unit_price"] is not None]
                line = priced[j] if j < len(priced) else None
            for f in ("quantity", "unit_price"):
                if f in el:
                    check(f"{key}.L{j + 1}.{f}", line is not None and line[f] == dec(el[f]) or
                          (f == "unit_price" and line is not None and line[f] is not None and
                           line["unit_price"] == dec(el[f])))
            if "currency" in el:
                check(f"{key}.L{j + 1}.currency", line is not None and line["currency_code"] == el["currency"])
            if "price_basis_qty" in el:
                check(f"{key}.L{j + 1}.price_basis", line is not None and line["price_basis_qty"] == el["price_basis_qty"])
        first = lines[0] if lines else None
        if "lead_time_days" in exp:
            check(f"{key}.lead_time_days", first is not None and first["lead_time_days"] == exp["lead_time_days"])
        if "freight_amount" in exp:
            want = dec(exp["freight_amount"])
            check(f"{key}.freight", first is not None and first["freight_amount"] == want)
        if "valid_until" in exp:
            check(f"{key}.valid_until", (t["valid_until"].isoformat() if t["valid_until"] else None) == exp["valid_until"])
        if not exp["lines"]:
            check(f"{key}.no_lines", not t["lines"])
    return passed, total, misses


if __name__ == "__main__":
    import tempfile
    from srlib import engine, extract
    from srlib.ledger import Ledger
    fx = ROOT / "tests/fixtures/s2"
    led = Ledger(Path(tempfile.mkdtemp()) / "l.db")
    run = led.start_run("eval")
    ids = {}
    for key in EXPECTED:
        path = next(fx.glob(key.split("_")[0] + "_*.txt"))
        doc = engine.ingest_document(led, run, path)
        ids[key] = doc["doc_id"]
        n = key.split("_")[0].lstrip("0")
        extract.commit(led, run, doc, "A", "haiku", "haiku", (fx / "haiku" / f"A{n}.json").read_text())
    p, t, m = evaluate(led, ids)
    print(f"{p}/{t} fields correct ({p / t:.1%}); misses: {m}")
