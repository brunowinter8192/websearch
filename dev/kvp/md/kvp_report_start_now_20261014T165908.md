# KVP report

- Generated: 2026-10-14T16:59:08Z
- Window: since beginning until now
- Log dir: `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch/src/logs`
- Records in window: searches: 265, drilldowns: 224, scrapes: 156, pipe URLs: 363, rag-cli searches: 361, collection files (unwindowed): 1189
- All verdicts are derived offline by `dev/kvp/kvp_classify.py`; the production logs hold facts only.
- `code_version` is stamped on records written after the M2 change; older records appear as `unversioned`.

## Ad hoc lane

### Headline indicators by code version (technical and relevance)

| code_version | searches | searches with >= 3 engines OK | searches with a blocked engine | scrapes | usable-body rate | silent-failure rate | searches leading to a scrape |
|---|---|---|---|---|---|---|---|
| all | 265 | 251/265 (94.7 %) | 176/265 (66.4 %) | 156 | 130/156 (83.3 %) | 23/156 (14.7 %) | 80/265 (30.2 %) |
| unversioned | 265 | 251/265 (94.7 %) | 176/265 (66.4 %) | 156 | 130/156 (83.3 %) | 23/156 (14.7 %) | 80/265 (30.2 %) |

### Engine runs, all versions

`blocked` = EMPTY with a block signal; `empty_no_signal` = EMPTY without one (true empty or unexplained).

| engine | runs | ok | blocked | empty_no_signal | transport_error | rate_skip | block rate |
|---|---|---|---|---|---|---|---|
| bing | 265 | 246 | 0 | 9 | 10 | 0 | 0/265 (0.0 %) |
| brave | 265 | 177 | 75 | 0 | 13 | 0 | 75/265 (28.3 %) |
| duckduckgo | 265 | 243 | 0 | 0 | 22 | 0 | 0/265 (0.0 %) |
| google | 265 | 130 | 0 | 115 | 20 | 0 | 0/265 (0.0 %) |
| mojeek | 149 | 121 | 10 | 9 | 9 | 0 | 10/149 (6.7 %) |
| openalex | 265 | 79 | 10 | 168 | 8 | 0 | 10/265 (3.8 %) |
| startpage | 265 | 237 | 0 | 0 | 28 | 0 | 0/265 (0.0 %) |
| yandex | 265 | 112 | 142 | 0 | 11 | 0 | 142/265 (53.6 %) |

### Block rate per engine by code version

| engine | unversioned |
|---|---|
| bing | 0/265 (0.0 %) |
| brave | 75/265 (28.3 %) |
| duckduckgo | 0/265 (0.0 %) |
| google | 0/265 (0.0 %) |
| mojeek | 10/149 (6.7 %) |
| openalex | 10/265 (3.8 %) |
| startpage | 0/265 (0.0 %) |
| yandex | 142/265 (53.6 %) |

### Scrape verdicts by code version

| code_version | scrapes | usable | no_content | filtered_to_nothing | http_error_page | login_wall | blocked | challenge_or_interstitial |
|---|---|---|---|---|---|---|---|---|
| all | 156 | 130 | 3 | 3 | 7 | 3 | 3 | 7 |
| unversioned | 156 | 130 | 3 | 3 | 7 | 3 | 3 | 7 |

### Relevance: click data

A scrape is attributed to a drilldown list when its URL is in the list and it happened within 3 h after the drilldown.

| code_version | searches | drilldowns | searches with scrape | attributed scrapes | rank of scraped URL (rank:count) |
|---|---|---|---|---|---|
| all | 265 | 224 | 80 | 102 | 1:39, 2:13, 3:19, 4:8, 5:1, 6:5, 7:5, 8:8, 9:3, 10:1 |
| unversioned | 265 | 224 | 80 | 102 | 1:39, 2:13, 3:19, 4:8, 5:1, 6:5, 7:5, 8:8, 9:3, 10:1 |

## Deep dive lane

### Technical and relevance per pipe run

Discovered, kept, rounds, cleanup cuts and indexed counts are not recorded anywhere (open milestone M3). Survival reads the collection as it is at report time, not as of the window.

| run | date | domains | code_version | URLs scraped | failed | zero-byte | http statuses | wall ms median | present in collection | survival |
|---|---|---|---|---|---|---|---|---|---|---|
| 34214881 | 2026-08-24 | docs.pytest.org | unversioned | 51 | 0 | 0 | 200=51 | 1880 | 51 | 51/51 (100.0 %) |
| 42d1a7e9 | 2026-08-25 | code.claude.com, platform.claude.com | unversioned | 7 | 0 | 0 | 200=7 | 8972 | 7 | 7/7 (100.0 %) |
| eeb9128d | 2026-08-27 | platform.claude.com | unversioned | 2 | 0 | 0 | 200=2 | 3120 | 0 | 0/2 (0.0 %) |
| 575fabca | 2026-08-31 | dev.to, developers.cloudflare.com, scrapebadger.com, scrapfly.io | unversioned | 6 | 0 | 0 | 200=5, 301=1 | 3694 | 6 | 6/6 (100.0 %) |
| 2527ff0b | 2026-09-02 | git-scm.com | unversioned | 1 | 0 | 0 | 200=1 | 2580 | 1 | 1/1 (100.0 %) |
| 9d949ee8 | 2026-09-03 | help.openalex.org | unversioned | 37 | 0 | 0 | 200=37 | 1692 | 37 | 37/37 (100.0 %) |
| cf4b5a19 | 2026-09-04 | code.claude.com | unversioned | 3 | 0 | 0 | 200=3 | 2069 | 3 | 3/3 (100.0 %) |
| 67554e80 | 2026-09-06 | platform.claude.com | unversioned | 50 | 0 | 0 | 200=50 | 2456 | 17 | 17/50 (34.0 %) |
| cf205813 | 2026-10-10 | docs.pytest.org | unversioned | 1 | 0 | 0 | 200=1 | 1937 | 0 | 0/1 (0.0 %) |
| 09dc0c1e | 2026-10-11 | sre.google | unversioned | 205 | 0 | 0 | 200=204, 301=1 | 1761 | 205 | 205/205 (100.0 %) |

### Collection `websearch-pages` (unwindowed state at report time)

- Files: 1189, indexed (`.json` sibling): 1189
- Flagged files by class: duplicate=4, title_only=1

### Usefulness: rag-cli retrieval

3 rag-cli searches on `websearch-pages`; 12 of 1189 indexed documents (12/1189 (1.0 %)) appear in a hit.

