import json, os, subprocess, sys, tempfile, unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from srlib import engine, brief           # noqa: E402
from srlib.ledger import Ledger, LedgerError, cache_key, SCHEMA_VERSION  # noqa: E402
from srlib.numparse import parse_date, parse_number  # noqa: E402
import sqlite3  # noqa: E402

CSV = """Part No,Supplier,Qty,Unit Price,Total,Order Date,Delivery Date
SV-2210-24,Alpine Fluid AG,200,31.50,6300.00,2026-09-28,2026-10-19
SV2210-24,Alpine Fluid GmbH,200,31.50,6300.00,2026-09-28,2026-10-19
SV-2210-24,Corvus,200,34.00,6900.00,2026-09-28,2026-10-01
SV-2210-24,Brightline,200,"38,40",7680.00,28/09/2026,2026-09-20
SV-2210-24,Delta,150,3150.00,472500,2026-09-28,2027-12-01
SV-2210-24,Eurotec,200,29.95,5990.00,2026-09-28,
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.led = Ledger(self.dir / "l.db")
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.led.close)

    def csv(self, text=CSV, name="q.csv"):
        p = self.dir / name
        p.write_text(text)
        return p


class LedgerTests(Base):
    def test_init_idempotent_and_versioned(self):
        self.led.close()
        led2 = Ledger(self.dir / "l.db")
        self.assertEqual(led2.db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        led2.close()
        self.led = Ledger(self.dir / "l.db")

    def test_newer_schema_refused(self):
        con = sqlite3.connect(self.dir / "new.db"); con.execute("PRAGMA user_version=99"); con.close()
        with self.assertRaises(LedgerError):
            Ledger(self.dir / "new.db")

    def test_actions_append_only(self):
        run = self.led.start_run("t")
        aid = self.led.log_action(run, "x")
        with self.assertRaises(sqlite3.DatabaseError):
            self.led.db.execute("UPDATE actions SET tool='y' WHERE action_id=?", (aid,))
        with self.assertRaises(sqlite3.DatabaseError):
            self.led.db.execute("DELETE FROM actions WHERE action_id=?", (aid,))

    def test_record_requires_document_and_finding_requires_evidence(self):
        run = self.led.start_run("t")
        with self.assertRaises(sqlite3.IntegrityError):
            self.led.upsert_record(999, "qty", "S!R1C1", "1", "sr.cell")
        with self.assertRaises(LedgerError):
            self.led.upsert_finding(run, None, "c", "1", "k", "low", "low", "concern", "claim", [])
        with self.assertRaises(sqlite3.IntegrityError):   # DB-level: primary evidence must exist
            self.led.db.execute("INSERT INTO findings(run_id,check_id,check_version,dedupe_key,severity,confidence,"
                                "kind,claim,primary_record_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (run, "c", "1", "k", "low", "low", "concern", "x", 12345, "now"))

    def test_bad_role_rejected(self):
        with self.assertRaises(LedgerError):
            self.led.log_action(self.led.start_run(), "x", role="gpt")

    def test_cache_key_depends_on_version_and_params(self):
        a = cache_key("sha", "check", "1", {"p": 1})
        self.assertEqual(a, cache_key("sha", "check", "1", {"p": 1}))
        self.assertNotEqual(a, cache_key("sha", "check", "2", {"p": 1}))
        self.assertNotEqual(a, cache_key("sha", "check", "1", {"p": 2}))

    def test_concurrent_writers(self):
        run = self.led.start_run("c")
        code = ("import sys; sys.path.insert(0, %r); from srlib.ledger import Ledger\n"
                "l = Ledger(%r)\nfor i in range(40): l.log_action(%d, 'w')\n")
        procs = [subprocess.Popen([sys.executable, "-I", "-c", code % (str(ROOT / "scripts"), str(self.dir / "l.db"), run)])
                 for _ in range(4)]
        self.assertTrue(all(p.wait() == 0 for p in procs))
        self.assertEqual(self.led.db.execute("SELECT COUNT(*) FROM actions").fetchone()[0], 160)
        self.assertEqual(self.led.verify(), [])


class NumParseTests(unittest.TestCase):
    def test_numbers(self):
        cases = {"1.200,50": "1200.50", "1,200.50": "1200.50", "38,40": "38.40", "12.5": "12.5", "(15.00)": "-15.00",
                 "EUR 1 234,5": "1234.5", "$9": "9", "1,234,567": "1234567", "0,125": "0.125", "7-": "-7"}
        for text, want in cases.items():
            self.assertEqual(parse_number(text)[0], Decimal(want), text)

    def test_ambiguous_and_malformed(self):
        v, f = parse_number("1,234")
        self.assertEqual(v, Decimal("1234")); self.assertIn("ambiguous_sep", f)
        v, f = parse_number("1.234")
        self.assertEqual(v, Decimal("1.234")); self.assertIn("ambiguous_sep", f)
        self.assertIsNone(parse_number("1,23,4.5")[0]); self.assertIsNone(parse_number("abc")[0])
        self.assertIsNone(parse_number("")[0]); self.assertIsNone(parse_number("1.2.3,4")[0])

    def test_dates(self):
        self.assertEqual(parse_date("2026-09-28")[0], date(2026, 9, 28))
        self.assertEqual(parse_date("28/09/2026")[0], date(2026, 9, 28))
        d, f = parse_date("03/04/2026"); self.assertIn("ambiguous", f)
        self.assertEqual(parse_date("03/04/2026", dayfirst=True)[0], date(2026, 4, 3))
        d, f = parse_date("2011-02-30"); self.assertIsNone(d); self.assertIn("invalid", f)
        self.assertIsNone(parse_date("soon")[0])


class EndToEndTests(Base):
    def run_all(self, text=CSV):
        run = self.led.start_run("t")
        doc = engine.ingest_document(self.led, run, self.csv(text))
        res = engine.run_checks(self.led, run, doc["doc_id"], today=date(2026, 10, 9))
        return run, doc, res

    def findings(self):
        return {(f["check_id"], f["dedupe_key"]): f for f in self.led.db.execute("SELECT * FROM findings")}

    def test_planted_errors_found_with_evidence(self):
        self.run_all()
        f = self.findings()
        self.assertEqual(f[("arith.line_total", "mismatch")]["count"], 1)
        self.assertIn(("hygiene.numbers", "locale_mix:unit_price"), f)
        self.assertIn(("date.logic", "due_before_date"), f)
        self.assertIn(("date.logic", "due_far_after_date"), f)
        self.assertIn(("ident.variants", "item_id"), f)
        self.assertIn(("ident.variants", "party"), f)
        self.assertIn(("hygiene.nulls", "nulls:date_due"), f)
        self.assertIn(("outlier.price", "far"), f)
        self.assertEqual(self.led.verify(), [])
        # traceability: evidence raw text equals the source cell
        rec = self.led.db.execute("SELECT r.* FROM findings x JOIN records r ON r.record_id=x.primary_record_id "
                                  "WHERE x.check_id='arith.line_total'").fetchone()
        self.assertEqual(rec["locator"], "csv!R4C3"); self.assertEqual(rec["raw_text"], "200")

    def test_clean_file_has_no_defects(self):
        clean = "Part No,Qty,Unit Price,Total,Order Date\nA-1,2,5.00,10.00,2026-01-02\nA-2,3,1.50,4.50,2026-01-03\n"
        self.run_all(clean)
        self.assertEqual([r["claim"] for r in self.led.db.execute("SELECT claim FROM findings WHERE kind='defect'")], [])

    def test_ingest_and_check_are_cached_and_logged(self):
        run, doc, _ = self.run_all()
        engine.ingest_document(self.led, run, self.csv())
        engine.run_checks(self.led, run, doc["doc_id"], today=date(2026, 10, 9))
        hits = self.led.db.execute("SELECT COUNT(*) FROM actions WHERE cache_hit=1").fetchone()[0]
        self.assertGreaterEqual(hits, 9)
        # a changed parameter misses the cache for the affected check
        before = self.led.db.execute("SELECT COUNT(*) FROM actions WHERE cache_hit=1").fetchone()[0]
        engine.run_checks(self.led, run, doc["doc_id"], only=["arith.line_total"], today=date(2026, 10, 9),
                          params={"tol_abs": "1000"})
        self.assertEqual(self.led.db.execute("SELECT COUNT(*) FROM actions WHERE cache_hit=1").fetchone()[0], before)
        self.assertEqual(self.findings().get(("arith.line_total", "mismatch")), None)   # stale finding pruned

    def test_changed_file_content_invalidates(self):
        run, doc, _ = self.run_all()
        d2 = engine.ingest_document(self.led, run, self.csv(CSV.replace("6900.00", "6800.00"), "q2.csv"))
        self.assertNotEqual(d2["doc_id"], doc["doc_id"])
        engine.run_checks(self.led, run, d2["doc_id"], only=["arith.line_total"], today=date(2026, 10, 9))
        self.assertFalse([f for f in self.findings().values() if f["doc_id"] == d2["doc_id"]
                          and f["check_id"] == "arith.line_total"])

    def test_missing_roles_are_reported_not_hidden(self):
        run, doc, res = self.run_all("Name,Value\nx,1\n")
        self.assertTrue(all(r["status"] == "skipped" for r in res if r["check"] != "dup.exact_rows"))
        text = brief.render(self.led)
        self.assertIn("Not checked", text); self.assertIn("skipped", text)

    def test_user_mapping_override_and_confidence(self):
        run = self.led.start_run("t")
        doc = engine.ingest_document(self.led, run, self.csv("Item,Amount x,Q,P\nA,10,2,5\nB,99,2,5\n"))
        mapping = engine.set_mapping(self.led, run, doc["doc_id"], ["qty=Q", "unit_price=P", "line_total=Amount x"])
        self.assertEqual(mapping["line_total"]["source"], "user")
        engine.run_checks(self.led, run, doc["doc_id"], only=["arith.line_total"])
        f = self.findings()[("arith.line_total", "mismatch")]
        self.assertEqual((f["count"], f["confidence"]), (1, "high"))
        with self.assertRaises(LedgerError):
            engine.set_mapping(self.led, run, doc["doc_id"], ["qty=Nope"])

    def test_human_status_survives_rerun(self):
        run, doc, _ = self.run_all()
        fid = self.findings()[("arith.line_total", "mismatch")]["finding_id"]
        self.led.set_finding_status(fid, "confirmed"); self.led.add_feedback(fid, "useful", "yes")
        engine.run_checks(self.led, run, doc["doc_id"], only=["arith.line_total"], today=date(2026, 10, 9), use_cache=False)
        f = self.led.db.execute("SELECT * FROM findings WHERE finding_id=?", (fid,)).fetchone()
        self.assertEqual(f["status"], "confirmed")

    def test_drill_and_brief(self):
        self.run_all()
        fid = self.findings()[("arith.line_total", "mismatch")]["finding_id"]
        f, doc, recs, blocks = engine.drill(self.led, fid)
        self.assertTrue(any(r["target"] and r["row_no"] == 4 for b in blocks for r in b["context"]))
        text = brief.render(self.led)
        self.assertIn("Defects", text); self.assertIn("csv!R4", text)

    def test_unsupported_and_missing_files(self):
        run = self.led.start_run("t")
        for name in ("a.pdf", "nope.csv"):
            p = self.dir / name
            if name.endswith("pdf"):
                p.write_bytes(b"%PDF-1.4")
            with self.assertRaises(LedgerError):
                engine.ingest_document(self.led, run, p)
        errs = self.led.db.execute("SELECT COUNT(*) FROM actions WHERE status='error'").fetchone()[0]
        self.assertGreaterEqual(errs, 1)     # failures are logged too


class ReviewRegressionTests(Base):
    """Findings from the S0/S1 code review."""

    def ingest_check(self, text, name="r.csv", only=None, mapping=None):
        run = self.led.start_run("t")
        doc = engine.ingest_document(self.led, run, self.csv(text, name))
        if mapping:
            engine.set_mapping(self.led, run, doc["doc_id"], mapping)
        engine.run_checks(self.led, run, doc["doc_id"], only=only, today=date(2026, 10, 9))
        return run, doc

    def f(self):
        return {(r["check_id"], r["dedupe_key"]): r for r in self.led.db.execute("SELECT * FROM findings")}

    def test_dirty_column_is_mapped_and_reported(self):                      # review #1
        rows = ["Part No,Qty,Unit Price,Total"]
        for i, q in enumerate(["5", "N/A", "tbd", "7", "?", "3", "2", "4", "6", "8"]):
            rows.append(f"P{i},{q},2.00,{'10.00' if q.isdigit() and int(q) == 5 else '99.00'}")
        run, doc = self.ingest_check("\n".join(rows) + "\n")
        mapping = json.loads(self.led.get_document(doc["doc_id"])["mapping_json"])
        self.assertEqual(mapping["qty"]["col"], "Qty"); self.assertTrue(mapping["qty"].get("dirty"))
        found = self.f()
        self.assertEqual(found[("hygiene.numbers", "unparsable:qty")]["count"], 3)
        self.assertIn(("arith.line_total", "mismatch"), found)            # checks still run on the valid cells
        self.assertIn("mapped but dirty", brief.render(self.led))

    def test_text_column_is_not_mapped_but_explained(self):
        run = self.led.start_run("t")
        doc = engine.ingest_document(self.led, run, self.csv("Part,Qty\nA,many\nB,some\nC,few\n", "t.csv"))
        self.assertNotIn("qty", json.loads(self.led.get_document(doc["doc_id"])["mapping_json"]))
        self.assertIn("header looks like qty", brief.render(self.led))

    def test_scientific_notation(self):                                       # review #2
        for text, want in {"1.5E+3": "1500", "2e-3": "0.002", "-4E2": "-400"}.items():
            self.assertEqual(parse_number(text)[0], Decimal(want), text)
        self.ingest_check("P,Qty,Unit Price,Total\nA,1.5E+3,2,3000\nB,2,1,5\n")
        self.assertEqual(self.f()[("arith.line_total", "mismatch")]["count"], 1)   # only B: 2*1 != 5

    def test_stale_finding_removed_when_check_inapplicable(self):            # review #3
        run, doc = self.ingest_check("P,Qty,Unit Price,Total\nA,2,5,99\nB,1,1,1\n")
        self.assertIn(("arith.line_total", "mismatch"), self.f())
        engine.set_mapping(self.led, run, doc["doc_id"], unsets=["qty"])
        engine.run_checks(self.led, run, doc["doc_id"], only=["arith.line_total"])
        self.assertNotIn(("arith.line_total", "mismatch"), self.f())
        self.assertTrue(self.led.db.execute("SELECT 1 FROM actions WHERE tool LIKE 'prune:%'").fetchone())

    def test_reviewed_finding_not_pruned_when_check_skipped(self):
        run, doc = self.ingest_check("P,Qty,Unit Price,Total\nA,2,5,99\nB,1,1,1\n")
        fid = self.f()[("arith.line_total", "mismatch")]["finding_id"]
        self.led.add_feedback(fid, "useful")
        engine.set_mapping(self.led, run, doc["doc_id"], unsets=["qty"])
        engine.run_checks(self.led, run, doc["doc_id"], only=["arith.line_total"])
        self.assertIn(("arith.line_total", "mismatch"), self.f())

    def test_untrusted_long_text_is_clipped(self):                           # review #4
        big = "x" * 50000
        run, doc = self.ingest_check(f"Part No,Qty,Unit Price,Total\n{big},2,5,10\n{big.upper()},1,1,1\nZ,1,1,1\n")
        text = brief.render(self.led)
        self.assertLess(len(text), 8000)
        self.assertIn("untrusted", text)
        f = self.f()[("ident.variants", "item_id")]
        self.assertLess(len(f["claim"]), 400)
        # the ledger still holds the verbatim value
        self.assertTrue(self.led.db.execute("SELECT 1 FROM records WHERE length(raw_text)=50000").fetchone())

    def test_document_lookup_never_guesses(self):                            # review #5
        run = self.led.start_run("t")
        a = engine.ingest_document(self.led, run, self.csv("A,B\n1,2\n", "a.csv"))
        b = engine.ingest_document(self.led, run, self.csv("A,B\n3,4\n", "b.csv"))
        with self.assertRaises(LedgerError): self.led.get_document("%")
        with self.assertRaises(LedgerError): self.led.get_document("abc")          # too short / not a hash
        self.assertEqual(self.led.get_document(a["sha256"][:8])["doc_id"], a["doc_id"])
        self.assertEqual(self.led.get_document(str(self.dir / "b.csv"))["doc_id"], b["doc_id"])

    def test_german_headers_and_semicolon_csv(self):                         # review #6
        run, doc = self.ingest_check("Artikel;Menge;Preis;Gesamt\nA-1;2;3,50;7,00\nA-2;3;1,25;9,99\n", "de.csv")
        m = json.loads(self.led.get_document(doc["doc_id"])["mapping_json"])
        self.assertEqual((m["qty"]["col"], m["unit_price"]["col"], m["line_total"]["col"], m["item_id"]["col"]),
                         ("Menge", "Preis", "Gesamt", "Artikel"))
        self.assertEqual(self.f()[("arith.line_total", "mismatch")]["count"], 1)

    def test_title_rows_above_header(self):                                  # review #8
        text = "Quotation Q-123,,,,\nAlpine Fluid AG,,,,\nPart,Qty,Unit Price,Total,Date\nA,2,5,10,2026-01-02\nB,1,1,9,2026-01-03\n"
        run, doc = self.ingest_check(text, "title.csv")
        prof = json.loads(self.led.get_document(doc["doc_id"])["profile_json"])
        sheet = prof["sheets"]["csv"]
        self.assertEqual((sheet["header_row"], sheet["data_rows"], len(sheet["preamble"])), (3, 2, 2))
        self.assertEqual(self.f()[("arith.line_total", "mismatch")]["count"], 1)
        self.assertEqual(self.led.db.execute("SELECT locator FROM records WHERE field='qty'").fetchone()[0], "csv!R5C2")
        self.assertIn("preamble", brief.render(self.led))

    def test_wide_table_header_is_row_one(self):
        run, doc = self.ingest_check("2024,2025,2026\n1,2,3\n4,5,6\n", "years.csv")
        self.assertEqual(json.loads(self.led.get_document(doc["doc_id"])["profile_json"])["sheets"]["csv"]["header_row"], 1)


class CheckCoverageTests(Base):
    """Checks that previously had no direct test."""

    def run_checks(self, text):
        run = self.led.start_run("t")
        self.n = getattr(self, "n", 0) + 1
        doc = engine.ingest_document(self.led, run, self.csv(text, f"c{self.n}.csv"))
        engine.run_checks(self.led, run, doc["doc_id"], today=date(2026, 10, 9))
        return {(r["check_id"], r["dedupe_key"]): r
                for r in self.led.db.execute("SELECT * FROM findings WHERE doc_id=?", (doc["doc_id"],))}

    def test_exact_duplicates(self):
        f = self.run_checks("Part,Qty,Unit Price\nA,1,2\nA,1,2\nB,1,2\nA,1,2\n")
        self.assertEqual(f[("dup.exact_rows", "exact_rows")]["count"], 2)

    def test_same_item_twice_in_document_at_different_prices(self):
        f = self.run_checks("Order No,Part,Unit Price\nPO1,A,2.00\nPO1,A,2.50\nPO2,A,2.00\nPO2,B,1\n")
        self.assertEqual(f[("dup.same_item_diff_price", "same_item_diff_price")]["count"], 1)

    def test_description_conflict(self):
        f = self.run_checks("Part,Description\nA,Valve 24V\nA,Valve 12V\nB,Bolt\n")
        self.assertEqual(f[("ident.attr_conflict", "item_multi_description")]["count"], 1)

    def test_nonpositive_values(self):
        f = self.run_checks("Part,Qty,Unit Price\nA,-1,0\nB,0,5\nC,2,-3\nD,4,4\n")
        self.assertEqual(f[("value.nonpositive", "price_nonpositive")]["count"], 2)
        self.assertEqual(f[("value.nonpositive", "qty_negative")]["count"], 1)
        self.assertEqual(f[("value.nonpositive", "qty_zero")]["count"], 1)

    def test_price_scale_slip(self):
        rows = ["Part,Unit Price"] + ["A,10"] * 6 + ["A,1000"]
        f = self.run_checks("\n".join(rows) + "\n")
        self.assertEqual(f[("outlier.price", "scale")]["count"], 1)

    def test_ambiguous_day_month_dates(self):
        f = self.run_checks("Part,Order Date\nA,03/04/2026\nB,05/06/2026\n")
        self.assertIn(("date.logic", "date:ambiguous"), f)
        g = self.run_checks("Part,Order Date\nA,03/04/2026\nB,25/06/2026\n")     # 25/06 proves the column is day-first
        self.assertNotIn(("date.logic", "date:ambiguous"), g)

    def test_row_list_truncation_is_flagged(self):
        from srlib import checks
        old = checks.MAX_ROWS_LISTED
        checks.MAX_ROWS_LISTED = 3
        try:
            f = self.run_checks("Part,Qty,Unit Price\n" + "\n".join(f"P{i},-1,1" for i in range(8)) + "\n")
        finally:
            checks.MAX_ROWS_LISTED = old
        d = json.loads(f[("value.nonpositive", "qty_negative")]["detail_json"])
        self.assertEqual((f[("value.nonpositive", "qty_negative")]["count"], len(d["rows"]), d["rows_truncated"]),
                         (8, 3, True))


@unittest.skipUnless(__import__("importlib").util.find_spec("openpyxl"), "needs openpyxl (run via `uv run --with openpyxl`)")
class XlsxTests(Base):
    def test_xlsx_dates_numbers_and_multiple_sheets(self):
        import openpyxl
        from datetime import datetime
        wb = openpyxl.Workbook()
        ws = wb.active; ws.title = "Quote"
        ws.append(["Part No", "Qty", "Unit Price", "Total", "Order Date"])
        ws.append(["A", 2, 5.5, 11.0, datetime(2026, 1, 2)])
        ws.append(["B", 1, 3.0, 4.0, datetime(2026, 1, 3)])
        ws2 = wb.create_sheet("Notes"); ws2.append(["Note"]); ws2.append(["hello"])
        p = self.dir / "q.xlsx"; wb.save(p)
        run = self.led.start_run("t")
        doc = engine.ingest_document(self.led, run, p)
        prof = json.loads(doc["profile_json"])
        self.assertEqual({k: v["data_rows"] for k, v in prof["sheets"].items()}, {"Quote": 2, "Notes": 1})
        engine.run_checks(self.led, run, doc["doc_id"], today=date(2026, 10, 9))
        f = self.led.db.execute("SELECT * FROM findings WHERE check_id='arith.line_total'").fetchone()
        self.assertEqual(f["count"], 1)
        rec = self.led.db.execute("SELECT locator FROM records WHERE field='qty' AND doc_id=?", (doc["doc_id"],)).fetchone()
        self.assertEqual(rec["locator"], "Quote!R3C2")


if __name__ == "__main__":
    unittest.main()
