# INFRASTRUCTURE
import json

ALTCHA_EVENT_NAMES = [
    "load", "statechange", "verified", "expired",
    "serververification", "codechallenge", "outofmemory",
]

_FACTS_JS_TEMPLATE = """
var _links = document.querySelectorAll('{result_link_selector}');
var _body = document.body ? document.body.innerText : '';
var _w = document.querySelector('altcha-widget');
var _state = null;
try {{ _state = (_w && typeof _w.getState === 'function') ? _w.getState() : null; }} catch (e) {{ _state = null; }}
return JSON.stringify({{
    result_link_count: _links.length,
    sample_hrefs: Array.prototype.slice.call(_links, 0, 3).map(function (a) {{ return a.href; }}),
    title: document.title,
    url: window.location.href,
    widget_present: !!_w,
    verify_is_function: _w ? (typeof _w.verify === 'function') : false,
    widget_state: _state,
    block_marker_present: _body.indexOf('{block_marker_text}') !== -1,
    in_flight_marker_present: _body.indexOf('{in_flight_marker_text}') !== -1,
    body_text_length: _body.length,
    body_text_sample: _body.slice(0, 300)
}});
"""

_ATTACH_EVENTS_JS_TEMPLATE = """
var _w = document.querySelector('altcha-widget');
if (!_w) return JSON.stringify({{attached: false, now: Date.now()}});
if (_w.__probeAttached) return JSON.stringify({{attached: true, already: true, now: Date.now()}});
_w.__probeAttached = true;
window.__mojeekEvents = window.__mojeekEvents || [];
var _names = {event_names_json};
_names.forEach(function (name) {{
    _w.addEventListener(name, function (ev) {{
        var _detail = (ev && ev.detail) ? ev.detail : null;
        window.__mojeekEvents.push({{
            event: name,
            t_ms: Date.now(),
            detail: _detail ? JSON.stringify(_detail) : null
        }});
    }});
}});
return JSON.stringify({{attached: true, already: false, now: Date.now()}});
"""

DRAIN_EVENTS_JS = """
var _buf = window.__mojeekEvents || [];
window.__mojeekEvents = [];
return JSON.stringify(_buf);
"""

FIRE_VERIFY_JS = """
var _w = document.querySelector('altcha-widget');
if (!_w || typeof _w.verify !== 'function') return JSON.stringify({fired: false});
_w.verify();
return JSON.stringify({fired: true});
"""

WIDGET_DETAIL_JS = """
var _w = document.querySelector('altcha-widget');
if (!_w) return JSON.stringify({});
var _attrs = {};
Array.prototype.slice.call(_w.attributes).forEach(function (a) { _attrs[a.name] = a.value; });
var _config = null;
try { _config = typeof _w.getConfiguration === 'function' ? _w.getConfiguration() : null; } catch (e) {}
return JSON.stringify({attributes: _attrs, configuration: _config});
"""


# FUNCTIONS

def build_facts_js(result_link_selector: str, block_marker_text: str, in_flight_marker_text: str) -> str:
    return _FACTS_JS_TEMPLATE.format(
        result_link_selector=result_link_selector,
        block_marker_text=block_marker_text,
        in_flight_marker_text=in_flight_marker_text,
    )


def build_attach_events_js() -> str:
    return _ATTACH_EVENTS_JS_TEMPLATE.format(event_names_json=json.dumps(ALTCHA_EVENT_NAMES))
