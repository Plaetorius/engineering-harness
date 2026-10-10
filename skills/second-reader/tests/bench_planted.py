#!/usr/bin/env python3
"""S1 acceptance benchmark: run the real CLI on retail_clean.csv (false-positive baseline) and
retail_planted.csv (known errors), then score recall. Needs fixtures (see fixtures/open/).
Usage: python3 -I tests/bench_planted.py"""
import json, sqlite3, subprocess, sys, tempfile, time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sr = str(root / "scripts" / "sr")
derived = root / "fixtures/open/derived"
for need in ("retail_clean.csv", "retail_planted.csv", "planted_truth.json"):
    if not (derived / need).exists():
        sys.exit(f"missing {derived / need}: run fixtures/open/fetch_fixtures.py then make_planted_retail.py")
truth = json.loads((derived / "planted_truth.json").read_text())

def run(csv_path):
    tmp = tempfile.mkdtemp(prefix="sr-bench-")
    db = f"{tmp}/ledger.db"
    t0 = time.time()
    for args in (["ingest", str(csv_path)], ["check", "--today", "2026-10-09"]):
        subprocess.run([sr, "--db", db] + args, check=True, capture_output=True)
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    out = {}
    for f in con.execute("SELECT check_id, dedupe_key, count, detail_json FROM findings"):
        out[(f["check_id"], f["dedupe_key"])] = (f["count"], set(json.loads(f["detail_json"] or "{}").get("rows", [])))
    ver = subprocess.run([sr, "--db", db, "verify"], capture_output=True, text=True).stdout.strip()
    return out, time.time() - t0, ver

clean, t_clean, v1 = run(derived / "retail_clean.csv")
planted, t_pl, v2 = run(derived / "retail_planted.csv")

def rows_recall(key, name):
    keys = key if isinstance(key, list) else [key]
    want = set(truth[name]); got = set().union(*(planted.get(k, (0, set()))[1] for k in keys))
    return len(want & got), len(want)
def delta(key):
    return planted.get(key, (0,))[0] - clean.get(key, (0,))[0]

results = []
for label, key, name in (
    ("arithmetic: total != qty x price", ("arith.line_total", "mismatch"), "arith"),
    ("price x100 slip, any outlier bucket", [("outlier.price", "scale"), ("outlier.price", "far")], "scale"),
    ("mixed decimal style ('12,5')", ("hygiene.numbers", "locale_mix:unit_price"), "locale"),
    ("invalid date (Feb 30)", ("date.logic", "date:unparsable"), "date_unparsable"),
    ("future date (2031)", ("date.logic", "date:future"), "date_future"),
    ("delivery before invoice", ("date.logic", "due_before_date"), "due_before"),
    ("delivery 900 days after invoice", ("date.logic", "due_far_after_date"), "due_far"),
):
    hit, tot = rows_recall(key, name)
    results.append((label, f"{hit}/{tot}", hit / tot, f"clean baseline flags: {sum(clean.get(k, (0,))[0] for k in (key if isinstance(key, list) else [key]))}"))
for label, key, n in (
    ("id spelling variants", ("ident.variants", "item_id"), truth["id_variants_count"]),
    ("blank quantity", ("hygiene.nulls", "nulls:qty"), len(truth["qty_blank"])),
    ("appended exact duplicates", ("dup.exact_rows", "exact_rows"), truth["dup_appended_count"]),
):
    d = delta(key)
    results.append((label, f"+{d} vs {n}", min(d, n) / n, f"count delta over clean ({clean.get(key,(0,))[0]})"))

hit_scale, tot_scale = rows_recall(("outlier.price", "scale"), "scale")
print(f"(of the planted x100 slips, {hit_scale}/{tot_scale} were classified as power-of-ten scale slips; the rest\n"
      f" were still flagged as far-from-median because the item's median is itself spread)\n")
width = max(len(r[0]) for r in results)
for label, frac, rec, note in results:
    print(f"{label:<{width}}  recall {rec:6.1%}  ({frac})  {note}")
print(f"\nledger verify: clean={v1!r} planted={v2!r}")
print(f"runtime: clean {t_clean:.0f}s, planted {t_pl:.0f}s (ingest + all checks)")
fp = {k: v[0] for k, v in clean.items() if k[0] in ("arith.line_total", "date.logic") or k == ("hygiene.numbers", "locale_mix:unit_price")}
print("clean-file hits on checks that should be silent on the clean copy:", fp or "none")
bad = [r for r in results if r[2] < 0.95]
sys.exit(1 if bad or fp or "OK" not in v1 + v2 else 0)
