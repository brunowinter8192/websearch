"""Tests for the degraded-run notice in src/search/search_web.py.

All non-boundary fixtures are the real per-engine `status` values lifted verbatim from
src/logs/query_log.jsonl `engine_run` records (re-verified against the raw file, not the
summary table in the milestone brief, which had merged two adjacent 2026-09-15T18:43 records
into one wrong "3 of 7" claim). The genuine 3-of-7 (43%) boundary case that separates a 30%
threshold from a 50% one is a DIFFERENT record (2026-09-15T18:43:05, "gegarte Speisen
abkuehlen ..."), confirmed against the raw log and included below.

Only `status` is read by the code under test — the fixtures below carry just that field,
matching the real records' status values exactly, in the real records' own engine order.
"""
from src.search.search_web import (
    DEGRADED_ENGINE_FAILURE_RATIO,
    BROWSER_REPAIR_COMMAND,
    _failing_engines,
    _format_degraded_notice,
    _prepend_degraded_notice,
)


def _stats(*status_pairs):
    return {name: {"status": status} for name, status in status_pairs}


def test_threshold_is_thirty_percent():
    assert DEGRADED_ENGINE_FAILURE_RATIO == 0.30


# ---------------------------------------------------------------------------
# Real recorded runs that must stay silent
# ---------------------------------------------------------------------------

def test_shear_revival_zero_failures_stays_silent():
    engine_stats = _stats(
        ("google", "EMPTY"), ("duckduckgo", "OK"), ("openalex", "OK"),
        ("startpage", "OK"), ("brave", "OK"), ("bing", "OK"), ("yandex", "EMPTY"),
    )
    assert _format_degraded_notice(engine_stats) is None


def test_hauswasserwerk_one_of_eight_stays_silent():
    engine_stats = _stats(
        ("google", "OK"), ("duckduckgo", "OK"), ("mojeek", "EMPTY"),
        ("openalex", "EMPTY"), ("startpage", "TIMEOUT_WATCHDOG"),
        ("brave", "EMPTY"), ("bing", "OK"), ("yandex", "OK"),
    )
    assert _format_degraded_notice(engine_stats) is None


def test_altcha_one_of_eight_stays_silent_even_with_error_browser_present():
    engine_stats = _stats(
        ("google", "EMPTY"), ("duckduckgo", "ERROR_BROWSER"), ("mojeek", "OK"),
        ("openalex", "EMPTY"), ("startpage", "OK"), ("brave", "EMPTY"),
        ("bing", "OK"), ("yandex", "OK"),
    )
    assert _format_degraded_notice(engine_stats) is None


# ---------------------------------------------------------------------------
# Real recorded runs that must fire
# ---------------------------------------------------------------------------

