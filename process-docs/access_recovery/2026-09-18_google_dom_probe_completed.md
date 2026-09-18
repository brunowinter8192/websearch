# The Google DOM probe was finally run, and it names the break exactly (2026-09-18)

Orchestrator record. Continues the `access_recovery` area. The entry
`2026-09-15_sprint_opening_state.md` in this same folder called
`dev/access_recovery/01_google_dom_probe.py` "the single most valuable outstanding measurement in
this area" and recorded that it had never been run to completion. It has now been run to
completion. No code was changed in this session as a result — this entry records what the probe
answered, so the next session starts from an answer instead of from a hypothesis.

## The run

`./venv/bin/python3 dev/access_recovery/01_google_dom_probe.py`, unmodified, against the shared
10-query set in `dev/access_recovery/queries.json`. Twenty navigations, each query once at
`num=100` and once at `num=10`, paced 15s apart. Report:
`dev/access_recovery/md/google_dom_probe_20260918_181820.md`. Raw HTML and per-navigation
diagnostic JSON under `dev/access_recovery/html/google_dom_probe_20260918_181820/` (gitignored).

Outcomes: OK 2, EMPTY_PARSED 18, NO_CONTAINERS 0, BLOCKED 0, ERROR 0.

## Two hypotheses died, one answer replaced them

**`num=100` is not the cause.** The `num=100` half of the run produced 1 OK and 9 EMPTY_PARSED.
The `num=10` half produced 1 OK and 9 EMPTY_PARSED. Identical. The lead recorded on 2026-09-15 —
that Google removed `num=100` behaviour in September 2025 and this project still sends it — is a
true fact about Google that is not the reason this project gets zero results. It can stay or go on
its own merits; it is not the fix.

**Blocking is not the cause either.** Zero of twenty navigations landed on `/sorry/`. Every
EMPTY_PARSED navigation found between 19 and 27 `div.MjjYud` containers. The page loads, the
containers are there.

## The actual break, read out of the saved HTML

`src/search/engines/google.py` finds `div.MjjYud`, then looks for `h3` or `.LC20lb` inside it and
walks up to an enclosing `a[href^="http"]`. The diagnostic pass shows the first two steps
succeeding and the third failing: sampled containers report `has_h3: true`, `has_lc20lb: true`,
`total_anchor_count` between 2 and 7, and `http_anchor_count: 0`. Anchors exist. None of them have
an href that starts with `http`.

The saved HTML says why. A real result anchor on 2026-09-18 looks like this (truncated):

```html
<a jsname="UWckNb" class="zReHs" href="/goto?url=CAES3QEB6zswFaZLUN_Z...">
  <h3 class="LC20lb MBeuO DKV0Md">The Best ANC Headphones to Buy in 2025</h3>
  ...
  <cite class="qLRx3b tjvcx GvPZzd cHaqb">https://headphones.com<span> › ... › Buying Guides</span></cite>
</a>
```

The href is a RELATIVE path, `/goto?url=<blob>`. Counted across that one page: 54 such hrefs, and
exactly 9 absolute `http` hrefs — all of them Google's own (`support.google.com`,
`policies.google.com`, `accounts.google.com`, `www.google.com`). Those 9 are precisely the
`page_wide_http_anchor_count: 9` the diagnostic reported. The production selector was matching
Google's own chrome links and nothing else.

The same blob also appears in the anchor's `ping` attribute as `/url?sa=t&...&url=<same blob>&uoh=1`.

## The destination URL is not on the page in plaintext

This is the part that makes it more than a selector swap, and it is the reason no fix was attempted
in this session.

The blob was base64url-decoded: 302 characters in, 226 bytes out, beginning `\x08\x01\x12\xdd\x01`
— a protobuf-shaped payload. The bytes `http` do not occur anywhere in it. The destination is not
merely encoded, it is opaque to us.

What IS on the page in plaintext is the `<cite>` element: the host (`https://headphones.com`) plus
an ellipsized breadcrumb (`› ... › Buying Guides`). A host, not a URL.

## What the next session has to decide, before writing any code

The options, none of them evaluated here:

1. Keep the relative href, resolve it against `https://www.google.com`, and let the consumer follow
   Google's redirect. Unknown: whether that redirect resolves outside the session that produced it,
   and whether handing Google-tracking URLs downstream is acceptable for this project.
2. Find the destination somewhere else in the page — the RSC/JS payload rather than the DOM.
   Unknown: whether it is there at all. The raw HTML from this run is on disk and can be searched
   for a known destination host without any new live run.
3. Accept host-only extraction from `<cite>`. Cheap, and probably useless for a pipeline whose
   whole output is URLs to scrape.

Option 2 is the one to test first, because the evidence to test it is already saved and costs no
live traffic.

## Scope note

This probe and this entry were produced during a session whose actual milestone was the search
lane's macOS focus and Spaces behaviour (see `process-docs/browser_posture/`). Google was
investigated first, then explicitly deprioritised by the owner in favour of the focus work, and no
Google code was touched. Post-change search runs in that same session continued to show google
returning 0 or 1 results, consistent with everything above and unaffected by the launch change.
