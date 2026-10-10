#!/usr/bin/env python3
"""Score extraction on a held-out email set. Usage: python3 -I tests/eval_heldout.py [heldout|sealed] [local|haiku|both]
local = the no-AI rule-based reader; haiku = recorded model outputs in <set>/haiku/<stem>.json (if present)."""
import json, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "tests"))
from srlib import engine, extract  # noqa: E402
from srlib.ledger import Ledger     # noqa: E402
import evalkit                      # noqa: E402

TARGET_QTY = {"heldout": 200, "sealed": 5000}      # the RFQ quantity of each set (selects price-break tiers)
SETS = {"heldout": ("s2_heldout", "expected_heldout.json"), "sealed": ("s2_sealed", "expected_sealed.json")}


def run(which="heldout", mode="local", verbose=True):
    folder, keyfile = SETS[which]
    fx = ROOT / "tests/fixtures" / folder
    expected = json.loads((fx / keyfile).read_text())
    led = Ledger(Path(tempfile.mkdtemp()) / "l.db")
    r = led.start_run("eval")
    ids = {}
    out = {}
    for stem in expected:
        doc = engine.ingest_document(led, r, fx / f"{stem}.txt")
        ids[stem] = doc["doc_id"]
        if mode in ("local", "both"):
            extract.local_extract(led, r, doc, target_qty=TARGET_QTY[which])
        model_file = fx / ("haiku_v3" if mode == "haiku3" else "haiku") / f"{stem}.json"
        if mode in ("haiku", "haiku3", "both") and model_file.exists():
            extract.commit(led, r, doc, "A", "haiku", "haiku", model_file.read_text())
    if mode in ("local", "both"):
        out["local"] = evalkit.evaluate(led, ids, expected, "L")
    if mode in ("haiku", "haiku3", "both"):
        sub = "haiku_v3" if mode == "haiku3" else "haiku"
        missing = [s for s in expected if not (fx / sub / f"{s}.json").exists()]
        if missing:
            raise FileNotFoundError(f"{which}/{sub}: recorded model output missing for {missing[:3]}...")
        out["haiku3" if mode == "haiku3" else "haiku"] = evalkit.evaluate(led, ids, expected, "A")
    led.close()
    if verbose:
        for name, res in out.items():
            print(f"[{which}] {name}: " + evalkit.summary(res))
            print("   misses:", res["misses"])
    return out


if __name__ == "__main__":
    run(*(sys.argv[1:3] or ["heldout", "local"]))
