# jhao104 validator overlay: knowledge moved out of code comments (2026-09-24)

## Why this file exists

`dev/news_pipeline/theblock/jhao104/patches/helper/validator.py` carried 6 comment lines and 6 docstrings. Code-Standards forbid them, so the content lives here. The code itself was not changed.

## Overlay mechanism

- `setup.sh` (same directory level as `patches/`) runs `cp -r "$PATCHES/"* "$UPSTREAM/"` after cloning jhao104/proxy_pool into `upstream/`.
- The overlay file is copied byte-for-byte over `upstream/helper/validator.py`. Nothing parses it, so comments are irrelevant to the overlay.
- `upstream/` is a gitignored clone and must not be edited. All changes go through `patches/`.

## Deltas against stock upstream validator.py

- `httpTimeOutValidator`: decorator removed, so it is not in `http_validator`. The function body is kept but unused (was the stock http check against `conf.httpUrl`).
- `customValidatorExample`: decorator removed, same reason. Stock example, always returns True.
- `httpsTimeOutValidator`: decorator removed, so `https_validator` stays empty. Consequence: `httpsValidator()` returns True for every proxy that passed the http validators. That is accurate because those proxies already tunnelled HTTPS to theblock, and it saves one qq.com HEAD request per cycle.
- `theblockValidator`: new, the sole `@ProxyValidator.addHttpValidator`. It is the Cloudflare pass gate.

## theblockValidator behaviour

- Uses `curl_cffi` with `impersonate="chrome"` (correct browser JA3 fingerprint) against `https://www.theblock.co/sitemap_tbco_index.xml`, timeout 15 s.
- Pass = HTTP 200 and one of `<?xml`, `<sitemapindex`, `<urlset`, `<sitemap>` inside the first 500 bytes of the body.
- One `Session` per call: safe across jhao104's 20 synchronous check threads, no shared state.
- Proxy URL is `http://host:port` for both the `http` and `https` proxies keys, because the Stage-1 pool is http-only.
- Any exception returns False.

## Other function docstrings that were removed

- `formatValidator`: checks proxy format via `IP_REGEX` (optional `user:pass@` prefix, IPv4, port).
- `httpTimeOutValidator`: HTTP check timeout, disabled, replaced by `theblockValidator`.
- `httpsTimeOutValidator`: HTTPS check timeout, disabled because `https_validator` is empty.
- `customValidatorExample`: custom validator sample, disabled.

## Verification

AST comparison (docstring nodes stripped) and token comparison (COMMENT/NL-only differences ignored) before and after. Verdict recorded in the session chat report.

## Also

`.gitignore` now lists `debug/` next to `logs/` (Code-Standards core rule).
