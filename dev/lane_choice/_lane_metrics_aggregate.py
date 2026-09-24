# INFRASTRUCTURE
LANES = ("chromium", "camoufox")


# FUNCTIONS

def winning_lane(chromium_value: float, camoufox_value: float) -> str:
    if chromium_value > camoufox_value:
        return "chromium"
    if camoufox_value > chromium_value:
        return "camoufox"
    return "tie"


def compute_aggregate(results: list[dict]) -> dict:
    words_wins = {"chromium": 0, "camoufox": 0, "tie": 0}
    pct_wins = {"chromium": 0, "camoufox": 0, "tie": 0}
    disagreements = []
    cap_excluded = {lane: {"blocks": 0, "words": 0} for lane in LANES}

    for entry in results:
        chromium_m = entry["lanes"]["chromium"]
        camoufox_m = entry["lanes"]["camoufox"]

        words_winner = winning_lane(chromium_m["words_content"], camoufox_m["words_content"])
        pct_winner = winning_lane(chromium_m["words_content_pct"], camoufox_m["words_content_pct"])
        words_wins[words_winner] += 1
        pct_wins[pct_winner] += 1
        if "tie" not in (words_winner, pct_winner) and words_winner != pct_winner:
            disagreements.append(entry["url"])

        for lane in LANES:
            cap_excluded[lane]["blocks"] += entry["lanes"][lane]["cap_excluded_blocks"]
            cap_excluded[lane]["words"] += entry["lanes"][lane]["cap_excluded_words"]

    zero_content_chromium = [e for e in results if e["lanes"]["chromium"]["blocks_content"] == 0]
    rescued_by_camoufox_prose = [
        e["url"] for e in zero_content_chromium if e["lanes"]["camoufox"]["prose_blocks"] >= 1
    ]
    not_rescued = [
        e["url"] for e in zero_content_chromium if e["lanes"]["camoufox"]["prose_blocks"] == 0
    ]

    return {
        "words_wins": words_wins,
        "pct_wins": pct_wins,
        "disagreements": disagreements,
        "cap_excluded": cap_excluded,
        "zero_content_chromium_count": len(zero_content_chromium),
        "rescued_by_camoufox_prose": rescued_by_camoufox_prose,
        "not_rescued": not_rescued,
    }