| domain | indexed | retrieved | share |
|---|---|---|---|
| docs.github.com | 349 | 2 | 2/349 (0.6 %) |
| sre.google | 205 | 3 | 3/205 (1.5 %) |
| api.stackexchange.com | 78 | 0 | 0/78 (0.0 %) |
| platform.claude.com | 61 | 0 | 0/61 (0.0 %) |
| docs.pytest.org | 51 | 0 | 0/51 (0.0 %) |
| developers.cloudflare.com | 48 | 0 | 0/48 (0.0 %) |
| help.openalex.org | 37 | 0 | 0/37 (0.0 %) |
| camoufox.com | 27 | 0 | 0/27 (0.0 %) |
| developers.google.com | 26 | 0 | 0/26 (0.0 %) |
| trafilatura.readthedocs.io | 25 | 0 | 0/25 (0.0 %) |
| developers.openalex.org | 24 | 0 | 0/24 (0.0 %) |
| crossref.org | 23 | 0 | 0/23 (0.0 %) |
| code.claude.com | 20 | 0 | 0/20 (0.0 %) |
| docs.hypersolutions.co | 20 | 0 | 0/20 (0.0 %) |
| browserleaks.com | 19 | 0 | 0/19 (0.0 %) |
| developers.binance.com | 17 | 0 | 0/17 (0.0 %) |
| docs.crawl4ai.com | 16 | 0 | 0/16 (0.0 %) |
| opendatalab.github.io | 14 | 1 | 1/14 (7.1 %) |
| playwright.dev | 13 | 2 | 2/13 (15.4 %) |
| docs.apify.com | 12 | 0 | 0/12 (0.0 %) |
| connectsafely.ai | 11 | 0 | 0/11 (0.0 %) |
| linkedapi.io | 11 | 0 | 0/11 (0.0 %) |
| old.reddit.com | 10 | 0 | 0/10 (0.0 %) |
| openlibrary.org | 7 | 0 | 0/7 (0.0 %) |
| lagrowthmachine.com | 6 | 0 | 0/6 (0.0 %) |
| northlight.ai | 6 | 0 | 0/6 (0.0 %) |
| schema.org | 6 | 0 | 0/6 (0.0 %) |
| linkedin.com | 6 | 0 | 0/6 (0.0 %) |
| anthropic.com | 5 | 0 | 0/5 (0.0 %) |
| github.com | 3 | 1 | 1/3 (33.3 %) |
| vayne.io | 3 | 0 | 0/3 (0.0 %) |
| api.semanticscholar.org | 2 | 0 | 0/2 (0.0 %) |
| scrapebadger.com | 2 | 0 | 0/2 (0.0 %) |
| scrapfly.io | 2 | 0 | 0/2 (0.0 %) |
| transformer-circuits.pub | 2 | 0 | 0/2 (0.0 %) |
| bot.sannysoft.com | 1 | 0 | 0/1 (0.0 %) |
| dev.to | 1 | 0 | 0/1 (0.0 %) |
| developer.apple.com | 1 | 0 | 0/1 (0.0 %) |
| eclecticlight.co | 1 | 0 | 0/1 (0.0 %) |
| evoleinik.com | 1 | 0 | 0/1 (0.0 %) |
| forum.latenightsw.com | 1 | 0 | 0/1 (0.0 %) |
| git-scm.com | 1 | 0 | 0/1 (0.0 %) |
| hacktricks.wiki | 1 | 0 | 0/1 (0.0 %) |
| journals.plos.org | 1 | 0 | 0/1 (0.0 %) |
| kb.mozillazine.org | 1 | 0 | 0/1 (0.0 %) |
| nick-liu.com | 1 | 0 | 0/1 (0.0 %) |
| peter.sh | 1 | 1 | 1/1 (100.0 %) |
| procxray.com | 1 | 0 | 0/1 (0.0 %) |
| stackoverflow.com | 1 | 1 | 1/1 (100.0 %) |
| support.apple.com | 1 | 0 | 0/1 (0.0 %) |
| tracemind.app | 1 | 0 | 0/1 (0.0 %) |
| wiki.mozilla.org | 1 | 0 | 0/1 (0.0 %) |
| binance.com | 1 | 0 | 0/1 (0.0 %) |
| context.dev | 1 | 0 | 0/1 (0.0 %) |
| firecrawl.dev | 1 | 0 | 0/1 (0.0 %) |
| reddit.com | 1 | 1 | 1/1 (100.0 %) |
| scrapingbee.com | 1 | 0 | 0/1 (0.0 %) |

## Silent failures to check

### Ad hoc scrapes (23)

