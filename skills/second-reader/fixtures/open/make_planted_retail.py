#!/usr/bin/env python3
"""Derive two CSVs from the UCI Online Retail xlsx (needs openpyxl; run via `uv run --with openpyxl`):
  derived/retail_clean.csv    original rows + LineTotal (=qty*price) + DeliveryDate (=InvoiceDate+7..30d)
  derived/retail_planted.csv  same, with known errors planted; truth in derived/planted_truth.json
Seeded; ground truth lists CSV record numbers (header = record 1) per planted error type."""
import csv, json, random, sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import statistics
from collections import defaultdict
import openpyxl

here = Path(__file__).resolve().parent
src = here / "data/uci_online_retail/Online Retail.xlsx"
out = here / "derived"; out.mkdir(exist_ok=True)
R = random.Random(2026)

wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
rows = [list(r) for r in wb.active.iter_rows(min_row=2, values_only=True)]
rows = [r for r in rows if r[0] is not None]
header = ["InvoiceNo","StockCode","Description","Quantity","InvoiceDate","UnitPrice","CustomerID","Country","LineTotal","DeliveryDate"]

def build(r):
    q, p, d = r[3], Decimal(str(r[5])), r[4]
    return [r[0], r[1], r[2], q, d.strftime("%Y-%m-%d %H:%M:%S"), str(p), "" if r[6] is None else int(r[6]), r[7],
            str((q * p).quantize(Decimal("0.01"))), (d + timedelta(days=R.randint(7, 30))).strftime("%Y-%m-%d")]

clean = [build(r) for r in rows]
def write(path, data):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(data)
write(out / "retail_clean.csv", clean)

# --- plant errors (record number = index + 2 because header is record 1)
pl = [list(r) for r in clean]; truth = defaultdict(list)
byitem = defaultdict(list)
for i, r in enumerate(pl):
    byitem[r[1]].append(i)
used = set()
def pick(pred, n):
    cands = [i for i in range(len(pl)) if i not in used and pred(i)]
    got = R.sample(cands, n); used.update(got); return got

# 1 arithmetic: total inflated 5-20%
for i in pick(lambda i: Decimal(pl[i][8]) > 5, 200):
    pl[i][8] = str((Decimal(pl[i][8]) * Decimal(R.uniform(1.05, 1.2)).quantize(Decimal("0.001"))).quantize(Decimal("0.01")))
    truth["arith"].append(i + 2)
# 2 price scale slip x100, total kept consistent so only the outlier check can see it
big = lambda i: len(byitem[pl[i][1]]) >= 8 and Decimal(pl[i][5]) >= Decimal("0.5") and pl[i][3] > 0
for i in pick(big, 100):
    p = Decimal(pl[i][5]) * 100; pl[i][5] = str(p); pl[i][8] = str((pl[i][3] * p).quantize(Decimal("0.01")))
    truth["scale"].append(i + 2)
# 3 locale: comma-decimal price strings (same value)
for i in pick(lambda i: "." in pl[i][5] and Decimal(pl[i][5]) != Decimal(pl[i][5]).to_integral(), 50):
    pl[i][5] = pl[i][5].replace(".", ","); truth["locale"].append(i + 2)
# 4 dates: impossible day, and future year
for i in pick(lambda i: True, 30):
    pl[i][4] = "2011-02-30 09:00:00"; truth["date_unparsable"].append(i + 2)
for i in pick(lambda i: True, 30):
    pl[i][4] = "2031" + pl[i][4][4:]; pl[i][9] = "2031-12-15"; truth["date_future"].append(i + 2)
# 5 delivery before invoice / absurdly late
for i in pick(lambda i: pl[i][4].startswith("201"), 25):
    d = datetime.strptime(pl[i][4][:10], "%Y-%m-%d"); pl[i][9] = (d - timedelta(days=3)).strftime("%Y-%m-%d")
    truth["due_before"].append(i + 2)
for i in pick(lambda i: pl[i][4].startswith("201"), 15):
    d = datetime.strptime(pl[i][4][:10], "%Y-%m-%d"); pl[i][9] = (d + timedelta(days=900)).strftime("%Y-%m-%d")
    truth["due_far"].append(i + 2)
# 6 id spelling variants: lowercase letters, or trailing space for numeric ids
n_var = 0
for i in pick(lambda i: True, 40):
    s = str(pl[i][1]); pl[i][1] = s.lower() if s.lower() != s else s + " "; n_var += 1
truth["id_variants_count"] = n_var
# 7 blanks in qty
for i in pick(lambda i: True, 40):
    pl[i][3] = ""; pl[i][8] = ""; truth["qty_blank"].append(i + 2)
# 8 appended exact duplicates
dups = R.sample(range(len(pl)), 60)
for i in dups:
    pl.append(list(pl[i]))
truth["dup_appended_count"] = len(dups)
write(out / "retail_planted.csv", pl)
json.dump(truth, open(out / "planted_truth.json", "w"))
print({k: (len(v) if isinstance(v, list) else v) for k, v in truth.items()}, "rows:", len(pl))
