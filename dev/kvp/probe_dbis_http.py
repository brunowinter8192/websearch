# INFRASTRUCTURE
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from dev.kvp.kvp_config import CANARY_JSON_DIR, REPORT_DIR

BODY_DUMP_DIR = Path("/tmp")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)
TIMEOUT_S = 30.0
SCRIPT_SRC = re.compile(r"<script[^>]*\ssrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
FORM_TAG = re.compile(r"<form[^>]*>", re.IGNORECASE)
INPUT_TAG = re.compile(r"<input[^>]*>", re.IGNORECASE)
TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
H1_TAG = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
OPEN_DIV = re.compile(r"<div\b", re.IGNORECASE)
CLOSE_DIV = re.compile(r"</div>", re.IGNORECASE)
CONTEXT_CHARS = 160


# ORCHESTRATOR

def main() -> None:
    args = parse_args()
    response = fetch(args.url)
    result = build_result(args, response)
    dump_path = dump_body(response, args.label)
    json_path, md_path = write_outputs({**result, "body_dump": str(dump_path)}, args.label)
    print(json_path)
    print(md_path)
    print(dump_path)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="One plain HTTP GET of one URL: what the server itself sends, without a browser")
    ap.add_argument("--url", required=True)
    ap.add_argument("--marker", required=True, help="Text that should be in the page if the result list is there")
    ap.add_argument("--label", required=True)
    return ap.parse_args()


def fetch(url: str) -> httpx.Response:
    with httpx.Client(follow_redirects=True, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
        return client.get(url)


def build_result(args: argparse.Namespace, response: httpx.Response) -> dict:
    body = response.text
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "url": args.url, "marker": args.marker, "label": args.label,
        "status": response.status_code, "final_url": str(response.url),
        "redirect_chain": [{"status": r.status_code, "url": str(r.url)} for r in response.history],
        "content_type": response.headers.get("content-type"),
        "body_bytes": len(response.content),
        "marker_in_body": args.marker in body,
        "marker_contexts": marker_contexts(body, args.marker),
        "title": clean(TITLE_TAG.search(body).group(1)) if TITLE_TAG.search(body) else None,
        "h1": [clean(h) for h in H1_TAG.findall(body)],
        "div_open_close": [len(OPEN_DIV.findall(body)), len(CLOSE_DIV.findall(body))],
        "script_srcs": SCRIPT_SRC.findall(body),
        "inline_script_bytes": [len(s) for s in INLINE_SCRIPT.findall(body)],
        "forms": FORM_TAG.findall(body)[:10],
        "inputs": INPUT_TAG.findall(body)[:20],
    }


def marker_contexts(body: str, marker: str) -> list[str]:
    contexts = []
    for match in re.finditer(re.escape(marker), body):
        start = max(0, match.start() - CONTEXT_CHARS)
        contexts.append(clean(body[start:match.end() + CONTEXT_CHARS]))
        if len(contexts) == 5:
            break
    return contexts


def clean(text: str) -> str:
    return " ".join(text.split())


def dump_body(response: httpx.Response, label: str) -> Path:
    path = BODY_DUMP_DIR / f"kvp55_probe_dbis_http_{label}_{_stamp()}.html"
    path.write_text(response.text, encoding="utf-8")
    return path


def write_outputs(result: dict, label: str) -> tuple[Path, Path]:
    CANARY_JSON_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"probe_dbis_http_{label}_{_stamp()}"
    json_path, md_path = CANARY_JSON_DIR / f"{stem}.json", REPORT_DIR / f"{stem}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return json_path, md_path


def render_markdown(result: dict) -> str:
    lines = [
        f"# probe_dbis_http `{result['label']}`", "",
        f"- Generated: {result['generated']}", f"- URL: {result['url']}", f"- Final URL: {result['final_url']}",
        f"- Status: {result['status']}, redirects: {json.dumps(result['redirect_chain'])}",
        f"- Content type: {result['content_type']}, body: {result['body_bytes']} B, title: {result['title']}",
        f"- Marker `{result['marker']}` in body: {result['marker_in_body']}",
        f"- h1: {json.dumps(result['h1'], ensure_ascii=False)}, div tags opened/closed: {result['div_open_close']}",
        f"- Body dump: `{result['body_dump']}`", "", "## Marker contexts", "",
    ]
    lines += [f"- {c}" for c in result["marker_contexts"]] or ["(none)"]
    lines += ["", "## Scripts", "", f"- External: {json.dumps(result['script_srcs'])}",
              f"- Inline script sizes (bytes): {json.dumps(result['inline_script_bytes'])}", "", "## Forms and inputs", ""]
    lines += [f"- `{tag}`" for tag in [*result["forms"], *result["inputs"]]] or ["(none)"]
    return "\n".join(lines) + "\n"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


if __name__ == "__main__":
    main()
