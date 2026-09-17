# ALTCHA Trigger Probe

Run: 2026-09-17T18:12:55Z
Target: https://www.mojeek.com/search?q=python+asyncio+tutorial
Live requests made this run: 4 sessions (1 inspection + 3 triggers), 2 navigations each
(control URL + target), 30s pause between sessions — 4 real requests against mojeek.com.

This is the second of two runs that actually reached Mojeek this session. The first (same 4
sessions, `SETTLE_TIMEOUT_S=15`, not committed) reached the identical verdicts; this run reruns
with `SETTLE_TIMEOUT_S=35` specifically to rule out "still waiting on the server" before calling
`verify_call`/`real_click` RAN_REJECTED, and reproduces the same outcome — 8 real requests against
mojeek.com total across both counted runs. A third attempt, immediately before the first of these
two, never reached Mojeek at all (`net::ERR_CONNECTION_REFUSED` on every session, concurrent with
an unrelated general network outage confirmed via `curl` failing against multiple unrelated domains
at the same time) — that attempt is not counted here since no request actually left the machine;
see this session's process-docs entry for the full timeline.

## Summary

| Trigger | Widget found | Computation started | Final widget state | verified event | Page outcome | Verdict |
|---|---|---|---|---|---|---|
| verify_call | True | True | verified | True | BLOCKED | RAN_REJECTED |
| auto_onload | True | False | verified | True | RESULTS | SUCCESS |
| real_click | True | True | verified | True | BLOCKED | RAN_REJECTED |

## Step 1 — Passive Inspection

Widget found: True
Page title at capture: Captcha
Widget state (getState()): unverified
Shadow root mode (via CDP DOM.describeNode, pierce=True — sees closed roots too): None
Interactive element located via: light DOM: input[type=checkbox], input[type=radio], [role=checkbox], button, label (tag: input)

humanInteractionSignature (getConfiguration()): True

### Attributes as served today

```json
{
  "id": "altcha-widget",
  "challenge": "/captcha/challenge",
  "name": "altcha",
  "theme": "default"
}
```

### getConfiguration() output

```json
{
  "fetch": null,
  "audioChallengeLanguage": "",
  "auto": "off",
  "barPlacement": "bottom",
  "challenge": "/captcha/challenge",
  "codeChallenge": null,
  "codeChallengeDisplay": "standard",
  "credentials": null,
  "debug": false,
  "disableAutoFocus": false,
  "display": "standard",
  "floatingAnchor": "",
  "floatingOffset": 8,
  "floatingPersist": false,
  "floatingPlacement": "auto",
  "hideFooter": false,
  "hideLogo": false,
  "humanInteractionSignature": true,
  "language": "",
  "mockError": false,
  "minDuration": 500,
  "overlayContent": "",
  "name": "altcha",
  "popoverPlacement": "auto",
  "retryOnOutOfMemoryError": true,
  "setCookie": null,
  "serverVerificationFields": false,
  "serverVerificationTimeZone": false,
  "test": false,
  "timeout": 90000,
  "type": "checkbox",
  "validationMessage": "",
  "verifyFunction": null,
  "verifyUrl": "",
  "workers": 14
}
```

### Deviations from ALTCHA's documented defaults

- none observed against the documented default set

### Surrounding form markup

