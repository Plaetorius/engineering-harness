"""Text / email / HTML documents -> canonical text + metadata + deterministic injection scan.

The canonical text is what every locator ('chars:S-E') and every model payload refers to.
Documents are untrusted: the scan flags instruction-like text and hidden text so a human sees it,
and extraction prompts treat the whole document as data.
"""
import re
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

TEXT_VERSION = "2"
TEXT_SUFFIXES = {".txt": "txt", ".md": "txt", ".eml": "eml", ".html": "html", ".htm": "html", ".pdf": "pdf"}
MAX_CHARS = 2_000_000
BLOCK_TAGS = {"p", "div", "tr", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "blockquote"}
HIDDEN_TAGS = {"title", "template"}      # never rendered in the message body
VOID_TAGS = {"br", "img", "meta", "link", "input", "hr", "area", "base", "col", "embed", "source", "wbr"}
HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?:px|pt|em|%)?\s*(?:;|$)|"
                          r"opacity\s*:\s*0(?:\.0+)?\s*(?:;|$)|color\s*:\s*(?:#f{3}(?:f{3})?|white)\b", re.I)


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden_parts, self.stack, self.skip = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
            return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")
        if tag in VOID_TAGS:
            return
        a = {}
        for k, v in attrs:                                  # HTML: the FIRST occurrence of a repeated attribute wins
            a.setdefault(k, v)
        hidden = tag in HIDDEN_TAGS or "hidden" in a or bool(HIDDEN_STYLE.search(a.get("style") or ""))
        parent_hidden = bool(self.stack) and self.stack[-1][1]
        self.stack.append((tag, bool(hidden or parent_hidden)))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        (self.hidden_parts if self.stack and self.stack[-1][1] else self.parts).append(data)


def html_to_text(html):
    p = _Html()
    p.feed(html)
    p.close()
    return "".join(p.parts), "".join(p.hidden_parts).strip()


_SOFT = re.compile("\u00ad")


def normalize_soft_hyphens(text):
    """U+00AD between alphanumerics is a real hyphen that a PDF font encoded as a soft hyphen (part numbers, phone numbers,
    heat numbers) unless both neighbours are lowercase letters (genuine hyphenation point: removed). -> (text, count)"""
    n = text.count("\u00ad")
    if not n:
        return text, 0
    text = re.sub("(?<=[a-z])\u00ad(?=[a-z])", "", text)
    return _SOFT.sub("-", text), n


