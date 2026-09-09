# Removal of the decode-failure fallback in bing.py::_clean_url (2026-09-09)

Sixth Phase 4 control-flow removal (see this same folder's entries on the pipe_scraper curl_cffi
fallback removal, the proxy_riding abort stub removal, the engine `search()` wrapper removal, the
camoufox raw-HTML fallback removal, and the engine `_parse_results` JSON-handler removal for the
five before it). `bing.py::_clean_url` base64url-decodes the `u` parameter of Bing's
`bing.com/ck/a?...&u=<prefix><base64>` tracking redirect, and on any decode exception returned the
raw wrapped `href` as the "cleaned" result URL — a second, degraded way to produce a result URL.
The user ordered its removal: the branch was added 2026-07-21 as a precaution when Bing was first
wired, with zero supporting observation since — 0 `bing.com/ck/a` URLs in the production query
log, 0 in 400 cache files.

## What changed, and what stayed

The `try/except Exception: return href` around `base64.urlsafe_b64decode(padded).decode("utf-8",
errors="ignore")` was deleted; the decode now runs bare. The two guards immediately above it —
`if not href: return ""` and `if not u: return href` — were kept untouched, since both are
input-shape handling (a genuinely empty href, or a direct unwrapped href that is already the
destination URL) rather than a fallback for a failure.

## Propagation path (confirmed, not assumed)

`_clean_url` is called only from `_build_results` in `bing.py` — confirmed via `grep -rn
"_clean_url" src dev cli.py`; the only other hits are `duckduckgo.py`'s and `google.py`'s own
separate, independently-implemented functions of the same name (a pre-existing cross-module
duplication noted in the earlier Phase 4 control-flow scan, not addressed by this task), and
`dev/search_pipeline/28_bing_probe.py`'s unrelated standalone copy. A decode exception now
propagates `_build_results` → `_parse_results` → `search_with_reason` → `_engine_with_timing` →
`_classify_engine_exception`. Both realistic exception types already land on `ERROR_PARSE` without
any change to that classifier: `binascii.Error` (malformed base64 padding or alphabet) and
`UnicodeDecodeError` (bad UTF-8 after a successful decode) are both `ValueError` subclasses,
already inside `_classify_engine_exception`'s `(json.JSONDecodeError, KeyError, ValueError,
AttributeError)` tuple.

## Tests

`dev/tests/test_bing_engine.py::test_clean_url_falls_back_to_raw_href_when_decode_raises` was
renamed to `test_clean_url_raises_when_decode_raises` (the old name asserted behavior that no
longer exists) and rewritten to assert `pytest.raises(ValueError)` around the `_clean_url` call,
keeping the same `base64.urlsafe_b64decode` monkeypatch. The other three `_clean_url` tests were
untouched — none exercised the removed branch. Net test count unchanged (a rename+rewrite, not an
addition/removal): 365 (baseline) = 365, confirmed by `./venv/bin/python -m pytest -q`.

## Docs

`src/search/engines/DOCS.md` gained a new Gotcha bullet (placed after the `_parse_results` handler
removal bullet from the previous task) documenting the removal, the evidence, and the confirmed
`ERROR_PARSE` surfacing path; `bing.py`'s LOC was updated (180→177). `dev/tests/DOCS.md`'s
`test_bing_engine.py` entry was updated to describe the renamed test.
