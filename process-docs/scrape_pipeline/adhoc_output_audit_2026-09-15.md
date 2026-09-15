# Ad-hoc scraper output audit, 2026-09-15

## What was audited and where the data lives

The ad-hoc scrape lane writes two artifacts, both under `src/logs/` (gitignored):

- `src/logs/scrape_log.jsonl` — one JSON record per scrape.
- `src/logs/scrape_content/<sanitized-ts>_<url-slug>.md` — the returned markdown, linked from the record's `content_path` field.

Both are written by `src/scraper/scrape_logger.py` (`log_scrape`, `write_sidecar`) and pruned by
`src/log_janitor.py`. Retention is `WEBSEARCH_LOG_RETENTION_DAYS`, default 14 days, applied to the
JSONL by record `ts` and to the sidecars by file mtime.

This audit read the whole retention window as it stood on 2026-09-15. No code was changed.

## Corpus size in the window

91 JSONL records spanning 2026-09-01 to 2026-09-15, across 11 active days. 90 sidecar files, 1.7 MB.

Per-day record counts: 09-01: 6, 09-02: 8, 09-03: 9, 09-04: 19, 09-05: 2, 09-06: 7, 09-08: 5,
09-09: 12, 09-12: 6, 09-13: 3, 09-15: 14. Four days inside the window had no scrapes at all
(09-07, 09-10, 09-11, 09-14).

The 2026-09-01 start is the 14-day retention cut, not the start of usage. Anything older was
deleted by the janitor, content and log lines alike.

## The 91 records were configurationally identical

Every single record in the window carried `mode=filtered`, `engine=chromium`, and
`config.launch_mode=cdp_headed_backgrounded`. Camoufox appeared zero times. A raw (unfiltered)
mode appeared zero times. Over 14 days of real use the ad-hoc lane exercised exactly one
configuration.

`crawl4ai_resolved_by` was `direct` in 87 records and null in 4. `crawl4ai_fallback_fetch_used`
was false in all 91. `crawl4ai_success` was false in 4.

In 11 records `landed_url` differed from the requested `url`.

## Fields that were empty across the entire window

- `og_published_time`: null in 91 of 91.
- `content_type`: null in 91 of 91.
- `acquisition_error`: null in 91 of 91, including the 13 records that did not return HTTP 200.

Note on `acquisition_error`: it being null on non-200 responses is not a bug under the lane's
premise (see below). It does mean the field carried no information in this window.

## Non-200 responses: 13 of 91

| ts | status | bytes_returned | host |
|---|---|---|---|
| 2026-09-01T13:40:08 | 307 | 9106 | unitflow.pro |
| 2026-09-01T17:44:42 | 301 | 3942 | abnamro.de |
| 2026-09-02T16:04:44 | 301 | 1400 | mediq.de |
| 2026-09-03T16:06:54 | 403 | 17922 | skeptics.stackexchange.com |
| 2026-09-04T13:05:22 | 410 | 398 | connecticum.de |
| 2026-09-06T16:03:28 | 403 | 506 | cosdna.com |
| 2026-09-06T20:37:26 | 404 | 158 | github.blog |
| 2026-09-06T20:38:08 | 404 | 3921 | techcrunch.com |
| 2026-09-08T14:59:11 | none | 0 | deal-magazin.com |
| 2026-09-12T15:59:07 | 404 | 881 | ub.uni-frankfurt.de |
| 2026-09-12T15:59:16 | 404 | 842 | ub.uni-frankfurt.de |
| 2026-09-12T15:59:38 | 404 | 866 | ub.uni-frankfurt.de |
| 2026-09-15T11:59:05 | 403 | 121 | stern.de |

Each of these produced a sidecar file whose content is the error page itself. Verbatim examples:

- stern.de (403, 121 bytes): `# Access Denied` plus an `errors.edgesuite.net` reference id.
  Akamai edge block.
- github.blog (404, 158 bytes): `# Whoops, we haven't written that blog post yet!`
- ub.uni-frankfurt.de (404, 842 bytes): the site's own German 404 page, complete with nav
  skip-links and a "zuletzt geändert am 4. Dezember 2023" footer.

