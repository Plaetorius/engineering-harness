# second-reader

An independent second reader for supply-chain and data documents. It reads the same material a human is reviewing and returns a
short list of things worth a second look, each with its evidence: values copied from the source, arithmetic checked by code,
quotes compared against an RFQ and a bid price. Findings are rule hits, not verdicts; the human decides.

Two skills share one toolkit (`scripts/sr`):
- `second-reader` (`SKILL.md`): orchestration protocol for Claude Code. Free code first, Haiku doers only for gaps (batched), Opus only for a compact list of conflicts.
- `second-reader-offline` (`../second-reader-offline/SKILL.md`): no AI, no network. A human runs `scripts/sr-offline` and gets a self-contained HTML report. The assistant is told to stay out of the data, because an assistant that reads the documents or the output has already received them.

**Activating the skills.** The harness installer links a fixed list of six skills and has its own tests, so these two are not linked
automatically (nothing in the harness was changed). To use them in Claude Code:
```
ln -s ~/Documents/harness/skills/second-reader ~/.claude/skills/second-reader
ln -s ~/Documents/harness/skills/second-reader-offline ~/.claude/skills/second-reader-offline
```
or add both names to `SKILLS` in `scripts/lib/harness.py` (and its installer tests) if you want the installer to own them.

Requirements: `python3` (3.10+). PDFs: `pdftotext`, `pdftoppm` (poppler) and `tesseract`. `.xlsx`: `openpyxl` (the `sr` launcher uses `uv run --with openpyxl==3.1.5` only when an xlsx is being ingested and the module is missing; `sr-offline` never downloads anything).

## What it does
```
files ──► ingest ──► canonical records with provenance ──► deterministic checks ──► findings ──► brief / HTML report
 csv xlsx json         (tables: cells; text/email/PDF: text spans + OCR boxes)        ▲
 txt eml html pdf                                                                    │
 scanned pdf  ──► text layer | local OCR (word confidence, bbox) ──► facts ──► VERIFIED against the source text
                                  rule-based reader (free)  ┐        ▲
                                  Haiku doers (batched)     ┴────────┘ two reads compared, disagreements flagged
 RFQ + bid price ──► match parts ──► quantity / lead time / validity / FX / freight ──► landed cost, ranking, margin
```
Everything is logged to one SQLite ledger (`./.second-reader/ledger.db`, per workspace, never committed: it holds commercial data) which
is also the cache. The action log is append-only (database triggers), a finding cannot exist without an evidence record, and any
change to the file, tool version, prompt version, mapping or parameters is a cache miss.

## Use
```
scripts/sr run start --goal "RFQ 4711"
scripts/sr rfq set --order-date 2026-09-28 --fx USD=1.08 ; scripts/sr rfq add --part SV-2210-24 --qty 200 --need-by-days 28 --bid-price 48 --currency EUR
scripts/sr ingest inbox/*                      # profile tables, canonical text for email/PDF (OCR when scanned)
scripts/sr check                               # tables: arithmetic, units, dates, duplicates, outliers, identifiers
scripts/sr extract local DOC ; scripts/sr qcheck DOC --pass L        # free rule-based read + single-document quote checks
scripts/sr batch prepare DOC... --out-dir d    # several documents per doer call; only what is not already cached
scripts/sr batch commit --ids 3 4 5 --input answer.json              # verifies every fact against the source text
scripts/sr extract compare DOC --a A --b L     # model read vs rule-based read
scripts/sr rfq compare                         # best quote, margin, why the cheapest is not the winner
scripts/sr brief | sr report --out report.html [--embed-pages]       # terminal brief | HTML report
scripts/sr findings | drill F | page DOC N | confirm F | dismiss F | feedback F --label useful|noise|already-known
scripts/sr log | export out.jsonl | verify | cache | mode offline | init --offline

scripts/sr-offline inbox --out report.html --part SV-2210-24 --qty 200 --need-by-days 28 --bid-price 48 --currency EUR --fx USD=1.08
```
DB path: `--db`, `$SR_DB`, or `./.second-reader/ledger.db`. `SR_OFFLINE=1` forces offline behaviour for any ledger.

