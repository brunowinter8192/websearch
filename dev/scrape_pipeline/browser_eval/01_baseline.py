#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.scraper.chromium_scrape import scrape_url_chromium_workflow


# ORCHESTRATOR

async def run_baseline_suite():
    domains = load_domains()
    _print_loaded_test_domains(domains)

    await _run_domain_baselines(domains)

    _print_line(domains)


# FUNCTIONS

def load_domains() -> list[str]:
    domains_file = Path(__file__).parent.parent / "domains.txt"
    domains = []

    with open(domains_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                domains.append(line)

    return domains


def _print_loaded_test_domains(domains):
    print(f"Loaded {len(domains)} test domains")
    print("=" * 80)


async def _run_domain_baselines(domains):
    for url in domains:
        await process_single_domain(url)


def _print_line(domains):
    print("=" * 80)
    print(f"Baseline suite completed: {len(domains)} domains processed")


async def process_single_domain(url: str) -> None:
    domain_name = extract_domain_name(url)
    print(f"\nProcessing: {domain_name}")
    print(f"URL: {url}")

    response = await scrape_url_chromium_workflow(url)

    if isinstance(response, list) and len(response) > 0:
        content = response[0].text
        if content.startswith("Error"):
            print(f"Failed: {content}")
        else:
            save_baseline(domain_name, url, content)
            print(f"Success: Saved iteration for {domain_name}")
    else:
        print(f"Failed: Unexpected response format")


def extract_domain_name(url: str) -> str:
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]

    if 'wikipedia.org' in parsed.netloc:
        return f"wikipedia_{path_parts[-1]}" if path_parts else "wikipedia"
    elif 'searxng.org' in parsed.netloc:
        return "searxng_docs"
    elif 'scikit-learn.org' in parsed.netloc:
        return "sklearn_docs"
    elif 'medium.com' in parsed.netloc:
        return "medium_article"
    elif 'trychroma.com' in parsed.netloc:
        return "chroma_docs"
    elif 'binance.com' in parsed.netloc:
        return "binance_docs"
    else:
        return parsed.netloc.replace('.', '_')


def save_baseline(domain_name: str, url: str, content: str) -> None:
    baselines_dir = Path(__file__).parent / "01_baselines" / domain_name
    baselines_dir.mkdir(parents=True, exist_ok=True)

    iteration_number = get_next_iteration(baselines_dir)

    content_file = baselines_dir / f"iteration_{iteration_number:03d}.md"
    metadata_file = baselines_dir / f"metadata_{iteration_number:03d}.json"

    with open(content_file, 'w', encoding='utf-8') as f:
        f.write(content)

    metadata = create_metadata(url, content, iteration_number)

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"  - Saved: {content_file.name}")
    print(f"  - Characters: {metadata['char_count']}")
    print(f"  - Words: {metadata['word_count']}")


def get_next_iteration(baselines_dir: Path) -> int:
    existing_iterations = list(baselines_dir.glob("iteration_*.md"))

    if not existing_iterations:
        return 1

    iteration_numbers = [
        int(f.stem.split('_')[1])
        for f in existing_iterations
    ]

    return max(iteration_numbers) + 1


def create_metadata(url: str, content: str, iteration_number: int) -> dict:
    return {
        "iteration": iteration_number,
        "timestamp": datetime.now().isoformat(),
        "url": url,
        "char_count": len(content),
        "word_count": len(content.split())
    }


if __name__ == "__main__":
    asyncio.run(run_baseline_suite())
