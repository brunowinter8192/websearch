# INFRASTRUCTURE
import json

ALTCHA_EVENT_NAMES = [
    "load", "statechange", "verified", "expired",
    "serververification", "codechallenge", "outofmemory",
]

INPUT_PROBE_EVENT_NAMES = ["mousedown", "mouseup", "click"]

VERIFY_IS_FUNCTION_JS = "() => { const el = document.querySelector('altcha-widget'); return el ? typeof el.verify === 'function' : null; }"
FIRE_VERIFY_JS = "() => { const el = document.querySelector('altcha-widget'); if (el && typeof el.verify === 'function') { el.verify(); } }"

INSPECTION_JS = """() => {
  const el = document.querySelector('altcha-widget');
  if (!el) return {};
  const attributes = {};
  Array.from(el.attributes).forEach((a) => { attributes[a.name] = a.value; });
  let configuration = null;
  try { configuration = typeof el.getConfiguration === 'function' ? el.getConfiguration() : null; } catch (e) {}
  let state = null;
  try { state = typeof el.getState === 'function' ? el.getState() : null; } catch (e) {}
  const form = el.closest('form');
  return {
    attributes: attributes,
    configuration: configuration,
    state: state,
    title: document.title,
    form_outer_html: form ? form.outerHTML.slice(0, 3000) : null,
    widget_outer_html: el.outerHTML.slice(0, 3000),
  };
}"""

_OUTCOME_JS_TEMPLATE = """() => {{
  const links = document.querySelectorAll('{result_link_selector}');
  const bodyText = document.body ? document.body.innerText : '';
  return {{
    result_link_count: links.length,
    sample_hrefs: Array.from(links).slice(0, 3).map((a) => a.href),
    title: document.title,
    block_marker_present: bodyText.includes('{block_marker_text}'),
    body_text_length: bodyText.length,
    body_text_sample: bodyText.slice(0, 300),
    li_count: document.querySelectorAll('li').length,
  }};
}}"""


# FUNCTIONS

def build_init_script(set_auto_onload: bool) -> str:
    auto_flag = "true" if set_auto_onload else "false"
    event_names_json = json.dumps(ALTCHA_EVENT_NAMES + INPUT_PROBE_EVENT_NAMES)
    return f"""
(() => {{
  const setAutoOnload = {auto_flag};
  function attach(el) {{
    if (el.__probeAttached) return;
    el.__probeAttached = true;
    if (setAutoOnload) {{
      try {{ el.setAttribute('auto', 'onload'); }} catch (e) {{}}
    }}
    const names = {event_names_json};
    names.forEach((name) => {{
      el.addEventListener(name, (ev) => {{
        const detail = (ev && ev.detail) ? ev.detail : null;
        const record = {{event: name, t_ms: Date.now(), detail: detail ? JSON.stringify(detail) : null}};
        if (window.__probeForward) {{ window.__probeForward(JSON.stringify(record)); }}
      }});
    }});
  }}
  const existing = document.querySelector('altcha-widget');
  if (existing) attach(existing);
  const mo = new MutationObserver((mutations) => {{
    for (const m of mutations) {{
      for (const node of m.addedNodes) {{
        if (node.nodeType === 1) {{
          if (node.tagName === 'ALTCHA-WIDGET') attach(node);
          if (node.querySelectorAll) {{
            node.querySelectorAll('altcha-widget').forEach(attach);
          }}
        }}
      }}
    }}
  }});
  mo.observe(document, {{childList: true, subtree: true}});
}})();
"""


def build_outcome_js(result_link_selector: str, block_marker_text: str) -> str:
    return _OUTCOME_JS_TEMPLATE.format(
        result_link_selector=result_link_selector, block_marker_text=block_marker_text,
    )
