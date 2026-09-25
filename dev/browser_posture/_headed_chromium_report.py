# INFRASTRUCTURE
import importlib.metadata
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import BACKGROUNDING_FLAGS

CRAWL4AI_UNCONDITIONAL_ARGS = {
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
}


# FUNCTIONS

def write_report(
    run_a: dict, run_b: dict, run_c: dict | None, bundle_path: Path,
    original_lsuielement: bool | None, plist_end_state: bool | None, plist_format_restored: bool,
    codesign_before: dict, codesign_after: dict | None, orphans: list[str], report_dir: Path,
) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"04_headed_chromium_probe_{ts}.md"
    crawl4ai_version = importlib.metadata.version("crawl4ai")
    patchright_version = importlib.metadata.version("patchright")

    lines = [
        f"# Headed Chromium (patchright) Launch Probe — {ts}",
        "",
        "Dev-only probe (macOS). All three launches use `try_scrape`'s exact BrowserConfig/adapter/"
        "strategy shape against a local throwaway page (never a third-party site). "
        f"`crawl4ai=={crawl4ai_version}`, `patchright=={patchright_version}`.",
        "",
    ]
    lines += _build_executable_section(run_a, run_b)
    lines += _build_backgrounding_flags_section(run_a, run_b)
    lines += _build_lsuielement_header(
        bundle_path, original_lsuielement, plist_end_state, plist_format_restored,
        codesign_before, codesign_after,
    )
    lines += _build_lsuielement_table(original_lsuielement, run_b, run_c)
    lines += _build_teardown_section(orphans)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _build_executable_section(run_a: dict, run_b: dict) -> list[str]:
    lines = [
        "## 1. Executable resolution",
        "",
        "| Run | headless | launch success | PID | executable |",
        "|-----|----------|-----------------|-----|------------|",
    ]
    for label, r in [("A", run_a), ("B", run_b)]:
        lines.append(f"| {label} | {r['headless']} | {r['launch_success']} | {r['pid']} | `{r['exe']}` |")
    hyp_a = "chromium_headless_shell-1228" in (run_a["exe"] or "") and "chrome-headless-shell" in (run_a["exe"] or "")
    hyp_b = "chromium-1228" in (run_b["exe"] or "") and "Google Chrome for Testing.app" in (run_b["exe"] or "")
    lines += [
        "",
        f"- Headless hypothesis (`chrome-headless-shell` under `chromium_headless_shell-1228`): "
        f"{'CONFIRMED' if hyp_a else 'NOT CONFIRMED'}",
        f"- Headed hypothesis (`Google Chrome for Testing.app` under `chromium-1228`): "
        f"{'CONFIRMED' if hyp_b else 'NOT CONFIRMED'}",
        f"- Run A error: {run_a['error_message'] or 'none'}",
        f"- Run B error: {run_b['error_message'] or 'none'}",
    ]
    return lines


def _build_backgrounding_flags_section(run_a: dict, run_b: dict) -> list[str]:
    lines = [
        "",
        "## 2. Backgrounding flags",
        "",
        "Attribution: **crawl4ai arg list** = present in the installed `browser_manager.py`'s "
        "`_build_browser_args()` unconditional output (read directly off the installed package "
        "this session). **driver-injected** = present on the real cmdline but NOT in that list — "
        "patchright/playwright's own internal default, not crawl4ai's doing.",
        "",
        "| Flag | headless (Run A) | headed (Run B) |",
        "|------|-------------------|------------------|",
    ]
    for flag in BACKGROUNDING_FLAGS:
        lines.append(f"| `{flag}` | {attribute_flag(flag, run_a['cmdline'])} | {attribute_flag(flag, run_b['cmdline'])} |")
    return lines


def _build_lsuielement_header(
    bundle_path: Path, original_lsuielement: bool | None, plist_end_state: bool | None,
    plist_format_restored: bool, codesign_before: dict, codesign_after: dict | None,
) -> list[str]:
    lines = [
        "",
        "## 3. LSUIElement viability",
        "",
        f"- Bundle: `{bundle_path}`",
        f"- Original `LSUIElement`: `{original_lsuielement}` (None = key absent, macOS default)",
        f"- End state (reverted): `{plist_end_state}`, byte-exact restore of original file: "
        f"{plist_format_restored} (`Info.plist` written back from a raw-bytes backup taken before "
        "any edit, not a plistlib round-trip — `plistlib.dump()` defaults to XML and would have "
        "silently converted the bundle's original binary (`bplist00`) plist to XML even on a "
        "content-correct revert; caught during this probe, fixed before this run)",
        f"- Codesign verify BEFORE edit: rc={codesign_before['verify_returncode']} — "
        f"{codesign_before['verify_stderr'] or 'ok'} (pre-existing on the untouched bundle, not "
        "caused by this probe)",
    ]
    if codesign_after is not None:
        lines.append(
            f"- Codesign verify AFTER `LSUIElement=true` edit: rc={codesign_after['verify_returncode']} — "
            f"{codesign_after['verify_stderr'] or 'ok'}"
        )
    return lines


