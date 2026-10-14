# INFRASTRUCTURE
import pytest

from dev.adhoc_persistence.deepdive_assessment import SERVES_NO, SERVES_PARTIAL, SERVES_YES, serves_of
from dev.adhoc_persistence.deepdive_candidates import RESEARCH, build_groups, candidates, era_at, mark_offered
from dev.adhoc_persistence.deepdive_join import join_scrapes_to_calls, normalize_url
from dev.adhoc_persistence.deepdive_transcripts import COMMAND_KINDS, skill_text_era, urls_in

SESSION = "adfd041c-8818-4a91-a341-aa14f638115a"
RESEARCH_PROJECT = "-Users-brunowinter2000-Documents-wise2627"


# FUNCTIONS

def _call(start: str, end: str, command: str) -> dict:
    return {"session": SESSION, "project": RESEARCH_PROJECT, "cwd": None, "start": start, "end": end, "command": command, "urls": urls_in(command)}


def _record(ts: str, url: str, domain: str) -> dict:
    return {"ts": ts, "url": url, "domain": domain, "verdict": "usable", "body": ""}


def test_urls_in_strips_the_semicolon_of_a_chained_command():
    command = "websearch scrape_url_chromium https://www.ub.uni-frankfurt.de/online/home.html; websearch scrape_url_chromium https://www.ub.uni-frankfurt.de/online/faq.html"

    assert urls_in(command) == [
        "https://www.ub.uni-frankfurt.de/online/home.html",
        "https://www.ub.uni-frankfurt.de/online/faq.html",
    ]


def test_urls_in_keeps_the_ampersands_of_a_quoted_query_url():
    command = 'websearch scrape_url_chromium "https://qis.server.uni-frankfurt.de/qisserver/rds?state=wsearchv&search=1&P_start=0"'

    assert urls_in(command) == ["https://qis.server.uni-frankfurt.de/qisserver/rds?state=wsearchv&search=1&P_start=0"]


def test_invocation_pattern_ignores_a_grep_for_the_command_name():
    command = 'grep -l "websearch scrape_url_chromium\\|websearch discover_urls" -r --include=*.jsonl . | wc -l'

    assert not COMMAND_KINDS["scrape"].search(command)
    assert not COMMAND_KINDS["discover"].search(command)


def test_invocation_pattern_matches_the_cli_py_form_after_a_cd():
    command = 'cd /repo && ./venv/bin/python cli.py discover_urls "https://sre.google/" --url-file /tmp/u.txt'

    assert COMMAND_KINDS["discover"].search(command)


def test_join_survives_a_regex_example_url_that_is_no_valid_ipv6_host():
    calls = [_call("2026-09-15T12:12:10Z", "2026-09-15T12:12:40Z", 'echo "https://[^ )]*errata"; websearch scrape_url_chromium "https://www.reddit.com/r/a/comments/1/x/"')]
    records = [_record("2026-09-15T12:12:14.000Z", "https://www.reddit.com/r/a/comments/1/x/", "reddit.com")]

    joined = join_scrapes_to_calls(records, calls)

    assert joined[0]["call"] is calls[0]


def test_join_matches_the_second_scrape_of_a_chain_inside_the_result_window():
    calls = [_call("2026-09-23T11:54:15Z", "2026-09-23T11:54:50Z", "websearch scrape_url_chromium https://a.test/1; websearch scrape_url_chromium https://a.test/2")]
    records = [_record("2026-09-23T11:54:39.000Z", "https://a.test/2", "a.test")]

    assert join_scrapes_to_calls(records, calls)[0]["call"] is calls[0]


def test_join_leaves_a_scrape_without_a_matching_call_unattributed():
    calls = [_call("2026-09-12T10:00:00Z", "2026-09-12T10:00:10Z", "websearch scrape_url_chromium https://a.test/1")]
    records = [_record("2026-09-12T15:59:07.000Z", "https://a.test/1", "a.test")]

    assert join_scrapes_to_calls(records, calls)[0]["call"] is None


def test_normalize_url_merges_www_and_trailing_slash():
    assert normalize_url("https://www.example.org/a/") == normalize_url("https://example.org/a")


@pytest.mark.parametrize(
    "ts,expected",
    [
        ("2026-09-20T19:47:03Z", "E0"),
        ("2026-09-20T19:47:04Z", "E1"),
        ("2026-09-24T18:46:25Z", "E2"),
        ("2026-10-11T11:58:39Z", "E3"),
        ("2026-10-14T16:37:27Z", "E4"),
    ],
)
def test_era_boundaries_follow_the_skill_commit_times(ts, expected):
    assert era_at(ts) == expected


def test_skill_text_era_tells_the_two_deep_dive_texts_apart_by_the_proposal_line():
    with_proposal = "Mache einen Deep Dive wenn auch andere urls\n- Schlage dem User proaktiv einen Deep Dive vor."
    without_proposal = "Mache einen Deep Dive wenn auch andere urls\n- Blog, News, Forum"

    assert skill_text_era(with_proposal) == "E2"
    assert skill_text_era(without_proposal) == "E3"


def test_groups_count_distinct_pages_per_session_and_host_only():
    joined = [
        {**_record("2026-09-21T10:12:55.000Z", "https://www.ub.uni-frankfurt.de/a", "ub.uni-frankfurt.de"), "call": _call("a", "b", ""), "offered": False},
        {**_record("2026-09-21T10:13:26.000Z", "https://www.ub.uni-frankfurt.de/a/", "ub.uni-frankfurt.de"), "call": _call("a", "b", ""), "offered": True},
        {**_record("2026-09-21T10:14:00.000Z", "https://www.wiwi.uni-frankfurt.de/x", "wiwi.uni-frankfurt.de"), "call": _call("a", "b", ""), "offered": True},
    ]
    sessions = {SESSION: {"skill_loaded_ts": None, "skill_text_era": None}}

    groups = build_groups(joined, sessions)

    assert candidates(groups, RESEARCH) == []
    assert {g["host"]: len(g["pages"]) for g in groups} == {"ub.uni-frankfurt.de": 1, "wiwi.uni-frankfurt.de": 1}


def test_mark_offered_needs_a_drilldown_within_three_hours_before_the_scrape():
    drilldowns = [{"ts": "2026-09-23T09:00:00.000Z", "urls": ["https://a.test/near", "https://a.test/far"]}]
    records = [_record("2026-09-23T11:00:00.000Z", "https://a.test/near", "a.test"), _record("2026-09-23T12:30:00.000Z", "https://a.test/far", "a.test")]

    marked = mark_offered(records, drilldowns)

    assert [r["offered"] for r in marked] == [True, False]


@pytest.mark.parametrize(
    "need_multi,stable,navigated,other,expected",
    [
        (True, "yes", ["p"], [], SERVES_YES),
        (True, "partly", [], ["s"], SERVES_PARTIAL),
        (True, "no", ["p"], ["s"], SERVES_NO),
        (False, "yes", ["p"], ["s"], SERVES_NO),
        (True, "yes", [], [], SERVES_NO),
    ],
)
def test_serves_derivation(need_multi, stable, navigated, other, expected):
    judgment = {"need_multi": need_multi, "stable": stable}
    group = {"navigated_pages": navigated, "other_sessions": other}

    assert serves_of(judgment, group) == expected
