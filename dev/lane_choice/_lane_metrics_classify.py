# INFRASTRUCTURE
LINK_DENSITY_SPLIT = 0.333333
PREV_LINK_DENSITY_SPLIT = 0.555556
CURR_WORDS_LOW_BRANCH_SPLIT = 16
NEXT_WORDS_LOW_BRANCH_SPLIT = 15
PREV_WORDS_LOW_BRANCH_SPLIT = 4
CURR_WORDS_HIGH_BRANCH_SPLIT = 40
NEXT_WORDS_HIGH_BRANCH_SPLIT = 17

HEADING_LOOKAHEAD_CHARS = 200

ZERO_NEIGHBOR = {"num_words": 0, "link_density": 0.0}


# FUNCTIONS

def classify_blocks(blocks: list[dict]) -> list[str]:
    n = len(blocks)
    classifications = []
    for i, block in enumerate(blocks):
        prev = blocks[i - 1] if i > 0 else ZERO_NEIGHBOR
        nxt = blocks[i + 1] if i < n - 1 else ZERO_NEIGHBOR
        classifications.append(classify_block(block, prev, nxt))
    return classifications


def apply_heading_rule(blocks: list[dict], tree_classifications: list[str]) -> list[str]:
    final = list(tree_classifications)
    for i, block in enumerate(blocks):
        if tree_classifications[i] != "BOILERPLATE" or not block["is_heading"]:
            continue
        cumulative_chars = 0
        for j in range(i + 1, len(blocks)):
            if tree_classifications[j] == "CONTENT" and cumulative_chars <= HEADING_LOOKAHEAD_CHARS:
                final[i] = "CONTENT"
                break
            cumulative_chars += blocks[j]["char_len"]
            if cumulative_chars > HEADING_LOOKAHEAD_CHARS:
                break
    return final


def classify_block(curr: dict, prev: dict, nxt: dict) -> str:
    if curr["link_density"] > LINK_DENSITY_SPLIT:
        return "BOILERPLATE"
    if prev["link_density"] <= PREV_LINK_DENSITY_SPLIT:
        if curr["num_words"] > CURR_WORDS_LOW_BRANCH_SPLIT:
            return "CONTENT"
        if nxt["num_words"] > NEXT_WORDS_LOW_BRANCH_SPLIT:
            return "CONTENT"
        if prev["num_words"] > PREV_WORDS_LOW_BRANCH_SPLIT:
            return "CONTENT"
        return "BOILERPLATE"
    if curr["num_words"] > CURR_WORDS_HIGH_BRANCH_SPLIT:
        return "CONTENT"
    if nxt["num_words"] > NEXT_WORDS_HIGH_BRANCH_SPLIT:
        return "CONTENT"
    return "BOILERPLATE"
