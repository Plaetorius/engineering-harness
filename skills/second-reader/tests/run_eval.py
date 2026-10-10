#!/usr/bin/env python3
"""S6: one command that measures the toolkit and compares it with the recorded baseline.

  python3 -I tests/run_eval.py            # run everything available, print a table, compare with tests/baseline.json
  python3 -I tests/run_eval.py --write    # (re)write tests/baseline.json and tests/BASELINE.md from this run
  python3 -I tests/run_eval.py --full     # also run the real-data benchmarks (needs fixtures/open/data; ~3 min)

Exit status 1 if a metric drops more than TOLERANCE below the baseline or any unit test fails. The 'sealed' set is
reported separately because it was written blind to the toolkit; see README for its history."""
import json, subprocess, sys, unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "tests"))
import eval_heldout, eval_s2   # noqa: E402

TOLERANCE = 0.02
BASELINE = ROOT / "tests/baseline.json"


def unit_tests():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    res = unittest.TextTestRunner(stream=open("/dev/null", "w"), verbosity=0).run(suite)
    return {"tests": res.testsRun, "failures": len(res.failures) + len(res.errors), "skipped": len(res.skipped)}


def frac(r):
    return round(r["passed"] / r["total"], 4)


def collect(full=False):
    m = {"unit": unit_tests()}
    for which in ("heldout", "sealed"):
        for mode in ("local", "haiku", "haiku3"):
            try:
                out = eval_heldout.run(which, mode, verbose=False)
            except Exception:
                continue
            for k, r in out.items():
                if r["total"]:
                    m[f"{which}.{k}"] = {"accuracy": frac(r), "fields": r["total"], "by_field": {f: round(v[0] / v[1], 3) for f, v in r["by_field"].items()}}
    if full:
        for name, script in (("bench_planted", "tests/bench_planted.py"), ("bench_mail", "tests/bench_mail.py")):
            p = subprocess.run([sys.executable, "-I", str(ROOT / script)], capture_output=True, text=True)
            m[name] = {"exit": p.returncode, "tail": p.stdout.strip().splitlines()[-6:]}
    return m


def render(m, base=None):
    rows = ["| Measure | Fields | Accuracy | Baseline |", "|---|---|---|---|"]
    for k, v in m.items():
        if isinstance(v, dict) and "accuracy" in v:
            b = base.get(k, {}).get("accuracy") if base else None
            rows.append(f"| {k} | {v['fields']} | {v['accuracy']:.1%} | {'-' if b is None else f'{b:.1%}'} |")
    u = m["unit"]
    rows.append(f"\nUnit tests: {u['tests']} run, {u['failures']} failing, {u['skipped']} skipped.")
    return "\n".join(rows)


def main(argv):
    full, write = "--full" in argv, "--write" in argv
    m = collect(full)
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() else None
    print(render(m, base))
    bad = []
    if m["unit"]["failures"]:
        bad.append("unit tests failing")
    for k, v in m.items():
        if isinstance(v, dict) and "accuracy" in v and base and k in base and v["accuracy"] < base[k]["accuracy"] - TOLERANCE:
            bad.append(f"{k} fell {base[k]['accuracy']:.1%} -> {v['accuracy']:.1%}")
    for k in ("bench_planted", "bench_mail"):
        if k in m and m[k]["exit"] != 0:
            bad.append(f"{k} failed")
    if write:
        BASELINE.write_text(json.dumps({k: v for k, v in m.items() if k != "unit"} | {"unit": m["unit"], "date": str(date.today())}, indent=1))
        (ROOT / "tests/BASELINE.md").write_text(f"# Measured baseline ({date.today()})\n\n{render(m)}\n\nSets: `heldout` (set A, rules were tuned against it), `sealed` "
                                                f"(set B, written blind; the toolkit and the v3 prompt were changed after seeing its first scores, so later numbers are not independent). "
                                                f"`haiku` = batched Haiku, original prompt; `haiku3` = prompt with the buyer's request.\n")
        print("baseline written")
    for b in bad:
        print("REGRESSION:", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
