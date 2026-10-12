import re
import unicodedata

# Keep Korean connecting endings intact; evidence stems work without endings.
BREAK = re.compile(r"[.!?。！？\n,;]+|(?:하지만|그런데|반면)\s*|지만|(?<![하오리])는데")


def normalize(text):
    return re.sub(r"[ \t\r\f\v]+", " ", unicodedata.normalize("NFC", text)).strip()


def clauses(text):
    """Yield normalized-text offsets. Original text is preserved separately."""
    start = 0
    for match in BREAK.finditer(text):
        if text[start:match.start()].strip():
            yield start, match.start(), text[start:match.start()]
        start = match.end()
    if text[start:].strip():
        yield start, len(text), text[start:]
