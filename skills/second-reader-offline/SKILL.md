---
name: second-reader-offline
description: The no-AI, no-network variant of second-reader for confidential client documents. Reads with local rules and OCR, checks and compares with code, and produces a self-contained HTML report on the user's own machine. The assistant must not read the documents or the report.
---

Use when the user says documents must not be sent to a third party. **An AI assistant that reads documents, or toolkit output derived from them, has already received that data.** So this skill gives the *human* a command to run and keeps the assistant out of the data.

## What you may and may not do
- You may: explain the options, build the exact command line, check that prerequisites exist (`python3`, `pdftotext`/`pdftoppm`/`tesseract` for PDFs, `openpyxl` for .xlsx; offline mode never installs or downloads anything), explain the report afterwards from generic knowledge, and help the user interpret numbers *they* paste.
- You may not: open, print, summarise or grep the client documents, the report, or the ledger; run any command whose output contains document-derived text; spawn subagents; run `sr extract prepare|commit`, `sr batch`, or anything from the online `second-reader` skill; point the toolkit at a ledger that already holds AI-read data. The toolkit enforces this: an offline ledger refuses AI payloads and AI-read data, and `SR_OFFLINE=1` forces it.
- If the user wants you to operate the tool and see results, ask them to confirm explicitly that the assistant seeing **counts and paths only** (`--quiet`) is acceptable. If not, give them the command and stop.

## The command (the human runs it)
```
<skill dir>/../second-reader/scripts/sr-offline <files or folders...> --out report.html \
    [--part SV-2210-24 --qty 200 --need-by-days 28 --bid-price 48.00 --currency EUR --fx USD=1.08 --order-date 2026-09-28] \
    [--rfq-file rfq.csv] [--embed-pages] [--quiet]
```
It creates an offline ledger next to the report (`report.ledger.db`, append-only audit trail, keep it with the report), reads every supported file (csv, tsv, xlsx, json, txt, eml, html, pdf incl. scanned), checks, compares quotes against the RFQ, and writes one HTML file with no scripts and no external loads. Open it in a browser; it prints cleanly.

## Reading the report (say this to the user)
- The banner says OFFLINE. Everything was read by rules: common English/German phrasings, tables, price breaks (the RFQ quantity selects the tier). It is measurably weaker than a model on unusual layouts, descriptive part numbers and other languages, so read **coverage** and the **documents table** (what was read, how many facts were verified) and spot-check any quote the comparison relies on.
- Each finding shows the source passage with the value highlighted, the page and OCR confidence for scans, and `sr drill <F>` to see more. Low-confidence OCR numbers and unreadable pages are called out; nothing is silently corrected.
- Recording decisions: `sr confirm F`, `sr dismiss F --label noise`, `sr feedback F --label useful` against the offline ledger (`--db report.ledger.db`); re-run `sr-offline` to refresh the report. Re-runs are cached.

## Limits to state
No model means: no reading of free-form layouts the rules do not know, no help with scanned handwriting, and descriptive item names are often missed as part numbers. When the rule-based reader finds nothing for a document, the report says so; it never invents a value.
