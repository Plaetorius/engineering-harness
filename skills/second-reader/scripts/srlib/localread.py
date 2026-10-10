"""Rule-based quote reader: the no-AI extractor.

Produces the SAME fact payload a Haiku doer would (entity / field / value / quote), which then goes through the same
`extract.commit` verification. So its output is exactly as traceable as a model's; it is just free, offline and less
flexible: it only knows common phrasings (English, some German/French), and anything it cannot read is simply absent
(reported, never guessed).

Used (1) as the extractor in offline mode, (2) as a free independent second opinion next to a model pass.

Context it can use: `target_qty` (the quantity the buyer asked for) selects the applicable row of a price-break table.
Without it, price-break tables are noted and skipped rather than guessed.
"""
import re

CCY = r"(?:EUR|USD|GBP|CHF|CZK|SEK|NOK|DKK|PLN|€|\$|£|euros?|dollars?|sterling|pounds?)"
AMOUNT = r"(?<!\d)(?:\d[\d.,']{0,30}\d|\d)(?!\d)"      # bounded and anchored to the whole digit run: linear time on hostile input
PRICE_RX = re.compile(rf"(?:(?P<c1>{CCY})\s?(?P<a1>{AMOUNT})|(?P<a2>{AMOUNT})\s?(?P<c2>{CCY}\b|{CCY}(?![A-Za-z])))", re.I)
PART_RX = re.compile(r"\b([A-Za-z]{1,5}-?\d{2,6}(?:-[0-9A-Za-z]{1,4})*[A-Za-z]?)\b")
PART_STOP = {"PO", "RFQ", "INV", "NO", "REF", "Q", "ISO", "EN", "DIN", "RAL", "IP", "DWG", "VAT", "NET", "IEC", "UL", "CE",
             "KW", "HRB", "TEL", "FAX", "PLZ", "ABN", "UST", "ID", "G", "M", "NPT", "BSPP", "PN"}
FREIGHT_KW = re.compile(r"\b(freight|shipping|carriage|courier|handling|delivered|fracht\w*|versand\w*|lieferung frei|frei haus|porto)\b", re.I)
INCOTERM_RX = re.compile(r"\b(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b")
LEAD_RX = re.compile(r"((?<!\d)\d+(?:\s*[-–]\s*\d+)?\s*(?:working days?|business days?|werktage?n?|days?|tage?n?|weeks?|wks?|wochen?|months?|monate?n?))\b", re.I)
LEAD_CTX = re.compile(r"\b(lead time|lead-time|delivery|deliver|ship|ships|shipping|arrive|come in|ready|ex[- ]?stock|lieferzeit|lieferung|aro|"
                      r"after receipt|production|délai|delai)\b", re.I)
NOT_LEAD_CTX = re.compile(r"\b(valid|validity|good until|payment|net ?\d*|open for|due|within \d+ days of invoice|prepay|gültig|zahlung)\b", re.I)
EX_STOCK_RX = re.compile(r"\b(ex[- ]?stock|in stock|from stock|ab lager|sofort lieferbar|on stock)\b", re.I)
_DATE = (r"(?P<d>\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?[\s.-]+[A-Za-z]{3,9}\.?,?[\s.-]+\d{4}|"
         r"[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?\b)")
VALID_UNTIL_RX = re.compile(r"(?:valid(?:ity)?|good|open|gültig|gueltig|bis zum)\s*(?:until|till|through|thru|to|bis|:)?\s*"
                            r"(?:until|till|through|thru|to|bis)\s*:?\s*" + _DATE, re.I)
