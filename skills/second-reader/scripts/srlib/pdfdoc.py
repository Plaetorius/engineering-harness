"""PDF -> canonical text. Text-layer pages via pdftotext; image-only (scanned) pages via pdftoppm + tesseract with
per-word confidence and bounding boxes. Everything runs locally; nothing leaves the machine.

PDFs are untrusted input handed to external parsers (poppler, tesseract): every call is argv-only (no shell), has a
timeout, and the page count is bounded.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PDF_VERSION = "1"
MIN_TEXT_CHARS = 25          # fewer non-space characters than this on a page => treat the page as scanned
OCR_DPI = 300
OCR_LANG = "eng"
UNREADABLE_CONF = 40       # a page whose mean OCR confidence is below this is dropped, not read
OCR_LOW_CONF = 75            # word confidence (0-100) below which a number is flagged
MAX_PAGES = 200
TIMEOUT = 180


class PdfError(Exception):
    pass


def _run(argv, timeout=TIMEOUT):
    try:
        return subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise PdfError(f"{argv[0]} is not installed; needed to read PDFs locally") from exc
    except subprocess.TimeoutExpired as exc:
        raise PdfError(f"{argv[0]} timed out after {timeout}s") from exc


def tools_available():
    return {t: shutil.which(t) is not None for t in ("pdfinfo", "pdftotext", "pdftoppm", "tesseract")}


def page_count(path):
    r = _run(["pdfinfo", str(path)])
    m = re.search(rb"Pages:\s+(\d+)", r.stdout)
    if r.returncode != 0 or not m:
        raise PdfError("not a readable PDF (pdfinfo failed)")
    return int(m.group(1))


def _page_text(path, page):
    r = _run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(path), "-"])
    text = r.stdout.decode("utf-8", "replace")
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    return "\n".join(l.rstrip() for l in text.split("\n")).strip("\n")


def _fix_page(text, counter):
    from .textdoc import normalize_soft_hyphens
    text, n = normalize_soft_hyphens(text)
    counter[0] += n
    return text


def _ocr_page(path, page, tmp, dpi=OCR_DPI, lang=OCR_LANG):
    """-> (text, words) where words = [(start, end, text, conf, x, y, w, h)] with offsets relative to `text`."""
    prefix = str(Path(tmp) / f"p{page}")
    r = _run(["pdftoppm", "-r", str(dpi), "-png", "-f", str(page), "-l", str(page), "-singlefile", str(path), prefix])
    img = prefix + ".png"
    if r.returncode != 0 or not Path(img).exists():
        raise PdfError(f"could not render page {page}")
    t = _run(["tesseract", img, "stdout", "--psm", "6", "-l", lang, "tsv"])
    if t.returncode != 0:
        raise PdfError(f"tesseract failed on page {page}")
    rows = [l.split("\t") for l in t.stdout.decode("utf-8", "replace").split("\n")[1:] if l.count("\t") >= 11]
    lines, order = {}, []
    for c in rows:
        word = c[11].strip()
        if not word or c[0] != "5":
            continue
        key = (c[2], c[3], c[4])
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append((word, float(c[10]), int(c[6]), int(c[7]), int(c[8]), int(c[9])))
    text, words = "", []
    for key in order:
        for word, conf, x, y, w, h in lines[key]:
            if text and not text.endswith("\n"):
                text += " "
            words.append((len(text), len(text) + len(word), word, conf, x, y, w, h))
            text += word
        text += "\n"
    return text.rstrip("\n"), words


def build(path, dpi=OCR_DPI, lang=OCR_LANG):
    """-> dict(text, kind='pdf', meta, hidden_text, hits, hidden_hits, pdf={pages, words})"""
    from .textdoc import scan_text
    path = Path(path)
    n = page_count(path)
    if n > MAX_PAGES:
        raise PdfError(f"{n} pages exceeds the {MAX_PAGES}-page limit")
    text, pages, words, softs = "", [], [], [0]
    with tempfile.TemporaryDirectory(prefix="sr-pdf-") as tmp:
        for p in range(1, n + 1):
            body = _fix_page(_page_text(path, p), softs)
            method, mean = "text", None
            if len(re.sub(r"\s", "", body)) < MIN_TEXT_CHARS:
                body, w = _ocr_page(path, p, tmp, dpi, lang)
                method = "ocr"
                mean = round(sum(x[3] for x in w) / len(w), 1) if w else 0.0
                if mean < UNREADABLE_CONF:                       # garbage must never reach extraction
                    body, w, method = "", [], "ocr_unreadable"
            else:
                w = []
            marker = f"[page {p}]\n"
            text += marker
            start = len(text)
            for (s, e, word, conf, x, y, ww, h) in w:
                words.append((p, start + s, start + e, word, conf, x, y, ww, h))
            text += body
            pages.append({"page": p, "method": method, "char_start": start, "char_end": len(text), "mean_conf": mean})
            text += "\n\n"
    text = text.rstrip("\n") + "\n"
    meta = {"pages": n, "ocr_pages": [p["page"] for p in pages if p["method"] == "ocr"],
            "unreadable_pages": [p["page"] for p in pages if p["method"] == "ocr_unreadable"], "hidden_chars": 0,
            "soft_hyphens_normalized": softs[0],
            "ocr": {"engine": "tesseract", "dpi": dpi, "lang": lang, "psm": 6} if words or any(
                p["method"].startswith("ocr") for p in pages) else None}
    return {"text": text, "kind": "pdf", "meta": meta, "hidden_text": "", "hits": scan_text(text), "hidden_hits": [],
            "pdf": {"pages": pages, "words": words}}


def locate(db, doc_id, start, end):
    """Where does text[start:end] sit on the page(s)? -> dict(page, method, bbox, min_conf, words) or None."""
    page = db.execute("SELECT * FROM doc_pages WHERE doc_id=? AND char_start<=? AND char_end>? ORDER BY page LIMIT 1",
                      (doc_id, start, start)).fetchone()
    if page is None:
        return None
    out = {"page": page["page"], "method": page["method"], "bbox": None, "min_conf": None, "words": 0}
    ws = db.execute("SELECT * FROM ocr_words WHERE doc_id=? AND page=? AND char_end>? AND char_start<?",
                    (doc_id, page["page"], start, end)).fetchall()
    if ws:
        out["bbox"] = (min(w["x"] for w in ws), min(w["y"] for w in ws),
                       max(w["x"] + w["w"] for w in ws), max(w["y"] + w["h"] for w in ws))
        out["min_conf"] = min(w["conf"] for w in ws)
        out["words"] = len(ws)
    return out


def render_page(path, page, out_png, dpi=110):
    r = _run(["pdftoppm", "-r", str(dpi), "-png", "-f", str(page), "-l", str(page), "-singlefile", str(path),
              str(out_png).removesuffix(".png")])
    if r.returncode != 0:
        raise PdfError("could not render the page")
    return out_png