## Premise clarification recorded on 2026-09-15

The project owner stated the intended behaviour explicitly during this audit: storing and
returning the body of a non-200 response IS the wanted behaviour. The lane's premise is to show
the agent what is actually there, error pages included. A 403 body that says "Access Denied" is
useful signal, not a defect to be suppressed.

Consequently the leverage is NOT in suppressing or flagging these 13 records. The leverage is in
reducing how many non-200s occur at all — meaning the mechanics of getting past paywalls,
Cloudflare-class challenges, and cookie/consent walls. That is where the 403s and the truncated
bodies come from.

## The one record with no sidecar

91 JSONL records, 90 sidecar files. The missing one is
`2026-09-08T14:59:11.167Z http://www.deal-magazin.com/news/2/130180/...`, with
`http_status: null`, `bytes_returned: 0`, `acquisition_error: null`. `write_sidecar` returns
early and writes nothing when `content` is empty, so the asymmetry follows directly from that
guard. It is not a lost file.

## Filter ratio is not a quality signal

`bytes_returned / bytes_raw_markdown` across the window: min 0.01, median roughly 0.5, max 0.93.
Absolute `bytes_returned`: min 0, p25 3921, median 7560, p75 17901, max 250181. Nine records
under 1000 bytes, sixteen under 3000.

A low ratio does not imply a bad result. Worked example: `moquer.com` on 2026-09-15 kept 5281 of
37353 bytes, ratio 0.14, and the surviving text contains the full product description, the
complete INCI ingredient table, the spec table, and the one customer review. The PruningContentFilter
threw away exactly the right 86 percent.

The inverse also holds: `github.blog` has ratio 0.01 because the page was a 404 stub, so there
was nothing to keep.

Conclusion for future readers: do not use the ratio as an automated quality gate. It correlates
with page chrome volume, not with content loss.

## Paywall truncation is invisible in both the record and the text

Observed once in this window. `iz.de` on 2026-09-08, HTTP 200, ratio 0.18, 1683 bytes. The
article body stops mid-word:

```
Der Frankfurter Kreditfonds-Anlageberater Aam2cred hat Insolvenz angemeldet. Das Amtsgericht
Frankfurt hat am 13. November die vorläufige Ve
```

and then continues normally into the site footer ("Sie haben Fragen oder Anmerkungen zu diesem
Artikel?", followed by related-article links). Nothing in the JSONL record distinguishes this
from a complete article: status 200, no error, plausible byte count.

A human reading the text notices the mid-word cut immediately. An automated marker was not
attempted here. One observation only — do not build machinery on this single case without
measuring how often it recurs.

## Boilerplate survives the filter

Counted over the 90 sidecar files:

- 26 files contain the word "cookie" at least once. Worst offender: 40 occurrences in
  `business-ecosystem-alliance.org`. Also high: 27 (job.deloitte.com), 24 (de.linkedin.com),
  24 (job.deloitte.com), 22 and 22 (tp-link.com).
- 18 files carry navigation skip-links ("Direkt zum Inhalt springen", "Skip to main content",
  "Press to skip carousel").
- 20 files end on navigation debris rather than a sentence — trailing lines include
  "Bis oben scrollen", "Report this ad", "Ask Docs", "Jetzt anmelden", "SubscribeLater",
  "previousnextslideshow", "Nur notwendigeEinstellungenAlle akzeptieren".

`config.remove_consent_popups` was true on all 91 records, so consent handling ran and this
residue survived it.

## Host distribution

69 distinct hosts over 91 scrapes. Repeat hosts: ub.uni-frankfurt.de (6), job.deloitte.com (4),
aam2core-holding-ag.jobs.personio.com (4), otsuka-europe.com (3), then five hosts with 2 each
(mediq.de, tp-link.com, pmc.ncbi.nlm.nih.gov, mojeek.com, amazon.de, faq.whatsapp.com,
reddit.com, fragrantica.de). The traffic is ad-hoc research across unrelated domains, which is
consistent with the lane being driven interactively rather than by a pipeline.
