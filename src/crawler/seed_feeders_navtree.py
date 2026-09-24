# INFRASTRUCTURE
import asyncio
import json
import logging
import re
from urllib.parse import urljoin, urlsplit

import httpx

from src.crawler.seed_feeders_constants import ABSENT_STATUSES, HTTP_TIMEOUT_S, USER_AGENT, NAVTREE_FETCH_CONCURRENCY

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_RSC_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
_RSC_ROW_ID_RE = re.compile(r'^[0-9a-f]+$')

_URL_KEYS = ("href", "url")
_CHILD_KEYS = ("childpages", "children", "items", "pages", "navigation", "nav", "subitems")
_VERSION_LIST_KEY_HINT = "version"
_CURRENT_VERSION_KEY_HINT = "currentversion"
_PATH_WITHOUT_LANGUAGE_KEY_HINT = "pathwithoutlanguage"


# FUNCTIONS

def _extract_next_data_payloads(html: str) -> list:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return []
    return [json.loads(match.group(1))]


def _extract_rsc_stream_payloads(html: str) -> list:
    matches = _RSC_PUSH_RE.findall(html)
    if not matches:
        return []
    full_stream = "".join(json.loads(m) for m in matches)
    rows = re.split(r'\n(?=[0-9a-f]+:)', full_stream)
    payloads = []
    non_json_rows = 0
    for row in rows:
        row_id, _, value = row.partition(":")
        if not _RSC_ROW_ID_RE.match(row_id):
            continue
        try:
            payloads.append(json.loads(value))
        except json.JSONDecodeError:
            non_json_rows += 1
    if non_json_rows:
        logger.debug("RSC stream: %d of %d rows are not JSON and were skipped", non_json_rows, len(rows))
    return payloads


def extract_payloads(html: str) -> list:
    for extractor in (_extract_next_data_payloads, _extract_rsc_stream_payloads):
        payloads = extractor(html)
        if payloads:
            return payloads
    return []


def _child_key_of(obj) -> str | None:
    if not isinstance(obj, dict):
        return None
    for key, value in obj.items():
        if (key.lower() in _CHILD_KEYS and isinstance(value, list) and value
                and all(isinstance(c, dict) for c in value)):
            return key
    return None


def _collect_tree_hrefs(node) -> list:
    hrefs = []
    if not isinstance(node, dict):
        return hrefs
    for key in _URL_KEYS:
        value = node.get(key)
        if isinstance(value, str) and value:
            hrefs.append(value)
            break
    child_key = _child_key_of(node)
    if child_key:
        for child in node[child_key]:
            hrefs.extend(_collect_tree_hrefs(child))
    return hrefs


def _find_tree_candidates(payload, out: list | None = None) -> list:
    if out is None:
        out = []
    if isinstance(payload, dict):
        if _child_key_of(payload):
            out.append(payload)
        for value in payload.values():
            _find_tree_candidates(value, out)
    elif isinstance(payload, list):
        for item in payload:
            _find_tree_candidates(item, out)
    return out


def _collect_flat_hrefs(payload, out: list) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in _URL_KEYS and isinstance(value, str):
                out.append(value)
            else:
                _collect_flat_hrefs(value, out)
    elif isinstance(payload, list):
        for item in payload:
            _collect_flat_hrefs(item, out)


def find_navigation_tree(payloads: list) -> tuple:
    best_hrefs = []
    best_source = None
    for payload in payloads:
        for candidate in _find_tree_candidates(payload):
            hrefs = _collect_tree_hrefs(candidate)
            if len(hrefs) > len(best_hrefs):
                best_hrefs = hrefs
                best_source = payload
    if best_hrefs:
        return best_hrefs, "tree", best_source

    flat_hrefs = []
    for payload in payloads:
        _collect_flat_hrefs(payload, flat_hrefs)
    flat_hrefs = [h for h in flat_hrefs if h and not h.startswith("#") and "/_next/" not in h]
    return flat_hrefs, "flat", None


def _find_field(payload, key_predicate, value_predicate):
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key_predicate(key) and value_predicate(value):
                return value
        for value in payload.values():
            found = _find_field(value, key_predicate, value_predicate)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_field(item, key_predicate, value_predicate)
            if found is not None:
                return found
    return None


