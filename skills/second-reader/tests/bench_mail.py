#!/usr/bin/env python3
"""Real-email robustness + injection-scan false-positive benchmark on the SpamAssassin public corpus (offline parse).
Needs fixtures: python3 -I fixtures/open/fetch_fixtures.py spamassassin_public_corpus
Usage: python3 -I tests/bench_mail.py"""
import sys, time, traceback
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "scripts"))
from srlib import textdoc  # noqa: E402

base = root / "fixtures/open/data/spamassassin_public_corpus"
if not base.exists():
    sys.exit("missing fixtures: python3 -I fixtures/open/fetch_fixtures.py spamassassin_public_corpus")

fail = False
for group in ("easy_ham", "hard_ham", "spam"):
    files = sorted(p for p in (base / group).iterdir() if p.is_file() and p.name != "cmds")
    errors, empty, hidden, attach, n_hit, labels, t0 = 0, 0, 0, 0, 0, Counter(), time.time()
    samples = []
    for p in files:
        try:
            b = textdoc.build_bytes(p.read_bytes(), "eml")
        except Exception:
            errors += 1
            if errors <= 3:
                traceback.print_exc()
            continue
        body = b["text"].split("\n\n", 1)[-1].strip()
        empty += len(body) == 0
        hidden += b["meta"]["hidden_chars"] > 0
        attach += bool(b["meta"].get("attachments"))
        if b["hits"]:
            n_hit += 1
            labels.update(h[0] for h in b["hits"])
            if len(samples) < 4:
                label, s, e = b["hits"][0]
                samples.append((p.name, label, " ".join(b["text"][max(0, s - 50):e + 50].split())))
    n = len(files)
    print(f"{group:<9} {n:>5} msgs  parse errors {errors}  empty body {empty}  with attachments {attach}  "
          f"hidden-html text {hidden}  injection-scan hits {n_hit} ({n_hit / n:.1%})  {time.time() - t0:.1f}s")
    if labels:
        print("          hits by pattern:", dict(labels))
    for name, label, ctx in samples:
        print(f"          e.g. {name} [{label}] ...{ctx[:140]}...")
    fail |= errors > 0
sys.exit(1 if fail else 0)
