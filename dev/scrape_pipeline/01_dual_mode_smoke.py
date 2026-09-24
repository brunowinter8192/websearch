#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import hashlib
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

QUERY_SECTION_RE = re.compile(r"^## Q(\d+): (.+)$")
ENTRY_RE = re.compile(r"^(\d+)\. \*\*\[([A-Z?]+)\]\*\*")
URL_LINE_RE = re.compile(r"^\s+URL: (https?://\S+)$")

FAILURE_SIGNALS = [
    ("PLUGIN_ROUTE_REQUIRED", "plugin_routed"),
    ("Cookie/consent wall detected", "cookie_wall"),
    ("Login/paywall detected", "login_wall"),
    ("Cloudflare protection", "cloudflare"),
    ("Cloudflare-protected page", "cloudflare"),
    ("HTTP error page", "http_error"),
    ("Navigation dump", "nav_dump"),
    ("Crawl4AI extraction error", "crawl4ai_error"),
    ("No content extracted", "no_content"),
]

WORKTREE_ROOT = Path(__file__).parent.parent.parent
PYTHON = str(WORKTREE_ROOT / "venv" / "bin" / "python3")
CLI = str(WORKTREE_ROOT / "cli.py")
SUBPROCESS_TIMEOUT = 180


# ORCHESTRATOR
async def dual_mode_smoke_workflow(input_path: str, query_id: int, output_dir: str | None):
    query_text, url_entries = parse_smoke_report(input_path, query_id)
    mode1_dir, mode2_dir = prepare_output_dirs(output_dir)
    log_start(query_id, query_text, len(url_entries))

    start_time = time.time()
    results = await scrape_all_urls(url_entries, mode1_dir, mode2_dir)
    end_time = time.time()

    report_path = write_report(
        results, query_text, query_id, input_path, mode1_dir.parent, start_time, end_time
    )
    log_completion(report_path, end_time - start_time)


# FUNCTIONS

def parse_smoke_report(input_path: str, query_id: int) -> tuple[str, list[tuple[int, str, str]]]:
    lines = Path(input_path).read_text(encoding="utf-8").splitlines()
    query_text, start, end = find_query_section(lines, query_id)
    return query_text, extract_urls(lines, start, end)


def find_query_section(lines: list[str], query_id: int) -> tuple[str, int, int]:
    start = -1
    query_text = ""
    for i, line in enumerate(lines):
        m = QUERY_SECTION_RE.match(line)
        if not m:
            continue
        if int(m.group(1)) == query_id:
            start = i
            query_text = m.group(2)
        elif start != -1:
            return query_text, start, i
    if start == -1:
        raise ValueError(f"Query Q{query_id} not found in smoke report")
    return query_text, start, len(lines)


def extract_urls(lines: list[str], start: int, end: int) -> list[tuple[int, str, str]]:
    entries = []
    current_pos, current_class = None, None
    for line in lines[start:end]:
        m = ENTRY_RE.match(line)
        if m:
            current_pos, current_class = int(m.group(1)), m.group(2)
            continue
        if current_pos is not None:
            um = URL_LINE_RE.match(line)
            if um:
                entries.append((current_pos, current_class, um.group(1)))
                current_pos, current_class = None, None
    return entries


def prepare_output_dirs(output_dir: str | None) -> tuple[Path, Path]:
    if output_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = WORKTREE_ROOT / "dev" / "scrape_pipeline" / "01_dual_mode_data" / ts
    else:
        base = Path(output_dir)
    mode1_dir = base / "mode1_raw"
    mode2_dir = base / "mode2_filtered"
    mode1_dir.mkdir(parents=True, exist_ok=True)
    mode2_dir.mkdir(parents=True, exist_ok=True)
    return mode1_dir, mode2_dir


async def scrape_all_urls(
    url_entries: list[tuple[int, str, str]], mode1_dir: Path, mode2_dir: Path
) -> list[dict]:
    results = []
    for pos, class_label, url in url_entries:
        print(f"  [{pos:02d}/20] {url[:90]}", file=sys.stderr)
        m1_task = asyncio.create_task(run_mode1(url, mode1_dir))
        m2_task = asyncio.create_task(run_mode2(url, mode2_dir))
        m1, m2 = await asyncio.gather(m1_task, m2_task)
        results.append({"pos": pos, "class_label": class_label, "url": url, "m1": m1, "m2": m2})
    return results