VALID_FOR_RX = re.compile(r"(?:valid|open|good|remains? open|gültig)\s+(?:for\s+)?(\d+\s*(?:days?|weeks?|months?|tage?n?))(?:\s+from[^.,;]*)?", re.I)
PAYMENT_RX = re.compile(r"\bpayment\b[:\s—.\-]*([^\n]+)", re.I)
MOQ_RX = re.compile(r"(?:minimum order(?: quantity)?|MOQ|min\.? order)\D{0,12}(\d[\d.,]*)", re.I)
QTY_RXS = [re.compile(p, re.I) for p in (
    r"\b(?:qty|quantity|menge)\s*[:=]?\s*(\d[\d.,]*)\b",
    r"(?<![\d.,])\b(\d[\d.,]*)\s+of\s+the\s+(?=[A-Z]{1,5}-?\d)",
    r"(?<![\d.,-])(\d[\d.,]*)\s*[- ]?(?:pcs|pieces?|units?|stk|stück)\b")]
BASIS_RX = re.compile(r"(per\s+\d[\d.,]*\s*(?:pcs|pieces|units|pc)?|pro\s+\d[\d.,]*\s*(?:stück|stk)|per\s+(?:piece|pc|pcs|unit|item)|"
                      r"pro stück|each\b|/\s*(?:pc|pcs|ea|piece|unit)\b|a piece|apiece)", re.I)
TIER_RX = re.compile(r"\b(only from|from \d+\s*(?:pcs|pieces|units)|ab \d+\s*(?:stk|stück)|price list|list price)\b", re.I)
LEGAL = (r"(?i:GmbH|AG|KG|e\.?K\.?|Ltd\.?|Limited|PLC|Inc\.?|LLC|Corp\.?|S\.?R\.?L\.?|SpA|S\.?A\.?|SARL|SAS|B\.?V\.?|NV|"
         r"s\.r\.o\.|AB|Co\.?,? ?Ltd\.?|Co\.?)")
SUPPLIER_RX = re.compile(rf"(?<![\w&.\-])([A-ZÄÖÜ][\w&.\-]*(?:\s+[A-ZÄÖÜ&][\w&.\-]*){{0,5}},?\s+{LEGAL})(?=\s|$|[,.;])")
SIGNOFF = re.compile(r"^(best|kind|many|warm)?\s*(regards|wishes|thanks|thank you|cheers|sincerely|mfg|grüße|gruss)\b", re.I)
ROW_RX = re.compile(rf"^\s*\d{{1,3}}\s+(?P<part>\S+)\s+(?:\S.*?)?\s(?P<qty>\d[\d.,]*)\s+(?P<c>{CCY})\s?(?P<price>{AMOUNT})\s+{CCY}\s?{AMOUNT}", re.I)
LAYOUT_GAPS = re.compile(r"\S {3,}\S.* {3,}\S")
CTX_CCY = re.compile(rf"\b(?:in|prices?\s+in|pricing\s+in)\s+(?P<c>{CCY})\b|\((?P<c2>{CCY})\)", re.I)
TIER_LINE = re.compile(rf"^\s*(?P<lo>\d[\d.,]*)\s*(?:(?:[-–]|to)\s*(?P<hi>\d[\d.,]*)|(?P<plus>\+))(?:\s*(?:pcs|pieces|stk|units))?\s+"
                       rf"(?P<c1>{CCY})?\s?(?P<amt>{AMOUNT})(?:\s*(?P<c2>{CCY}))?\s*$", re.I)
RANGE_CELL = re.compile(r"^\s*(?P<lo>\d[\d.,]*)\s*(?:(?:[-–]|to|bis)\s*(?P<hi>\d[\d.,]*)|(?P<plus>\+))\s*$", re.I)


def _flat(s):
    return re.sub(r"\s+", " ", s).strip()


def _num(s):
    s = s.replace(",", "").replace("'", "")
    try:
        return float(s)
    except ValueError:
        return None