```html
<form id="altcha-form" method="post" action="/captcha/verify"><altcha-widget id="altcha-widget" challenge="/captcha/challenge" name="altcha" theme="default"><!----><!----> <div class="altcha" data-state="unverified" data-display="standard" data-visible="true" dir=""><!----> <div class="altcha-main"><div><div class="altcha-checkbox-wrap"><div class="altcha-checkbox" data-loading="false"><input type="checkbox" id="altcha-checkbox-altcha-widget" name="" required=""> <svg aria-hidden="true" width="12" height="9" viewBox="0 0 12 9"><polyline points="1 5 4 8 11 1"></polyline></svg> <div class="altcha-spinner altcha-checkbox-spinner" aria-hidden="true"></div></div><!----> <label for="altcha-checkbox-altcha-widget">I'm not a robot<!----></label></div> <div><a target="_blank" class="altcha-logo" aria-hidden="true" tabindex="-1" href="https://altcha.org" aria-label="Altcha (official website)"><svg width="22" height="22" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2.33955 16.4279C5.88954 20.6586 12.1971 21.2105 16.4279 17.6604C18.4699 15.947 19.6548 13.5911 19.9352 11.1365L17.9886 10.4279C17.8738 12.5624 16.909 14.6459 15.1423 16.1284C11.7577 18.9684 6.71167 18.5269 3.87164 15.1423C1.03163 11.7577 1.4731 6.71166 4.8577 3.87164C8.24231 1.03162 13.2883 1.4731 16.1284 4.8577C16.9767 5.86872 17.5322 7.02798 17.804 8.2324L19.9522 9.01429C19.7622 7.07737 19.0059 5.17558 17.6604 3.57212C14.1104 -0.658624 7.80283 -1.21043 3.57212 2.33956C-0.658625 5.88958 -1.21046 12.1971 2.33955 16.4279Z" fill="currentColor"></path><path d="M3.57212 2.33956C1.65755 3.94607 0.496389 6.11731 0.12782 8.40523L2.04639 9.13961C2.26047 7.15832 3.21057 5.25375 4.8577 3.87164C8.24231 1.03162 13.2883 1.4731 16.1284 4.8577L13.8302 6.78606L19.9633 9.13364C19.7929 7.15555 19.0335 5.20847 17.6604 3.57212C14.1104 -0.658624 7.80283 -1.21043 3.57212 2.33956Z" fill="currentColor"></path><path d="M7 10H5C5 12.7614 7.23858 15 10 15C12.7614 15 15 12.7614 15 10H13C13 11.6569 11.6569 13 10 13C8.3431 13 7 11.6569 7 10Z" fill="currentColor"></path></svg></a></div><!----></div> <div class="altcha-footer"><p>Protected by <a href="https://altcha.org/" tabindex="-1" target="_blank" aria-label="Altcha (official website)">ALTCHA</a></p> <!----></div><!----> <!----> <input type="hidden" name="altcha"><!----></div> <!----></div></altcha-widget><div id="captcha-note" class="captcha-note">Waiting for verification.</div></form>
```

### Widget markup

```html
<altcha-widget id="altcha-widget" challenge="/captcha/challenge" name="altcha" theme="default"><!----><!----> <div class="altcha" data-state="unverified" data-display="standard" data-visible="true" dir=""><!----> <div class="altcha-main"><div><div class="altcha-checkbox-wrap"><div class="altcha-checkbox" data-loading="false"><input type="checkbox" id="altcha-checkbox-altcha-widget" name="" required=""> <svg aria-hidden="true" width="12" height="9" viewBox="0 0 12 9"><polyline points="1 5 4 8 11 1"></polyline></svg> <div class="altcha-spinner altcha-checkbox-spinner" aria-hidden="true"></div></div><!----> <label for="altcha-checkbox-altcha-widget">I'm not a robot<!----></label></div> <div><a target="_blank" class="altcha-logo" aria-hidden="true" tabindex="-1" href="https://altcha.org" aria-label="Altcha (official website)"><svg width="22" height="22" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2.33955 16.4279C5.88954 20.6586 12.1971 21.2105 16.4279 17.6604C18.4699 15.947 19.6548 13.5911 19.9352 11.1365L17.9886 10.4279C17.8738 12.5624 16.909 14.6459 15.1423 16.1284C11.7577 18.9684 6.71167 18.5269 3.87164 15.1423C1.03163 11.7577 1.4731 6.71166 4.8577 3.87164C8.24231 1.03162 13.2883 1.4731 16.1284 4.8577C16.9767 5.86872 17.5322 7.02798 17.804 8.2324L19.9522 9.01429C19.7622 7.07737 19.0059 5.17558 17.6604 3.57212C14.1104 -0.658624 7.80283 -1.21043 3.57212 2.33956C-0.658625 5.88958 -1.21046 12.1971 2.33955 16.4279Z" fill="currentColor"></path><path d="M3.57212 2.33956C1.65755 3.94607 0.496389 6.11731 0.12782 8.40523L2.04639 9.13961C2.26047 7.15832 3.21057 5.25375 4.8577 3.87164C8.24231 1.03162 13.2883 1.4731 16.1284 4.8577L13.8302 6.78606L19.9633 9.13364C19.7929 7.15555 19.0335 5.20847 17.6604 3.57212C14.1104 -0.658624 7.80283 -1.21043 3.57212 2.33956Z" fill="currentColor"></path><path d="M7 10H5C5 12.7614 7.23858 15 10 15C12.7614 15 15 12.7614 15 10H13C13 11.6569 11.6569 13 10 13C8.3431 13 7 11.6569 7 10Z" fill="currentColor"></path></svg></a></div><!----></div> <div class="altcha-footer"><p>Protected by <a href="https://altcha.org/" tabindex="-1" target="_blank" aria-label="Altcha (official website)">ALTCHA</a></p> <!----></div><!----> <!----> <input type="hidden" name="altcha"><!----></div> <!----></div></altcha-widget>
```