async def run_mode1(url: str, output_dir: Path) -> dict:
    cmd = [PYTHON, CLI, "scrape_url_raw", url, str(output_dir)]
    rc, stdout, _ = await run_subprocess_async(cmd, SUBPROCESS_TIMEOUT)
    if rc == -1:
        return {"status": "timeout", "bytes": 0, "first_lines": "", "filepath": None}
    return parse_mode1_result(stdout)


async def run_mode2(url: str, output_dir: Path) -> dict:
    cmd = [PYTHON, CLI, "scrape_url_chromium", url]
    rc, stdout, _ = await run_subprocess_async(cmd, SUBPROCESS_TIMEOUT)
    if rc == -1:
        stdout = f"[Timeout after {SUBPROCESS_TIMEOUT}s]"
    out_file = output_dir / (sanitize_filename(url) + ".md")
    out_file.write_text(stdout, encoding="utf-8")
    return parse_mode2_result(stdout, out_file)


async def run_subprocess_async(cmd: list, timeout: int) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(WORKTREE_ROOT),
    )
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        rc = proc.returncode if proc.returncode is not None else 0
        return rc, out_b.decode("utf-8", errors="replace"), err_b.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return -1, "", f"Timeout after {timeout}s"


def parse_mode1_result(stdout: str) -> dict:
    m = re.search(r"^Saved: (.+?) \(", stdout, re.MULTILINE)
    if m:
        filepath = Path(m.group(1))
        if filepath.exists():
            bytes_count = filepath.stat().st_size
            content = filepath.read_text(encoding="utf-8", errors="replace")
            body = [l for l in content.splitlines() if l.strip() and not l.startswith("<!--")][:3]
            return {
                "status": "ok",
                "bytes": bytes_count,
                "first_lines": " | ".join(body),
                "filepath": str(filepath),
            }
    return {
        "status": detect_failure_type(stdout),
        "bytes": 0,
        "first_lines": "",
        "filepath": None,
    }


def parse_mode2_result(stdout: str, out_file: Path) -> dict:
    marker = "# Content from: "
    idx = stdout.find(marker)
    if idx != -1:
        sep = stdout.find("\n\n", idx)
        preview = stdout[sep + 2: sep + 202].strip() if sep != -1 else stdout[idx: idx + 200]
        content_bytes = len(stdout[idx:].encode("utf-8"))
        return {
            "status": "ok",
            "bytes": content_bytes,
            "garbage_type": "—",
            "preview": preview,
            "out_file": str(out_file),
        }
    failure = detect_failure_type(stdout)
    return {
        "status": failure,
        "bytes": len(stdout.encode("utf-8")),
        "garbage_type": failure,
        "preview": stdout[-400:].strip(),
        "out_file": str(out_file),
    }


def detect_failure_type(text: str) -> str:
    for signal, label in FAILURE_SIGNALS:
        if signal in text:
            return label
    return "unknown_error"


def sanitize_filename(url: str) -> str:
    slug = re.sub(r"[^\w]", "_", url)[:80]
    h = hashlib.md5(url.encode()).hexdigest()[:6]
    return f"{slug}_{h}"


def write_report(
    results: list, query_text: str, query_id: int, input_path: str,
    output_dir: Path, start_time: float, end_time: float,
) -> Path:
    m1_ok = [r for r in results if r["m1"]["status"] == "ok"]
    m2_ok = [r for r in results if r["m2"]["status"] == "ok"]
    m1_bytes = [r["m1"]["bytes"] for r in m1_ok]
    m2_failures: dict[str, int] = {}
    for r in results:
        if r["m2"]["status"] != "ok":
            g = r["m2"]["garbage_type"]
            m2_failures[g] = m2_failures.get(g, 0) + 1

    sections = [
        format_header(query_text, query_id, input_path, output_dir, len(results), start_time, end_time),
        format_summary_table(results),
        format_per_url_details(results),
        format_aggregate(results, m1_ok, m2_ok, m1_bytes, m2_failures),
    ]

    report_path = output_dir / "01_dual_mode_report.md"
    report_path.write_text("\n".join(sections), encoding="utf-8")
    return report_path


