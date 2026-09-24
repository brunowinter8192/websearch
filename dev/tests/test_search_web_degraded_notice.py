from src.search.degraded_notice import (
    DEGRADED_ENGINE_FAILURE_RATIO,
    BROWSER_REPAIR_COMMAND,
    _failing_engines,
    _format_degraded_notice,
    _prepend_degraded_notice,
)


def _stats(*rows):
    return {row[0]: {"status": row[1], "drop_reason": row[2] if len(row) > 2 else None} for row in rows}


WATCHDOG = "asyncio.TimeoutError after 6.0s watchdog"


def _ws_refused(port):
    return (
        f"Failed to get browser ws address: Cannot connect to host localhost:{port} ssl:default "
        f"[Multiple exceptions: [Errno 61] Connect call failed ('::1', {port}, 0, 0), "
        f"[Errno 61] Connect call failed ('127.0.0.1', {port})]"
    )


def _nav_refused(url):
    return f"Navigation to {url} failed: net::ERR_CONNECTION_REFUSED"


def _record_2026_09_21_0841():
    reason = _ws_refused(9256)
    return _stats(
        ("google", "TIMEOUT_WATCHDOG", WATCHDOG), ("duckduckgo", "TIMEOUT_WATCHDOG", WATCHDOG),
        ("mojeek", "TIMEOUT_WATCHDOG", WATCHDOG), ("openalex", "OK"),
        ("startpage", "ERROR_BROWSER", reason), ("brave", "ERROR_BROWSER", reason),
        ("bing", "ERROR_BROWSER", reason), ("yandex", "ERROR_BROWSER", reason),
    )


def _record_2026_09_24_1713_excalidraw():
    q = "excalidraw+text+shifts+when+editing+safari"
    return _stats(
        ("google", "ERROR_BROWSER", _nav_refused(f"https://www.google.com/search?q={q}&hl=en&num=100")),
        ("duckduckgo", "ERROR_BROWSER", _nav_refused(f"https://html.duckduckgo.com/html/?q={q}&kl=wt-wt")),
        ("mojeek", "ERROR_BROWSER", _nav_refused(f"https://www.mojeek.com/search?q={q}&safe=1")),
        ("openalex", "ERROR_HTTP", "502 Bad Gateway"),
        ("startpage", "ERROR_BROWSER", _nav_refused("https://www.startpage.com/")),
        ("brave", "ERROR_BROWSER", _nav_refused(f"https://search.brave.com/search?q={q}")),
        ("bing", "ERROR_BROWSER", _nav_refused(f"https://www.bing.com/search?q={q}")),
        ("yandex", "ERROR_BROWSER", _nav_refused(f"https://yandex.com/search/?text={q}")),
    )


def test_threshold_is_thirty_percent():
    assert DEGRADED_ENGINE_FAILURE_RATIO == 0.30


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


