# INFRASTRUCTURE
import asyncio
from pathlib import Path

from src.news.engine.proxy_riding import abort as abort_mod
from src.news.engine.proxy_riding import reporter as reporter_mod
from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
from src.news.engine.proxy_riding.state import RiderState


# FUNCTIONS

def test_abort_stall_writes_no_job_md_on_reporter_failure(tmp_path, monkeypatch, capsys):
    def _raise(*a, **kw):
        raise RuntimeError("simulated reporter failure")
    monkeypatch.setattr(reporter_mod, "write_riding_report", _raise)

    exit_codes = []
    monkeypatch.setattr(abort_mod.os, "_exit", lambda code: exit_codes.append(code))

    state = _make_state(tmp_path)
    abort_mod._abort_stall(state, idle_s=123.0)

    assert exit_codes == [1]
    assert not (state.job_dir / "job.md").exists()
    err = capsys.readouterr().err
    assert "write_riding_report WARN" in err
    assert "simulated reporter failure" in err


def _make_state(tmp_path: Path) -> RiderState:
    return RiderState(
        url_queue=asyncio.Queue(),
        proxy_pool=[],
        cooldown_mgr=RidingCooldownManager(),
        output_dir=tmp_path,
        job_dir=tmp_path / "scrape_jobs" / "job1",
        burn_threshold=2,
        page_timeout_ms=8_000,
        total_urls=1,
        target_urls=frozenset({"https://x.test/a"}),
    )