| ts | url | status | bytes | class | evidence | sidecar |
|---|---|---|---|---|---|---|
| 2026-09-06T16:03:28 | https://www.cosdna.com/eng/cosmetic_8dde453460.html | 403 | 506 | blocked | http_status=403 with 506 B | scrape_content/2026-09-06T16-03-28.540Z_www-cosdna-com-eng-cosmetic-8dde453460-html.md |
| 2026-09-06T20:37:26 | https://github.blog/changelog/2025-01-09-github-copilot-in-vs-code-december-release-v0-23/ | 404 | 158 | http_error_page | http_status=404 | scrape_content/2026-09-06T20-37-26.437Z_github-blog-changelog-2025-01-09-github-copilot-in-vs-code-december-release-v0-2.md |
| 2026-09-06T20:38:08 | https://techcrunch.com/2025/01/07/nvidia-ceo-jensen-huang-says-his-ai-chips-are-improving-faster-than-moores-law/ | 404 | 3921 | http_error_page | http_status=404 | scrape_content/2026-09-06T20-38-08.120Z_techcrunch-com-2025-01-07-nvidia-ceo-jensen-huang-says-his-ai-chips-are-improvin.md |
| 2026-09-12T15:59:07 | https://www.ub.uni-frankfurt.de/bruw/schliessfaecher.html | 404 | 881 | http_error_page | http_status=404 | scrape_content/2026-09-12T15-59-07.076Z_www-ub-uni-frankfurt-de-bruw-schliessfaecher-html.md |
| 2026-09-12T15:59:16 | https://www.ub.uni-frankfurt.de/bsp/a-z.html | 404 | 842 | http_error_page | http_status=404 | scrape_content/2026-09-12T15-59-16.355Z_www-ub-uni-frankfurt-de-bsp-a-z-html.md |
| 2026-09-12T15:59:28 | https://www.ub.uni-frankfurt.de/formulare/dauerschliessfach.html | 200 | 482 | login_wall | landed on idp.ub.uni-frankfurt.de/idp/profile/SAML2/Redirect/SSO | scrape_content/2026-09-12T15-59-28.971Z_www-ub-uni-frankfurt-de-formulare-dauerschliessfach-html.md |
| 2026-09-12T15:59:38 | https://www.ub.uni-frankfurt.de/bsp/ausstattung.html | 404 | 866 | http_error_page | http_status=404 | scrape_content/2026-09-12T15-59-38.085Z_www-ub-uni-frankfurt-de-bsp-ausstattung-html.md |
| 2026-09-15T11:59:05 | https://www.stern.de/lifestyle/trendduefte-fuer-maenner--diese-10-parfums-sind-2026-angesagt-30873928.html | 403 | 121 | blocked | http_status=403 with 121 B | scrape_content/2026-09-15T11-59-05.468Z_www-stern-de-lifestyle-trendduefte-fuer-maenner-diese-10-parfums-sind-2026-anges.md |
| 2026-09-15T15:40:45 | https://www.ub.uni-frankfurt.de/formulare/carrel.html | 200 | 482 | login_wall | landed on idp.ub.uni-frankfurt.de/idp/profile/SAML2/Redirect/SSO | scrape_content/2026-09-15T15-40-45.235Z_www-ub-uni-frankfurt-de-formulare-carrel-html.md |
| 2026-09-15T16:13:39 | https://www.ub.uni-frankfurt.de/formulare/dauerschliessfach.html | 200 | 482 | login_wall | landed on idp.ub.uni-frankfurt.de/idp/profile/SAML2/Redirect/SSO | scrape_content/2026-09-15T16-13-39.570Z_www-ub-uni-frankfurt-de-formulare-dauerschliessfach-html.md |
| 2026-09-15T16:14:12 | https://www.ub.uni-frankfurt.de/bsp/dauerarbeitsplaetze.html | 404 | 890 | http_error_page | http_status=404 | scrape_content/2026-09-15T16-14-12.068Z_www-ub-uni-frankfurt-de-bsp-dauerarbeitsplaetze-html.md |
| 2026-09-15T16:19:23 | https://www.ub.uni-frankfurt.de/bskw/dauerarbeitsplatz.html | 404 | 887 | http_error_page | http_status=404 | scrape_content/2026-09-15T16-19-23.855Z_www-ub-uni-frankfurt-de-bskw-dauerarbeitsplatz-html.md |
| 2026-09-15T18:43:34 | https://vorschriften.bgn-branchenwissen.de/daten/gv/eg_2004_853/a35.htm | 200 | 1 | filtered_to_nothing | returned 1 B of 16742 B raw | scrape_content/2026-09-15T18-43-34.358Z_vorschriften-bgn-branchenwissen-de-daten-gv-eg-2004-853-a35-htm.md |
| 2026-09-16T07:06:51 | https://forums.raspberrypi.com/viewtopic.php?t=315674 | 403 | 522 | blocked | http_status=403 with 522 B | scrape_content/2026-09-16T07-06-51.172Z_forums-raspberrypi-com-viewtopic-php-t-315674.md |
| 2026-09-17T16:41:00 | https://www.mojeek.com/search?q=python+asyncio+tutorial | 200 | 185 | challenge_or_interstitial | marker 'verification required' in 185 B body | scrape_content/2026-09-17T16-41-00.707Z_www-mojeek-com-search-q-python-asyncio-tutorial.md |
| 2026-09-17T16:44:09 | https://www.mojeek.com/search?q=python+asyncio+tutorial | 200 | 185 | challenge_or_interstitial | marker 'verification required' in 185 B body | scrape_content/2026-09-17T16-44-09.595Z_www-mojeek-com-search-q-python-asyncio-tutorial.md |
| 2026-09-17T16:44:48 | https://www.mojeek.com/search?q=python+asyncio+tutorial | 200 | 185 | challenge_or_interstitial | marker 'verification required' in 185 B body | scrape_content/2026-09-17T16-44-48.629Z_www-mojeek-com-search-q-python-asyncio-tutorial.md |
| 2026-09-17T16:45:05 | https://www.mojeek.com/search?q=rust+ownership+model | 200 | 185 | challenge_or_interstitial | marker 'verification required' in 185 B body | scrape_content/2026-09-17T16-45-05.246Z_www-mojeek-com-search-q-rust-ownership-model.md |
| 2026-09-17T16:45:48 | https://www.mojeek.com/search?q=python+asyncio+tutorial | 200 | 185 | challenge_or_interstitial | marker 'verification required' in 185 B body | scrape_content/2026-09-17T16-45-48.430Z_www-mojeek-com-search-q-python-asyncio-tutorial.md |
| 2026-09-17T16:54:15 | https://www.mojeek.com/search?q=python+asyncio+tutorial | 200 | 185 | challenge_or_interstitial | marker 'verification required' in 185 B body | scrape_content/2026-09-17T16-54-15.360Z_www-mojeek-com-search-q-python-asyncio-tutorial.md |
| 2026-09-23T11:55:02 | https://dbis.ur.de/UBFM/resources?q=JSTOR | 200 | 1 | filtered_to_nothing | returned 1 B of 15774 B raw | scrape_content/2026-09-23T11-55-02.168Z_dbis-ur-de-UBFM-resources-q-JSTOR.md |
| 2026-09-23T11:55:11 | https://dbis.ur.de/UBFM/resources?q=Business+Source | 200 | 1 | filtered_to_nothing | returned 1 B of 15774 B raw | scrape_content/2026-09-23T11-55-11.730Z_dbis-ur-de-UBFM-resources-q-Business-Source.md |
| 2026-09-26T11:21:53 | https://www.amazon.de/Bellroy-Via-Work-Laptop-Messenger/dp/B0DHTBG112 | 200 | 374 | challenge_or_interstitial | marker 'klicke auf die schaltfläche' in 374 B body | scrape_content/2026-09-26T11-21-53.666Z_www-amazon-de-Bellroy-Via-Work-Laptop-Messenger-dp-B0DHTBG112.md |

### Engine runs recorded as EMPTY with a block signal (237)