def _clean(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{4,}", "\n\n\n", text).strip("\n") + "\n"


def _decode(raw):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


_NUM = re.compile(r"\d+(?:[.,']\d+)*")


def _alternative_diff(plain, html_text):
    """The plain-text and HTML alternatives of one email are two documents: extraction reads the plain one, most mail
    programs show the HTML one. -> None when they agree on every number and the HTML has no instruction-like wording."""
    p, h = set(_NUM.findall(plain)), set(_NUM.findall(html_text))
    hits = sorted({label for label, _, _ in scan_text(html_text)})
    if p == h and not hits:
        return None
    return {"html_only": sorted(h - p)[:20], "plain_only": sorted(p - h)[:20], "html_hits": hits}


def _eml(raw):
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    head = "".join(f"{h}: {str(msg[h]).strip()}\n" for h in ("From", "To", "Cc", "Subject", "Date") if msg[h])
    body, hidden, kinds = "", "", []
    html_part = plain_part = None
    for part in msg.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        ct = part.get_content_type()
        if ct == "text/plain" and plain_part is None:
            plain_part = part
        elif ct == "text/html" and html_part is None:
            html_part = part

    def content(part):
        try:
            return part.get_content()
        except (LookupError, UnicodeDecodeError):
            return _decode(part.get_payload(decode=True) or b"")

    if plain_part is not None:
        body = content(plain_part)
        kinds.append("plain")
    alternative = None
    if html_part is not None:
        html_text, hidden = html_to_text(content(html_part))
        kinds.append("html")
        if plain_part is None:
            body = html_text
        else:
            alternative = _alternative_diff(body, html_text)
    attachments = [{"filename": p.get_filename(), "content_type": p.get_content_type(),
                    "bytes": len(p.get_payload(decode=True) or b"")} for p in msg.iter_attachments()]
    return head + "\n" + body, {"headers": {h: str(msg[h])[:200] for h in ("From", "To", "Subject", "Date") if msg[h]},
                                "parts": kinds, "attachments": attachments,
                                **({"alternative": alternative} if alternative else {})}, hidden


# ---- injection / manipulation scan (deterministic heuristics; a hit is a prompt for a human, not a verdict) ----
SCAN_PATTERNS = [
    ("ignore_instructions", r"\b(?:ignore|disregard|forget|override)\b[^.]{0,30}\b(?:previous|prior|above|earlier|all|any)\b"
                            r"[^.]{0,30}\b(?:instructions?|prompts?|rules?|guidelines?)\b"),
    ("addresses_ai", r"\b(?:you are now|you must act as|act as (?:an? |the )?(?:ai|assistant|chatbot|language model|llm|agent)|"
                     r"(?:^|[.!?]\s+)pretend (?:to be|you are)|you (?:must |will |should )?pretend|as an ai|language model|ai assistant|ai (?:systems?|agents?|models?|reviewers?)|"
                     r"(?:hey|hi|hello|dear|attention)[,:]?\s+(?:claude|chatgpt|gpt|gemini|llm|ai|assistant)|"
                     r"(?:note|message|instructions?|attention)\s+(?:to|for)\s+(?:the\s+)?(?:ai|llm|assistants?|"
                     r"automated|language models?))\b"),
    ("system_prompt", r"\b(?:system prompt|developer message|hidden instructions?)\b"),
    ("fake_role_tag", r"(?:<(?:\s*/)?\s*(?:system|assistant|instructions?)\s*>|^\s*(?:system|assistant)\s*:)"),
    ("exfiltration", r"\b(?:reveal|print|output|send|forward|leak|exfiltrate|share|disclose|paste)\b[^.]{0,30}\b(?:"
                     r"(?:the|your|its|my|admin(?:'s)?)\s+(?:\w+\s+){0,1}(?:api[ -]?keys?|system prompt|credentials|private keys?)|"
                     r"(?:your|its|my|admin(?:'s)?)\s+(?:\w+\s+){0,2}(?:passwords?|secrets?|tokens?))\b"),
    ("decision_steering", r"\b(?:pick|select|choose|rank|mark|recommend|rate)\b[^.]{0,25}\b(?:this|our|my)\b[^.]{0,15}"
                          r"\b(?:quote|offer|supplier|bid|proposal)\b[^.]{0,25}\b(?:best|cheapest|winner|preferred|"
                          r"first|top|lowest)\b"),
    ("secrecy", r"\b(?:do not|don't|never)\b[^.]{0,15}\b(?:tell|inform|mention|alert|notify|reveal)\b[^.]{0,25}"
                r"\b(?:user|human|operator|reviewer|buyer|anyone)\b"),
]
_COMPILED = [(label, re.compile(rx, re.I | re.M)) for label, rx in SCAN_PATTERNS]
# zero-width and format characters, bidi embeddings/overrides/isolates (display order != logical order), and the Unicode
# "tag" block (invisible text that language models still read)
_INVISIBLE = re.compile("[\u034f\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff\U000e0000-\U000e007f]")


def scan_text(text):
    """-> list of (label, start, end). One hit per label (the first), plus invisible-character runs."""
    hits = []
    for label, rx in _COMPILED:
        m = rx.search(text)
        if m:
            hits.append((label, m.start(), m.end()))
    m = _INVISIBLE.search(text[1:])
    if m:
        hits.append(("invisible_characters", m.start() + 1, m.end() + 1))
    return hits


def build(path):
    """-> dict(text, kind, meta, hidden_text, hits). Never raises on odd encodings."""
    path = Path(path)
    if TEXT_SUFFIXES[path.suffix.lower()] == "pdf":
        from . import pdfdoc
        return pdfdoc.build(path)
    return build_bytes(path.read_bytes(), TEXT_SUFFIXES[path.suffix.lower()])


def build_bytes(raw, kind):
    raw = raw[: MAX_CHARS * 4]
    meta, hidden = {}, ""
    if kind == "eml":
        text, meta, hidden = _eml(raw)
    elif kind == "html":
        text, hidden = html_to_text(_decode(raw))
    else:
        text = _decode(raw)
    text, softs = normalize_soft_hyphens(text)
    text = _clean(text)[:MAX_CHARS]
    meta["hidden_chars"] = len(hidden)
    meta["soft_hyphens_normalized"] = softs
    return {"text": text, "kind": kind, "meta": meta, "hidden_text": hidden, "hits": scan_text(text),
            "hidden_hits": scan_text(hidden) if hidden else []}