def format_header(
    query_text: str, query_id: int, input_path: str, output_dir: Path,
    total: int, start_time: float, end_time: float,
) -> str:
    started = datetime.fromtimestamp(start_time).isoformat(timespec="seconds")
    finished = datetime.fromtimestamp(end_time).isoformat(timespec="seconds")
    runtime = end_time - start_time
    return (
        f"# Dual-Mode Scrape Report — Q{query_id}: {query_text}\n\n"
        f"**Source:** `{input_path}`  \n"
        f"**Query:** Q{query_id} — {query_text}  \n"
        f"**Output dir:** `{output_dir}`  \n"
        f"**URLs:** {total}  \n"
        f"**Started:** {started}  \n"
        f"**Finished:** {finished}  \n"
        f"**Runtime:** {runtime:.0f}s  \n\n---"
    )


def format_summary_table(results: list) -> str:
    rows = ["## Summary Table\n",
            "| # | Class | URL | M1 status | M1 bytes | M2 status | M2 bytes | M2 garbage |",
            "|---|-------|-----|-----------|----------|-----------|----------|------------|"]
    for r in results:
        url_s = r["url"][:60] + ("…" if len(r["url"]) > 60 else "")
        m1, m2 = r["m1"], r["m2"]
        rows.append(
            f"| {r['pos']} | {r['class_label']} | {url_s} "
            f"| {m1['status']} | {m1['bytes']:,} "
            f"| {m2['status']} | {m2['bytes']:,} "
            f"| {m2['garbage_type']} |"
        )
    return "\n".join(rows) + "\n\n---"


def format_per_url_details(results: list) -> str:
    lines = ["## Per-URL Details\n"]
    for r in results:
        m1, m2 = r["m1"], r["m2"]
        url = r["url"]
        fl = m1["first_lines"][:120] if m1["first_lines"] else "_(none)_"
        lines += [
            f"### URL {r['pos']}: {url[:70]}",
            "",
            f"**Full URL:** {url}  ",
            f"**Class:** {r['class_label']} | Position: {r['pos']}  ",
            "",
            "**Mode 1 (raw):**  ",
            f"- Status: `{m1['status']}`  ",
            f"- Bytes: {m1['bytes']:,}  ",
            f"- First content lines: `{fl}`  ",
            "",
            "**Mode 2 (filtered):**  ",
            f"- Status: `{m2['status']}`  ",
            f"- Bytes: {m2['bytes']:,}  ",
            f"- Garbage type: `{m2['garbage_type']}`  ",
            f"- Preview: {m2['preview'][:200]}  ",
            "",
        ]
    return "\n".join(lines) + "---"


def format_aggregate(
    results: list, m1_ok: list, m2_ok: list, m1_bytes: list, m2_failures: dict
) -> str:
    lines = [
        "## Aggregate\n",
        f"**Mode 1 (raw) success:** {len(m1_ok)}/{len(results)}  ",
        f"**Mode 2 (filtered) success:** {len(m2_ok)}/{len(results)}  ",
    ]
    if m2_failures:
        lines += ["", "**Mode 2 failure breakdown:**  ", ""]
        for g, count in sorted(m2_failures.items(), key=lambda x: -x[1]):
            lines.append(f"- `{g}`: {count}  ")
    if m1_bytes:
        med = statistics.median(m1_bytes)
        lines += [
            "",
            "**Mode 1 byte-size distribution (successes only):**  ",
            f"- Min: {min(m1_bytes):,}  ",
            f"- Median: {med:,.0f}  ",
            f"- Max: {max(m1_bytes):,}  ",
        ]
    return "\n".join(lines)


def log_start(query_id: int, query_text: str, url_count: int) -> None:
    print(f"dual_mode_smoke: Q{query_id} — {query_text}", file=sys.stderr)
    print(f"URLs to scrape: {url_count} (M1+M2 parallel per URL, sequential across URLs)", file=sys.stderr)


def log_completion(report_path: Path, runtime: float) -> None:
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Runtime: {runtime:.0f}s", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Dual-mode scrape comparison: raw (Mode 1) vs filtered (Mode 2) on 20 URLs from a search smoke report."
    )
    parser.add_argument("--input", required=True, help="Path to search smoke report MD file")
    parser.add_argument("--query", type=int, default=1, help="Query number to use (default: 1)")
    parser.add_argument(
        "--output-dir", dest="output_dir", default=None,
        help="Output directory (default: dev/scrape_pipeline/01_dual_mode_data/<timestamp>/)"
    )
    args = parser.parse_args()
    asyncio.run(dual_mode_smoke_workflow(args.input, args.query, args.output_dir))


if __name__ == "__main__":
    main()
