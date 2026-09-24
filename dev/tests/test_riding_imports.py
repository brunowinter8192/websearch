from pathlib import Path


def test_riding_package_imports_defaults_and_late_import():
    import src.news.engine.proxy_riding.rider as rider_mod
    import src.news.engine.proxy_riding.abort as abort_mod
    import src.news.engine.proxy_riding.reporter as reporter_mod
    from src.news.engine.proxy_riding.scrape import RidingScrapeConfig, BROWSER_ELIGIBLE_PROTOS

    cfg = RidingScrapeConfig()
    assert cfg.n_browsers == 4
    assert cfg.n_slots == 64
    assert cfg.stall_timeout_s == 300.0
    assert cfg.burn_threshold == 2
    assert cfg.page_timeout_ms == 8_000

    assert BROWSER_ELIGIBLE_PROTOS == frozenset({"http", "socks5"})

    src_rider = Path(rider_mod.__file__).read_text()
    src_abort = Path(abort_mod.__file__).read_text()
    src_reporter = Path(reporter_mod.__file__).read_text()
    assert "sys.path.insert" not in src_rider
    assert "sys.path.insert" not in src_abort
    assert "sys.path.insert" not in src_reporter
    assert "src.news.engine.proxy_riding.reporter" in src_abort