## Guarantees (each is tested)
- **Traceability.** A fact is verified only if its quote occurs verbatim in the document, its value occurs verbatim inside that quote, and the value has the right type. Models must copy values as written; conversion (`38,40`, `3-5 working days`, `per 100`) is done by code and noted. Unverified values never reach comparison. OCR errors are kept as read and flagged by confidence, not corrected.
- **Untrusted documents.** Instruction-like text and HTML-hidden text are flagged; quoted text is clipped and labelled; the HTML report escapes everything, has no scripts and a CSP that forbids loads.
- **Offline is enforced, not promised.** An offline ledger refuses to prepare AI payloads or accept AI-read facts, a ledger that already holds AI-read data cannot be declared offline, and a test runs the whole pipeline with network calls made to fail.
- **No silent wins.** Cheapest is not recommended unless compliant and fully costed; partial quantity, late lead time, expired quote, unknown FX or freight, substitute part numbers and prices quoted for another quantity are disqualifications or conditions, each with a reason.

## Measured results
Re-run with `python3 -I tests/run_eval.py` (compares with `tests/baseline.json`, written by `--write`; numbers in `tests/BASELINE.md`).

| Measure | Result |
|---|---|
| Unit + integration tests | 111 (110 run without openpyxl; the XLSX test needs it) |
| Real transactions, 541,909 rows (UCI Online Retail), planted errors (`bench_planted.py`) | 9 of 10 error types 100% recall; id spelling variants 39/40; no false alarms on arithmetic/date/decimal-style checks in the clean copy. The price-outlier check flags 841 natural cases on the clean file (precision is poor: tune with feedback labels) |
| 3,251 real emails (SpamAssassin corpus), parser robustness | 0 parse errors; 0 injection-scan false positives (corpus predates LLM injection, so this measures false positives only) |
| Your exercise (5 emails + Eurotec PDF), rule-based only, offline | Recommends Alpine at 6,420 EUR landed, margin 3,180 EUR (33.1%): matches the answer key. Brightline 7,277.78 EUR, Delta (partial + substitute) and Eurotec (84 d vs 28 d) disqualified |
| Emails, rule-based reader | 94.5% of fields on set A (tuned against it), **67.9% on sealed set B** (never tuned on) |
| Emails, batched Haiku, original prompt | 89.5% on A, 80.0% on B |
| Emails, batched Haiku, prompt with the buyer's request | 95.3% on A, 91.4% on B |
| OCR (poppler + tesseract, local) | clean scan 91% mean word confidence: all key values correct; poor scan: values correct except an `S`->`8` in the part number, kept as read and flagged at 0% confidence; unreadable scan: page dropped and reported |

**Honesty about the sealed set.** Set B was written by an agent that never saw the toolkit. It was scored once with the rule-based reader (67.9%, not tuned afterwards) and once with Haiku. Its failures then informed the v3 prompt (price tiers, descriptive part numbers), so the 91.4% is a post-fix number measured on the data that motivated the fix, not an independent one. Set A was used to tune the rules and the prompt. A third blind set is needed for a clean final figure.

**Cost observed (Haiku via subagents).** One call per document: about 19k tokens each, almost all fixed overhead. Batched, 6-8 documents per call: about 4.8k tokens per document. The rule-based reader costs nothing and also serves as the second opinion, so a second model pass is usually unnecessary. A doer sometimes returns an incomplete or slightly malformed batch (seen twice in 8 calls): the commit reports the missing documents and a re-prepare skips what is cached.

## Known limits
- Rule-based reading knows common English/German phrasings, tables and price breaks; it misses descriptive part numbers, unusual layouts, other languages and handwriting. It never invents a value, and it reports what it could not read.
- A relative validity ("valid 30 days") is reported as relative; no expiry date is invented. Business days convert at x7/5 and ranges use the upper bound (noted on each quote). "Free above a threshold" freight is unknown, not zero.
- Tables: `price outlier` is noisy on large item lists; cross-document checks cover quotes against an RFQ, not arbitrary table joins; there is no ERP connector.
- Doers invoked as subagents are told to use only a Read and a Write tool; that is an instruction, not enforcement. Prompt-injection resistance is tested with synthetic cases; no real-world injected corpus was available.
- PDFs and OCR run external parsers (poppler, tesseract) on untrusted files: argv-only, timeouts, 200-page cap.

## Layout
```
SKILL.md  README.md  scripts/{sr, sr-offline, sr.py, srlib/*}      srlib: ledger, ingest, checks, numparse, textdoc, pdfdoc, extract, localread, quotes, rfq, report, engine, brief
tests/    test_*.py (unit/integration)  eval_*.py evalkit.py run_eval.py bench_*.py  baseline.json BASELINE.md
tests/fixtures/{s2,s2_heldout,s2_sealed,s3,s4}    emails + recorded Haiku outputs + answer keys, PDFs (text layer, scanned clean/poor/unreadable)
(repo root) evals/second-reader/open/    manifest.json fetch_fixtures.py make_planted_retail.py; downloads and derived data are git-ignored and live outside the skill
```
