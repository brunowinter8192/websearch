# INFRASTRUCTURE
import html
import re


# FUNCTIONS

def strip_bloat(text: str) -> str:
    text = html.unescape(text)
    text = _strip_doubled_prefix(text)
    text = re.sub(r'^Web results', '', text)
    text = re.sub(r'^Featured snippet from the web', '', text)
    text = re.sub(r'^\s*·\s*Translate this page', '', text)
    text = re.sub(r'\bRead more.*', '', text)
    text = re.sub(r'\d[\d,.]*[Kk]?\+? *(likes|comments|answers|posts) *·[^\n]*', '', text)
    text = re.sub(r'\S*›\S*', '', text)
    text = re.sub(r'\d{1,2} \w{3,9} \d{4} — ', '', text)
    text = re.sub(r'&[a-z]+;|&#\d+;', '', text)
    text = re.sub(r'Tagged with [\w, ]+\.?$', '', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(text.split())


def _strip_doubled_prefix(text: str) -> str:
    if len(text) < 60:
        return text
    head = text[:300]
    best_cut = 0
    for L in (100, 70, 50, 30):
        if len(head) < 2 * L:
            continue
        for start in range(0, min(len(head) - 2 * L, 100)):
            chunk = head[start:start + L]
            second = head.find(chunk, start + L)
            if 0 < second and second + L <= len(head):
                cut = second + L
                if cut > best_cut:
                    best_cut = cut
    return text[best_cut:] if best_cut else text


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    sub  = text[:max_len]
    half = max_len // 2
    idx = sub.rfind(". ")
    if idx >= half:
        return text[:idx + 1]
    idx = sub.rfind(" ")
    if idx >= 0:
        return text[:idx] + "…"
    return text[:max_len] + "…"
