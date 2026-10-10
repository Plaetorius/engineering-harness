"""Deterministic discrepancy checks over mapped tabular roles. No LLM, no randomness.

Each check: id, version, needs (role tuples; ANY listed alternative set may satisfy), fn(ctx) -> list[Draft].
Findings aggregate by pattern (count + capped examples) so a 500k-row file yields a readable brief.
"""
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal

from .ingest import iter_rows
from .numparse import parse_date, parse_number

MAX_EXAMPLES = 5
MAX_ROWS_LISTED = 5000
CLIP = 60


def clip(text, n=CLIP):
    text = str(text)
    return text if len(text) <= n else text[:n] + f"…(+{len(text) - n} chars)"
LEGAL_SUFFIXES = {"gmbh", "ag", "kg", "ltd", "plc", "inc", "llc", "corp", "co", "sa", "sarl", "sas", "spa",
                  "srl", "bv", "nv", "sro", "as", "ab", "limited", "company"}


@dataclass
class Example:
    sheet: str
    row_no: int
    cols: list            # [[column name, 0-based index, role], ...]


@dataclass
class Draft:
    dedupe_key: str
    severity: str         # high | medium | low | info
    confidence: str       # high | medium | low (before mapping-confidence cap)
    kind: str             # defect | concern
    claim: str
    count: int
    examples: list
    rows: list = field(default_factory=list)
    impact: str = None
    detail: dict = field(default_factory=dict)

    def to_json(self):
        return asdict(self)

    @staticmethod
    def from_json(d):
        d = dict(d)
        d["examples"] = [Example(**e) for e in d["examples"]]
        return Draft(**d)


class Ctx:
    def __init__(self, db, doc_id, mapping, profile, today, params):
        self.db, self.doc_id, self.mapping, self.profile = db, doc_id, mapping, profile
        self.today, self.params = today, params

    def has(self, *roles):
        sheets = {self.mapping[r]["sheet"] for r in roles if r in self.mapping}
        return all(r in self.mapping for r in roles) and len(sheets) == 1

    def sheet(self, role):
        return self.mapping[role]["sheet"]

    def col(self, role):
        """-> [name, index, role]"""
        m = self.mapping[role]
        names = [c["name"] for c in self.profile["sheets"][m["sheet"]]["columns"]]
        return [m["col"], names.index(m["col"]), role]

    def idx(self, role):
        return self.col(role)[1]

    def colprofile(self, role):
        m = self.mapping[role]
        return next(c for c in self.profile["sheets"][m["sheet"]]["columns"] if c["name"] == m["col"])

    def rows(self, role_or_sheet):
        sheet = self.mapping[role_or_sheet]["sheet"] if role_or_sheet in self.mapping else role_or_sheet
        return iter_rows(self.db, self.doc_id, sheet)

    def param(self, name, default, cast=str):
        return cast(self.params[name]) if name in self.params else default

    def mapping_confidence(self, roles):
        srcs = {self.mapping[r]["source"] for r in roles if r in self.mapping}
        return "medium" if "auto-fuzzy" in srcs else "high"


def cell(cells, i):
    return cells[i] if i < len(cells) else None


def blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def ex(ctx, role_list, row_no, sheet=None):
    sheet = sheet or ctx.sheet(role_list[0])
    return Example(sheet, row_no, [ctx.col(r) for r in role_list])


def money(x):
    return str(x.quantize(Decimal("0.01")))


# ---------------------------------------------------------------------------------------------
def check_arith_line_total(ctx):
    qi, pi, ti = ctx.idx("qty"), ctx.idx("unit_price"), ctx.idx("line_total")
    tol = ctx.param("tol_abs", Decimal("0.01"), Decimal)
    bad, checked = [], 0
    for rn, c in ctx.rows("qty"):
        q, _ = parse_number(cell(c, qi))
        p, _ = parse_number(cell(c, pi))
        t, _ = parse_number(cell(c, ti))
        if q is None or p is None or t is None:
            continue
        checked += 1
        gap = abs(q * p - t)
        if gap > tol:
            bad.append((gap, rn))
    if not bad:
        return []
    bad.sort(reverse=True)
    total_gap = sum(g for g, _ in bad)
    sheet = ctx.sheet("qty")
    return [Draft("mismatch", "high", "high", "defect",
                  f"{len(bad)} of {checked} lines where qty x unit price does not equal the line total "
                  f"(sum of gaps {money(total_gap)}, largest {money(bad[0][0])})",
                  len(bad), [ex(ctx, ["qty", "unit_price", "line_total"], rn, sheet) for _, rn in bad[:MAX_EXAMPLES]],
                  rows=sorted(rn for _, rn in bad)[:MAX_ROWS_LISTED], impact=money(total_gap),
                  detail={"tolerance": str(tol), "checked": checked})]