### Events observed during passive load (no trigger fired)

(no widget events observed)

## Trigger: verify_call

Widget found: True
load event observed during readiness wait: False
typeof verify === 'function' at readiness check: True
Computation started (VERIFYING observed): True
verified event fired: True
Final widget state: verified
Page outcome: BLOCKED
Verdict: RAN_REJECTED

### Page outcome detail

```json
{
  "result_link_count": 0,
  "sample_hrefs": [],
  "title": "Captcha",
  "block_marker_present": true,
  "body_text_length": 215,
  "body_text_sample": " \nVerification required\n\nPlease complete the challenge to continue.\n\nVerified\n\nProtected by ALTCHA\n\nChecking verification with server...\n\u00dcber\nAPI\nUnterst\u00fctzung\nBlog\nFeedback\nDatenschutz\nBedingungen\nSucheinstellungen",
  "li_count": 33
}
```

### Event sequence

| t_ms | event | detail |
|---|---|---|
| 0 | statechange | {"payload":null,"state":"verifying"} |
| 537 | statechange | {"payload":"eyJjaGFsbGVuZ2UiOnsicGFyYW1ldGVycyI6eyJhbGdvcml0aG0iOiJQQktERjIvU0hBLTI1NiIsImNvc3QiOjgwMDAsImtleUxlbmd0aCI6MzIsImtleVByZWZpeCI6IjBlNmNhMDAwYmM4ODQ2OTI4NDgxMzI4YzdhNzZhM2U1Iiwibm9uY2UiOiI1MmJkN2E1NTJiN2ZiZGFjNWE2ODU5ZTc5M2Y3YWFmMyIsInNhbHQiOiI1M2EzMjdmOWZkNmNhNDljMWFhZmQwZjljMTIxZjEzNCIsImtleVNpZ25hdHVyZSI6IjczYWQyYmM5MGI0N2ZhYjRjZmZkODE1OTAwYTgyNGIwMDcwMDhkYTJhNDljODY1YjNmYmJmNzlkZGY2ZjBlOGIiLCJleHBpcmVzQXQiOjE3ODk2NjkyNTJ9LCJzaWduYXR1cmUiOiJjNzdlODA3ZTI2NDMwNDk1ZDk0NWJjYzc0YjBlMmU3ZGFmMjhlZmQ3YTc2YThjN2RlMzM1OTZhMDZkZWY2YWRhIn0sInNvbHV0aW9uIjp7ImNvdW50ZXIiOjIwNSwiZGVyaXZlZEtleSI6IjBlNmNhMDAwYmM4ODQ2OTI4NDgxMzI4YzdhNzZhM2U1M2I5MjY5YmExODdhZDFiYTY3YjY4ZTgyODY1ZDA0ODkiLCJ0aW1lIjo0MTEuOX19","state":"verified"} |
| 538 | verified | {"payload":"eyJjaGFsbGVuZ2UiOnsicGFyYW1ldGVycyI6eyJhbGdvcml0aG0iOiJQQktERjIvU0hBLTI1NiIsImNvc3QiOjgwMDAsImtleUxlbmd0aCI6MzIsImtleVByZWZpeCI6IjBlNmNhMDAwYmM4ODQ2OTI4NDgxMzI4YzdhNzZhM2U1Iiwibm9uY2UiOiI1MmJkN2E1NTJiN2ZiZGFjNWE2ODU5ZTc5M2Y3YWFmMyIsInNhbHQiOiI1M2EzMjdmOWZkNmNhNDljMWFhZmQwZjljMTIxZjEzNCIsImtleVNpZ25hdHVyZSI6IjczYWQyYmM5MGI0N2ZhYjRjZmZkODE1OTAwYTgyNGIwMDcwMDhkYTJhNDljODY1YjNmYmJmNzlkZGY2ZjBlOGIiLCJleHBpcmVzQXQiOjE3ODk2NjkyNTJ9LCJzaWduYXR1cmUiOiJjNzdlODA3ZTI2NDMwNDk1ZDk0NWJjYzc0YjBlMmU3ZGFmMjhlZmQ3YTc2YThjN2RlMzM1OTZhMDZkZWY2YWRhIn0sInNvbHV0aW9uIjp7ImNvdW50ZXIiOjIwNSwiZGVyaXZlZEtleSI6IjBlNmNhMDAwYmM4ODQ2OTI4NDgxMzI4YzdhNzZhM2U1M2I5MjY5YmExODdhZDFiYTY3YjY4ZTgyODY1ZDA0ODkiLCJ0aW1lIjo0MTEuOX19"} |

