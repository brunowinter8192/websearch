# INFRASTRUCTURE
from datetime import datetime, timezone
from pathlib import Path

from _lane_metrics_aggregate import LANES
from _lane_metrics_prose import PROSE_PERCENTILE

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"


# FUNCTIONS

def write_report(results: list[dict], aggregate: dict, cap: int, distribution: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / f"04_lane_metrics_report_{ts}.md"

    sections = [
        "# Lane content/boilerplate metrics (Kohlschuetter Algorithm 2 + PROSE cap)",
        format_cap_section(cap, distribution),
        "\n\n".join(format_url_section(entry) for entry in results),
        format_table(results),
        format_aggregate_section(aggregate, len(results)),
        format_rescue_section(aggregate),
    ]
    report_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    return report_path


def format_cap_section(cap: int, distribution: dict) -> str:
    lines = [
        "## PROSE length cap (derived from the chromium block-word-count distribution)",
        "",
        f"- Chromium blocks measured: {distribution['n']}",
        f"- median: {distribution['median']:.0f}  p50: {distribution['p50']:.0f}  "
        f"p75: {distribution['p75']:.0f}  p90: {distribution['p90']:.0f}  "
        f"p95: {distribution['p95']:.0f}  p99: {distribution['p99']:.0f}  max: {distribution['max']}",
        f"- Cap chosen: {cap} words — the {PROSE_PERCENTILE}th percentile of the distribution above.",
    ]
    return "\n".join(lines)


def format_url_section(entry: dict) -> str:
    lines = [f"### {entry['url']}", ""]
    for lane in LANES:
        lines.append(format_lane_line(lane, entry["lanes"][lane]))
    return "\n".join(lines)


def format_table(results: list[dict]) -> str:
    header = (
        "| URL | Lane | Content words | Content % | Blocks | Link density | Longest (w) | "
        "Prose blocks | Prose words |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for entry in results:
        for lane in LANES:
            m = entry["lanes"][lane]
            rows.append(
                f"| {entry['url']} | {lane} | {m['words_content']}/{m['words_total']} | "
                f"{m['words_content_pct']:.0f}% | {m['blocks_content']}/{m['blocks_total']} | "
                f"{m['link_density_overall']:.2f} | {m['longest_content_block']} | "
                f"{m['prose_blocks']}/{m['blocks_content']} | {m['prose_words']} |"
            )
    return f"## All {len(results)} URLs\n\n" + "\n".join(rows)


def format_aggregate_section(aggregate: dict, pair_count: int) -> str:
    ww = aggregate["words_wins"]
    pw = aggregate["pct_wins"]
    ce = aggregate["cap_excluded"]
    lines = [
        f"## Aggregate ({pair_count} pairs)",
        "",
        f"- More CONTENT words: chromium {ww['chromium']}, camoufox {ww['camoufox']}, tie {ww['tie']}",
        f"- Higher CONTENT percentage: chromium {pw['chromium']}, camoufox {pw['camoufox']}, tie {pw['tie']}",
        f"- Pairs where the two measures point at different lanes: {len(aggregate['disagreements'])}",
    ]
    if aggregate["disagreements"]:
        lines.append("")
        for url in aggregate["disagreements"]:
            lines.append(f"  - {url}")
    lines += [
        "",
        "- PROSE-cap exclusions (CONTENT blocks with a sentence-ending mark, over the cap), per lane:",
        f"  - chromium: {ce['chromium']['blocks']} blocks, {ce['chromium']['words']} words",
        f"  - camoufox: {ce['camoufox']['blocks']} blocks, {ce['camoufox']['words']} words",
    ]
    return "\n".join(lines)


def format_rescue_section(aggregate: dict) -> str:
    rescued = aggregate["rescued_by_camoufox_prose"]
    not_rescued = aggregate["not_rescued"]
    lines = [
        "## Pairs where chromium has zero CONTENT blocks",
        "",
        f"- Total: {aggregate['zero_content_chromium_count']}",
        f"- Of those, camoufox has at least one PROSE block: {len(rescued)}",
        f"- Of those, camoufox has zero PROSE blocks: {len(not_rescued)}",
    ]
    if rescued:
        lines += ["", "### camoufox has >=1 PROSE block"]
        for url in rescued:
            lines.append(f"- {url}")
    if not_rescued:
        lines += ["", "### camoufox has zero PROSE blocks"]
        for url in not_rescued:
            lines.append(f"- {url}")
    return "\n".join(lines)


def format_lane_line(lane: str, m: dict) -> str:
    content_str = f"content {m['words_content']}/{m['words_total']} words ({m['words_content_pct']:.0f}%)"
    blocks_str = f"blocks {m['blocks_content']}/{m['blocks_total']}"
    link_str = f"link-density {m['link_density_overall']:.2f}"
    longest_str = f"longest {m['longest_content_block']}w"
    prose_str = f"prose {m['prose_blocks']}/{m['blocks_content']}blk {m['prose_words']}w"
    return (
        f"{lane:<9s} {pad_min2(content_str, 32)}{pad_min2(blocks_str, 12)}"
        f"{pad_min2(link_str, 18)}{pad_min2(longest_str, 14)}{prose_str}"
    )


def pad_min2(s: str, width: int) -> str:
    return s + " " * max(2, width - len(s))
