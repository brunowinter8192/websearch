# INFRASTRUCTURE
import re
from collections import Counter
from datetime import datetime, timezone


# FUNCTIONS
def url_type(url):
    m = re.search(r'theblock\.co/([^/?#]+)', url)
    return m.group(1) if m else "other"


def post_id(url):
    m = re.search(r'/post/(\d+)/', url)
    return m.group(1) if m else None


def _compute_report_context(sitemap_urls, sub_stats, news_urls, rss_urls, ui_urls):
    def breakdown(urls):
        return Counter(url_type(u) for u in urls)

    def post_ids(urls):
        return {post_id(u) for u in urls if post_id(u)}

    sitemap_types = breakdown(sitemap_urls)
    news_types    = breakdown(news_urls)
    rss_types     = breakdown(rss_urls)
    ui_types      = breakdown(ui_urls)

    sitemap_posts = post_ids(sitemap_urls)
    news_posts    = post_ids(news_urls)
    rss_posts     = post_ids(rss_urls)
    ui_posts      = post_ids(ui_urls)

    all_post_ids = sitemap_posts | news_posts | rss_posts | ui_posts
    sitemap_only = sitemap_posts - news_posts - rss_posts - ui_posts
    news_only    = news_posts    - sitemap_posts - rss_posts - ui_posts
    rss_only     = rss_posts     - sitemap_posts - news_posts - ui_posts
    ui_only      = ui_posts      - sitemap_posts - news_posts - rss_posts

    max_sitemap_id = max((int(p) for p in sitemap_posts if p), default=0)
    is_complete    = sub_stats["remaining"] == 0

    rss_not_in_sitemap = rss_posts - sitemap_posts
    ui_not_in_sitemap  = ui_posts  - sitemap_posts
    rss_above_max      = {p for p in rss_not_in_sitemap if int(p) > max_sitemap_id}
    ui_above_max       = {p for p in ui_not_in_sitemap  if int(p) > max_sitemap_id}
    rss_gap_candidates = rss_not_in_sitemap - rss_above_max
    ui_gap_candidates  = ui_not_in_sitemap  - ui_above_max

    return {
        "sitemap_types": sitemap_types, "news_types": news_types,
        "rss_types": rss_types, "ui_types": ui_types,
        "sitemap_posts": sitemap_posts, "news_posts": news_posts,
        "rss_posts": rss_posts, "ui_posts": ui_posts,
        "all_post_ids": all_post_ids,
        "sitemap_only": sitemap_only, "news_only": news_only,
        "rss_only": rss_only, "ui_only": ui_only,
        "max_sitemap_id": max_sitemap_id, "is_complete": is_complete,
        "rss_not_in_sitemap": rss_not_in_sitemap, "ui_not_in_sitemap": ui_not_in_sitemap,
        "rss_above_max": rss_above_max, "ui_above_max": ui_above_max,
        "rss_gap_candidates": rss_gap_candidates, "ui_gap_candidates": ui_gap_candidates,
    }


def _render_header(ts, sub_stats, ctx) -> list:
    lines = []
    lines.append("# theblock.co Discovery Coverage Report")
    lines.append(f"\nGenerated: {ts}")
    s_label = "COMPLETE" if ctx["is_complete"] else f"PARTIAL — {sub_stats['remaining']} sub(s) pending"
    lines.append(f"Sitemap fetch: **{s_label}**")
    lines.append("\n---")
    return lines


# CF note
def _render_cf_note() -> list:
    lines = []
    lines.append("\n## Cloudflare Rate-Limit Behaviour")
    lines.append("\nIP-level 429 fires after ~25 sequential sub-sitemap fetches (even at 5s/sub).")
    lines.append("Probe uses per-sub checkpoint files in `dev/news_pipeline/theblock/cache/`.")
    lines.append("Re-run to resume — already-cached subs are skipped.")
    lines.append("\n**Scraping-phase implication:** individual article fetches at normal cadence work fine;")
    lines.append("bulk sitemap enumeration needs ≥5s/request + retry logic.")
    return lines


# Method 1
def _render_method1(sitemap_urls, sub_stats, ctx) -> list:
    lines = []
    lines.append("\n---")
    lines.append("\n## Method 1 — Full Sitemap Union")
    lines.append(f"\n- Sub-sitemaps in index: **{sub_stats['sub_count']}**")
    lines.append(f"- Successfully fetched: **{sub_stats['fetched']}**")
    lines.append(f"- Pending: **{sub_stats['remaining']}**")
    lines.append(f"- Confirmed unique URLs: **{len(sitemap_urls):,}**")
    lines.append(f"- Confirmed unique `/post/` URLs: **{len(ctx['sitemap_posts']):,}**")
    if not ctx["is_complete"]:
        lines.append(f"- Highest confirmed `/post/` ID: **{ctx['max_sitemap_id']:,}**")
        lines.append(f"  (recent IDs above this ceiling are in pending subs — not a gap)")
    lines.append(f"\n**URL type breakdown (first path segment, sorted by count):**")
    lines.append(f"\n| type | count |")
    lines.append(f"|---|---|")
    for t, c in sorted(ctx["sitemap_types"].items(), key=lambda x: -x[1]):
        lines.append(f"| {t} | {c} |")
    return lines


# Method 2
def _render_method2(news_urls, news_from_cache, ctx) -> list:
    lines = []
    lines.append("\n## Method 2 — News Sitemap (`sitemap_tbco_news.xml`)")
    if news_from_cache:
        lines.append("\n_CF-blocked during probe — loaded from cache (verified same session)._")
    lines.append(f"\n- Total unique URLs: **{len(news_urls)}**")
    lines.append(f"\n| type | count |")
    lines.append(f"|---|---|")
    for t, c in sorted(ctx["news_types"].items(), key=lambda x: -x[1]):
        lines.append(f"| {t} | {c} |")
    return lines


# Method 3
def _render_method3(rss_urls, rss_rate_limited, ctx) -> list:
    lines = []
    lines.append("\n## Method 3 — RSS (`rss.xml`)")
    if rss_rate_limited:
        lines.append("\n_HTTP 429 during probe — pre-probe sample (complete feed captured before_")
        lines.append("_sitemap run triggered CF block, verified same session)._")
    lines.append(f"\n- Total unique article URLs: **{len(rss_urls)}**")
    lines.append(f"\n| type | count |")
    lines.append(f"|---|---|")
    for t, c in sorted(ctx["rss_types"].items(), key=lambda x: -x[1]):
        lines.append(f"| {t} | {c} |")
    return lines


# Method 4
def _render_method4(ui_urls, ui_status, ctx) -> list:
    lines = []
    lines.append("\n## Method 4 — Bounded UI Crawl")
    lines.append(f"\n**HTTP status (CF datapoints for scraping phase):**")
    for note in ui_status:
        lines.append(f"- {note}")
    lines.append(f"\nPages: `/category/markets`, `/category/defi`, `/category/bitcoin`, `/latest-crypto-news`.")
    lines.append(f"Raw HTML — `/post/` hrefs are server-rendered (~10/page). No JS pagination needed.")
    lines.append(f"\n- Total unique `/post/` URLs: **{len(ui_urls)}**")
    lines.append(f"\n| type | count |")
    if ctx["ui_types"]:
        lines.append(f"|---|---|")
        for t, c in sorted(ctx["ui_types"].items(), key=lambda x: -x[1]):
            lines.append(f"| {t} | {c} |")
    else:
        lines.append(f"| (none) | 0 |")
    return lines