## Trigger: auto_onload

Widget found: True
load event observed during readiness wait: False
typeof verify === 'function' at readiness check: None
Computation started (VERIFYING observed): False
verified event fired: True
Final widget state: verified
Page outcome: RESULTS
Verdict: SUCCESS

### Page outcome detail

```json
{
  "result_link_count": 10,
  "sample_hrefs": [
    "https://realpython.com/async-io-python/",
    "https://codesamplez.com/programming/python-asyncio-tutorial",
    "https://github.com/econchick/mayhem"
  ],
  "title": "python asyncio tutorial - Mojeek Search",
  "block_marker_present": false,
  "body_text_length": 3395,
  "body_text_sample": " \n\u2715Mojeek User Survey\n \nWebSummaryImagesNews\n\nErgebnisse 1 bis 10 von 24,511 in 0.08s\n\nhttps://realpython.com \u203a async-io-python\n\nPython's asyncio: A Hands-On Walkthrough \u2013 Real Python\n\nIn this tutorial, you \u2019 ll learn how Python asyncio works, how to define and run coroutines, and when to use asynch",
  "li_count": 74
}
```

### Event sequence

| t_ms | event | detail |
|---|---|---|
| 0 | statechange | {"payload":"eyJjaGFsbGVuZ2UiOnsicGFyYW1ldGVycyI6eyJhbGdvcml0aG0iOiJQQktERjIvU0hBLTI1NiIsImNvc3QiOjgwMDAsImtleUxlbmd0aCI6MzIsImtleVByZWZpeCI6IjYwZGRlZGRhZGFiNGNjNWJlNGI3N2IyODk3ZTIwZGY2Iiwibm9uY2UiOiJjNmNmYzAzYTc3NmNjMzAzNjkwNWZlNDY3ZGI3YTkzNCIsInNhbHQiOiJjY2FkMmZhMDQ5YjM1NDNmMjIwOWFhZmFkYzVhNDYzNCIsImtleVNpZ25hdHVyZSI6ImIxMDhhNjMxYWU0ZDVlMjNiMzMxOWI1NzE3MmUzZGQzMzQ2NDg1OTk5NzU4MmM5Mjc2ZjM1MGRjMmU4NDY3NTciLCJleHBpcmVzQXQiOjE3ODk2NjkyODN9LCJzaWduYXR1cmUiOiI5ZTIzYTFkNmQwNjRhYjIyYjNjN2NkODMxODliOGI1YWE2OTFhZmE0NGViYTYzNmNhZWQ5NjljOWQ0MmU3ODVjIn0sInNvbHV0aW9uIjp7ImNvdW50ZXIiOjIwMSwiZGVyaXZlZEtleSI6IjYwZGRlZGRhZGFiNGNjNWJlNGI3N2IyODk3ZTIwZGY2ZDk0ZTRhZDkwNWIyMTZkMmM2YzVlYzk1ZDNhNjM3MDIiLCJ0aW1lIjoxMTV9fQ==","state":"verified"} |
| 1 | verified | {"payload":"eyJjaGFsbGVuZ2UiOnsicGFyYW1ldGVycyI6eyJhbGdvcml0aG0iOiJQQktERjIvU0hBLTI1NiIsImNvc3QiOjgwMDAsImtleUxlbmd0aCI6MzIsImtleVByZWZpeCI6IjYwZGRlZGRhZGFiNGNjNWJlNGI3N2IyODk3ZTIwZGY2Iiwibm9uY2UiOiJjNmNmYzAzYTc3NmNjMzAzNjkwNWZlNDY3ZGI3YTkzNCIsInNhbHQiOiJjY2FkMmZhMDQ5YjM1NDNmMjIwOWFhZmFkYzVhNDYzNCIsImtleVNpZ25hdHVyZSI6ImIxMDhhNjMxYWU0ZDVlMjNiMzMxOWI1NzE3MmUzZGQzMzQ2NDg1OTk5NzU4MmM5Mjc2ZjM1MGRjMmU4NDY3NTciLCJleHBpcmVzQXQiOjE3ODk2NjkyODN9LCJzaWduYXR1cmUiOiI5ZTIzYTFkNmQwNjRhYjIyYjNjN2NkODMxODliOGI1YWE2OTFhZmE0NGViYTYzNmNhZWQ5NjljOWQ0MmU3ODVjIn0sInNvbHV0aW9uIjp7ImNvdW50ZXIiOjIwMSwiZGVyaXZlZEtleSI6IjYwZGRlZGRhZGFiNGNjNWJlNGI3N2IyODk3ZTIwZGY2ZDk0ZTRhZDkwNWIyMTZkMmM2YzVlYzk1ZDNhNjM3MDIiLCJ0aW1lIjoxMTV9fQ=="} |