def check_dup_exact(ctx):
    sheet = next(iter(ctx.profile["sheets"]), None)
    if sheet is None:
        return []
    seen, dups = {}, defaultdict(list)
    for rn, c in ctx.rows(sheet):
        key = tuple(str(v).strip().lower() if v is not None else "" for v in c)
        if key in seen:
            dups[seen[key]].append(rn)
        else:
            seen[key] = rn
    if not dups:
        return []
    extra = sum(len(v) for v in dups.values())
    firsts = sorted(dups, key=lambda r: -len(dups[r]))[:MAX_EXAMPLES]
    cols = [[c["name"], i, c["name"]] for i, c in enumerate(ctx.profile["sheets"][sheet]["columns"][:6])]
    return [Draft("exact_rows", "medium", "medium", "concern",
                  f"{extra} rows are exact repeats of an earlier row ({len(dups)} distinct rows repeated); "
                  f"may be double entries or legitimate repeated lines",
                  extra, [Example(sheet, r, cols) for r in firsts],
                  rows=sorted(r for v in dups.values() for r in v)[:MAX_ROWS_LISTED],
                  detail={"distinct_repeated": len(dups)})]


def check_dup_key_conflict(ctx):
    di, ii, pi = ctx.idx("doc_ref"), ctx.idx("item_id"), ctx.idx("unit_price")
    seen = defaultdict(dict)       # (doc, item) -> {price: first row}
    for rn, c in ctx.rows("doc_ref"):
        d, i = cell(c, di), cell(c, ii)
        p, _ = parse_number(cell(c, pi))
        if blank(d) or blank(i) or p is None:
            continue
        seen[(str(d).strip(), str(i).strip())].setdefault(p, rn)
    conflicts = {k: v for k, v in seen.items() if len(v) > 1}
    if not conflicts:
        return []
    sheet = ctx.sheet("doc_ref")
    exs = []
    for k in list(conflicts)[:3]:
        for rn in list(conflicts[k].values())[:2]:
            exs.append(ex(ctx, ["doc_ref", "item_id", "unit_price"], rn, sheet))
    return [Draft("same_item_diff_price", "medium", "medium", "concern",
                  f"{len(conflicts)} items appear more than once in the same document at different unit prices",
                  len(conflicts), exs)]


def check_outlier_price(ctx):
    ii, pi = ctx.idx("item_id"), ctx.idx("unit_price")
    qi = ctx.idx("qty") if "qty" in ctx.mapping and ctx.has("item_id", "qty") else None
    min_n = ctx.param("min_obs", 5, int)
    far = ctx.param("far_ratio", 10.0, float)
    groups = defaultdict(list)
    for rn, c in ctx.rows("item_id"):
        item = cell(c, ii)
        p, _ = parse_number(cell(c, pi))
        if blank(item) or p is None or p <= 0:
            continue
        q = parse_number(cell(c, qi))[0] if qi is not None else None
        groups[str(item).strip()].append((p, rn, q))
    scale, other = [], []
    for item, obs in groups.items():
        if len(obs) < min_n:
            continue
        med = statistics.median(float(p) for p, _, _ in obs)
        if med <= 0:
            continue
        for p, rn, q in obs:
            ratio = float(p) / med
            if ratio >= far or ratio <= 1 / far:
                hit = (item, rn, p, med, q)
                if any(abs(ratio / (10.0 ** k) - 1) <= 0.05 for k in (-3, -2, -1, 1, 2, 3)):
                    scale.append(hit)
                else:
                    other.append(hit)
    sheet = ctx.sheet("item_id")
    roles = ["item_id", "unit_price"]

    def impact(hits):
        tot = Decimal(0)
        for _, _, p, med, q in hits:
            tot += abs(p - Decimal(str(med))) * (abs(q) if q is not None else 1)
        return money(tot)

    out = []
    for key, hits, claim, sev in (
            ("scale", scale, "unit prices that are ~10/100/1000x (or 1/10..1/1000) of the item's median price - "
                             "possible per-100/per-1000 or decimal-place slip", "high"),
            ("far", other, f"unit prices >= {far:g}x or <= 1/{far:g} of the item's median price", "medium")):
        if hits:
            hits.sort(key=lambda h: -abs(float(h[2]) / h[3] - 1))
            out.append(Draft(key, sev, "medium", "concern", f"{len(hits)} {claim}", len(hits),
                             [ex(ctx, roles, h[1], sheet) for h in hits[:MAX_EXAMPLES]],
                             rows=sorted(h[1] for h in hits)[:MAX_ROWS_LISTED], impact=impact(hits),
                             detail={"items_affected": len({h[0] for h in hits}), "min_obs": min_n,
                                     "examples": [{"item": h[0], "price": str(h[2]), "median": round(h[3], 4)}
                                                  for h in hits[:MAX_EXAMPLES]]}))
    return out