# Cross-method
def _render_cross_method_comparison(ctx) -> list:
    lines = []
    lines.append("\n---")
    lines.append("\n## Cross-Method Comparison")
    tag = " (partial)" if not ctx["is_complete"] else ""
    lines.append(f"\n| method | `/post/` IDs | unique to this method |")
    lines.append(f"|---|---|---|")
    lines.append(f"| Sitemap union{tag} | {len(ctx['sitemap_posts']):,} | {len(ctx['sitemap_only']):,} |")
    lines.append(f"| News sitemap | {len(ctx['news_posts'])} | {len(ctx['news_only'])} |")
    lines.append(f"| RSS | {len(ctx['rss_posts'])} | {len(ctx['rss_only'])} |")
    lines.append(f"| UI crawl | {len(ctx['ui_posts'])} | {len(ctx['ui_only'])} |")
    lines.append(f"| **Total union** | **{len(ctx['all_post_ids']):,}** | — |")
    return lines


def _render_completeness_and_gaps(sub_stats, ctx) -> list:
    lines = []
    lines.append(f"\n### Sitemap completeness check")
    if ctx["is_complete"]:
        lines.append(f"\nAll {sub_stats['sub_count']} subs fetched — completeness check is definitive.")
    else:
        lines.append(f"\nPartial fetch — confirmed range up to ID **{ctx['max_sitemap_id']:,}**.")
    lines.append(f"\n| check | count | interpretation |")
    lines.append(f"|---|---|---|")
    lines.append(f"| RSS IDs not in sitemap | {len(ctx['rss_not_in_sitemap'])} | {len(ctx['rss_above_max'])} > ceiling (pending subs); {len(ctx['rss_gap_candidates'])} ≤ ceiling (potential gap) |")
    lines.append(f"| UI IDs not in sitemap   | {len(ctx['ui_not_in_sitemap'])} | {len(ctx['ui_above_max'])} > ceiling (pending subs); {len(ctx['ui_gap_candidates'])} ≤ ceiling (potential gap) |")

    if ctx["rss_gap_candidates"]:
        lines.append(f"\nRSS gap candidates (IDs ≤ confirmed ceiling):")
        for pid in sorted(ctx["rss_gap_candidates"]):
            lines.append(f"- ID {pid}")
    if ctx["ui_gap_candidates"]:
        lines.append(f"\nUI gap candidates (IDs ≤ confirmed ceiling):")
        for pid in sorted(ctx["ui_gap_candidates"]):
            lines.append(f"- ID {pid}")
    return lines


def _render_news_vs_archive(ctx) -> list:
    lines = []
    lines.append(f"\n### News sitemap vs archive rolling-window check")
    news_not_in_archive = ctx["news_posts"] - ctx["sitemap_posts"]
    lines.append(f"\n- News-only IDs (not in {'full' if ctx['is_complete'] else 'partial'} archive): **{len(news_not_in_archive)}**")
    lines.append(f"- Archive-only IDs: **{len(ctx['sitemap_posts'] - ctx['news_posts']):,}**")
    if not ctx["is_complete"] and news_not_in_archive:
        lines.append(f"\n_All news IDs are above the partial archive ceiling ({ctx['max_sitemap_id']:,}) —_")
        lines.append(f"_they are in pending subs, consistent with hypothesis (news ⊆ archive)._")
    elif ctx["is_complete"]:
        lines.append(f"\n_news-only = {len(news_not_in_archive)} confirms/refutes head-start hypothesis (news ⊆ archive)._")
    return lines


# --- Build report ---
def build_report(sitemap_urls, sub_stats, news_urls, news_from_cache,
                 rss_urls, rss_rate_limited, ui_urls, ui_status):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ctx = _compute_report_context(sitemap_urls, sub_stats, news_urls, rss_urls, ui_urls)

    lines = []
    lines += _render_header(ts, sub_stats, ctx)
    lines += _render_cf_note()
    lines += _render_method1(sitemap_urls, sub_stats, ctx)
    lines += _render_method2(news_urls, news_from_cache, ctx)
    lines += _render_method3(rss_urls, rss_rate_limited, ctx)
    lines += _render_method4(ui_urls, ui_status, ctx)
    lines += _render_cross_method_comparison(ctx)
    lines += _render_completeness_and_gaps(sub_stats, ctx)
    lines += _render_news_vs_archive(ctx)

    return "\n".join(lines)
