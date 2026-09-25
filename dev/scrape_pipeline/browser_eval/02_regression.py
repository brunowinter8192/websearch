#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import difflib
from datetime import datetime
from pathlib import Path


# ORCHESTRATOR

def compare_all_baselines():
    baselines_dir = _compute_baselines_dir()

    if not baselines_dir.exists():
        print("No baselines directory found. Run run_baseline.py first.")
        return

    domain_dirs = _compute_domain_dirs(baselines_dir)

    if not domain_dirs:
        print("No domain baselines found. Run run_baseline.py first.")
        return

    _print_top_rule()
    print("BASELINE COMPARISON REPORT")
    _print_header_rule()


    all_results = _compare_domains(domain_dirs)

    save_comparison_report(all_results)

    _print_bottom_rule(all_results)


# FUNCTIONS

def _compute_baselines_dir():
    baselines_dir = Path(__file__).parent / "01_baselines"
    return baselines_dir


def _compute_domain_dirs(baselines_dir):
    domain_dirs = [d for d in baselines_dir.iterdir() if d.is_dir()]
    return domain_dirs


def _print_top_rule():
    print("=" * 80)


def _print_header_rule():
    print("=" * 80)


def _compare_domains(domain_dirs):
    all_results = []
    for domain_dir in sorted(domain_dirs):
        result = compare_domain_iterations(domain_dir)
        if result:
            all_results.append(result)
    return all_results


def save_comparison_report(results: list[dict]) -> None:
    reports_dir = Path(__file__).parent / "md"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"02_diff_report_{timestamp}.txt"

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("SCRAPING SUITE COMPARISON REPORT\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")

        for result in results:
            write_domain_result(f, result)

    print(f"\nReport saved: {report_file}")


def _print_bottom_rule(all_results):
    print("\n" + "=" * 80)
    print(f"Comparison completed: {len(all_results)} domains analyzed")


def compare_domain_iterations(domain_dir: Path) -> dict | None:
    metadata_files = sorted(domain_dir.glob("metadata_*.json"))

    if len(metadata_files) < 2:
        print(f"\n{domain_dir.name}: Only {len(metadata_files)} iteration(s) found, need at least 2")
        return None

    latest = metadata_files[-1]
    previous = metadata_files[-2]

    latest_meta = load_metadata(latest)
    previous_meta = load_metadata(previous)

    print(f"\n{domain_dir.name}:")
    print(f"  Comparing iteration {previous_meta['iteration']} vs {latest_meta['iteration']}")

    char_diff = latest_meta['char_count'] - previous_meta['char_count']
    word_diff = latest_meta['word_count'] - previous_meta['word_count']

    char_percent = (char_diff / previous_meta['char_count'] * 100) if previous_meta['char_count'] > 0 else 0
    word_percent = (word_diff / previous_meta['word_count'] * 100) if previous_meta['word_count'] > 0 else 0

    print(f"  Characters: {previous_meta['char_count']} -> {latest_meta['char_count']} ({char_diff:+d}, {char_percent:+.1f}%)")
    print(f"  Words: {previous_meta['word_count']} -> {latest_meta['word_count']} ({word_diff:+d}, {word_percent:+.1f}%)")

    status = determine_status(char_percent, word_percent)
    print(f"  Status: {status}")

    content_diff = None

    if char_diff != 0 or word_diff != 0:
        content_diff = generate_content_diff(domain_dir, previous_meta['iteration'], latest_meta['iteration'])
        print(f"  Content changed - see diff report")

    return {
        "domain": domain_dir.name,
        "previous_iteration": previous_meta['iteration'],
        "latest_iteration": latest_meta['iteration'],
        "previous_chars": previous_meta['char_count'],
        "latest_chars": latest_meta['char_count'],
        "char_diff": char_diff,
        "char_percent": char_percent,
        "previous_words": previous_meta['word_count'],
        "latest_words": latest_meta['word_count'],
        "word_diff": word_diff,
        "word_percent": word_percent,
        "status": status,
        "content_diff": content_diff
    }


def write_domain_result(f, result: dict) -> None:
    f.write(f"\nDOMAIN: {result['domain']}\n")
    f.write("-" * 80 + "\n")
    f.write(f"Iterations: {result['previous_iteration']} -> {result['latest_iteration']}\n")
    f.write(f"Characters: {result['previous_chars']} -> {result['latest_chars']} ({result['char_diff']:+d}, {result['char_percent']:+.1f}%)\n")
    f.write(f"Words: {result['previous_words']} -> {result['latest_words']} ({result['word_diff']:+d}, {result['word_percent']:+.1f}%)\n")
    f.write(f"Status: {result['status']}\n")

    if result['content_diff']:
        f.write("\nCONTENT DIFF:\n")
        f.write(result['content_diff'])
        f.write("\n")

    f.write("\n" + "=" * 80 + "\n")


def load_metadata(metadata_file: Path) -> dict:
    with open(metadata_file, 'r') as f:
        return json.load(f)


def determine_status(char_percent: float, word_percent: float) -> str:
    max_change = max(abs(char_percent), abs(word_percent))

    if max_change == 0:
        return "IDENTICAL"
    elif max_change < 5:
        return "MINOR_CHANGE"
    elif max_change < 20:
        return "MODERATE_CHANGE"
    else:
        return "MAJOR_CHANGE"


def generate_content_diff(domain_dir: Path, prev_iter: int, latest_iter: int) -> str:
    prev_content_file = domain_dir / f"iteration_{prev_iter:03d}.md"
    latest_content_file = domain_dir / f"iteration_{latest_iter:03d}.md"

    with open(prev_content_file, 'r', encoding='utf-8') as f:
        prev_lines = f.readlines()

    with open(latest_content_file, 'r', encoding='utf-8') as f:
        latest_lines = f.readlines()

    diff = difflib.unified_diff(
        prev_lines,
        latest_lines,
        fromfile=f"iteration_{prev_iter:03d}.md",
        tofile=f"iteration_{latest_iter:03d}.md",
        lineterm=''
    )

    return '\n'.join(diff)


if __name__ == "__main__":
    compare_all_baselines()
