# INFRASTRUCTURE

import math
from pathlib import Path


# FUNCTIONS

def _write_cumulative_plot(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    xs = stats["ok_completion_s"]
    x  = [0.0] + xs if xs else [0.0]
    y  = list(range(len(x)))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.step(x, y, where="post", linewidth=1.5)
    ax.set_xlabel("Elapsed (s)")
    ax.set_ylabel("Cumulative OK fetches")
    ax.set_title("Cumulative OK fetches over time")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(job_dir / "cumulative.png", dpi=100)
    plt.close(fig)


def _write_load_hist(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    load_times     = stats["load_times"]
    page_timeout_s = stats["page_timeout_s"]

    upper  = math.ceil(max(load_times) / 0.25) * 0.25
    n_bins = max(1, math.ceil(upper / 0.25))
    bins   = [i * 0.25 for i in range(n_bins + 1)]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(load_times, bins=bins, edgecolor="white", linewidth=0.5)
    ax.axvline(page_timeout_s, color="red", linewidth=1.2,
               label=f"page_timeout {page_timeout_s:.1f} s")
    ax.legend(fontsize=9)
    ax.set_xlim(0, upper)
    ax.set_xlabel("Load time (s)  [elapsed − DELAY_BEFORE_HTML 0.5 s]")
    ax.set_ylabel("OK fetches")
    ax.set_title("Success load-time distribution")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(job_dir / "success_load_hist.png", dpi=100)
    plt.close(fig)


def _write_cf_hist(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    cf_times       = stats["cf_times"]
    page_timeout_s = stats["page_timeout_s"]

    upper  = math.ceil(max(cf_times) / 0.25) * 0.25
    n_bins = max(1, math.ceil(upper / 0.25))
    bins   = [i * 0.25 for i in range(n_bins + 1)]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(cf_times, bins=bins, edgecolor="white", linewidth=0.5)
    ax.axvline(page_timeout_s, color="red", linewidth=1.2,
               label=f"page_timeout {page_timeout_s:.1f} s")
    ax.legend(fontsize=9)
    ax.set_xlim(0, upper)
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Connect-fail fetches")
    ax.set_title("Connect-fail elapsed distribution")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(job_dir / "connect_fail_hist.png", dpi=100)
    plt.close(fig)
