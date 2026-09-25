#!/usr/bin/env python3
# INFRASTRUCTURE
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPORT_PATH = SCRIPT_DIR / "md" / "12_emoji_scan.md"
PROJECT_ROOT = SCRIPT_DIR.parents[1]
GLYPH_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B50, 0x2B50), (0x2B55, 0x2B55), (0xFE0F, 0xFE0F), (0x231A, 0x231B), (0x23E9, 0x23FF), (0x2B1B, 0x2B1C))
GLYPHS = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in GLYPH_RANGES) + "]")
SCANNED_SUFFIXES = (".py", ".sh", ".toml", ".yml", ".yaml", ".txt")
EXEMPT_MARKERS = (
    ("/md/", "generated reports kept as historical artifacts"),
    ("_output/", "generated reports kept as historical artifacts"),
    ("_data/", "scraped third-party fixture data"),
    ("01_dual_mode_data", "scraped third-party fixture data"),
    ("/runs/", "generated run artifacts"),
)


# ORCHESTRATOR

def emoji_scan_workflow() -> None:
    files = tracked_dev_files()
    findings, exempt_counts = scan(files)
    write_report(render_report(findings, exempt_counts))
    print_summary(findings)


# FUNCTIONS

def tracked_dev_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files", "dev"], cwd=PROJECT_ROOT, text=True)
    return [f for f in out.split("\n") if f]


def scan(files: list[str]) -> tuple[list[str], dict]:
    findings: list[str] = []
    exempt_counts: dict[str, int] = {}
    for rel in files:
        hits = glyph_lines(rel)
        if not hits:
            continue
        reason = exemption(rel)
        if reason:
            exempt_counts[reason] = exempt_counts.get(reason, 0) + 1
        else:
            findings += [f"{rel}:{line}: {text}" for line, text in hits]
    return findings, exempt_counts


def render_report(findings: list[str], exempt_counts: dict) -> str:
    lines = ["# 12_emoji_scan report", "", f"findings in scripts and docs: {len(findings)}", ""]
    lines += ["## Findings", ""] + [f"- {f}" for f in findings] + [""]
    lines += ["## Exempt files with glyphs (count of files)", ""] + [f"- {reason}: {n}" for reason, n in sorted(exempt_counts.items())] + [""]
    return "\n".join(lines) + "\n"


def write_report(report: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def print_summary(findings: list[str]) -> None:
    print(f"findings={len(findings)} report={REPORT_PATH}")


def glyph_lines(rel: str) -> list[tuple[int, str]]:
    text = (PROJECT_ROOT / rel).read_text(encoding="utf-8", errors="replace")
    return [(i, line.strip()[:100]) for i, line in enumerate(text.split("\n"), 1) if GLYPHS.search(line)]


def exemption(rel: str) -> str | None:
    for marker, reason in EXEMPT_MARKERS:
        if marker in "/" + rel:
            return reason
    if not rel.endswith(SCANNED_SUFFIXES) and not rel.endswith("DOCS.md"):
        return "tracked data or report file type"
    return None


if __name__ == "__main__":
    emoji_scan_workflow()