def segments(text):
    """Soft-wrapped lines are joined; 'Label: ...' lines, table rows, blank lines and sentence ends start new segments."""
    out = []
    for para in re.split(r"\n\s*\n", text):
        cur = []
        for line in para.split("\n"):
            s = line.strip()
            if not s:
                continue
            if LAYOUT_GAPS.search(line) or ROW_RX.match(s):
                if cur:
                    out.append(_flat(" ".join(cur)))
                    cur = []
                out.append(_flat(s))
                continue
            new = re.match(r"^[A-Za-z][A-Za-z ]{1,24}:\s", s) is not None
            if cur and (new or re.search(r"[.!?:]$", cur[-1])):
                out.append(_flat(" ".join(cur)))
                cur = []
            cur.append(s)
        if cur:
            out.append(_flat(" ".join(cur)))
    sentences = []
    for seg in out:
        if ROW_RX.match(seg):
            sentences.append(seg)
            continue
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(@])", seg):
            sentences.extend(p for p in re.split(r"(?<=[a-z]{3}\.)\s+(?=[a-z])", part) if p.strip())
    return sentences


def _parts(s):
    return [m.group(1) for m in PART_RX.finditer(s) if m.group(1).split("-")[0].rstrip("0123456789").upper() not in PART_STOP
            and not re.fullmatch(r"[A-Za-z]{1,2}\d{2}", m.group(1)) and not re.fullmatch(r"\d.*", m.group(1))]


def _clauses(sentence):
    return re.split(r",\s+|;\s+", sentence)


