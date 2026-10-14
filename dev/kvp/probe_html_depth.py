# INFRASTRUCTURE
import argparse
import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import lxml.html
from crawl4ai import DefaultMarkdownGenerator, LXMLWebScrapingStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter

from dev.kvp.kvp_config import CANARY_JSON_DIR, REPORT_DIR

PRUNING_THRESHOLD = 0.48
PRESERVE_TAGS = ["pre", "code"]
OPEN_DIV = re.compile(r"<div\b", re.IGNORECASE)
CLOSE_DIV = re.compile(r"</div>", re.IGNORECASE)


# ORCHESTRATOR

def main() -> None:
    args = parse_args()
    html = read_html(Path(args.html))
    default_run = measure(html, args.url, args.contains, huge_tree=False)
    huge_run = measure(html, args.url, args.contains, huge_tree=True)
    result = build_result(args, html, default_run, huge_run)
    json_path, md_path = write_outputs(result, Path(args.html))
    print(json_path)
    print(md_path)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Offline: what crawl4ai's lxml scraping strategy keeps of a saved HTML page with the default parser and with huge_tree")
    ap.add_argument("--html", required=True, help="Saved page, plain or .gz")
    ap.add_argument("--url", required=True, help="URL the page was fetched from")
    ap.add_argument("--contains", nargs="+", required=True, help="Strings whose presence in the output is checked")
    return ap.parse_args()


def read_html(path: Path) -> str:
    return gzip.open(path, "rt", encoding="utf-8").read() if path.suffix == ".gz" else path.read_text(encoding="utf-8")


def measure(html: str, url: str, needles: list[str], huge_tree: bool) -> dict:
    default_parser = lxml.html.html_parser
    lxml.html.html_parser = lxml.html.HTMLParser(huge_tree=huge_tree)
    try:
        cleaned = LXMLWebScrapingStrategy().scrap(url, html).cleaned_html
        markdown = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=PRUNING_THRESHOLD, preserve_tags=PRESERVE_TAGS)
        ).generate_markdown(input_html=cleaned, base_url=url)
        document = lxml.html.document_fromstring(html, parser=lxml.html.HTMLParser(huge_tree=huge_tree))
    finally:
        lxml.html.html_parser = default_parser
    return {
        "huge_tree": huge_tree,
        "parsed_text_chars": len(document.text_content()),
        "max_depth": max(_depth(element) for element in document.iter()),
        "cleaned_html_chars": len(cleaned),
        "raw_markdown_chars": len(markdown.raw_markdown),
        "fit_markdown_chars": len(markdown.fit_markdown),
        "in_raw_markdown": {needle: needle in markdown.raw_markdown for needle in needles},
    }


def _depth(element) -> int:
    depth = 0
    while element is not None:
        depth += 1
        element = element.getparent()
    return depth


def build_result(args: argparse.Namespace, html: str, default_run: dict, huge_run: dict) -> dict:
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "html": args.html, "url": args.url, "html_chars": len(html),
        "div_tags_opened_closed": [len(OPEN_DIV.findall(html)), len(CLOSE_DIV.findall(html))],
        "runs": [default_run, huge_run],
    }


def write_outputs(result: dict, html_path: Path) -> tuple[Path, Path]:
    CANARY_JSON_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"probe_html_depth_{html_path.name.split('.')[0]}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    json_path, md_path = CANARY_JSON_DIR / f"{stem}.json", REPORT_DIR / f"{stem}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return json_path, md_path


def render_markdown(result: dict) -> str:
    lines = [
        "# probe_html_depth", "",
        f"- Generated: {result['generated']}", f"- Page: `{result['html']}` ({result['html_chars']} chars), fetched from {result['url']}",
        f"- `<div` tags opened / `</div>` closed in the source: {result['div_tags_opened_closed'][0]} / {result['div_tags_opened_closed'][1]}", "",
        "| parser | max tree depth | text chars parsed | cleaned_html chars | raw markdown chars | fit markdown chars | strings in raw markdown |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in result["runs"]:
        lines.append(
            f"| {'huge_tree' if run['huge_tree'] else 'lxml default'} | {run['max_depth']} | {run['parsed_text_chars']} | {run['cleaned_html_chars']} | "
            f"{run['raw_markdown_chars']} | {run['fit_markdown_chars']} | {json.dumps(run['in_raw_markdown'], ensure_ascii=False)} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
