# INFRASTRUCTURE
import json

BLOCK_MARKER_TEXTS = [
    "captcha", "schieberegler ziehen", "drag the slider", "proof of work",
    "checking your browser", "es wird überprüft", "kein bot", "kurze überprüfung",
]
VERIFYING_MARKER_TEXTS = ["letting you in"]
TRIGGER_TEXT_CANDIDATES = ["verifizieren", "verify", "i'm not a robot", "i am not a robot"]

_DEEP_QUERY_FN = """
function _deepQueryAll(root, pred) {
    var out = [];
    var all = root.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
        var el = all[i];
        if (pred(el)) { out.push(el); }
        if (el.shadowRoot) { out = out.concat(_deepQueryAll(el.shadowRoot, pred)); }
    }
    return out;
}
"""

_FACTS_JS_TEMPLATE = """
%(deep_query_fn)s
var _body = document.body ? document.body.innerText.toLowerCase() : '';
var _title = document.title.toLowerCase();
var _blockMarkers = %(block_markers_json)s;
var _verifyingMarkers = %(verifying_markers_json)s;
var _triggerTexts = %(trigger_texts_json)s;
var _markerHit = null;
for (var i = 0; i < _blockMarkers.length; i++) {
    if (_body.indexOf(_blockMarkers[i]) !== -1 || _title.indexOf(_blockMarkers[i]) !== -1) { _markerHit = _blockMarkers[i]; break; }
}
var _verifyingHit = false;
for (var j = 0; j < _verifyingMarkers.length; j++) {
    if (_body.indexOf(_verifyingMarkers[j]) !== -1) { _verifyingHit = true; break; }
}
var _candidates = _deepQueryAll(document, function (el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    var role = el.getAttribute ? (el.getAttribute('role') || '') : '';
    if (tag !== 'button' && role !== 'button') { return false; }
    var text = (el.textContent || '').trim().toLowerCase();
    for (var k = 0; k < _triggerTexts.length; k++) {
        if (text.indexOf(_triggerTexts[k]) !== -1) { return true; }
    }
    return false;
});
var _candidateInfo = _candidates.slice(0, 3).map(function (el) {
    var rect = el.getBoundingClientRect();
    return {
        tag: el.tagName.toLowerCase(),
        text: (el.textContent || '').trim().slice(0, 60),
        in_shadow: el.getRootNode() !== document,
        rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
    };
});
return JSON.stringify({
    result_link_count: document.querySelectorAll('div[data-type="web"]').length,
    pow_link_present: !!document.querySelector('a[href*="pow-captcha"]'),
    marker_present: !!_markerHit,
    marker: _markerHit,
    verifying_marker_present: _verifyingHit,
    button_candidates: _candidateInfo,
    title: document.title,
    url: window.location.href,
    ready_state: document.readyState,
    body_text_sample: _body.slice(0, 300)
});
"""

_TRIGGER_JS_TEMPLATE = """
%(deep_query_fn)s
var _triggerTexts = %(trigger_texts_json)s;
var _candidates = _deepQueryAll(document, function (el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    var role = el.getAttribute ? (el.getAttribute('role') || '') : '';
    if (tag !== 'button' && role !== 'button') { return false; }
    var text = (el.textContent || '').trim().toLowerCase();
    for (var k = 0; k < _triggerTexts.length; k++) {
        if (text.indexOf(_triggerTexts[k]) !== -1) { return true; }
    }
    return false;
});
if (!_candidates.length) { return JSON.stringify({found: false}); }
var el = _candidates[0];
var rect = el.getBoundingClientRect();
var tag = el.tagName.toLowerCase();
var text = (el.textContent || '').trim().slice(0, 60);
var inShadow = el.getRootNode() !== document;
try {
    el.click();
} catch (e) {
    return JSON.stringify({found: true, clicked: false, error: String(e)});
}
return JSON.stringify({
    found: true, clicked: true,
    tag: tag, text: text, in_shadow: inShadow,
    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
});
"""


# FUNCTIONS

def build_facts_js() -> str:
    return _FACTS_JS_TEMPLATE % {
        "deep_query_fn": _DEEP_QUERY_FN,
        "block_markers_json": json.dumps(BLOCK_MARKER_TEXTS),
        "verifying_markers_json": json.dumps(VERIFYING_MARKER_TEXTS),
        "trigger_texts_json": json.dumps(TRIGGER_TEXT_CANDIDATES),
    }


def build_trigger_js() -> str:
    return _TRIGGER_JS_TEMPLATE % {
        "deep_query_fn": _DEEP_QUERY_FN,
        "trigger_texts_json": json.dumps(TRIGGER_TEXT_CANDIDATES),
    }