def _build_lsuielement_table(original_lsuielement: bool | None, run_b: dict, run_c: dict | None) -> list[str]:
    lines = [
        "",
        "| Run | plist state | launch success | focus samples | chrome frontmost | % chrome frontmost | distinct apps seen |",
        "|-----|-------------|-----------------|----------------|-------------------|----------------------|----------------------|",
    ]
    lines.append(
        f"| B (no fix) | LSUIElement={original_lsuielement} | {run_b['launch_success']} | "
        f"{len(run_b['focus_samples'])} | {run_b['chrome_frontmost_count']} | "
        f"{pct(run_b['chrome_frontmost_count'], len(run_b['focus_samples']))} | "
        f"{sorted(set(run_b['focus_samples']))} |"
    )
    if run_c is not None:
        lines.append(
            f"| C (with fix) | LSUIElement=True | {run_c['launch_success']} | "
            f"{len(run_c['focus_samples'])} | {run_c['chrome_frontmost_count']} | "
            f"{pct(run_c['chrome_frontmost_count'], len(run_c['focus_samples']))} | "
            f"{sorted(set(run_c['focus_samples']))} |"
        )
        lines += [
            "",
            f"- Run C error: {run_c['error_message'] or 'none'}",
        ]
        if not run_c["launch_success"]:
            lines += [
                "",
                "**Verdict: NOT VIABLE as a direct lever on this bundle.** Reproduced 2x (this run "
                "plus one manual repro during investigation): `LSUIElement=true` on the chromium-1228 "
                "`Google Chrome for Testing.app` bundle reliably breaks the launch itself — "
                "`TargetClosedError`, browser log shows `icudtl.dat not found in bundle` / `Invalid "
                "file descriptor to ICU data received`. Isolated from the plist FORMAT (binary vs "
                "XML): a control launch against the identical bundle in XML format with the key "
                "ABSENT succeeded — the failure tracks the `LSUIElement` key specifically, not the "
                "file encoding. Differs from the Camoufox precedent (`process-docs/camoufox_lane/"
                "pipe_switch_and_no_focus_steal_2026-08-20.md`), where the same mechanism worked "
                "cleanly on `Camoufox.app`. Root cause not investigated further (out of scope for "
                "this probe) — plausibly this bundle's ICU-data resource lookup path depends on "
                "`NSApplicationActivationPolicy`/regular-app startup sequencing that `LSUIElement` "
                "changes. A future milestone needs a DIFFERENT no-focus-steal lever for this lane.",
            ]
    return lines


def _build_teardown_section(orphans: list[str]) -> list[str]:
    lines = [
        "",
        "## Teardown",
        "",
        f"Orphan processes/launchd jobs immediately after this script's own `check_orphans()` call: "
        f"{len(orphans)}.",
        "",
        "**Confirmed root cause (found during this probe's development, NOT fully bounded by the "
        "in-script sweep below — verify manually ~20s after this script exits, e.g. `pgrep -fl "
        '"ms-playwright/chromium"` + `launchctl list | grep chrome.for.testing`).** Run C\'s crash '
        "(`icudtl.dat not found in bundle`, SIGTRAP) makes macOS itself register a launchd per-app "
        "supervision job, `application.com.google.chrome.for.testing.<ids>` (`launchctl list`), "
        "which auto-relaunches the FULL browser (new PID: main process + crashpad + GPU/utility "
        "helpers) on a delay observed to range ~10-15s after process exit — outside what any bounded "
        "in-script sleep can reliably wait out. This is NOT the AsyncWebCrawler/Playwright "
        "context-manager's own teardown failing (Run A/B, which never crash, leave 0 orphans with no "
        "launchd job involved at all) — it is macOS's own crash-recovery, triggered specifically "
        "because Run C's launch crashes. `kill_survivors()` removes any matching launchd job every "
        "sweep round (`remove_stray_launchd_jobs()`) in addition to killing processes; `check_orphans"
        "()` reports residual launchd jobs too, not just processes. One-shot-per-crash, not a "
        "repeating loop (confirmed stable over a 90s undisturbed manual watch after cleanup).",
    ]
    if orphans:
        lines.append("")
        lines.extend(f"    {o}" for o in orphans)
    return lines


def attribute_flag(flag: str, cmdline: list[str] | None) -> str:
    present = bool(cmdline) and flag in cmdline
    if not present:
        return "absent"
    if flag in CRAWL4AI_UNCONDITIONAL_ARGS:
        return "present — crawl4ai arg list"
    return "present — driver-injected (not in crawl4ai's _build_browser_args output)"


def pct(count: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{round(100 * count / total)}%"