| ts | engine | query | signals |
|---|---|---|---|
| 2026-09-06T16:01:18 | yandex | strong hold pomade sensitive scalp dandruff | marker=captcha, showcaptcha |
| 2026-09-06T16:02:08 | yandex | Shear Revival Grey Ghost ingredients | marker=captcha, showcaptcha |
| 2026-09-06T16:09:28 | yandex | Ronuls Professional Haarwachs amazon.de | marker=captcha, showcaptcha |
| 2026-09-06T16:09:33 | yandex | mango-friseurbedarf Versandkosten | marker=captcha, showcaptcha |
| 2026-09-06T16:11:47 | yandex | Uppercut Deluxe Pomade ingredients INCI | marker=captcha, showcaptcha |
| 2026-09-06T16:45:46 | yandex | Hercules Sägemann Grobzahnkamm Lockenkamm | marker=captcha, showcaptcha |
| 2026-09-08T14:58:26 | yandex | aam2core Holding AG Insolvenz 2026 | marker=captcha, showcaptcha |
| 2026-09-08T16:34:31 | yandex | Anthropic skill authoring best practices progressive disclos | marker=captcha, showcaptcha |
| 2026-09-09T12:34:32 | yandex | Otsuka Europe subsidiaries pharmaceutical nutraceutical acqu | marker=captcha, showcaptcha |
| 2026-09-09T12:34:56 | yandex | Otsuka Holdings Europe new management company established | marker=captcha, showcaptcha |
| 2026-09-09T12:35:49 | yandex | Otsuka Nutrition Sante Europe chemical medical device busine | marker=captcha, showcaptcha |
| 2026-09-09T13:13:35 | yandex | EU AI Act application dates August 2026 high risk | marker=captcha, showcaptcha |
| 2026-09-09T13:13:41 | yandex | AI Act digital omnibus delay high-risk obligations 2026 | marker=captcha, showcaptcha |
| 2026-09-09T13:21:09 | yandex | Frankfurt Bahnhofsviertel Videoueberwachung Polizei Gesichts | marker=captcha, showcaptcha |
| 2026-09-09T13:21:23 | yandex | Hessen Polizei Videoschutzanlage Hauptbahnhof biometrische E | marker=captcha, showcaptcha |
| 2026-09-09T19:13:57 | yandex | CRM Immobilien Asset Manager Investor Relations Deutschland | marker=captcha, showcaptcha |
| 2026-09-09T19:14:22 | yandex | aam2core Stellenangebote Software Yardi iX-Haus SAP Systeme | marker=captcha, showcaptcha |
| 2026-09-09T19:15:39 | yandex | aam2core "CRM" Stellenanzeige Assistenz Office Management | marker=captcha, showcaptcha |
| 2026-09-09T19:15:44 | yandex | Investor Relations CRM Immobilienfonds Fundraising Software  | marker=captcha, showcaptcha |
| 2026-09-12T15:58:34 | yandex | Goethe Universität Bibliothek Schließfächer über Nacht | marker=captcha, showcaptcha |
| 2026-09-12T15:58:45 | yandex | Bibliothek Sozialwissenschaften Psychologie BSP Frankfurt Sc | marker=captcha, showcaptcha |
| 2026-09-12T16:00:11 | yandex | Hörsaalzentrum Campus Westend Schließfächer PIN Nutzungsdaue | marker=captcha, showcaptcha |
| 2026-09-13T11:42:23 | yandex | WhatsApp verification network problem WiFi disable error | marker=captcha, showcaptcha |
| 2026-09-13T11:42:28 | yandex | WhatsApp registration requires mobile data or SMS only prepa | marker=captcha, showcaptcha |
| 2026-09-13T13:49:18 | yandex | tool result token overhead Claude API tool_use serialization | marker=captcha, showcaptcha |
| 2026-09-13T13:49:23 | yandex | prompt cache write cost per tool call agent loop measurement | marker=captcha, showcaptcha |
| 2026-09-15T11:49:12 | yandex | Hehlerware Preise Anteil Verkaufswert Forschung Diebesgut | marker=captcha, showcaptcha |
| 2026-09-15T11:49:30 | yandex | stolen goods resale price percentage retail value fence rese | marker=captcha, showcaptcha |
| 2026-09-15T11:49:34 | yandex | Polizeiliche Kriminalstatistik Ladendiebstahl Parfum Drogeri | marker=captcha, showcaptcha |
| 2026-09-15T11:50:13 | yandex | Sutton Handling Stolen Goods Home Office research study thie | marker=captcha, showcaptcha |
| 2026-09-15T11:50:27 | yandex | Hehler zahlt Drittel Neuwert Marktreduktionsansatz Kriminolo | marker=captcha, showcaptcha |
| 2026-09-15T11:50:58 | yandex | prolific thieves Derby stolen goods prices paid fence third  | marker=captcha, showcaptcha |
| 2026-09-15T11:51:03 | brave | gestohlene Kosmetik Parfum Weiterverkauf Preis Bahnhofsviert | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T11:51:03 | yandex | gestohlene Kosmetik Parfum Weiterverkauf Preis Bahnhofsviert | marker=captcha, showcaptcha |
| 2026-09-15T11:51:19 | brave | problem oriented policing guide stolen goods markets Sutton  | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T11:51:19 | yandex | problem oriented policing guide stolen goods markets Sutton  | marker=captcha, showcaptcha |
| 2026-09-15T11:52:18 | brave | EHI Inventurdifferenzen meistgestohlene Artikel Parfum Kosme | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T11:52:18 | yandex | EHI Inventurdifferenzen meistgestohlene Artikel Parfum Kosme | marker=captcha, showcaptcha |
| 2026-09-15T11:57:26 | openalex | beste Herrenparfums 2026 Trends Duefte Bestseller | http_status=429 |
| 2026-09-15T11:57:26 | brave | beste Herrenparfums 2026 Trends Duefte Bestseller | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T11:57:26 | yandex | beste Herrenparfums 2026 Trends Duefte Bestseller | marker=captcha, showcaptcha |
| 2026-09-15T12:10:58 | yandex | Parfum auf Wolle spruehen Flecken Pullover Textilien schaedl | marker=captcha, showcaptcha |
| 2026-09-15T12:12:38 | brave | Levis 541 Athletic Taper Deutschland kaufen verfuegbar | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:12:38 | yandex | Levis 541 Athletic Taper Deutschland kaufen verfuegbar | marker=captcha, showcaptcha |
| 2026-09-15T12:13:09 | brave | Lee Extreme Motion Jeans Deutschland kaufen Herren | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:13:09 | yandex | Lee Extreme Motion Jeans Deutschland kaufen Herren | marker=captcha, showcaptcha |
| 2026-09-15T12:19:29 | yandex | best value for money mens fragrance fresh summer clone Hawas | marker=captcha, showcaptcha |
| 2026-09-15T12:20:09 | brave | Versace Pour Homme EdT 100ml Preis notino idealo | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:20:09 | yandex | Versace Pour Homme EdT 100ml Preis notino idealo | marker=captcha, showcaptcha |
| 2026-09-15T12:20:13 | brave | Rasasi Hawas Ice Eau de Parfum Preis Deutschland 100ml | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:20:13 | yandex | Rasasi Hawas Ice Eau de Parfum Preis Deutschland 100ml | marker=captcha, showcaptcha |
| 2026-09-15T12:23:33 | brave | Crystal Lake pomade hair ingredients INCI | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:23:33 | yandex | Crystal Lake pomade hair ingredients INCI | marker=captcha, showcaptcha |
| 2026-09-15T12:23:38 | brave | Grey Ghost hair product pomade ingredients | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:23:38 | yandex | Grey Ghost hair product pomade ingredients | marker=captcha, showcaptcha |
| 2026-09-15T12:24:29 | brave | Levis 568 loose straight 555 relaxed straight Jeans Herren D | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:24:29 | yandex | Levis 568 loose straight 555 relaxed straight Jeans Herren D | marker=captcha, showcaptcha |
| 2026-09-15T12:25:16 | brave | Shear Revival strong hold high shine pomade without coconut  | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:25:16 | yandex | Shear Revival strong hold high shine pomade without coconut  | marker=captcha, showcaptcha |
| 2026-09-15T12:25:44 | brave | Uppercut Deluxe Pomade strong hold high shine water soluble  | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:25:44 | yandex | Uppercut Deluxe Pomade strong hold high shine water soluble  | marker=captcha, showcaptcha |
| 2026-09-15T12:25:48 | brave | Reuzel Pink heavy hold water soluble pomade INCI Inhaltsstof | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:25:48 | yandex | Reuzel Pink heavy hold water soluble pomade INCI Inhaltsstof | marker=captcha, showcaptcha |
| 2026-09-15T12:46:06 | brave | coconut oil penetrates hair shaft lauric acid Rele Mohile st | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:46:06 | yandex | coconut oil penetrates hair shaft lauric acid Rele Mohile st | marker=captcha, showcaptcha |
| 2026-09-15T12:46:37 | brave | Reuzel Daily Conditioner Inhaltsstoffe INCI Liste | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:46:37 | yandex | Reuzel Daily Conditioner Inhaltsstoffe INCI Liste | marker=captcha, showcaptcha |
| 2026-09-15T12:47:02 | brave | Creed Aventus Duftnoten Ananas Birke Zusammensetzung Pyramid | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:47:02 | yandex | Creed Aventus Duftnoten Ananas Birke Zusammensetzung Pyramid | marker=captcha, showcaptcha |
| 2026-09-15T12:47:06 | brave | Armaf Club de Nuit Intense Man Aventus Klon Vergleich Duftno | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:47:06 | yandex | Armaf Club de Nuit Intense Man Aventus Klon Vergleich Duftno | marker=captcha, showcaptcha |
| 2026-09-15T12:49:37 | brave | Uppercut Deluxe Pomade 100g Preis Amazon.de Euro | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:49:42 | brave | Layrite Superhold pomade INCI ingredients list coconut | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:55:58 | brave | pomade dry stiff feeling scalp itch wax versus oil content h | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:55:58 | yandex | pomade dry stiff feeling scalp itch wax versus oil content h | marker=captcha, showcaptcha |
| 2026-09-15T12:56:28 | brave | Reuzel Blue Pomade strong hold high shine INCI Inhaltsstoffe | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:56:28 | yandex | Reuzel Blue Pomade strong hold high shine INCI Inhaltsstoffe | marker=captcha, showcaptcha |
| 2026-09-15T12:56:56 | brave | Reuzel Blue Pomade 113g Preis Amazon Deutschland kaufen | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T12:56:56 | yandex | Reuzel Blue Pomade 113g Preis Amazon Deutschland kaufen | marker=captcha, showcaptcha |
| 2026-09-15T13:07:16 | brave | Reuzel Red Grease medium hold high shine oil based INCI Inha | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:07:16 | yandex | Reuzel Red Grease medium hold high shine oil based INCI Inha | marker=captcha, showcaptcha |
| 2026-09-15T13:16:38 | brave | PVP polymer hair stiff brittle film versus acrylates copolym | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:16:38 | yandex | PVP polymer hair stiff brittle film versus acrylates copolym | marker=captcha, showcaptcha |
| 2026-09-15T13:19:41 | brave | Uppercut Deluxe Pomade 100g idealo Preisvergleich Deutschlan | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:26:46 | brave | best fresh citrus body wash men does not clash with fragranc | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:26:46 | yandex | best fresh citrus body wash men does not clash with fragranc | marker=captcha, showcaptcha |
| 2026-09-15T13:28:49 | brave | Duschgel Herren neutral parfuemfrei dm Rossmann Nivea Sebame | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:28:49 | yandex | Duschgel Herren neutral parfuemfrei dm Rossmann Nivea Sebame | marker=captcha, showcaptcha |
| 2026-09-15T13:48:17 | brave | Issey Miyake L'Eau d'Issey Pour Homme Preis 125ml idealo | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:48:21 | brave | Terre d'Hermes Eau Givree Preis 100ml idealo Deutschland | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:48:21 | yandex | Terre d'Hermes Eau Givree Preis 100ml idealo Deutschland | showcaptcha |
| 2026-09-15T13:50:28 | brave | Aussie 3 Minute Miracle Inhaltsstoffe INCI Liste Kokosoel | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:54:36 | brave | best office appropriate mens fragrance professional subtle n | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:54:36 | yandex | best office appropriate mens fragrance professional subtle n | showcaptcha |
| 2026-09-15T13:55:08 | brave | Chanel Platinum Egoiste 100ml Preis idealo Deutschland | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:55:08 | yandex | Chanel Platinum Egoiste 100ml Preis idealo Deutschland | showcaptcha |
| 2026-09-15T13:55:13 | brave | Hermes H24 Eau de Toilette 100ml Preis idealo | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:55:13 | yandex | Hermes H24 Eau de Toilette 100ml Preis idealo | showcaptcha |
| 2026-09-15T13:55:17 | brave | Tom Ford Grey Vetiver 100ml Preis idealo Deutschland | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T13:55:17 | yandex | Tom Ford Grey Vetiver 100ml Preis idealo Deutschland | showcaptcha |
| 2026-09-15T14:08:13 | yandex | Aussie 3 Minute Miracle Moisture INCI Inhaltsstoffe Liste Be | showcaptcha |
| 2026-09-15T14:08:18 | brave | Sebamed Duschgel parfuemfrei Nivea Men Sensitive Duschgel Am | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T14:08:18 | yandex | Sebamed Duschgel parfuemfrei Nivea Men Sensitive Duschgel Am | showcaptcha |
| 2026-09-15T14:14:49 | brave | Duschgel Bergamotte Zitrus Herren Amazon Deutschland kaufen  | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T14:14:49 | yandex | Duschgel Bergamotte Zitrus Herren Amazon Deutschland kaufen  | showcaptcha |
| 2026-09-15T14:20:03 | brave | Uppercut Deluxe Deluxe Pomade 100g strong hold high shine Am | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T14:20:03 | yandex | Uppercut Deluxe Deluxe Pomade 100g strong hold high shine Am | showcaptcha |
| 2026-09-15T14:20:09 | brave | Levis 555 Relaxed Straight W31 L30 Zalando Herren kaufen | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T14:20:09 | yandex | Levis 555 Relaxed Straight W31 L30 Zalando Herren kaufen | showcaptcha |
| 2026-09-15T14:24:10 | brave | Duschgel parfuemfrei gut bewertet Amazon CeraVe Eucerin Sane | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T14:24:10 | yandex | Duschgel parfuemfrei gut bewertet Amazon CeraVe Eucerin Sane | showcaptcha |
| 2026-09-15T14:28:42 | brave | Deo ohne Duft unparfuemiert Herren Antitranspirant Amazon De | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T14:28:42 | yandex | Deo ohne Duft unparfuemiert Herren Antitranspirant Amazon De | showcaptcha |
| 2026-09-15T15:39:50 | brave | Universitaetsbibliothek Frankfurt Dauerarbeitsplatz Rollcont | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T15:39:50 | yandex | Universitaetsbibliothek Frankfurt Dauerarbeitsplatz Rollcont | marker=captcha, showcaptcha |
| 2026-09-15T15:40:15 | brave | UB Frankfurt BRuW Recht und Wirtschaft Dauerarbeitsplatz Sch | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T15:40:15 | yandex | UB Frankfurt BRuW Recht und Wirtschaft Dauerarbeitsplatz Sch | marker=captcha, showcaptcha |
| 2026-09-15T15:53:16 | brave | chromium headless detection bypass 2026 | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T15:53:16 | yandex | chromium headless detection bypass 2026 | marker=captcha, showcaptcha |
| 2026-09-15T16:13:53 | yandex | ub.uni-frankfurt.de Formular Dauerarbeitsplatz BSP Benutzung | marker=captcha, showcaptcha |
| 2026-09-15T16:19:23 | brave | site ub.uni-frankfurt.de formulare Uebersicht Anmeldung Daue | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T16:19:23 | yandex | site ub.uni-frankfurt.de formulare Uebersicht Anmeldung Daue | marker=captcha, showcaptcha |
| 2026-09-15T17:56:56 | brave | google num=100 parameter removed september 2025 scrapers imp | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T17:56:56 | yandex | google num=100 parameter removed september 2025 scrapers imp | marker=captcha, showcaptcha |
| 2026-09-15T17:57:20 | brave | brave search api free tier pricing queries per month 2026 | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T18:43:05 | brave | gegarte Speisen abkuehlen Kuehlschrank Zeitvorgabe Bacillus  | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T18:43:05 | yandex | gegarte Speisen abkuehlen Kuehlschrank Zeitvorgabe Bacillus  | marker=captcha, showcaptcha |
| 2026-09-15T18:43:16 | yandex | Hackfleisch Lagertemperatur Vorschrift | marker=captcha, showcaptcha |
| 2026-09-15T18:43:28 | brave | BfR Schutz Lebensmittelinfektionen Privathaushalt Merkblatt | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T18:43:28 | yandex | BfR Schutz Lebensmittelinfektionen Privathaushalt Merkblatt | marker=captcha, showcaptcha |
| 2026-09-15T18:43:34 | brave | focus measurement probe query | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T18:43:34 | yandex | focus measurement probe query | marker=captcha, showcaptcha |
| 2026-09-15T18:43:59 | brave | BfR Verbrauchertipps Schutz Lebensmittelinfektionen Kueche | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T18:43:59 | yandex | BfR Verbrauchertipps Schutz Lebensmittelinfektionen Kueche | marker=captcha, showcaptcha |
| 2026-09-15T18:44:08 | brave | BfR Stellungnahme 048/2020 Bacillus cereus Lebensmitteln | marker=captcha, pow_link, http_status=429 |
| 2026-09-15T18:44:08 | yandex | BfR Stellungnahme 048/2020 Bacillus cereus Lebensmitteln | marker=captcha, showcaptcha |
| 2026-09-15T18:51:01 | brave | BfR Clostridium perfringens Lebensmittel Fleischgerichte | marker=captcha, pow_link, http_status=429 |
| 2026-09-16T07:06:18 | yandex | DS18B20 disappears from /sys/bus/w1/devices reboot fixes | marker=captcha, showcaptcha |
| 2026-09-16T07:06:26 | yandex | w1_master_slave_count 0 sensor lost raspberry pi 1-wire | marker=captcha, showcaptcha |
| 2026-09-16T07:07:28 | brave | DS18B20 1-wire dropout compressor fridge electrical noise re | marker=captcha |
| 2026-09-16T07:07:28 | yandex | DS18B20 1-wire dropout compressor fridge electrical noise re | marker=captcha, showcaptcha |
| 2026-09-16T07:07:45 | yandex | linux w1 slave_ttl module parameter timeout search removes s | marker=captcha, showcaptcha |
| 2026-09-17T10:49:58 | yandex | Hochschule Karlsruhe SPO Wiederholung Prüfung Bachelor | marker=captcha, showcaptcha |
| 2026-09-17T10:53:53 | yandex | Goethe Universität Fachbereich Wirtschaftswissenschaften Dea | marker=captcha, showcaptcha |
| 2026-09-17T10:53:58 | yandex | Dean's List Goethe Wirtschaftswissenschaften Kriterien Ausze | marker=captcha, showcaptcha |
| 2026-09-17T10:58:31 | yandex | Goethe Wirtschaftswissenschaften Notenverteilung Notenspiege | marker=captcha, showcaptcha |
| 2026-09-17T10:58:35 | yandex | Notenverteilung Fachbereich Wirtschaftswissenschaften Goethe | marker=captcha, showcaptcha |
| 2026-09-17T10:58:50 | yandex | ECTS-Einstufungstabelle Goethe Universität Wirtschaftswissen | marker=captcha, showcaptcha |
| 2026-09-17T16:53:58 | brave | altcha widget auto onload verify programmatically | marker=captcha |
| 2026-09-17T16:53:58 | yandex | altcha widget auto onload verify programmatically | marker=captcha, showcaptcha |
| 2026-09-17T20:38:55 | brave | altcha widget server verification cookie | marker=captcha |
| 2026-09-17T20:38:55 | yandex | altcha widget server verification cookie | marker=captcha, showcaptcha |
| 2026-09-17T20:39:56 | brave | mojeek captcha verification blocked automated queries | marker=captcha |
| 2026-09-17T20:39:56 | yandex | mojeek captcha verification blocked automated queries | marker=captcha, showcaptcha |
| 2026-09-17T20:40:08 | brave | mojeek community altcha captcha challenge | marker=captcha |
| 2026-09-17T20:40:08 | yandex | mojeek community altcha captcha challenge | showcaptcha |
| 2026-09-17T21:41:14 | brave | altcha proof of work widget | marker=captcha |
| 2026-09-18T16:51:11 | yandex | wie funktioniert ein waermepumpentrockner | marker=captcha, showcaptcha |
| 2026-09-18T17:56:28 | yandex | hebeanlage keller abwasser wartung | marker=captcha, showcaptcha |
| 2026-09-18T18:35:58 | yandex | faltenbalg antriebswelle wechseln kosten werkstatt | marker=captcha, showcaptcha |
| 2026-09-18T19:07:47 | brave | yandex captcha why am i seeing this support spravka | marker=captcha |
| 2026-09-18T19:08:08 | brave | yandex showcaptcha spravka cookie after solving captcha | marker=captcha, showcaptcha |
| 2026-09-18T19:08:08 | yandex | yandex showcaptcha spravka cookie after solving captcha | marker=captcha, showcaptcha |
| 2026-09-19T11:35:06 | brave | cloudflare turnstile captcha widget verify programmatically | marker=captcha |
| 2026-09-19T14:46:19 | brave | dachbodendaemmung materialstaerke | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T14:51:53 | brave | hauswasserwerk druckschalter vwin1 | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T14:52:41 | brave | hauswasserwerk druckschalter vwin2 | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T14:53:29 | brave | hauswasserwerk druckschalter vwin3 | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T14:54:16 | brave | hauswasserwerk druckschalter vwin4 | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T14:55:04 | brave | hauswasserwerk druckschalter vwin5 | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T14:55:51 | brave | hauswasserwerk druckschalter vwin6 | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T14:56:37 | brave | hauswasserwerk druckschalter vwin7 | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T14:57:25 | brave | hauswasserwerk druckschalter vwin8 | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T15:07:50 | brave | hauswasserwerk druckschalter | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T15:10:02 | brave | hauswasserwerk druckschalter kennlinie zwei | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T16:58:37 | yandex | estrich trocknungszeit heizestrich | marker=captcha, showcaptcha |
| 2026-09-19T17:08:16 | brave | waermepumpe jahresarbeitszahl berechnen | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T17:42:58 | brave | waermepumpe jahresarbeitszahl berechnen zwei | marker=captcha, pow_link, http_status=429 |
| 2026-09-19T18:04:35 | yandex | dachziegel frostschaden erkennen | marker=captcha, showcaptcha |
| 2026-09-19T18:09:20 | mojeek | linkedin KPMG Frankfurt Digital Auditing Mitarbeiter Datenau | challenge_triggered |
| 2026-09-19T18:09:20 | yandex | linkedin KPMG Frankfurt Digital Auditing Mitarbeiter Datenau | marker=captcha, showcaptcha |
| 2026-09-21T09:32:04 | yandex | NSApplication activateIgnoringOtherApps deprecated macOS 14 | marker=captcha, showcaptcha |
| 2026-09-21T09:55:28 | yandex | python asyncio tutorial | marker=captcha, showcaptcha |
| 2026-09-21T10:48:48 | yandex | Goethe Universität QIS LSF Modulbelegung Wirtschaftswissensc | marker=captcha, showcaptcha |
| 2026-09-22T18:57:18 | yandex | Sara Bormann Goethe Universitaet Management Control professo | marker=captcha, showcaptcha |
| 2026-09-22T18:57:39 | yandex | Christine Riedmann-Streitz Honorarprofessorin Goethe Univers | marker=captcha, showcaptcha |
| 2026-09-22T18:57:44 | yandex | Matteo Merlo Goethe University accounting sustainability rep | marker=captcha, showcaptcha |
| 2026-09-22T18:58:27 | yandex | Katharina Hombach Goethe Universitaet Financial Accounting C | marker=captcha, showcaptcha |
| 2026-09-22T18:58:33 | yandex | Matthias Zieschang Fraport Honorarprofessor Goethe | marker=captcha, showcaptcha |
| 2026-09-22T18:58:57 | yandex | Goethe Universitaet Wirtschaftswissenschaften Lehrpreis gute | marker=captcha, showcaptcha |
| 2026-09-22T18:59:04 | yandex | Merlo Goethe Frankfurt Financial Statement Analysis Valuatio | marker=captcha, showcaptcha |
| 2026-09-22T19:30:55 | yandex | Oliver Schellenberger Professur fuer Versicherung Goethe Uni | marker=captcha, showcaptcha |
| 2026-09-22T19:35:20 | yandex | Doron Reichmann Goethe University accounting assistant profe | marker=captcha, showcaptcha |
| 2026-09-23T11:54:09 | yandex | UB Frankfurt Datenbanken Wirtschaftswissenschaften | marker=captcha, showcaptcha |
| 2026-09-23T11:55:30 | mojeek | dbis UBFM JSTOR | challenge_triggered |
| 2026-09-23T11:55:30 | openalex | dbis UBFM JSTOR | http_status=429 |
| 2026-09-23T11:58:40 | openalex | "Behavioral Risk Management in Banks" Kaiser Frankfurt | http_status=429 |
| 2026-09-23T11:58:47 | mojeek | Versicherungstechnologie und ihre Grenzen Schellenberger | challenge_triggered |
| 2026-09-23T11:58:47 | openalex | Versicherungstechnologie und ihre Grenzen Schellenberger | http_status=429 |
| 2026-09-23T12:30:23 | yandex | wiwi uni-frankfurt Moodle Kursmaterialien Studierende | marker=captcha, showcaptcha |
| 2026-09-23T12:31:19 | mojeek | Controlling und Kostenanalyse Goethe Altklausur | challenge_triggered |
| 2026-09-23T12:31:19 | openalex | Controlling und Kostenanalyse Goethe Altklausur | http_status=429 |
| 2026-09-23T12:31:25 | openalex | Data Science in Accounting Goethe Reichmann exam | http_status=429 |
| 2026-09-23T12:31:25 | yandex | Data Science in Accounting Goethe Reichmann exam | marker=captcha, showcaptcha |
| 2026-09-23T12:34:17 | mojeek | Rohlfing-Bastian Controlling und Kostenanalyse Vorlesung Unt | challenge_triggered |
| 2026-09-24T13:59:42 | yandex | anthropic api previous_message_id | marker=captcha, showcaptcha |
| 2026-09-24T14:00:01 | openalex | webkit font smoothing canvas text thinner | http_status=429 |
| 2026-09-24T14:00:01 | yandex | webkit font smoothing canvas text thinner | marker=captcha, showcaptcha |
| 2026-09-24T14:00:06 | openalex | canvas fillText font smoothing macOS Safari | http_status=429 |
| 2026-09-24T14:00:06 | yandex | canvas fillText font smoothing macOS Safari | marker=captcha, showcaptcha |
| 2026-09-24T14:00:37 | mojeek | claude api server-side conversation threads thread_not_found | challenge_triggered |
| 2026-09-26T09:36:13 | yandex | Reebok Club C 85 weiß 44.5 | marker=captcha, showcaptcha |
| 2026-09-26T10:31:25 | yandex | Cravar FC 15 laptop bag | marker=captcha, showcaptcha |
| 2026-09-26T10:31:49 | openalex | Bellroy Laptoptasche Deutschland Versand Rückgabe | http_status=429 |
| 2026-09-26T10:34:56 | openalex | Tumi Laptoptasche Herren Aktentasche | http_status=429 |
| 2026-09-26T10:50:23 | yandex | Sandqvist GO Briefcase review | marker=captcha, showcaptcha |
| 2026-09-26T10:51:41 | yandex | Samsonite Aktentasche 17.3 Zoll Laptoptasche | marker=captcha, showcaptcha |
| 2026-09-26T10:51:57 | yandex | Samsonite Evosight 17.3 Aktentasche idealo | marker=captcha, showcaptcha |
| 2026-09-26T10:52:03 | yandex | Samsonite Guardit 3.0 Briefcase 17.3 | marker=captcha, showcaptcha |
| 2026-09-26T10:53:49 | yandex | Stilord Davis Messenger Bag Laptop Zoll | marker=captcha, showcaptcha |
| 2026-09-26T10:53:55 | yandex | Jost Rana Business Bag Laptop Zoll | marker=captcha, showcaptcha |
| 2026-09-26T11:02:28 | yandex | Bellroy Tech Briefcase 16 Zoll | marker=captcha, showcaptcha |
| 2026-09-26T11:02:34 | yandex | Briggs Riley work Aktentasche 16 Zoll kaufen Deutschland | marker=captcha, showcaptcha |
| 2026-09-26T11:21:43 | yandex | Bellroy Via Work Bag 16 amazon.de | marker=captcha, showcaptcha |
| 2026-09-26T11:28:22 | yandex | Vinted Käuferschutz Rückgabe gefällt nicht | marker=captcha, showcaptcha |
| 2026-09-26T13:05:48 | yandex | deitel.com Intro to Python errata | marker=captcha, showcaptcha |
| 2026-09-30T14:39:17 | mojeek | jaegersoehne.de Sanitär Frankfurt Telefon | challenge_triggered |
| 2026-10-10T10:34:36 | mojeek | Prüfungstermine Wintersemester 2026/27 wiwi uni-frankfurt Kl | challenge_triggered |
| 2026-10-10T12:09:15 | mojeek | van Kann Vorstand der AG ESV-Digital | challenge_triggered, challenge_widget |
| 2026-10-11T14:11:22 | yandex | continuous improvement software observability logs | marker=captcha, showcaptcha |
| 2026-10-11T14:11:28 | yandex | LLM agent evaluation from production traces | marker=captcha, showcaptcha |
| 2026-10-11T14:11:34 | yandex | search quality evaluation click logs | marker=captcha, showcaptcha |
| 2026-10-11T14:11:40 | yandex | web scraping monitoring success rate | marker=captcha, showcaptcha |
| 2026-10-12T15:09:52 | mojeek | Nunito variable font italic weight axis | challenge_triggered |
| 2026-10-12T15:09:52 | yandex | Nunito variable font italic weight axis | marker=captcha, showcaptcha |
| 2026-10-14T16:39:24 | yandex | WebKit contenteditable selection slow transform scale | marker=captcha, showcaptcha |
| 2026-10-14T16:39:36 | yandex | Safari text selection lag contenteditable | marker=captcha, showcaptcha |

