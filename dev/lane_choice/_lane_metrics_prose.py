# INFRASTRUCTURE
import statistics
from pathlib import Path

from _lane_metrics_blocks import read_blocks
from _lane_metrics_classify import apply_heading_rule, classify_blocks

# The PROSE length cap is this percentile of the corpus's own chromium block-word-count
# distribution (see process-docs/lane_choice/ for the measured distribution and the reasoning for
# picking a percentile at all) — chromium output is post-PruningContentFilter, the best available
# proxy in this project for what a real prose block looks like.
PROSE_PERCENTILE = 99


# FUNCTIONS

# Derive the PROSE cap (PROSE_PERCENTILE of the pooled chromium block-word-count distribution)
# plus the distribution itself, for the report
def compute_prose_cap(chromium_block_lists: list[list[dict]]) -> tuple[int, dict]:
    word_counts = sorted(b["num_words"] for blocks in chromium_block_lists for b in blocks)
    quantiles = statistics.quantiles(word_counts, n=100, method="inclusive")
    cap = round(quantiles[PROSE_PERCENTILE - 1])
    distribution = {
        "n": len(word_counts),
        "median": statistics.median(word_counts),
        "p50": quantiles[49],
        "p75": quantiles[74],
        "p90": quantiles[89],
        "p95": quantiles[94],
        "p99": quantiles[98],
        "max": word_counts[-1],
    }
    return cap, distribution


# CONTENT, at or under the corpus-derived length cap, and containing a sentence-ending mark
def is_prose_block(classification: str, block: dict, cap: int) -> bool:
    return classification == "CONTENT" and block["num_words"] <= cap and block["has_sentence_end"]


# blocks_total/content, words_total/content(+pct), overall link density, longest content block,
# PROSE blocks/words, and blocks/words the cap excludes (CONTENT + sentence-ending, over cap)
def aggregate_file_metrics(blocks: list[dict], classifications: list[str], cap: int) -> dict:
    blocks_total = len(blocks)
    blocks_content = sum(1 for c in classifications if c == "CONTENT")
    words_total = sum(b["num_words"] for b in blocks)
    words_content = sum(b["num_words"] for b, c in zip(blocks, classifications) if c == "CONTENT")
    link_tokens_total = sum(b["link_tokens"] for b in blocks)
    link_density_overall = link_tokens_total / words_total if words_total else 0.0
    words_content_pct = (words_content / words_total * 100) if words_total else 0.0
    content_word_counts = [b["num_words"] for b, c in zip(blocks, classifications) if c == "CONTENT"]
    longest_content_block = max(content_word_counts, default=0)

    prose_flags = [is_prose_block(c, b, cap) for b, c in zip(blocks, classifications)]
    prose_blocks = sum(prose_flags)
    prose_words = sum(b["num_words"] for b, flag in zip(blocks, prose_flags) if flag)

    cap_excluded_flags = [
        c == "CONTENT" and b["has_sentence_end"] and b["num_words"] > cap
        for b, c in zip(blocks, classifications)
    ]
    cap_excluded_blocks = sum(cap_excluded_flags)
    cap_excluded_words = sum(b["num_words"] for b, flag in zip(blocks, cap_excluded_flags) if flag)

    return {
        "blocks_total": blocks_total,
        "blocks_content": blocks_content,
        "words_total": words_total,
        "words_content": words_content,
        "words_content_pct": words_content_pct,
        "link_density_overall": link_density_overall,
        "longest_content_block": longest_content_block,
        "prose_blocks": prose_blocks,
        "prose_words": prose_words,
        "cap_excluded_blocks": cap_excluded_blocks,
        "cap_excluded_words": cap_excluded_words,
    }


# Classify (tree + heading rule) + aggregate an already-read block list
def compute_metrics_from_blocks(blocks: list[dict], cap: int) -> dict:
    tree_classifications = classify_blocks(blocks)
    final_classifications = apply_heading_rule(blocks, tree_classifications)
    return aggregate_file_metrics(blocks, final_classifications, cap)


# Full metric set for one file: read blocks once, classify, aggregate
def compute_file_metrics(path: Path, cap: int) -> dict:
    blocks = read_blocks(path)
    return compute_metrics_from_blocks(blocks, cap)
