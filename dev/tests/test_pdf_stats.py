# INFRASTRUCTURE
import json

import pytest

from dev.tests._pdf_fakes import conversion_log
from src.pdf.report import WorkflowError
from src.pdf.stats import stats_workflow


# FUNCTIONS

def start(run_id, ts, pages, config_hash="aaaa"):
    return {"record_type": "start", "run_id": run_id, "ts_start": ts, "pages": pages, "config_hash": config_hash}


def end(run_id, ts, outcome, failure_class=None, wall_s=60.0):
    return {"record_type": "end", "run_id": run_id, "ts_end": ts, "outcome": outcome,
            "failure_class": failure_class, "wall_s": wall_s}


def write_log(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


@pytest.fixture
def sample_log(conversion_log):
    write_log(conversion_log, [
        start("r1", "2026-09-01T10:00:00.000Z", 100, "old"),
        end("r1", "2026-09-01T10:10:00.000Z", "ok", wall_s=600.0),
        start("r2", "2026-10-02T10:00:00.000Z", 200),
        end("r2", "2026-10-02T10:01:00.000Z", "failed", "no_text_layer", wall_s=60.0),
        start("r3", "2026-10-03T10:00:00.000Z", 300),
        start("r4", "2026-10-04T10:00:00.000Z", 400),
        end("r4", "2026-10-04T10:20:00.000Z", "failed", "missing_batch", wall_s=1200.0),
        end("r4", "2026-10-04T10:30:00.000Z", "ok", wall_s=1800.0),
    ])
    return conversion_log


def test_stats_counts_runs_failures_unfinished_and_averages(sample_log):
    text = stats_workflow(None).text
    assert "runs: 4  ok: 2  failed: 1  unfinished: 1" in text
    assert "recovered by retry: 1" in text
    assert "failures by reason: no_text_layer=1" in text
    assert "mean pages: 250.0" in text
    assert "mean duration: 13.7 min" in text


def test_stats_since_excludes_earlier_runs_and_splits_by_config(sample_log):
    text = stats_workflow("2026-10-01").text
    assert "runs: 3  ok: 1  failed: 1  unfinished: 1" in text
    assert "config aaaa: 3 runs, 1 ok" in text
    assert "config old" not in text


def test_stats_on_a_missing_log_reports_zero_runs(conversion_log):
    text = stats_workflow(None).text
    assert "runs: 0  ok: 0  failed: 0  unfinished: 0" in text
    assert "mean pages: n/a" in text
    assert "failures by reason: none" in text


def test_stats_rejects_an_end_record_without_start(conversion_log):
    write_log(conversion_log, [end("ghost", "2026-10-02T10:00:00.000Z", "ok")])
    with pytest.raises(WorkflowError):
        stats_workflow(None)