### Collection files (unwindowed) (5)

| file | class | evidence |
|---|---|---|
| developers_binance_com_docs_binance_spot_api_docs_rest_api_general_api_information.md | duplicate | same body as developers_binance_com_docs_binance_spot_api_docs_rest_api.md |
| developers_cloudflare_com_waf_reference_cloudflare_challenges.md | duplicate | same body as developers_cloudflare_com_cloudflare_challenges.md |
| opendatalab_github_io_MinerU_demo.md | title_only | 6 B after source line |
| platform_claude_com_docs_en_about_claude_models_whats_new_claude_4_8.md | duplicate | same body as platform_claude_com_docs_en_about_claude_models_whats_new_claude_4_7.md |
| sre_google_books_building_secure_reliable_systems.md | duplicate | same body as sre_google_books.md |

### Counter-check: marked failed or error status, classified usable (5)

Scrapes classified usable although `crawl4ai_success` is false or the final status is 400 or higher. Check these for false negatives.

| ts | url | status | crawl4ai_success | bytes |
|---|---|---|---|---|
| 2026-09-24T14:00:25 | https://stackoverflow.com/questions/59268831/how-to-make-font-in-canvas-smooth-just-like-using-webkit-font-smoothing-antia | 200 | False | 14770 |
| 2026-09-25T16:25:19 | https://superuser.com/questions/1792027/how-to-kill-all-unnecessary-processes-on-mac | 200 | False | 12697 |
| 2026-09-25T16:26:26 | https://eclecticlight.co/2025/06/16/spotlight-search-can-be-blocked-by-extended-attributes/ | 200 | False | 8430 |
| 2026-09-26T10:51:10 | https://www.trustpilot.com/review/sandqvist.com | 200 | False | 21283 |
| 2026-09-26T13:05:31 | https://stackoverflow.com/questions/57400620/python-comparison-operator-precedence | 200 | False | 11942 |

## Not covered

- Ad hoc usefulness (from transcripts) is out of scope.
- Deep dive discovered, kept and indexed counts need the run record of M3.
- The classification of EMPTY without a signal is open: the report cannot tell a true empty from an unexplained one.
