# INFRASTRUCTURE
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


def _write_ride_length_plot(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    lengths = stats["ride_lengths"]
    fig, ax = plt.subplots(figsize=(8, 4))
    if lengths:
        bins = list(range(0, max(lengths) + 2))
        ax.hist(lengths, bins=bins, edgecolor="black", alpha=0.8)
    ax.set_xlabel("URLs attempted per proxy ride")
    ax.set_ylabel("Number of rides")
    ax.set_title("Proxy ride length distribution")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(job_dir / "ride_lengths.png", dpi=100)
    plt.close(fig)


def _write_regwall_position_plot(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    rwp = stats["regwall_rate_by_pos"]
    fig, ax = plt.subplots(figsize=(8, 4))
    if rwp:
        positions = sorted(rwp.keys())
        rates     = [rwp[p] * 100 for p in positions]
        ax.bar(positions, rates, edgecolor="black", alpha=0.8)
    ax.set_xlabel("Ride position (URL index within proxy)")
    ax.set_ylabel("Regwall rate (%)")
    ax.set_title("Regwall rate vs ride position")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(job_dir / "regwall_position.png", dpi=100)
    plt.close(fig)
