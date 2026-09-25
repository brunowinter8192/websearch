# INFRASTRUCTURE
import random
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

RANDOM_SEED = 42
DOI_SAMPLE_SIZE = 300

TIER1_DOMAINS = frozenset({"arxiv.org", "aclanthology.org", "openreview.net", "pmc.ncbi.nlm.nih.gov"})
TIER2_DOMAINS = frozenset({"openalex.org", "semanticscholar.org"})
TIER3_DOMAINS = frozenset({"doi.org"})
TIER4_DOMAINS = frozenset({
    "dl.acm.org", "link.springer.com", "ieeexplore.ieee.org", "jstor.org",
    "books.google.com", "sciencedirect.com", "muse.jhu.edu", "mdpi.com",
    "onlinelibrary.wiley.com", "nature.com", "springer.com", "tandfonline.com",
    "researchgate.net", "direct.mit.edu", "biorxiv.org", "medrxiv.org",
    "ssrn.com", "cambridge.org", "oup.com", "acm.org", "worldscientific.com",
    "frontiersin.org", "plos.org", "hindawi.com", "thieme-connect.com",
    "search.proquest.com", "scribd.com", "spiedigitallibrary.org",
    "elib.uni-stuttgart.de", "cyberleninka.ru", "inspirehep.net",
    "search.ebscohost.com",
})


# FUNCTIONS

def _latest_report(glob_pattern: str, report_dir: Path) -> Path:
    candidates = sorted(report_dir.glob(glob_pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No report matching {glob_pattern} in {report_dir}")
    return candidates[0]


def _extract_pool(smoke_path: Path, free_path: Path) -> set[str]:
    smoke_text = smoke_path.read_text(encoding="utf-8")
    free_text = free_path.read_text(encoding="utf-8")

    urls: set[str] = set()

    for line in smoke_text.splitlines():
        m = re.match(r"\s*URL:\s+(https?://\S+)", line)
        if m:
            urls.add(m.group(1).rstrip(".,)"))

    for m in re.finditer(r"\| \d+ \| \S+ \| \d+ \| (https?://\S+?) \|", free_text):
        urls.add(m.group(1))

    return {u for u in urls if _has_real_path(u)}


def _filter_and_tier(all_urls: set[str]) -> list[tuple[str, str]]:
    tiered = [(u, t) for u in all_urls if (t := _url_tier(u)) is not None]
    tiered.sort(key=lambda x: (_base_domain(x[0]), x[0]))
    return tiered


def _apply_doi_sampling(tier_pool: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], list[str]]:
    doi_urls = [u for u, t in tier_pool if t == "T3"]
    non_doi = [(u, t) for u, t in tier_pool if t != "T3"]

    rng = random.Random(RANDOM_SEED)
    doi_sample = sorted(rng.sample(doi_urls, min(DOI_SAMPLE_SIZE, len(doi_urls))))
    sampled = non_doi + [(u, "T3") for u in doi_sample]
    sampled.sort(key=lambda x: (_base_domain(x[0]), x[0]))
    return sampled, doi_sample


def _write_pool_files(sampled_pool: list[tuple[str, str]], doi_sample: list[str], ts: str, data_dir: Path) -> None:
    pool_path = data_dir / f"pool_{ts}.txt"
    pool_path.write_text("\n".join(u for u, _ in sampled_pool) + "\n", encoding="utf-8")
    print(f"[pool] written: {pool_path.name}", file=sys.stderr)

    doi_path = data_dir / f"pool_doi_sample_{ts}.txt"
    doi_path.write_text("\n".join(doi_sample) + "\n", encoding="utf-8")
    print(f"[pool] written: {doi_path.name}", file=sys.stderr)


def _has_real_path(url: str) -> bool:
    path = urlparse(url).path
    return bool(path) and path != "/"


def _url_tier(url: str) -> str | None:
    d = _base_domain(url)
    if d in TIER1_DOMAINS or any(d.endswith("." + t) for t in TIER1_DOMAINS):
        return "T1"
    if d in TIER2_DOMAINS or any(d.endswith("." + t) for t in TIER2_DOMAINS):
        return "T2"
    if d in TIER3_DOMAINS or any(d.endswith("." + t) for t in TIER3_DOMAINS):
        return "T3"
    if d in TIER4_DOMAINS or any(d.endswith("." + t) for t in TIER4_DOMAINS):
        return "T4"
    return None


def _base_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc
