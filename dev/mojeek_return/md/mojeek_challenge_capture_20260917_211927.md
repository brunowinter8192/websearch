# Mojeek challenge page, as actually served

Run: 2026-09-17T21:19:27Z
Target: https://www.mojeek.com/search?q=python+asyncio+tutorial&safe=1
Live requests against mojeek.com: 1 (one navigation, cold profile).

Captured to settle which strings are real. An English literal that has never been observed matching must not become an engine's block signal.

## immediately after navigation

```json
{
  "title": "Captcha",
  "url": "https://www.mojeek.com/search?q=python+asyncio+tutorial&safe=1",
  "html_lang": "de",
  "widget_present": true,
  "widget_state": "unverified",
  "widget_attributes": {
    "id": "altcha-widget",
    "challenge": "/captcha/challenge",
    "name": "altcha",
    "theme": "default"
  },
  "captcha_note_text": "Waiting for verification.",
  "form_action": "/captcha/verify",
  "result_link_count": 0,
  "literal_verification_required": true,
  "literal_checking_with_server": false,
  "lowercase_body_contains_captcha": false,
  "lowercase_title_contains_captcha": true,
  "body_text": " \nVerification required\n\nPlease complete the challenge to continue.\n\nI'm not a robot\n\nProtected by ALTCHA\n\nWaiting for verification.\nÜber\nAPI\nUnterstützung\nBlog\nFeedback\nDatenschutz\nBedingungen\nSucheinstellungen"
}
```

## right after verify() was dispatched

```json
{
  "title": "Captcha",
  "url": "https://www.mojeek.com/search?q=python+asyncio+tutorial&safe=1",
  "html_lang": "de",
  "widget_present": true,
  "widget_state": "verifying",
  "widget_attributes": {
    "id": "altcha-widget",
    "challenge": "/captcha/challenge",
    "name": "altcha",
    "theme": "default"
  },
  "captcha_note_text": "Waiting for verification.",
  "form_action": "/captcha/verify",
  "result_link_count": 0,
  "literal_verification_required": true,
  "literal_checking_with_server": false,
  "lowercase_body_contains_captcha": false,
  "lowercase_title_contains_captcha": true,
  "body_text": " \nVerification required\n\nPlease complete the challenge to continue.\n\nVerifying...\n\nProtected by ALTCHA\n\nWaiting for verification.\nÜber\nAPI\nUnterstützung\nBlog\nFeedback\nDatenschutz\nBedingungen\nSucheinstellungen"
}
```

## state=verifying note='Waiting for verification.'

```json
{
  "title": "Captcha",
  "url": "https://www.mojeek.com/search?q=python+asyncio+tutorial&safe=1",
  "html_lang": "de",
  "widget_present": true,
  "widget_state": "verifying",
  "widget_attributes": {
    "id": "altcha-widget",
    "challenge": "/captcha/challenge",
    "name": "altcha",
    "theme": "default"
  },
  "captcha_note_text": "Waiting for verification.",
  "form_action": "/captcha/verify",
  "result_link_count": 0,
  "literal_verification_required": true,
  "literal_checking_with_server": false,
  "lowercase_body_contains_captcha": false,
  "lowercase_title_contains_captcha": true,
  "body_text": " \nVerification required\n\nPlease complete the challenge to continue.\n\nVerifying...\n\nProtected by ALTCHA\n\nWaiting for verification.\nÜber\nAPI\nUnterstützung\nBlog\nFeedback\nDatenschutz\nBedingungen\nSucheinstellungen"
}
```

## state=verified note='Checking verification with server...'

```json
{
  "title": "Captcha",
  "url": "https://www.mojeek.com/search?q=python+asyncio+tutorial&safe=1",
  "html_lang": "de",
  "widget_present": true,
  "widget_state": "verified",
  "widget_attributes": {
    "id": "altcha-widget",
    "challenge": "/captcha/challenge",
    "name": "altcha",
    "theme": "default"
  },
  "captcha_note_text": "Checking verification with server...",
  "form_action": "/captcha/verify",
  "result_link_count": 0,
  "literal_verification_required": true,
  "literal_checking_with_server": true,
  "lowercase_body_contains_captcha": false,
  "lowercase_title_contains_captcha": true,
  "body_text": " \nVerification required\n\nPlease complete the challenge to continue.\n\nVerified\n\nProtected by ALTCHA\n\nChecking verification with server...\nÜber\nAPI\nUnterstützung\nBlog\nFeedback\nDatenschutz\nBedingungen\nSucheinstellungen"
}
```

## state=verified note='Verified successfully. Reloading...'

```json
{
  "title": "Captcha",
  "url": "https://www.mojeek.com/search?q=python+asyncio+tutorial&safe=1",
  "html_lang": "de",
  "widget_present": true,
  "widget_state": "verified",
  "widget_attributes": {
    "id": "altcha-widget",
    "challenge": "/captcha/challenge",
    "name": "altcha",
    "theme": "default"
  },
  "captcha_note_text": "Verified successfully. Reloading...",
  "form_action": "/captcha/verify",
  "result_link_count": 0,
  "literal_verification_required": true,
  "literal_checking_with_server": false,
  "lowercase_body_contains_captcha": false,
  "lowercase_title_contains_captcha": true,
  "body_text": " \nVerification required\n\nPlease complete the challenge to continue.\n\nVerified\n\nProtected by ALTCHA\n\nVerified successfully. Reloading...\nÜber\nAPI\nUnterstützung\nBlog\nFeedback\nDatenschutz\nBedingungen\nSucheinstellungen"
}
```

## state=None note=None

```json
{
  "title": "python asyncio tutorial - Mojeek Search",
  "url": "https://www.mojeek.com/search?q=python+asyncio+tutorial&safe=1&chv=a7bba7e60e374505a60b966436088f5c",
  "html_lang": "de",
  "widget_present": false,
  "widget_state": null,
  "widget_attributes": {},
  "captcha_note_text": null,
  "form_action": null,
  "result_link_count": 1,
  "literal_verification_required": false,
  "literal_checking_with_server": false,
  "lowercase_body_contains_captcha": false,
  "lowercase_title_contains_captcha": false,
  "body_text": " \nMojeek User Survey\n \nWebSummaryImagesNews\n\nErgebnisse 1 bis 10 von 24,368 in 0.14s\n\nhttps://realpython.com › async-io-python\n\nPython's asyncio: A Hands-On Walkthrough – Real Python\n\nIn this tutorial, you ’ ll lear"
}
```