## Trigger: real_click

Widget found: True
load event observed during readiness wait: False
typeof verify === 'function' at readiness check: True
Computation started (VERIFYING observed): True
verified event fired: True
Final widget state: verified
Page outcome: BLOCKED
Verdict: RAN_REJECTED

### Click target (real_click trigger only)

Click actually delivered to the DOM (mousedown/mouseup/click observed on the widget host, bubbled from wherever it lands — composed events bubble out of shadow roots regardless of open/closed mode): True

```json
{
  "shadow_mode": null,
  "used_selector": "light DOM: input[type=checkbox], input[type=radio], [role=checkbox], button, label",
  "target_tag": "input"
}
```

### Page outcome detail

```json
{
  "result_link_count": 0,
  "sample_hrefs": [],
  "title": "Captcha",
  "block_marker_present": true,
  "body_text_length": 215,
  "body_text_sample": " \nVerification required\n\nPlease complete the challenge to continue.\n\nVerified\n\nProtected by ALTCHA\n\nChecking verification with server...\n\u00dcber\nAPI\nUnterst\u00fctzung\nBlog\nFeedback\nDatenschutz\nBedingungen\nSucheinstellungen",
  "li_count": 33
}
```

### Event sequence

| t_ms | event | detail |
|---|---|---|
| 0 | mousedown | 1 |
| 4 | mouseup | 1 |
| 4 | click | 1 |
| 4 | click |  |
| 6 | statechange | {"payload":null,"state":"verifying"} |
| 651 | statechange | {"payload":"eyJjaGFsbGVuZ2UiOnsicGFyYW1ldGVycyI6eyJhbGdvcml0aG0iOiJQQktERjIvU0hBLTI1NiIsImNvc3QiOjgwMDAsImtleUxlbmd0aCI6MzIsImtleVByZWZpeCI6IjA5YWRkNjA5NmFlZDkxNWYzMjUxNzAzMWYxNDM5ZWI4Iiwibm9uY2UiOiI2OGFkNGZjZGYzM2Q3MDVhNGRlNjk0OWM4OWExMzI0ZSIsInNhbHQiOiI1OWU0NjU5MTk1ZDcyNDY3OWYwNTBiM2M2Zjg2MDIzNiIsImtleVNpZ25hdHVyZSI6ImQwZGFmODIzNWE2NDMzODE2ZjMwYjAwYTE5ZDU1Y2FkYjJlMzMzNzY1ZDdjN2M1ODJjOTIyOGE4YzljY2ZmY2EiLCJleHBpcmVzQXQiOjE3ODk2NjkzNDV9LCJzaWduYXR1cmUiOiI5ZmE2NWUyZmQzYzU3OTJjNjUxNmE2YTQ0ZjQwMmFhMmIyYjNmOThhYmIyODc2OGNmMTJmMDMxOGE5YTNkMGUwIn0sInNvbHV0aW9uIjp7ImNvdW50ZXIiOjI4NSwiZGVyaXZlZEtleSI6IjA5YWRkNjA5NmFlZDkxNWYzMjUxNzAzMWYxNDM5ZWI4NDk1YzhiMGM3NGViNmZiYjQ1MTBlMGU5ZTljOGUxMmEiLCJ0aW1lIjo1MjMuNn19","state":"verified"} |
| 651 | verified | {"payload":"eyJjaGFsbGVuZ2UiOnsicGFyYW1ldGVycyI6eyJhbGdvcml0aG0iOiJQQktERjIvU0hBLTI1NiIsImNvc3QiOjgwMDAsImtleUxlbmd0aCI6MzIsImtleVByZWZpeCI6IjA5YWRkNjA5NmFlZDkxNWYzMjUxNzAzMWYxNDM5ZWI4Iiwibm9uY2UiOiI2OGFkNGZjZGYzM2Q3MDVhNGRlNjk0OWM4OWExMzI0ZSIsInNhbHQiOiI1OWU0NjU5MTk1ZDcyNDY3OWYwNTBiM2M2Zjg2MDIzNiIsImtleVNpZ25hdHVyZSI6ImQwZGFmODIzNWE2NDMzODE2ZjMwYjAwYTE5ZDU1Y2FkYjJlMzMzNzY1ZDdjN2M1ODJjOTIyOGE4YzljY2ZmY2EiLCJleHBpcmVzQXQiOjE3ODk2NjkzNDV9LCJzaWduYXR1cmUiOiI5ZmE2NWUyZmQzYzU3OTJjNjUxNmE2YTQ0ZjQwMmFhMmIyYjNmOThhYmIyODc2OGNmMTJmMDMxOGE5YTNkMGUwIn0sInNvbHV0aW9uIjp7ImNvdW50ZXIiOjI4NSwiZGVyaXZlZEtleSI6IjA5YWRkNjA5NmFlZDkxNWYzMjUxNzAzMWYxNDM5ZWI4NDk1YzhiMGM3NGViNmZiYjQ1MTBlMGU5ZTljOGUxMmEiLCJ0aW1lIjo1MjMuNn19"} |