def check_value_nonpositive(ctx):
    out = []
    sheet = ctx.sheet("unit_price") if "unit_price" in ctx.mapping else ctx.sheet("qty")
    specs = []
    if "unit_price" in ctx.mapping:
        specs.append(("unit_price", "price_nonpositive", lambda v: v <= 0, "medium", "concern",
                      "rows with a zero or negative unit price (free items, credits or missing price)"))
    if "qty" in ctx.mapping:
        specs.append(("qty", "qty_negative", lambda v: v < 0, "low", "concern",
                      "rows with a negative quantity (returns/credit notes, or sign errors)"))
        specs.append(("qty", "qty_zero", lambda v: v == 0, "low", "concern", "rows with zero quantity"))
    for role, key, pred, sev, kind, claim in specs:
        i = ctx.idx(role)
        hits = []
        for rn, c in ctx.rows(role):
            v, _ = parse_number(cell(c, i))
            if v is not None and pred(v):
                hits.append(rn)
        if hits:
            roles = [role] + [r for r in ("item_id", "qty", "unit_price") if r in ctx.mapping and r != role][:2]
            out.append(Draft(key, sev, "high", kind, f"{len(hits)} {claim}", len(hits),
                             [ex(ctx, roles, rn, sheet) for rn in hits[:MAX_EXAMPLES]], rows=hits[:MAX_ROWS_LISTED]))
    return out


def check_date_logic(ctx):
    out = []
    today = ctx.today
    for role in [r for r in ("date", "date_due") if r in ctx.mapping]:
        i, cp = ctx.idx(role), ctx.colprofile(role)
        dayfirst = cp.get("dayfirst")
        bad_parse, future, old, ambiguous = [], [], [], []
        for rn, c in ctx.rows(role):
            v = cell(c, i)
            if blank(v):
                continue
            d, flags = parse_date(v, dayfirst)
            if d is None:
                bad_parse.append(rn)
                continue
            if role == "date" and d > today:
                future.append(rn)
            if d < date(1990, 1, 1):
                old.append(rn)
            if "ambiguous" in flags:
                ambiguous.append(rn)
        sheet = ctx.sheet(role)
        for key, rows, sev, kind, claim in (
                ("unparsable", bad_parse, "medium", "defect", "values in the {col} column are not recognisable dates"),
                ("future", future, "medium", "defect", f"{{col}} values are after today ({today})"),
                ("implausible", old, "low", "concern", "{col} values are before 1990"),
                ("ambiguous", ambiguous, "medium", "concern",
                 "{col} values could be day/month or month/day and the column gives no evidence which; "
                 "interpreted month-first")):
            if rows:
                out.append(Draft(f"{role}:{key}", sev, "high", kind,
                                 f"{len(rows)} " + claim.format(col=ctx.mapping[role]["col"]), len(rows),
                                 [ex(ctx, [role], rn, sheet) for rn in rows[:MAX_EXAMPLES]],
                                 rows=rows[:MAX_ROWS_LISTED]))
    if ctx.has("date", "date_due"):
        a, b = ctx.idx("date"), ctx.idx("date_due")
        da, db_ = ctx.colprofile("date").get("dayfirst"), ctx.colprofile("date_due").get("dayfirst")
        bad, far = [], []
        far_days = ctx.param("max_lead_days", 365, int)
        for rn, c in ctx.rows("date"):
            d1, _ = parse_date(cell(c, a), da)
            d2, _ = parse_date(cell(c, b), db_)
            if d1 and d2 and d2 < d1:
                bad.append(rn)
            elif d1 and d2 and (d2 - d1).days > far_days:
                far.append(rn)
        if far:
            out.append(Draft("due_far_after_date", "medium", "medium", "concern",
                             f"{len(far)} rows where the due/delivery date is more than {far_days} days after the "
                             f"document date (typo in year, or an unrealistic lead time)",
                             len(far), [ex(ctx, ["date", "date_due"], rn) for rn in far[:MAX_EXAMPLES]],
                             rows=far[:MAX_ROWS_LISTED]))
        if bad:
            out.append(Draft("due_before_date", "high", "high", "defect",
                             f"{len(bad)} rows where the due/delivery date is earlier than the document date",
                             len(bad), [ex(ctx, ["date", "date_due"], rn) for rn in bad[:MAX_EXAMPLES]],
                             rows=bad[:MAX_ROWS_LISTED]))
    return out


