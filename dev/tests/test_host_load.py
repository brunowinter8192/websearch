# INFRASTRUCTURE
import os
from collections import namedtuple

from src import host_load
from src.host_load import cpu_busy_pct, host_facts_since, parse_ps_output, take_host_snapshot, top_cpu_processes

CpuTimes = namedtuple("CpuTimes", "user nice system idle")

PS_OUTPUT = """    1 4:40.35 /sbin/launchd
  403 1263:52.16 /System/Library/PrivateFrameworks/SkyLight.framework/Resources/WindowServer
  503 279:22.78 /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/Metadata.framework/Versions/A/Support/mds_stores
 8713 417:52.45 /System/Applications/Preview.app/Contents/MacOS/Preview
90001 0:05.20 /Applications/Google Chrome.app/Contents/Frameworks/Google Chrome Helper (Renderer).app/Contents/MacOS/Google Chrome Helper (Renderer)
90002 0:03.10 /Applications/Google Chrome.app/Contents/Frameworks/Google Chrome Helper (Renderer).app/Contents/MacOS/Google Chrome Helper (Renderer)
"""


# FUNCTIONS

def test_real_ps_lines_parse_to_pid_name_and_cpu_seconds():
    errors = []

    processes = parse_ps_output(PS_OUTPUT, errors)

    assert errors == []
    assert processes[403] == ("WindowServer", 1263 * 60 + 52.16)
    assert processes[503][0] == "mds_stores"
    assert processes[90001][0] == "Google Chrome Helper (Renderer)"


def test_unparseable_ps_line_is_recorded_and_the_other_lines_still_count():
    errors = []

    processes = parse_ps_output("    1 4:40.35 /sbin/launchd\n  777 3-04:05:06 /usr/bin/odd\nnot a line\n", errors)

    assert list(processes) == [1]
    assert len(errors) == 1
    assert "2 unparseable lines" in errors[0]
    assert "3-04:05:06" in errors[0]


def test_cpu_busy_is_the_non_idle_share_of_the_window():
    start = CpuTimes(user=100.0, nice=0.0, system=50.0, idle=850.0)
    end = CpuTimes(user=160.0, nice=0.0, system=70.0, idle=870.0)

    assert cpu_busy_pct(start, end) == 80.0


def test_cpu_busy_is_none_when_a_snapshot_is_missing_or_no_time_passed():
    same = CpuTimes(user=1.0, nice=0.0, system=1.0, idle=1.0)

    assert cpu_busy_pct(None, same) is None
    assert cpu_busy_pct(same, same) is None


def test_top_processes_aggregate_by_name_rank_by_window_delta_and_skip_the_own_pid():
    own = os.getpid()
    start = {503: ("mds_stores", 100.0), 90001: ("Google Chrome Helper (Renderer)", 1.0), own: ("python", 10.0)}
    end = {
        503: ("mds_stores", 104.5),
        90001: ("Google Chrome Helper (Renderer)", 3.0),
        90002: ("Google Chrome Helper (Renderer)", 1.5),
        own: ("python", 50.0),
        8713: ("Preview", 400.0),
    }

    top = top_cpu_processes(start, end)

    assert top[0] == {"name": "Preview", "cpu_s": 400.0, "procs": 1}
    assert top[1] == {"name": "mds_stores", "cpu_s": 4.5, "procs": 1}
    assert top[2] == {"name": "Google Chrome Helper (Renderer)", "cpu_s": 3.5, "procs": 2}
    assert all(item["name"] != "python" for item in top)


def test_reused_pid_with_a_different_name_counts_its_full_cpu_time():
    top = top_cpu_processes({42: ("old_tool", 500.0)}, {42: ("new_tool", 2.0)})

    assert top == [{"name": "new_tool", "cpu_s": 2.0, "procs": 1}]


def test_host_facts_carry_the_cpu_count_load_and_no_errors_on_clean_input(monkeypatch):
    monkeypatch.setattr(host_load.os, "getloadavg", lambda: (4.8012, 4.0068, 3.6904))
    monkeypatch.setattr(host_load.psutil, "cpu_times", lambda: CpuTimes(1.0, 0.0, 1.0, 8.0))
    outputs = iter(["  503 1:00.00 /x/mds_stores\n", "  503 1:03.00 /x/mds_stores\n"])
    monkeypatch.setattr(host_load, "read_ps_output", lambda: next(outputs))

    start = take_host_snapshot()
    facts = host_facts_since(start)

    assert facts["cpu_count"] == os.cpu_count()
    assert facts["load_avg_start"] == [4.8, 4.01, 3.69]
    assert facts["top_cpu_processes"] == [{"name": "mds_stores", "cpu_s": 3.0, "procs": 1}]
    assert facts["errors"] == []


def test_ps_failure_is_recorded_in_the_facts_and_never_raises(monkeypatch):
    def _broken():
        raise OSError("ps not available")

    monkeypatch.setattr(host_load, "read_ps_output", _broken)

    facts = host_facts_since(take_host_snapshot())

    assert facts["top_cpu_processes"] is None
    assert facts["errors"] == ["ps: OSError: ps not available"]


def test_unparseable_ps_line_reaches_the_facts_once_and_keeps_the_other_fields(monkeypatch):
    monkeypatch.setattr(host_load, "read_ps_output", lambda: "  503 1:00.00 /x/mds_stores\nbroken line here\n")

    facts = host_facts_since(take_host_snapshot())

    assert len(facts["errors"]) == 1
    assert "1 unparseable lines" in facts["errors"][0]
    assert facts["top_cpu_processes"] == []
    assert facts["cpu_count"] == os.cpu_count()