def test_techniker_krankenkasse_hauptverwaltung_seven_of_eight_fires():
    engine_stats = _stats(
        ("google", "TIMEOUT_WATCHDOG"), ("duckduckgo", "TIMEOUT_WATCHDOG"),
        ("mojeek", "TIMEOUT_WATCHDOG"), ("openalex", "EMPTY"),
        ("startpage", "ERROR_BROWSER"), ("brave", "ERROR_BROWSER"),
        ("bing", "ERROR_BROWSER"), ("yandex", "ERROR_BROWSER"),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice is not None
    assert notice.startswith("Engine failures: 7/8 selected engines returned an error or timeout status.")
    assert notice.endswith(f"Repair: {BROWSER_REPAIR_COMMAND}")


def test_bramfelder_strasse_seven_of_eight_fires_with_repair_hint():
    engine_stats = _stats(
        ("google", "TIMEOUT_WATCHDOG"), ("duckduckgo", "TIMEOUT_WATCHDOG"),
        ("mojeek", "TIMEOUT_WATCHDOG"), ("openalex", "OK"),
        ("startpage", "ERROR_BROWSER"), ("brave", "ERROR_BROWSER"),
        ("bing", "ERROR_BROWSER"), ("yandex", "ERROR_BROWSER"),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice == (
        "Engine failures: 7/8 selected engines returned an error or timeout status.\n"
        "  google               TIMEOUT_WATCHDOG\n"
        "  duckduckgo           TIMEOUT_WATCHDOG\n"
        "  mojeek               TIMEOUT_WATCHDOG\n"
        "  startpage            ERROR_BROWSER\n"
        "  brave                ERROR_BROWSER\n"
        "  bing                 ERROR_BROWSER\n"
        "  yandex               ERROR_BROWSER\n"
        f"Repair: {BROWSER_REPAIR_COMMAND}"
    )


def test_hackfleisch_verordnung_seven_of_seven_fires():
    engine_stats = _stats(
        ("google", "ERROR_BROWSER"), ("duckduckgo", "TIMEOUT_NONCOOP"),
        ("openalex", "TIMEOUT_HTTPX"), ("startpage", "TIMEOUT_NONCOOP"),
        ("brave", "TIMEOUT_WATCHDOG"), ("bing", "TIMEOUT_WATCHDOG"),
        ("yandex", "TIMEOUT_WATCHDOG"),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice is not None
    assert notice.startswith("Engine failures: 7/7 selected engines returned an error or timeout status.")


def test_hackfleisch_vorschrift_five_of_seven_fires():
    engine_stats = _stats(
        ("google", "ERROR_BROWSER"), ("duckduckgo", "TIMEOUT_WATCHDOG"),
        ("openalex", "TIMEOUT_HTTPX"), ("startpage", "TIMEOUT_WATCHDOG"),
        ("brave", "TIMEOUT_WATCHDOG"), ("bing", "OK"), ("yandex", "EMPTY"),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice is not None
    assert notice.startswith("Engine failures: 5/7 selected engines returned an error or timeout status.")


def test_gegarte_speisen_boundary_case_three_of_seven_43_percent_fires():
    # The real boundary record (2026-09-15T18:43:05, "gegarte Speisen abkuehlen Kuehlschrank
    # Zeitvorgabe Bacillus cereus") that separates a 30% threshold from a 50% one. It still
    # returned 10 URLs total (bing=OK) -- a partially degraded run that must still speak up,
    # because 3 engines' worth of coverage silently went missing.
    engine_stats = _stats(
        ("google", "ERROR_BROWSER"), ("duckduckgo", "TIMEOUT_WATCHDOG"),
        ("openalex", "EMPTY"), ("startpage", "TIMEOUT_WATCHDOG"),
        ("brave", "EMPTY"), ("bing", "OK"), ("yandex", "EMPTY"),
    )
    failing = _failing_engines(engine_stats)
    assert len(failing) == 3
    assert len(failing) / len(engine_stats) == 3 / 7
    notice = _format_degraded_notice(engine_stats)
    assert notice is not None
    assert notice.startswith("Engine failures: 3/7 selected engines returned an error or timeout status.")


def test_gegarte_speisen_boundary_case_would_stay_silent_at_fifty_percent_threshold():
    engine_stats = _stats(
        ("google", "ERROR_BROWSER"), ("duckduckgo", "TIMEOUT_WATCHDOG"),
        ("openalex", "EMPTY"), ("startpage", "TIMEOUT_WATCHDOG"),
        ("brave", "EMPTY"), ("bing", "OK"), ("yandex", "EMPTY"),
    )
    failing = _failing_engines(engine_stats)
    assert len(failing) / len(engine_stats) < 0.50


# ---------------------------------------------------------------------------
# Branch coverage not yet observed in the real data (hypothesis, explicitly labelled)
# ---------------------------------------------------------------------------

def test_hypothesis_fires_without_error_browser_omits_repair_hint():
    """HYPOTHESIS, never observed: every real record in the 164-record query_log.jsonl that
    crosses the 30% threshold has at least one ERROR_BROWSER in its failing set (verified by
    scanning the whole file, not sampling). This case cannot be built from an observed record,
    so it exists purely to prove the repair line is conditional on ERROR_BROWSER specifically,
    not on the notice firing at all."""
    engine_stats = _stats(
        ("google", "TIMEOUT_WATCHDOG"), ("duckduckgo", "TIMEOUT_WATCHDOG"),
        ("openalex", "OK"), ("startpage", "OK"),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice is not None
    assert "Repair:" not in notice


# ---------------------------------------------------------------------------
# Placement and byte-identical-on-healthy-runs guarantee
# ---------------------------------------------------------------------------

def test_prepend_puts_notice_before_breakdown_not_after():
    engine_stats = _stats(
        ("google", "TIMEOUT_WATCHDOG"), ("duckduckgo", "TIMEOUT_WATCHDOG"),
        ("mojeek", "TIMEOUT_WATCHDOG"), ("openalex", "OK"),
        ("startpage", "ERROR_BROWSER"), ("brave", "ERROR_BROWSER"),
        ("bing", "ERROR_BROWSER"), ("yandex", "ERROR_BROWSER"),
    )
    breakdown_text = 'Engine breakdown for "q":\n  google               0'
    combined = _prepend_degraded_notice(breakdown_text, engine_stats)
    assert combined.startswith("Engine failures:")
    assert combined.endswith(breakdown_text)


def test_prepend_is_byte_identical_to_breakdown_alone_on_healthy_run():
    engine_stats = _stats(
        ("google", "OK"), ("duckduckgo", "OK"), ("openalex", "OK"),
        ("startpage", "OK"), ("brave", "OK"), ("bing", "OK"), ("yandex", "EMPTY"),
    )
    breakdown_text = 'Engine breakdown for "q":\n  google               10\n\nUse ... drilldown.'
    assert _prepend_degraded_notice(breakdown_text, engine_stats) == breakdown_text