## Methodology

Every session (1 inspection + 3 triggers) launches the same Chromium bundle production's `src/scraper/chromium_scrape.py`/`chromium_process.py` self-launches — resolved dynamically from patchright's own installed browser (`Google Chrome for Testing.app` on this machine, not the user's real Chrome), with the exact same `ManagedBrowser.build_browser_flags(enable_stealth=True)` CLI flags — against its own fresh `--user-data-dir`, backgrounded via `open -g -n -a`, with a PID-keyed focus-steal reclaim watchdog for the session's whole run. This script does not import from `src/` (a hard constraint enforced on new files in this repo's tooling), so the launch/resolve/flag-building/watchdog helpers are an inline copy of `src/scraper/chromium_process.py`'s current shape rather than a shared import — the same dev-isolation convention several sibling probes in this directory already use — but nothing about the actual browser build or its fingerprint differs from what production drives.

Before navigating to Mojeek, every session first navigates to a neutral control URL in that same browser/profile. If that control navigation fails, the whole probe aborts immediately with the raw error instead of continuing to produce verdicts — a session that cannot reach the open internet at all cannot tell 'Mojeek refused' apart from 'this environment is blind right now', and reporting NEVER_STARTED in that case would be reporting nothing.

Each session's page had a `Page.addScriptToEvaluateOnNewDocument`-equivalent init script registered (code guaranteed to run before any of Mojeek's own scripts) before the Mojeek navigation. That script installs a `MutationObserver` on `document` from the first instant of navigation, attaching listeners for every documented ALTCHA widget event the moment the widget node appears, and — for the `auto_onload` session only — setting `auto="onload"` in that same synchronous callback, before the custom element upgrade can read a stale attribute. Widget events are bridged out to Python via an exposed binding call, a genuine push event, not a poll.

The interactive element used for the `real_click` trigger is located via a raw CDP `DOM.describeNode(pierce=true)` call, which reports the widget's actual shadow-root mode and can resolve into the shadow tree regardless of whether that mode is `open` or `closed` — CDP inspection is not subject to the JS-level restriction that hides closed shadow content from `element.shadowRoot`. The click itself dispatches through CDP's real mouse input path (`Input.dispatchMouseEvent`), producing a trusted (`isTrusted=true`) synthetic click, distinct from a JS-level `.click()` call.

The init script also attaches `mousedown`/`mouseup`/`click` listeners directly on the widget HOST element (not just the ALTCHA-specific events) — these are standard, composed UI events, so they bubble out to the host regardless of whether the actual target sits inside an open or closed shadow root, giving an independent, structural signal for whether the dispatched click was delivered to the page at all. This distinction matters: extensive ad-hoc testing during this milestone's build (documented in this session's process-docs entry, not repeated here — coordinates verified correct via `DOM.getNodeForLocation` hit-testing, `Target.activateTarget`/`Page.bringToFront`/`Emulation.setFocusEmulationEnabled` all tried, `document.hasFocus()`/`document.visibilityState` both already true/visible) found that `Input.dispatchMouseEvent` clicks (raw CDP, `page.mouse`, and `locator.click()` all three tried) land and fire correctly on light-DOM elements outside any shadow root in this self-launch-plus-`connect_over_cdp` session shape, but never reach ANY element located inside a shadow root (open or closed, button or checkbox alike) — zero `mousedown`/`mouseup`/`click` observed even at the dispatch target itself — while the exact same click on the exact same shadow-DOM control succeeds when Playwright launches and owns the browser process directly instead of attaching to a self-launched one. Since ALTCHA's `<altcha-widget>` is a Web Component and its own docs describe it as using the browser's native custom-element machinery, its interactive content is very likely shadow-DOM-scoped — the inspection pass below checks this directly rather than assuming it. If `click_delivered` is `False` below, the `real_click` trigger's NEVER_STARTED verdict reflects this gap in the click-delivery mechanism itself, not a refusal by Mojeek's widget, and must be read accordingly — a genuine limitation of the self-launch-plus-`connect_over_cdp` session shape production's own scrape lane also uses, not something specific to this probe.

Readiness (element present, `load` event observed, `typeof verify === 'function'`) and trigger completion (`verified`/`error`/`expired` observed) are both awaited event- or poll-driven with a bounded timeout, never a single fixed sleep before one check. After the widget signals completion (or times out), the page outcome is re-checked at 1s intervals for up to a further 35s, stopping as soon as the outcome resolves to something other than UNKNOWN, to allow for either a full page reload or an in-place content swap.

Page outcome is read from the live DOM using the selector `ul.results-standard > li > a.ob` (verified live on 2026-05-03, recorded in `process-docs/engine_expansion/mojeek.md`) for real results and the literal, locale-independent string `"Verification required"` for the block page. If neither is present the outcome is reported as UNKNOWN with the raw supporting facts (title, body text sample, `<li>` count) attached — never silently reclassified as one of the other two.

A NEVER_STARTED or RAN_REJECTED verdict on every trigger is a complete and valid result for this milestone; nothing here was tuned toward a positive outcome.