def _find_version_list(payload) -> dict | None:
    return _find_field(
        payload,
        lambda k: _VERSION_LIST_KEY_HINT in k.lower(),
        lambda v: isinstance(v, dict) and len(v) >= 2 and all(isinstance(x, dict) for x in v.values()),
    )


def _find_current_version(payload) -> str | None:
    return _find_field(
        payload,
        lambda k: k.lower() == _CURRENT_VERSION_KEY_HINT,
        lambda v: isinstance(v, str) and v,
    )


def _find_path_without_language(payload) -> str | None:
    return _find_field(
        payload,
        lambda k: _PATH_WITHOUT_LANGUAGE_KEY_HINT in k.lower(),
        lambda v: isinstance(v, str) and v,
    )


def _build_version_urls(seed_url: str, all_versions: dict | None, current_version: str | None,
                        path_without_language: str | None) -> dict:
    if not all_versions or not current_version or path_without_language is None:
        return {}

    seed_path = urlsplit(seed_url).path
    if not seed_path.endswith(path_without_language):
        return {}
    lang_prefix = (seed_path[: len(seed_path) - len(path_without_language)]
                   if path_without_language else seed_path)

    content_path = path_without_language
    version_prefix = f"/{current_version}"
    if content_path == version_prefix:
        content_path = ""
    elif content_path.startswith(version_prefix + "/"):
        content_path = content_path[len(version_prefix):]

    parts = urlsplit(seed_url)
    base = f"{parts.scheme}://{parts.netloc}"
    return {
        version_key: f"{base}{lang_prefix.rstrip('/')}/{version_key}{content_path}"
        for version_key in all_versions
        if version_key != current_version
    }


def canonicalize_version_url(url: str, version_keys) -> str:
    parts = urlsplit(url)
    segments = parts.path.split("/")
    for version_key in version_keys:
        if version_key in segments:
            idx = segments.index(version_key)
            new_path = "/".join(segments[:idx] + segments[idx + 1:]) or "/"
            canonical = f"{parts.scheme}://{parts.netloc}{new_path}"
            return f"{canonical}?{parts.query}" if parts.query else canonical
    return url


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    response = await client.get(url, timeout=HTTP_TIMEOUT_S,
                                headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    if response.status_code in ABSENT_STATUSES:
        return None
    if response.status_code != 200:
        raise RuntimeError(f"unexpected status {response.status_code} for {url}")
    return response.text


async def _resolve_one_version(client: httpx.AsyncClient, version_url: str, all_version_keys: list) -> list:
    html = await _fetch_html(client, version_url)
    if html is None:
        logger.warning("navtree: version page absent, skipped: %s", version_url)
        return []
    hrefs, _tier, _source = find_navigation_tree(extract_payloads(html))
    absolute = (urljoin(version_url, href) for href in hrefs)
    return [canonicalize_version_url(url, all_version_keys) for url in absolute]


async def resolve_navigation_tree(client: httpx.AsyncClient, seed_url: str) -> tuple:
    html = await _fetch_html(client, seed_url)
    if html is None:
        raise RuntimeError(f"could not fetch seed_url: {seed_url!r}")

    payloads = extract_payloads(html)
    hrefs, tier, source_payload = find_navigation_tree(payloads)
    absolute = [urljoin(seed_url, href) for href in hrefs]

    if source_payload is None:
        return absolute, tier, None

    all_versions = _find_version_list(source_payload)
    current_version = _find_current_version(source_payload)
    path_without_language = _find_path_without_language(source_payload)
    version_urls = _build_version_urls(seed_url, all_versions, current_version, path_without_language)
    all_version_keys = list(all_versions.keys()) if all_versions else None
    if not version_urls:
        return absolute, tier, all_version_keys

    canonical_default = [canonicalize_version_url(url, all_version_keys) for url in absolute]

    semaphore = asyncio.Semaphore(NAVTREE_FETCH_CONCURRENCY)

    async def _bounded(version_url: str) -> list:
        async with semaphore:
            return await _resolve_one_version(client, version_url, all_version_keys)

    per_version_results = await asyncio.gather(*[_bounded(u) for u in version_urls.values()])

    union = list(canonical_default)
    for urls in per_version_results:
        union.extend(urls)
    return union, tier, all_version_keys