def _supplier(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    body = [l for l in lines if not re.match(r"^(From|To|Cc|Subject|Date):", l)]
    for l in body[:3]:                                    # letterhead
        m = SUPPLIER_RX.search(_flat(l))
        if m:
            return m.group(1).strip(), _flat(l)
    for l in reversed(body[-6:]):                         # signature block
        m = SUPPLIER_RX.search(_flat(l))
        if m:
            return m.group(1).strip(), _flat(l)
    for i in range(len(body) - 1, -1, -1):                # last title-case line that is not a sign-off
        l = _flat(body[i])
        if re.fullmatch(r"(?:[A-Z][\w&.\-]+\s+){1,3}[A-Z][\w&.\-]+", l) and not SIGNOFF.match(l):
            return l, l
        break
    return None, None


# ---- tables --------------------------------------------------------------------------------------------------
def _cells(line):
    cells = [c.strip() for c in line.split("|")]
    if cells and not cells[0]:
        cells = cells[1:]
    if cells and not cells[-1]:
        cells = cells[:-1]
    return cells


def _col_roles(header):
    roles = {}
    for i, h in enumerate(header):
        h = h.lower()
        if re.search(r"range|staffel|tier|von\b|from\b", h):
            roles.setdefault("range", i)
        elif re.search(r"total|gesamt|summe|betrag|montant", h):
            roles.setdefault("total", i)
        elif re.search(r"price|preis|prix|rate", h):
            roles.setdefault("price", i)
        elif re.search(r"^(qty|quantity|menge|anzahl|pcs|stk)\b", h):
            roles.setdefault("qty", i)
        elif re.search(r"part|art\.?-?nr|artikel|p/n|sku|mpn|ref", h):
            roles.setdefault("part", i)
    return roles


def _find_tables(lines):
    """-> list of (start, end) line ranges of pipe tables."""
    out, i = [], 0
    while i < len(lines):
        if lines[i].count("|") >= 2:
            j = i
            while j < len(lines) and (lines[j].count("|") >= 2 or re.fullmatch(r"[\s\-+|=:]+", lines[j] or "")):
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def read(text, target_qty=None):
    """-> dict(facts=[...], notes=[...]) in the extraction payload format."""
    facts, notes, seen = [], [], set()
    raw_lines = text.split("\n")
    work = ["" if l.lstrip().startswith(">") else l for l in raw_lines]   # quoted lines are someone else's numbers

    def add(entity, field, value, quote, conf):
        quote = _flat(quote)[:300]
        key = (entity, field, value)
        if value and key not in seen and _flat(value) in quote:
            seen.add(key)
            facts.append({"entity": entity, "field": field, "value": _flat(value), "quote": quote, "confidence": conf})

    name, quote = _supplier("\n".join(work))
    if name:
        add("doc", "supplier_name", name, quote, 0.6)

    lines, ccys, pending_qty = [], [], []

    def new_line(part=None, part_sent=None):
        ln = {"id": f"L{len(lines) + 1}", "part": part, "part_sent": part_sent, "has_price": False, "has_qty": False}
        lines.append(ln)
        if pending_qty:
            val, sent = pending_qty.pop()
            ln["has_qty"] = True
            add(ln["id"], "quantity", val, sent, 0.6)
        return ln

    ctx_text = "\n".join(work)
    ctx_ccy = CTX_CCY.search(ctx_text)

    # ---- pipe tables and whitespace price-break rows
    handled, tier_rows = set(), []
    for (a, b) in _find_tables(work):
        header_idx = next((i for i in range(a, b) if re.search(r"[A-Za-z]{3}", work[i]) and
                           _col_roles(_cells(work[i])) and not re.fullmatch(r"[\s\-+|=:]+", work[i])), None)
        if header_idx is None:
            continue
        roles = _col_roles(_cells(work[header_idx]))
        hdr = CTX_CCY.search(work[header_idx])
        hdr_ccy = (hdr.group("c") or hdr.group("c2")) if hdr else None
        data = [i for i in range(header_idx + 1, b) if not re.fullmatch(r"[\s\-+|=:]+", work[i])]
        handled.update(range(a, b))
        if "price" not in roles:
            continue
        for i in data:
            cells = _cells(work[i])
            if len(cells) <= roles["price"]:
                continue
            pm = PRICE_RX.search(cells[roles["price"]]) or re.search(rf"(?P<a2>{AMOUNT})", cells[roles["price"]])
            gd = pm.groupdict() if pm else {}
            amount = gd.get("a1") or gd.get("a2")
            if not amount:
                continue
            ccy_tok = gd.get("c1") or gd.get("c2")
            part = cells[roles["part"]] if "part" in roles and len(cells) > roles["part"] else None
            if "range" in roles and len(cells) > roles["range"]:
                rm = RANGE_CELL.match(cells[roles["range"]])
                if rm:
                    tier_rows.append((i, _num(rm["lo"]), _num(rm["hi"]) if rm["hi"] else None, amount, ccy_tok, part,
                                      hdr_ccy, work[header_idx]))
                continue
            ln = new_line(part, work[i])
            ln["has_price"] = True
            q = cells[roles["qty"]] if "qty" in roles and len(cells) > roles["qty"] else None
            if part and re.search(r"\d", part):
                add(ln["id"], "part_number", part, work[i], 0.7)
            if q and re.fullmatch(r"\d[\d.,]*", q):
                ln["has_qty"] = True
                add(ln["id"], "quantity", q, work[i], 0.7)
            add(ln["id"], "unit_price", amount, work[i], 0.7)
            if ccy_tok:
                ccys.append((ccy_tok, work[i]))
            elif hdr_ccy:
                ccys.append((hdr_ccy, work[header_idx]))
    for i, l in enumerate(work):                         # whitespace-aligned price breaks: "200-499 pcs   £1,585.00"
        m = TIER_LINE.match(l)
        if m and i not in handled:
            tier_rows.append((i, _num(m["lo"]), _num(m["hi"]) if m["hi"] else None, m["amt"], m["c1"] or m["c2"], None, None, None))
    if tier_rows:
        handled.update(r[0] for r in tier_rows)
        if target_qty is None:
            notes.append("price-break table found; pass the requested quantity (--qty) so the applicable tier can be chosen")
        else:
            hit = next((r for r in tier_rows if r[1] is not None and r[1] <= target_qty and (r[2] is None or target_qty <= r[2])), None)
            if hit is None:
                notes.append(f"no price-break row covers {target_qty:g} pcs")
            else:
                i, lo, hi, amount, ccy_tok, part, hdr_c, hdr_line = hit
                rest_text = "\n".join(w for k, w in enumerate(work) if k not in handled)
                part_guess = part or next(iter(_parts(rest_text)), None)
                ln = new_line(part_guess, None)
                ln["has_price"] = True
                add(ln["id"], "unit_price", amount, work[i], 0.6)
                if part and re.search(r"\d", part):
                    add(ln["id"], "part_number", part, work[i], 0.6)
                if ccy_tok:
                    ccys.append((ccy_tok, work[i]))
                elif hdr_c and hdr_line:
                    ccys.append((hdr_c, hdr_line))
    for i in handled:
        work[i] = ""

    sents = [s for s in segments("\n".join(work)) if not re.match(r"^(From|To|Cc|Subject|Date):", s)]
    subject = next((l for l in raw_lines if l.startswith("Subject:")), "")
    part_sentence = {}
    for s in sents:
        for p in _parts(s):
            part_sentence.setdefault(p, s)
    for ln in lines:                                    # tier-table line: its part is named elsewhere in the text
        if ln["part"] and ln["part_sent"] is None:
            ln["part_sent"] = part_sentence.get(ln["part"])
    last_part = last_part_sent = None
    price_ctx = re.compile(r"\b(each|per|pro|unit price|price|preis|a piece|apiece)\b|/\s*(?:pc|pcs|ea)|@", re.I)
    for s in sents:
        row = ROW_RX.match(s)
        if row:                                          # layout table row: "1 PART description qty CCY price CCY total"
            part = row["part"].strip("-_.|~\"'`*,;:")
            ln = new_line(part, s)
            ln.update(has_price=True, has_qty=True)
            if part and any(ch.isdigit() for ch in part):
                add(ln["id"], "part_number", part, s, 0.7)
            add(ln["id"], "quantity", row["qty"], s, 0.8)
            add(ln["id"], "unit_price", row["price"], s, 0.8)
            ccys.append((row["c"], s))
            continue
        parts = _parts(s)
        if parts:
            last_part, last_part_sent = parts[0], s
        freight = FREIGHT_KW.search(s) is not None
        tier = bool(TIER_RX.search(s)) and not re.search(r"\bfor \d", s)

        prices, freight_seen = [], False
        for clause in _clauses(s):
            if FREIGHT_KW.search(clause):
                freight_seen = True
                continue
            if re.search(r"\b(total|subtotal|vat|tax|mwst)\b|\(one-off\)", clause, re.I):
                continue
            if freight_seen and not price_ctx.search(clause):
                continue
            found = list(PRICE_RX.finditer(clause))
            if any(m.group("c1") for m in found):
                found = [m for m in found if m.group("c1") or not (m.group("a2") or "").isdigit()]
            prices.extend((m, clause) for m in found)
        if prices and tier:
            notes.append("price tier / list price ignored: " + s[:80])
            prices = []

        ln = None
        if prices:
            m, clause = prices[0]
            amount, ccy = m.group("a1") or m.group("a2"), m.group("c1") or m.group("c2")
            if lines and lines[-1]["has_price"] and lines[-1]["part_sent"] is None and not parts and not any(
                    x["has_price"] is False for x in lines):
                pass
            same_item = parts and lines and lines[-1]["part"] == parts[0] and not lines[-1]["has_price"]
            if parts and not same_item:
                ln = new_line(parts[0], s)
                add(ln["id"], "part_number", parts[0], s, 0.7)
            elif lines and not lines[-1]["has_price"]:
                ln = lines[-1]
            else:
                ln = new_line(last_part, last_part_sent)
            ln["has_price"] = True
            add(ln["id"], "unit_price", amount, s, 0.7)
            ccys.append((ccy, s))
            b = BASIS_RX.search(s)
            if b:
                add(ln["id"], "price_basis", b.group(1), s, 0.6)

        s_q = MOQ_RX.sub(" ", s)
        if not tier and (prices or not freight) and not VALID_UNTIL_RX.search(s):
            rest = re.search(r"\b(?:remaining|rest)\s+(\d[\d.,]*)", s, re.I)
            if rest and not prices and not PAYMENT_RX.search(s):
                ln = new_line(lines[-1]["part"] if lines else last_part, s)
                ln["has_qty"] = True
                add(ln["id"], "quantity", rest.group(1), s, 0.6)
                lm = LEAD_RX.search(s)
                if lm:
                    add(ln["id"], "lead_time", lm.group(1), s, 0.6)
            else:
                for rx in QTY_RXS:
                    m = next((m for m in rx.finditer(s_q) if not re.search(r"per\s+$|/\s*$|pro\s+$", s_q[:m.start()])), None)
                    if m:
                        target = ln if ln is not None else (lines[-1] if lines and not lines[-1]["has_qty"] else None)
                        if target is None:
                            pending_qty[:] = [(m.group(1), s)]
                            break
                        target["has_qty"] = True
                        add(target["id"], "quantity", m.group(1), s, 0.7)
                        break
        m = MOQ_RX.search(s)
        if m and lines:
            add(lines[-1]["id"], "min_order_qty", m.group(1).rstrip(".,"), s, 0.7)

        # --- document-level facts
        if not re.search(r"\b(?:remaining|rest)\s+\d", s, re.I) or prices:
            lm = LEAD_RX.search(s)
            if lm and not NOT_LEAD_CTX.search(s) and (LEAD_CTX.search(s) or prices):
                add("doc", "lead_time", lm.group(1), s, 0.7)
        m = VALID_UNTIL_RX.search(s)
        if m:
            add("doc", "valid_until", m.group("d"), s, 0.8)
        else:
            m = VALID_FOR_RX.search(s)
            if m:
                add("doc", "validity_period", m.group(0), s, 0.7)
        m = PAYMENT_RX.search(s)
        if m:
            val = re.sub(r"[\s.\-—|_~=]+$", "", m.group(1).strip())
            if len(re.findall(r"[A-Za-z0-9]", val)) >= 4:
                add("doc", "payment_terms", val, s, 0.7)
        if freight:
            fc = _clauses(s)
            start = next(i for i, c in enumerate(fc) if FREIGHT_KW.search(c))
            add("doc", "freight", ", ".join(fc[start:]).rstrip("."), s, 0.6)
        if INCOTERM_RX.search(s):
            add("doc", "incoterms", INCOTERM_RX.search(s).group(1), s, 0.8)

    # ex-stock wording counts as a lead time only when no explicit duration was found
    if not any(f["field"] == "lead_time" for f in facts):
        for s in sents:
            m = EX_STOCK_RX.search(s)
            if m and not NOT_LEAD_CTX.search(s):
                add("doc", "lead_time", m.group(1), s, 0.5)
                break

    for ln in lines:
        if any(f["entity"] == ln["id"] and f["field"] == "part_number" for f in facts):
            continue
        if ln["part"] and ln["part_sent"]:
            add(ln["id"], "part_number", ln["part"], ln["part_sent"], 0.6)
        elif len(part_sentence) == 1:
            p, sent = next(iter(part_sentence.items()))
            add(ln["id"], "part_number", p, sent, 0.5)
        elif not part_sentence and len(_parts(subject)) == 1 and len(lines) == 1:
            add(ln["id"], "part_number", _parts(subject)[0], subject, 0.4)
    if ccys:
        if len({c.upper() for c, _ in ccys}) == 1:
            add("doc", "currency", ccys[0][0], ccys[0][1], 0.7)
        else:
            for ln, (c, s) in zip([l for l in lines if l["has_price"]], ccys):
                add(ln["id"], "currency", c, s, 0.6)
    elif ctx_ccy and any(l["has_price"] for l in lines):
        add("doc", "currency", ctx_ccy.group("c") or ctx_ccy.group("c2"),
            next(w for w in work + raw_lines if CTX_CCY.search(w)), 0.5)
    priced = [l["id"] for l in lines if l["has_price"]]
    if len(priced) == 1 and not any(f["field"] == "price_basis" for f in facts):
        bm = next(((BASIS_RX.search(w), w) for w in raw_lines if not w.lstrip().startswith(">") and BASIS_RX.search(w)
                   and not re.match(r"^(From|To|Cc|Subject|Date):", w)), None)
        if bm:
            add(priced[0], "price_basis", bm[0].group(1), bm[1], 0.5)
    if not priced:
        notes.append("no priced line found")
    return {"facts": facts, "notes": notes}