def _norm_key(s, party):
    s = str(s).lower()
    toks = re.findall(r"[a-z0-9]+", s)
    if party:
        toks = [t for t in toks if t not in LEGAL_SUFFIXES] or toks
    return "".join(toks)


def check_ident_variants(ctx):
    out = []
    for role, party, noun in (("item_id", False, "part/item identifiers"), ("party", True, "party names")):
        if role not in ctx.mapping:
            continue
        i = ctx.idx(role)
        by_key = defaultdict(dict)       # normalized -> {raw: first row}
        for rn, c in ctx.rows(role):
            v = cell(c, i)
            if blank(v):
                continue
            raw = str(v)
            by_key[_norm_key(raw, party)].setdefault(raw, rn)
        var = {k: v for k, v in by_key.items() if len(v) > 1 and k}
        if not var:
            continue
        keys = sorted(var, key=lambda k: -len(var[k]))
        exs = [ex(ctx, [role], rn) for k in keys[:3] for rn in list(var[k].values())[:2]]
        out.append(Draft(role, "medium", "medium", "concern",
                         f"{len(var)} {noun} appear in more than one spelling (case/punctuation/spacing"
                         f"{'/legal suffix' if party else ''} differences), e.g. "
                         + "; ".join(" | ".join(clip(v) for v in list(var[k])[:3]) for k in keys[:2]),
                         len(var), exs, detail={"samples": [[clip(v) for v in list(var[k])[:4]] for k in keys[:5]]}))
    return out


def check_attr_conflict(ctx):
    ii, di = ctx.idx("item_id"), ctx.idx("description")
    first = defaultdict(dict)          # item -> {normalized desc: first row}
    for rn, c in ctx.rows("item_id"):
        item, desc = cell(c, ii), cell(c, di)
        if blank(item) or blank(desc):
            continue
        first[str(item).strip()].setdefault(re.sub(r"\s+", " ", str(desc).strip().lower()), rn)
    conflicts = {k: v for k, v in first.items() if len(v) > 1}
    if not conflicts:
        return []
    keys = sorted(conflicts, key=lambda k: -len(conflicts[k]))
    exs = [ex(ctx, ["item_id", "description"], rn) for k in keys[:3] for rn in list(conflicts[k].values())[:2]]
    return [Draft("item_multi_description", "low", "medium", "concern",
                  f"{len(conflicts)} item identifiers carry more than one description "
                  f"(same id, different item - or inconsistent naming)", len(conflicts), exs)]


def check_hygiene_nulls(ctx):
    out = []
    for role in ("item_id", "qty", "unit_price", "line_total", "date", "date_due", "party", "doc_ref"):
        if role not in ctx.mapping:
            continue
        cp = ctx.colprofile(role)
        if cp["nulls"] == 0:
            continue
        i = ctx.idx(role)
        rows = [rn for rn, c in ctx.rows(role) if blank(cell(c, i))]
        rate = cp["null_rate"]
        out.append(Draft(f"nulls:{role}", "medium" if rate >= 0.05 else "low", "high", "concern",
                         f"{len(rows)} rows ({rate:.1%}) have no value in {ctx.mapping[role]['col']} ({role})",
                         len(rows), [ex(ctx, [role], rn) for rn in rows[:MAX_EXAMPLES]], rows=rows[:MAX_ROWS_LISTED]))
    return out


