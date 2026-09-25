# INFRASTRUCTURE
from datetime import datetime, timezone
from pathlib import Path


# FUNCTIONS

def write_report(
    path: Path,
    batches: list[dict],
    oldest_date: str,
    final_btn_state: str,
    click_nets: dict,
    har_path: Path,
) -> None:
    lines: list[str] = []
    lines += _render_header(har_path)
    lines += _render_trajectory_table(batches)
    lines += _render_final_summary(batches, oldest_date, final_btn_state)
    lines += _render_network_candidates(click_nets)
    lines += _render_click_diff(click_nets)

    lines.append(f"\n## HAR\n\n`{har_path}`")
    lines.append("\nFull network session including response bodies captured above.")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_depth_report(
    path: Path,
    max_unique: int,
    oldest_date: str,
    stop_reason: str,
    final_btn_state: str,
    milestone_rows: list[str],
    coindesk_log: list[dict],
    any_content_fetch: bool,
) -> None:
    lines: list[str] = []
    lines.append("# CoinDesk Pagination Depth Report — Ceiling Probe")
    lines.append(f"\n**Run:** {datetime.now(timezone.utc).isoformat()}\n")

    lines.append("## Result\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Max unique feed URLs | **{max_unique}** |")
    lines.append(f"| Oldest date reached | **{oldest_date}** |")
    lines.append(f"| Stop reason | **{stop_reason}** |")
    lines.append(f"| Button end-state | {final_btn_state} |")
    lines.append(f"| CoinDesk content fetch fired | {'YES — see log below' if any_content_fetch else 'NO — pure client-side'} |\n")

    lines.append("## Milestone Progress (every 10 clicks + first 5)\n")
    lines.append("```")
    lines.extend(milestone_rows)
    lines.append("```\n")

    lines.append("## CoinDesk Network Log (non-static, non-metrics)\n")
    filtered = [e for e in coindesk_log
                if "metrics.coindesk.com" not in e["url"]
                and "downloads.coindesk.com" not in e["url"]]
    if filtered:
        lines.append("| Method | URL | Status |")
        lines.append("|--------|-----|--------|")
        seen_urls: set[str] = set()
        for e in filtered:
            url_short = e["url"][:120] + ("…" if len(e["url"]) > 120 else "")
            if url_short not in seen_urls:
                seen_urls.add(url_short)
                lines.append(f"| {e['method']} | `{url_short}` | {e['status']} |")
    else:
        lines.append("_(none — all coindesk.com traffic was metrics or static assets)_")

    path.write_text("\n".join(lines), encoding="utf-8")


def _render_header(har_path: Path) -> list:
    lines: list[str] = []
    lines.append("# CoinDesk Pagination Probe — Findings Report")
    lines.append(f"\n**Run:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**HAR:** `{har_path}`\n")
    return lines


def _render_trajectory_table(batches: list) -> list:
    lines = ["## Per-Click Trajectory\n"]
    lines.append("| Click# | Cumulative Unique | New This Click | Oldest Date | Button State |")
    lines.append("|--------|------------------|----------------|-------------|--------------|")
    for row in batches:
        lines.append(
            f"| {row['click_n']} | {row['cumulative_unique']} | {row['new_this_click']} "
            f"| {row['oldest_date']} | {row['btn_state']} |"
        )
    return lines


def _render_final_summary(batches: list, oldest_date: str, final_btn_state: str) -> list:
    lines = [f"\n**Final total unique URLs:** {batches[-1]['cumulative_unique']}"]
    lines.append(f"**Oldest date reached:** {oldest_date}")
    lines.append(f"**Button end-state:** {final_btn_state}\n")
    return lines


def _render_network_candidates(click_nets: dict) -> list:
    lines = ["## Network Candidates (non-static, per click)\n"]
    for cn in sorted(click_nets.keys()):
        entries = click_nets[cn]
        label = "Initial page load" if cn == 0 else f"Click {cn}"
        lines.append(f"### {label} ({len(entries)} candidates)\n")
        for e in entries:
            lines.append(f"**{e['method']} {e['url']}**")
            lines.append(f"- Status: {e['status']}")
            if e["next_action"]:
                lines.append(f"- `Next-Action`: `{e['next_action']}`")
            if e["has_rsc"]:
                lines.append("- Contains `_rsc` query parameter: YES")
            if e["post_data"]:
                pd = e["post_data"]
                if len(pd) > 600:
                    pd = pd[:600] + "…"
                lines.append(f"- POST body: `{pd}`")
            lines.append("")
    return lines


def _render_click_diff(click_nets: dict) -> list:
    lines = ["## Click-1 vs Click-2 Request Diff\n"]
    lines.append("*(What changes between the first and second pagination calls — reveals the cursor/offset parameter)*\n")
    c1_entries = click_nets.get(1, [])
    c2_entries = click_nets.get(2, [])

    if not c1_entries and not c2_entries:
        lines.append("No candidates captured for clicks 1 or 2.\n")
        return lines

    c1_posts = [e for e in c1_entries if e["method"] == "POST" or e["has_rsc"]]
    c2_posts = [e for e in c2_entries if e["method"] == "POST" or e["has_rsc"]]

    lines.extend(_render_click_posts("Click 1", c1_posts))
    lines.extend(_render_click_posts("Click 2", c2_posts))

    c1_urls = [e["url"] for e in c1_posts]
    c2_urls = [e["url"] for e in c2_posts]
    lines.extend(_render_shared_base_diff(c1_urls, c2_urls))

    return lines


def _render_click_posts(label: str, posts: list) -> list:
    lines = [f"**{label} — POST / _rsc candidates ({len(posts)}):**"]
    for e in posts:
        lines.append(f"- `{e['method']} {e['url']}`")
        if e["next_action"]:
            lines.append(f"  - Next-Action: `{e['next_action']}`")
        if e["post_data"]:
            pd = e["post_data"]
            if len(pd) > 400:
                pd = pd[:400] + "…"
            lines.append(f"  - POST body: `{pd}`")
    lines.append("")
    return lines


def _render_shared_base_diff(c1_urls: list, c2_urls: list) -> list:
    shared_bases: list[str] = []
    for u1 in c1_urls:
        base1 = u1.split("?")[0]
        for u2 in c2_urls:
            if u2.split("?")[0] == base1 and base1 not in shared_bases:
                shared_bases.append(base1)

    if not shared_bases:
        return [
            "No shared base URLs between click-1 and click-2 POST/_rsc candidates — "
            "pagination may use POST body parameters (see body diff above) rather than query strings."
        ]

    lines = ["**Shared base URLs — query string diff reveals pagination param:**"]
    for base in shared_bases:
        u1_match = next((u for u in c1_urls if u.split("?")[0] == base), None)
        u2_match = next((u for u in c2_urls if u.split("?")[0] == base), None)
        q1 = ("?" + u1_match.split("?")[1]) if u1_match and "?" in u1_match else "(none)"
        q2 = ("?" + u2_match.split("?")[1]) if u2_match and "?" in u2_match else "(none)"
        lines.append(f"- Base: `{base}`")
        lines.append(f"  - Click 1 query: `{q1}`")
        lines.append(f"  - Click 2 query: `{q2}`")
    return lines
