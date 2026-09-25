#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import difflib
import json
import re
import statistics
import sys
from pathlib import Path

DESCRIPTION = """
analyze.py — Diff sweep candidate outputs against clean-raw baseline.

For each (config, URL): compute line-set recall/precision/F1 vs clean-raw.
Aggregate per config (median F1, min F1, mean recall, mean precision, per-shape).
Generate _analysis.md with cross-config table + per-shape breakdown +
unified_diff drill-downs for top-3 configs on representative URLs.

Usage:
    ./venv/bin/python dev/scrape_pipeline/04_overview_sweep/analyze.py
    ./venv/bin/python dev/scrape_pipeline/04_overview_sweep/analyze.py --sweep <ts-dir>
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SWEEP_BASE = PROJECT_ROOT / "dev" / "scrape_pipeline" / "04_overview_sweep" / "sweep_data"
CLEANRAW_BASE = PROJECT_ROOT / "dev" / "scrape_pipeline" / "03_cleanup" / "cleaned_data"

SHAPE_MAP = {
    "chuniversiteit.nl":           "Blog",
    "seirdy.one":                  "Blog",
    "justtothepoint.com":          "Blog",
    "www.contextractor.com":       "Blog",
    "trafilatura.readthedocs.io":  "Blog",
    "arxiv.org":                   "Paper-Landing",
    "doi.org":                     "Paper-Landing",
    "news.ycombinator.com":        "Forum-Thread",
    "github.com":                  "Repo-Heavy-Chrome",
    "www.libhunt.com":             "Index-Aggregator",
    "adrien.barbaresi.eu":         "Index-Aggregator",
    "webscraping.fyi":             "_excluded_scrape_failure",
    "downloads.webis.de":          "_excluded_pdf",
    "searchstudies.org":           "_excluded_pdf",
}
EXCLUDE_PREFIXES = ("_excluded_",)


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--sweep", default=None, help="Path to sweep_data/<ts>/ (default: latest)")
    parser.add_argument("--cleanraw", default=None, help="Path to cleaned_data/<ts>/ (default: latest)")
    parser.add_argument("--drill", type=int, default=4, help="Number of URLs for diff drill-down (default 4)")
    args = parser.parse_args()

    sweep_dir = Path(args.sweep) if args.sweep else find_latest_dir(SWEEP_BASE)
    cleanraw_dir = Path(args.cleanraw) if args.cleanraw else find_latest_dir(CLEANRAW_BASE)
    analyze_workflow(sweep_dir, cleanraw_dir, args.drill)


# FUNCTIONS

def find_latest_dir(base: Path) -> Path:
    candidates = sorted(p for p in base.iterdir() if p.is_dir())
    if not candidates:
        raise SystemExit(f"No subdirs in {base}")
    return candidates[-1]


def analyze_workflow(sweep_dir: Path, cleanraw_dir: Path, drill_count: int) -> None:
    print(f"sweep:    {sweep_dir}", file=sys.stderr)
    print(f"cleanraw: {cleanraw_dir}\n", file=sys.stderr)

    metadata = json.loads((sweep_dir / "_run_metadata.json").read_text(encoding="utf-8"))
    cleanraw_by_url = load_cleanraws(cleanraw_dir)

    config_metrics = []
    for cfg_meta in metadata["configs"]:
        config_name = cfg_meta["name"]
        config_dir = sweep_dir / config_name
        if not config_dir.is_dir():
            continue
        per_url = analyze_config(config_dir, cleanraw_by_url, cfg_meta)
        agg = aggregate_metrics(config_name, cfg_meta, per_url)
        config_metrics.append(agg)
        print(f"  {config_name:55s}  median F1: {agg['median_f1']:.3f}  min: {agg['min_f1']:.3f}  ({agg['analyzed_n']}/{agg['total_n']} URLs)", file=sys.stderr)

    config_metrics.sort(key=lambda c: c["median_f1"], reverse=True)

    report_path = sweep_dir / "_analysis.md"
    write_report(report_path, sweep_dir, cleanraw_dir, config_metrics, cleanraw_by_url, drill_count)
    print(f"\nReport: {report_path}", file=sys.stderr)


def load_cleanraws(cleanraw_dir: Path) -> dict:
    out = {}
    for f in cleanraw_dir.glob("*.md"):
        if f.name.startswith("_") or f.name == "02_raw_report.md":
            continue
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^<!-- source: (\S+) -->", text)
        if m:
            out[m.group(1)] = text
    return out


def analyze_config(config_dir: Path, cleanraw_by_url: dict, cfg_meta: dict) -> list:
    per_url = []
    for output in cfg_meta.get("outputs", []):
        url = output["url"]
        shape = url_shape(url)
        if shape.startswith(EXCLUDE_PREFIXES):
            continue
        if output["status"] != "ok":
            per_url.append({
                "url": url, "shape": shape, "status": output["status"],
                "recall": None, "precision": None, "f1": None,
                "candidate_bytes": 0, "cleanraw_bytes": len(cleanraw_by_url.get(url, "")),
                "bytes_diff": -len(cleanraw_by_url.get(url, "")),
            })
            continue
        candidate_path = config_dir / output["filename"]
        if not candidate_path.is_file():
            continue
        candidate = candidate_path.read_text(encoding="utf-8")
        cleanraw = cleanraw_by_url.get(url, "")
        if not cleanraw:
            continue

        recall, precision, f1 = line_set_metrics(candidate, cleanraw)
        per_url.append({
            "url": url, "shape": shape, "status": "ok",
            "recall": recall, "precision": precision, "f1": f1,
            "candidate_bytes": len(candidate), "cleanraw_bytes": len(cleanraw),
            "bytes_diff": len(candidate) - len(cleanraw),
        })
    return per_url


def aggregate_metrics(config_name: str, cfg_meta: dict, per_url: list) -> dict:
    valid = [u for u in per_url if u["f1"] is not None]
    f1s = [u["f1"] for u in valid]
    recalls = [u["recall"] for u in valid]
    precisions = [u["precision"] for u in valid]
    bytes_diffs = [u["bytes_diff"] for u in valid]

    shape_groups = {}
    for u in valid:
        shape_groups.setdefault(u["shape"], []).append(u["f1"])
    shape_medians = {s: statistics.median(fs) for s, fs in shape_groups.items()}

    fail_count = sum(1 for u in per_url if u["status"] != "ok") + sum(1 for u in valid if u["f1"] < 0.3)

    return {
        "config_name": config_name,
        "filter": cfg_meta["filter"]["name"],
        "content_source": cfg_meta["content_source"],
        "selector": cfg_meta["selector"]["name"],
        "elapsed_seconds": cfg_meta.get("elapsed_seconds", 0),
        "median_f1": statistics.median(f1s) if f1s else 0,
        "min_f1": min(f1s) if f1s else 0,
        "max_f1": max(f1s) if f1s else 0,
        "mean_recall": statistics.mean(recalls) if recalls else 0,
        "mean_precision": statistics.mean(precisions) if precisions else 0,
        "median_bytes_diff": int(statistics.median(bytes_diffs)) if bytes_diffs else 0,
        "fail_count": fail_count,
        "analyzed_n": len(valid),
        "total_n": len(per_url),
        "shape_medians": shape_medians,
        "per_url": per_url,
    }


def write_report(path: Path, sweep_dir: Path, cleanraw_dir: Path, configs: list, cleanraw_by_url: dict, drill_count: int) -> None:
    lines = _format_header_and_ranking(sweep_dir, cleanraw_dir, configs)
    lines += _format_per_shape_breakdown(configs)
    lines += _format_drill_down(configs, cleanraw_by_url, sweep_dir, drill_count)
    path.write_text("\n".join(lines), encoding="utf-8")


def line_set_metrics(candidate: str, cleanraw: str) -> tuple[float, float, float]:
    cand_lines = normalize_lines(candidate)
    ref_lines = normalize_lines(cleanraw)
    if not ref_lines or not cand_lines:
        return 0.0, 0.0, 0.0
    inter = len(cand_lines & ref_lines)
    recall = inter / len(ref_lines)
    precision = inter / len(cand_lines)
    if recall + precision == 0:
        return 0.0, 0.0, 0.0
    f1 = 2 * recall * precision / (recall + precision)
    return recall, precision, f1


def _format_header_and_ranking(sweep_dir: Path, cleanraw_dir: Path, configs: list) -> list:
    lines = [
        "# Overview Sweep Analysis",
        "",
        f"**Sweep:** `{sweep_dir.relative_to(PROJECT_ROOT)}`",
        f"**Clean-raw baseline:** `{cleanraw_dir.relative_to(PROJECT_ROOT)}`",
        f"**Configs analyzed:** {len(configs)}",
        "",
        "## Cross-Config Ranking (by median F1)",
        "",
        "| # | Config | Filter | Source | Selector | Median F1 | Min F1 | Recall | Precision | bytes Δ | Fails | Time |",
        "|---|--------|--------|--------|----------|-----------|--------|--------|-----------|---------|-------|------|",
    ]
    for i, c in enumerate(configs, 1):
        lines.append(
            f"| {i} | `{c['config_name']}` | {c['filter']} | {c['content_source']} | {c['selector']} "
            f"| {c['median_f1']:.3f} | {c['min_f1']:.3f} | {c['mean_recall']:.3f} | {c['mean_precision']:.3f} "
            f"| {c['median_bytes_diff']:+,} | {c['fail_count']} | {c['elapsed_seconds']:.0f}s |"
        )
    return lines


def _format_per_shape_breakdown(configs: list) -> list:
    lines = [
        "",
        "## Per-Shape Median F1 (top 10 configs)",
        "",
        "Shape rows × top-10 configs cols. Catches per-shape config differences (e.g. best for Blog ≠ best for Forum).",
        "",
    ]
    top = configs[:10]
    all_shapes = sorted({s for c in configs for s in c["shape_medians"].keys()})
    header = "| Shape | " + " | ".join(f"#{i+1}" for i in range(len(top))) + " |"
    sep = "|---|" + "|".join("---" for _ in top) + "|"
    lines += [header, sep]
    for shape in all_shapes:
        row = f"| {shape} | " + " | ".join(
            (f"{c['shape_medians'][shape]:.2f}" if shape in c["shape_medians"] else "—") for c in top
        ) + " |"
        lines.append(row)
    lines += [
        "",
        "Top-10 column legend:",
    ]
    for i, c in enumerate(top, 1):
        lines.append(f"- **#{i}** = `{c['config_name']}`")
    return lines


def _format_drill_down(configs: list, cleanraw_by_url: dict, sweep_dir: Path, drill_count: int) -> list:
    lines = ["", "## Diff Drill-Down — Top 3 Configs"]
    top3 = configs[:3]
    drill_urls = pick_drill_urls(cleanraw_by_url, drill_count)
    for c in top3:
        lines += [
            "",
            f"### Config: `{c['config_name']}`",
            f"Filter: {c['filter']} | Source: {c['content_source']} | Selector: {c['selector']}",
            f"Median F1: {c['median_f1']:.3f} | Recall: {c['mean_recall']:.3f} | Precision: {c['mean_precision']:.3f}",
            "",
        ]
        for url in drill_urls:
            shape = url_shape(url)
            url_metric = next((u for u in c["per_url"] if u["url"] == url), None)
            if not url_metric or url_metric["status"] != "ok":
                continue
            lines += [
                f"#### {shape} — `{url}`",
                f"F1: {url_metric['f1']:.3f} | recall: {url_metric['recall']:.3f} | precision: {url_metric['precision']:.3f} | bytes Δ: {url_metric['bytes_diff']:+,}",
                "",
            ]
            diff = generate_diff(c["config_name"], sweep_dir, url, cleanraw_by_url)
            lines.append("```diff")
            lines.append(diff)
            lines.append("```")
            lines.append("")
    return lines


def normalize_lines(text: str) -> set:
    out = set()
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("<!-- source:"):
            continue
        s = re.sub(r"\s+", " ", s).lower()
        out.add(s)
    return out


def pick_drill_urls(cleanraw_by_url: dict, n: int) -> list:
    by_shape: dict[str, list] = {}
    for url in cleanraw_by_url.keys():
        s = url_shape(url)
        if s.startswith(EXCLUDE_PREFIXES):
            continue
        by_shape.setdefault(s, []).append(url)
    picks = []
    for shape, urls in by_shape.items():
        picks.append(sorted(urls)[0])
        if len(picks) >= n:
            break
    while len(picks) < n:
        for shape, urls in by_shape.items():
            if len(urls) > 1 and len(picks) < n:
                for u in sorted(urls):
                    if u not in picks:
                        picks.append(u)
                        break
        if len(picks) >= n:
            break
        else:
            break
    return picks[:n]


def generate_diff(config_name: str, sweep_dir: Path, url: str, cleanraw_by_url: dict) -> str:
    cleanraw = cleanraw_by_url.get(url, "")
    cand_path = next(
        (sweep_dir / config_name).glob(f"*{hashlib_md5(url)}*.md"),
        None
    )
    if not cand_path:
        return "(candidate file not found)"
    candidate = cand_path.read_text(encoding="utf-8")

    cand_lines = candidate.splitlines()[:300]
    ref_lines = cleanraw.splitlines()[:300]
    diff = list(difflib.unified_diff(
        ref_lines, cand_lines, fromfile="cleanraw", tofile="candidate", lineterm="", n=2
    ))
    if len(diff) > 60:
        diff = diff[:60] + ["... [diff truncated, showing first 60 lines] ..."]
    return "\n".join(diff)


def url_shape(url: str) -> str:
    for domain, shape in SHAPE_MAP.items():
        if domain in url:
            return shape
    return "Unknown"


def hashlib_md5(url: str) -> str:
    import hashlib as h
    return h.md5(url.encode()).hexdigest()[:6]


if __name__ == "__main__":
    main()