def check_hygiene_numbers(ctx):
    out = []
    for role in [r for r in ("qty", "unit_price", "line_total", "lead_time") if r in ctx.mapping]:
        i = ctx.idx(role)
        unparsable, dot, comma, ambiguous = [], [], [], []
        for rn, c in ctx.rows(role):
            v = cell(c, i)
            if blank(v):
                continue
            num, flags = parse_number(v)
            if num is None:
                unparsable.append(rn)
            if "style_dot_decimal" in flags:
                dot.append(rn)
            if "style_comma_decimal" in flags:
                comma.append(rn)
            if "ambiguous_sep" in flags:
                ambiguous.append(rn)
        col = ctx.mapping[role]["col"]
        if unparsable:
            out.append(Draft(f"unparsable:{role}", "high", "high", "defect",
                             f"{len(unparsable)} non-blank cells in {col} ({role}) are not valid numbers "
                             f"({len(unparsable) / max(1, ctx.colprofile(role)['filled']):.1%} of the column)",
                             len(unparsable), [ex(ctx, [role], rn) for rn in unparsable[:MAX_EXAMPLES]],
                             rows=unparsable[:MAX_ROWS_LISTED]))
        if dot and comma:
            minority = comma if len(comma) <= len(dot) else dot
            out.append(Draft(f"locale_mix:{role}", "high", "high", "defect",
                             f"{col} ({role}) mixes decimal styles: {len(dot)} use '.', {len(comma)} use ','; "
                             f"values may be mis-scaled when parsed",
                             len(minority), [ex(ctx, [role], rn) for rn in minority[:MAX_EXAMPLES]],
                             rows=minority[:MAX_ROWS_LISTED], detail={"dot": len(dot), "comma": len(comma)}))
        if ambiguous:
            out.append(Draft(f"ambiguous_sep:{role}", "medium", "medium", "concern",
                             f"{len(ambiguous)} values in {col} ({role}) like 1,234 / 1.234 could be a thousand "
                             f"or a decimal; read as thousands for ',' and decimal for '.'",
                             len(ambiguous), [ex(ctx, [role], rn) for rn in ambiguous[:MAX_EXAMPLES]],
                             rows=ambiguous[:MAX_ROWS_LISTED]))
    return out


# id, version, needs (list of alternative role-sets; first satisfiable one is used), fn, description
CHECKS = [
    ("arith.line_total", "1", [("qty", "unit_price", "line_total")], check_arith_line_total,
     "qty x unit price = line total"),
    ("dup.exact_rows", "1", [()], check_dup_exact, "exact repeated rows"),
    ("dup.same_item_diff_price", "1", [("doc_ref", "item_id", "unit_price")], check_dup_key_conflict,
     "same item twice in one document at different prices"),
    ("outlier.price", "2", [("item_id", "unit_price")], check_outlier_price,
     "unit price far from the item's median (incl. power-of-ten slips)"),
    ("value.nonpositive", "1", [("unit_price",), ("qty",)], check_value_nonpositive,
     "zero/negative price or quantity"),
    ("date.logic", "2", [("date",), ("date_due",)], check_date_logic,
     "unparsable, future, implausible, ambiguous or inverted dates"),
    ("ident.variants", "1", [("item_id",), ("party",)], check_ident_variants,
     "same identifier/party written several ways"),
    ("ident.attr_conflict", "1", [("item_id", "description")], check_attr_conflict,
     "same item id with different descriptions"),
    ("hygiene.nulls", "1", [("item_id",), ("qty",), ("unit_price",), ("line_total",), ("date",), ("date_due",),
                            ("party",), ("doc_ref",)], check_hygiene_nulls, "empty cells in key roles"),
    ("hygiene.numbers", "2", [("qty",), ("unit_price",), ("line_total",), ("lead_time",)], check_hygiene_numbers,
     "invalid numbers, mixed decimal styles, ambiguous separators"),
]


def applicable(ctx, needs):
    """First satisfiable role-set, or None. An empty tuple means no mapping is required."""
    for roles in needs:
        if all(r in ctx.mapping for r in roles) and (not roles or ctx.has(*roles)):
            return roles
    return None
