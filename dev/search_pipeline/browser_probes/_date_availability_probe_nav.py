# INFRASTRUCTURE
import asyncio
import json
from urllib.parse import quote_plus

from pydoll.commands.network_commands import NetworkCommands
from pydoll.protocol.network.types import CookieSameSite

from _date_availability_probe_browser import _extract_value, _generic_diagnose, _wait_for

SOCS_NAME = "SOCS"
SOCS_VALUE = "CAISHAgCEhJnd3NfMjAyNjA0MDctMCAgIBgEIAEaBgiA_fC8Bg"
SOCS_DOMAIN = ".google.com"
GOOGLE_CONSENT_DOMAIN = "consent.google.com"
GOOGLE_CAPTCHA_PATH = "/sorry/"
DDG_CAPTCHA_SELECTOR = "form#challenge-form"
STARTPAGE_HOME_URL = "https://www.startpage.com/"
YANDEX_BLOCK_MARKERS = ("showcaptcha", "checkcaptcha", "/captcha")

CONTAINER_SELECTOR = {
    "google":     "div.MjjYud",
    "duckduckgo": "#links > div.web-result",
    "mojeek":     "ul.results-standard > li",
    "startpage":  "div.result",
    "brave":      'div[data-type="web"]',
    "bing":       "li.b_algo",
    "yandex":     "li.serp-item",
    "lobsters":   "li.story",
}


# FUNCTIONS

def nav_funcs() -> dict:
    return {
        "google": nav_google, "duckduckgo": nav_duckduckgo, "mojeek": nav_mojeek,
        "startpage": nav_startpage, "brave": nav_brave, "bing": nav_bing,
        "yandex": nav_yandex, "lobsters": nav_lobsters,
    }


async def nav_google(tab, query: str):
    await tab._execute_command(NetworkCommands.set_cookie(
        name=SOCS_NAME, value=SOCS_VALUE, domain=SOCS_DOMAIN, path="/",
        secure=True, same_site=CookieSameSite.LAX,
    ))
    url = f"https://www.google.com/search?q={quote_plus(query)}&hl=en&num=10"
    await tab.go_to(url, timeout=3.0)
    current = await tab.current_url
    inline_consent = _extract_value(await tab.execute_script(
        "var b = document.body ? document.body.innerText : ''; "
        "return b.indexOf('Before you continue') !== -1 || b.indexOf('cookies and data') !== -1;"
    ))
    if GOOGLE_CONSENT_DOMAIN in current or inline_consent:
        await tab.execute_script(
            "var btn = document.querySelector('button[jsname=\"b3VHJd\"]') || "
            "document.querySelector('.lssxud') || "
            "document.querySelector('form[action*=\"consent\"] button[type=\"submit\"]') || "
            "document.querySelector('button[aria-label*=\"Accept\"]'); "
            "if (btn) { btn.click(); return true; } return false;"
        )
        await tab.go_to(url, timeout=3.0)
        current = await tab.current_url
    if GOOGLE_CAPTCHA_PATH in current:
        return False, {"marker": "captcha_path_redirect", "url": current, "ready_state": "", "title": ""}
    if not await _wait_for(tab, CONTAINER_SELECTOR["google"], 3, 0.2):
        return False, await _generic_diagnose(tab)
    return True, None


async def nav_duckduckgo(tab, query: str):
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=wt-wt"
    await tab.go_to(url, timeout=3.0)
    captcha_count = _extract_value(await tab.execute_script(
        f"return document.querySelectorAll('{DDG_CAPTCHA_SELECTOR}').length"
    ))
    if captcha_count and int(captcha_count) > 0:
        current = await tab.current_url
        return False, {"marker": "challenge-form", "url": current, "ready_state": "", "title": ""}
    if not await _wait_for(tab, CONTAINER_SELECTOR["duckduckgo"], 3, 0.2):
        return False, await _generic_diagnose(tab)
    return True, None


async def nav_mojeek(tab, query: str):
    url = f"https://www.mojeek.com/search?q={quote_plus(query)}&safe=1"
    await tab.go_to(url, timeout=3.0)
    if not await _wait_for(tab, "ul.results-standard > li > a.ob", 3, 0.2):
        return False, await _generic_diagnose(tab)
    return True, None


async def nav_startpage(tab, query: str):
    await tab.go_to(STARTPAGE_HOME_URL, timeout=10.0)
    await asyncio.sleep(1.5)
    js_set = f"""
    var inp = document.querySelector('#q');
    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeSetter.call(inp, {json.dumps(query)});
    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
    """
    await tab.execute_script(js_set)
    await asyncio.sleep(0.3)
    await tab.execute_script("document.querySelector('button.search-btn').click();")
    if not await _wait_for(tab, CONTAINER_SELECTOR["startpage"], 25, 0.3):
        return False, await _generic_diagnose(tab)
    return True, None


async def nav_brave(tab, query: str):
    url = f"https://search.brave.com/search?q={query.replace(' ', '+')}"
    await tab.go_to(url, timeout=10.0)
    await asyncio.sleep(1.5)
    diag = await _generic_diagnose(tab)
    pow_link = _extract_value(await tab.execute_script(
        'return !!document.querySelector(\'a[href*="pow-captcha"]\');'
    ))
    if diag.get("marker") or pow_link:
        diag["pow_link"] = bool(pow_link)
        return False, diag
    if not await _wait_for(tab, CONTAINER_SELECTOR["brave"], 20, 0.3):
        return False, await _generic_diagnose(tab)
    return True, None


async def nav_bing(tab, query: str):
    url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
    await tab.go_to(url, timeout=10.0)
    if not await _wait_for(tab, CONTAINER_SELECTOR["bing"], 20, 0.3):
        return False, await _generic_diagnose(tab)
    return True, None


async def nav_yandex(tab, query: str):
    url = f"https://yandex.com/search/?text={query.replace(' ', '+')}"
    await tab.go_to(url, timeout=10.0)
    current = await tab.current_url
    if any(m in current.lower() for m in YANDEX_BLOCK_MARKERS):
        return False, {"marker": "block_url_redirect", "url": current, "ready_state": "", "title": ""}
    if not await _wait_for(tab, CONTAINER_SELECTOR["yandex"], 20, 0.3):
        return False, await _generic_diagnose(tab)
    return True, None


async def nav_lobsters(tab, query: str):
    url = f"https://lobste.rs/search?q={quote_plus(query)}&what=stories&order=relevance"
    await tab.go_to(url, timeout=3.0)
    if not await _wait_for(tab, CONTAINER_SELECTOR["lobsters"], 3, 0.2):
        return False, await _generic_diagnose(tab)
    return True, None
