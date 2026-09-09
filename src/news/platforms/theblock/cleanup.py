# INFRASTRUCTURE
import json
import re
import sys

from crawl4ai.html2text import HTML2Text

_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

_LINK_URL_RE       = re.compile(r'\[([^\]]+)\]\(https?://[^)]+\)')
_DISCLAIMER_RE     = re.compile(r'^Disclaimer: The Block is an independent media outlet.*$', re.MULTILINE)
_COPYRIGHT_RE      = re.compile(
    r'^©\s*\d{4}\s+(?:The Block Crypto,\s*Inc\.|The Block)\.?\s*All Rights Reserved.*$',
    re.MULTILINE,
)
_NEWSLETTER_CTA_RE = re.compile(r'^_.*subscribe to the .*newsletter.*$', re.MULTILINE)
_BLANK_RUN_RE      = re.compile(r'\n{3,}')

_MCE_SPAN_RE        = re.compile(r'<span[^>]*data-mce-type[^>]*>.*?</span>', re.DOTALL)
_COMMISSIONED_RE    = re.compile(r'^_?This post is commissioned\b.*$', re.MULTILINE)
_PODCAST_SUB_CTA_RE = re.compile(r'^[*_]*Listen below[,.]?\s+and subscribe to\b.*$', re.MULTILINE)
_NEWSLETTER_PROMO_RE = re.compile(
    r'^\*\*The Block Newsletters[^\n]*\n[^\n]*theblock\.co/newsletters[^\n]*',
    re.MULTILINE,
)
_CAMPUS_CTA_RE      = re.compile(r'^.*theblock\.co/campus.*$', re.MULTILINE)

_SPONSOR_BLOCK_RE   = re.compile(
    r'\n\*{0,2}This episode is brought to you by\b.*',
    re.DOTALL | re.IGNORECASE,
)


# FUNCTIONS

def cleanup(raw_html: str, entry: dict) -> str:
    data = _find_news_article(raw_html)
    if data is None:
        print(f"[theblock] cleanup: no JSON-LD NewsArticle found — {entry.get('url','?')}", file=sys.stderr)
        return ""

    article_body = data.get("articleBody", "")
    if not article_body:
        print(f"[theblock] cleanup: empty articleBody — {entry.get('url','?')}", file=sys.stderr)
        return ""

    pub_date = data.get("datePublished", "")
    if pub_date:
        entry["publication_date"] = pub_date

    return _post_clean(_html_to_markdown(article_body))


def _find_news_article(html: str) -> dict | None:
    for raw in _LD_RE.findall(html):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        for candidate in _iter_candidates(data):
            if _is_news_article(candidate):
                return candidate
    return None


def _iter_candidates(data) -> object:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
    elif isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                if isinstance(item, dict):
                    yield item


def _is_news_article(data: dict) -> bool:
    t = data.get("@type", "")
    if isinstance(t, list):
        return "NewsArticle" in t
    return t == "NewsArticle"


def _post_clean(md: str) -> str:
    md = _LINK_URL_RE.sub(r'\1', md)
    md = _MCE_SPAN_RE.sub('', md)
    md = _DISCLAIMER_RE.sub('', md)
    md = _COPYRIGHT_RE.sub('', md)
    md = _NEWSLETTER_CTA_RE.sub('', md)
    md = _COMMISSIONED_RE.sub('', md)
    md = _PODCAST_SUB_CTA_RE.sub('', md)
    md = _NEWSLETTER_PROMO_RE.sub('', md)
    md = _CAMPUS_CTA_RE.sub('', md)
    md = _SPONSOR_BLOCK_RE.sub('', md)
    lines = [line.rstrip() for line in md.splitlines()]
    md = '\n'.join(lines)
    md = _BLANK_RUN_RE.sub('\n\n', md)
    return md.strip()


def _html_to_markdown(html: str) -> str:
    h = HTML2Text()
    h.body_width   = 0
    h.ignore_images = True
    return h.handle(html).strip()