def test_techniker_krankenkasse_hauptverwaltung_seven_of_eight_fires():
    reason = _ws_refused(9296)
    engine_stats = _stats(
        ("google", "TIMEOUT_WATCHDOG", WATCHDOG), ("duckduckgo", "TIMEOUT_WATCHDOG", WATCHDOG),
        ("mojeek", "TIMEOUT_WATCHDOG", WATCHDOG), ("openalex", "EMPTY"),
        ("startpage", "ERROR_BROWSER", reason), ("brave", "ERROR_BROWSER", reason),
        ("bing", "ERROR_BROWSER", reason), ("yandex", "ERROR_BROWSER", reason),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice is not None
    assert notice.startswith("Engine failures: 7/8 selected engines returned an error or timeout status.")
    assert notice.endswith(f"Repair: {BROWSER_REPAIR_COMMAND}")


def test_bramfelder_strasse_2026_09_21_shape_names_fact_and_keeps_repair_line():
    notice = _format_degraded_notice(_record_2026_09_21_0841())
    print("\n" + notice)
    ws = "Failed to get browser ws address: Cannot connect to host localhost:9256"
    assert notice == (
        "Engine failures: 7/8 selected engines returned an error or timeout status.\n"
        "  google               TIMEOUT_WATCHDOG   asyncio.TimeoutError after 6.0s watchdog\n"
        "  duckduckgo           TIMEOUT_WATCHDOG   asyncio.TimeoutError after 6.0s watchdog\n"
        "  mojeek               TIMEOUT_WATCHDOG   asyncio.TimeoutError after 6.0s watchdog\n"
        f"  startpage            ERROR_BROWSER      {ws}\n"
        f"  brave                ERROR_BROWSER      {ws}\n"
        f"  bing                 ERROR_BROWSER      {ws}\n"
        f"  yandex               ERROR_BROWSER      {ws}\n"
        f"Repair: {BROWSER_REPAIR_COMMAND}"
    )


def test_2026_09_24_network_refused_shape_names_fact_and_has_no_repair_line():
    notice = _format_degraded_notice(_record_2026_09_24_1713_excalidraw())
    print("\n" + notice)
    nav = "Navigation failed: net::ERR_CONNECTION_REFUSED"
    assert notice == (
        "Engine failures: 8/8 selected engines returned an error or timeout status.\n"
        f"  google               ERROR_BROWSER      {nav}\n"
        f"  duckduckgo           ERROR_BROWSER      {nav}\n"
        f"  mojeek               ERROR_BROWSER      {nav}\n"
        "  openalex             ERROR_HTTP         502 Bad Gateway\n"
        f"  startpage            ERROR_BROWSER      {nav}\n"
        f"  brave                ERROR_BROWSER      {nav}\n"
        f"  bing                 ERROR_BROWSER      {nav}\n"
        f"  yandex               ERROR_BROWSER      {nav}"
    )
    assert "Repair:" not in notice
    assert "http" not in notice


def test_2026_09_24_second_run_webkit_query_shape_has_no_repair_line():
    q = "webkit+line-height+fractional+rounded+textarea"
    engine_stats = _stats(
        ("google", "ERROR_BROWSER", _nav_refused(f"https://www.google.com/search?q={q}&hl=en&num=100")),
        ("duckduckgo", "ERROR_BROWSER", _nav_refused(f"https://html.duckduckgo.com/html/?q={q}&kl=wt-wt")),
        ("mojeek", "ERROR_BROWSER", _nav_refused(f"https://www.mojeek.com/search?q={q}&safe=1")),
        ("openalex", "ERROR_HTTP", "502 Bad Gateway"),
        ("startpage", "ERROR_BROWSER", _nav_refused("https://www.startpage.com/")),
        ("brave", "ERROR_BROWSER", _nav_refused(f"https://search.brave.com/search?q={q}")),
        ("bing", "ERROR_BROWSER", _nav_refused(f"https://www.bing.com/search?q={q}")),
        ("yandex", "ERROR_BROWSER", _nav_refused(f"https://yandex.com/search/?text={q}")),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice.startswith("Engine failures: 8/8")
    assert "Repair:" not in notice
    assert "search?q=" not in notice


def test_hypothesis_error_browser_without_drop_reason_gets_no_repair_line():
    engine_stats = _stats(
        ("google", "ERROR_BROWSER"), ("duckduckgo", "ERROR_BROWSER", "some unseen browser error"),
        ("openalex", "OK"), ("startpage", "OK"),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice is not None
    assert "Repair:" not in notice
    assert "  google               ERROR_BROWSER\n" in notice


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


def test_hypothesis_fires_without_error_browser_omits_repair_hint():
    engine_stats = _stats(
        ("google", "TIMEOUT_WATCHDOG"), ("duckduckgo", "TIMEOUT_WATCHDOG"),
        ("openalex", "OK"), ("startpage", "OK"),
    )
    notice = _format_degraded_notice(engine_stats)
    assert notice is not None
    assert "Repair:" not in notice


def test_prepend_puts_notice_before_breakdown_not_after():
    engine_stats = _record_2026_09_21_0841()
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
