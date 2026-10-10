"""Locale-aware number and date parsing. Returns values plus flags; never guesses silently.

parse_number flags:
  style_dot_decimal / style_comma_decimal  - the decimal separator evidenced by this value
  ambiguous_sep   - a single separator followed by exactly 3 digits ("1,234" / "1.234"); value is a guess
  thousands_sep   - separator(s) interpreted as grouping
  malformed       - looked numeric but separators are inconsistent (value is None)
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_CUR_WORDS = re.compile(r"(?i)\b(eur|usd|gbp|chf|cad|aud|jpy|czk|sek|nok|dkk|pln)\b")
_CUR_SYMS = re.compile(r"[€$£¥]")


def parse_number(value):
    """-> (Decimal | None, set(flags))"""
    if value is None or isinstance(value, bool):
        return None, set()
    if isinstance(value, Decimal):
        return value, set()
    if isinstance(value, int):
        return Decimal(value), set()
    if isinstance(value, float):
        return (Decimal(repr(value)) if value == value and abs(value) != float("inf") else None), set()
    s = str(value).strip()
    if not s:
        return None, set()
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    s = s.replace(" ", " ").replace(" ", " ")
    s = _CUR_WORDS.sub("", s)
    s = _CUR_SYMS.sub("", s).strip()
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("-"):
        neg, s = True, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    s = s.strip().replace(" ", "").replace("'", "")
    if re.fullmatch(r"(\d+\.?\d*|\.\d+)[eE][+-]?\d+", s):          # scientific notation, e.g. 1.5E+3
        try:
            num = Decimal(s)
        except InvalidOperation:
            return None, {"malformed"}
        return Decimal(format(-num if neg else num, "f")), set()
    if not s or not re.fullmatch(r"[0-9.,]+", s) or not re.search(r"\d", s):
        return None, set()
    flags = set()
    dots, commas = s.count("."), s.count(",")
    if dots and commas:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        if s.count(dec) > 1 or s.rfind(thou) > s.rfind(dec):
            return None, {"malformed"}
        groups = s.split(dec)[0].split(thou)
        if not all(len(g) == 3 for g in groups[1:]) or not 1 <= len(groups[0]) <= 3:
            return None, {"malformed"}
        s = s.replace(thou, "").replace(dec, ".")
        flags.add("style_dot_decimal" if dec == "." else "style_comma_decimal")
    elif dots or commas:
        sep = "." if dots else ","
        parts = s.split(sep)
        if len(parts) > 2:
            if all(len(g) == 3 for g in parts[1:]) and 1 <= len(parts[0]) <= 3:
                s = "".join(parts)
                flags.add("thousands_sep")
            else:
                return None, {"malformed"}
        else:
            head, tail = parts
            if len(tail) == 3 and 1 <= len(head) <= 3 and head != "0":
                flags.add("ambiguous_sep")
                if sep == ",":          # guess: comma-grouped thousands
                    s = head + tail
                    flags.add("thousands_sep")
                # a lone "." keeps its decimal reading
            else:
                flags.add("style_dot_decimal" if sep == "." else "style_comma_decimal")
                s = head + "." + tail
    try:
        num = Decimal(s)
    except InvalidOperation:
        return None, {"malformed"}
    return (-num if neg else num), flags


_ISO = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[T\s].*)?$")
_DMY = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})(?:[T\s].*)?$")


_MONTHS = {"jan": 1, "january": 1, "januar": 1, "feb": 2, "february": 2, "februar": 2, "mar": 3, "march": 3,
           "mrz": 3, "maerz": 3, "marz": 3, "apr": 4, "april": 4, "may": 5, "mai": 5, "jun": 6, "june": 6, "juni": 6,
           "jul": 7, "july": 7, "juli": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
           "october": 10, "okt": 10, "oktober": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
           "dez": 12, "dezember": 12}
_DMONY = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?[\s.\-]+([A-Za-z]{3,9})\.?,?[\s.\-]+(\d{4})$")
_MONDY = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$")


def parse_date(value, dayfirst=None):
    """-> (date | None, set(flags)). flags: ambiguous (day/month order guessed), invalid (looked like a date)."""
    if isinstance(value, datetime):
        return value.date(), set()
    if isinstance(value, date):
        return value, set()
    if value is None:
        return None, set()
    s = str(value).strip()
    if not s:
        return None, set()
    m = _ISO.match(s)
    if m:
        y, mo, d = map(int, m.groups())
        return _mk(y, mo, d)
    m = _DMONY.match(s)
    if m and m.group(2).lower() in _MONTHS:
        return _mk(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    m = _MONDY.match(s)
    if m and m.group(1).lower() in _MONTHS:
        return _mk(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    m = _DMY.match(s)
    if m:
        a, b, y = m.groups()
        a, b, y = int(a), int(b), int(y) + (0 if len(y) == 4 else (2000 if int(y) < 70 else 1900))
        if a > 12 and b <= 12:
            return _mk(y, b, a)
        if b > 12 and a <= 12:
            return _mk(y, a, b)
        if a == b:
            return _mk(y, a, b)
        d, flags = _mk(y, b, a) if dayfirst else _mk(y, a, b)
        if dayfirst is None:
            flags = flags | {"ambiguous"}
        return d, flags
    return None, set()


def _mk(y, mo, d):
    try:
        return date(y, mo, d), set()
    except ValueError:
        return None, {"invalid"}
