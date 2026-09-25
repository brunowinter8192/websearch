# INFRASTRUCTURE
import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

from _mojeek_pydoll_probe_launch import launch_browser, teardown
from _mojeek_pydoll_probe_query import QUERY_BUDGET_S, run_query, verify_environment_reachable
from _mojeek_pydoll_probe_report import build_report_md, write_report

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "md"

CONTROL_URL = "https://example.org/"
SEARCH_URL = "https://www.mojeek.com/search?q={}&safe=1"

GAP_BETWEEN_QUERIES_S = 20.0
GAP_BETWEEN_PHASES_S = 20.0

WARM_PROFILE_PREFIX = "mojeek-probe-carryover-"
FRESH_PROFILE_PREFIX = "mojeek-probe-fresh-"

PRIOR_SPEND_NOTE = (
    "Second live run of this milestone. An earlier run of this same probe, same day, same shape "
    "(10 Mojeek navigations), produced the identical per-phase challenge pattern but its cookie "
    "capture was void: it read cookies through `Tab.get_cookies()`, which resolves to CDP "
    "`Network.getCookies` scoped to the page the tab currently shows, so every before-navigation "
    "snapshot was taken on `about:blank` and came back empty. That was diagnosed against a local "
    "fixture (a cookie set on one origin is invisible to `Network.getCookies` from a blank tab "
    "and visible to `Storage.getCookies`), the reader was switched to browser-wide "
    "`Storage.getCookies`, and the run was repeated. Total live requests against mojeek.com for "
    "this milestone: 20 across the two runs, against a budget of 40."
)

PHASE_COLD = "A cold"
PHASE_WARM = "C warm after relaunch"
PHASE_FRESH = "D fresh control"

PHASE_COLD_DESCRIPTION = (
    "a brand new empty profile, one browser process, four queries in sequence. Query 1 is the "
    "cold data point; queries 2 to 4 are warm within a single browser process."
)
PHASE_WARM_DESCRIPTION = (
    "the same profile directory as phase A, after a full teardown and a relaunch of Chrome. This "
    "is production's shape: the profile persists on disk, the process does not."
)
PHASE_FRESH_DESCRIPTION = (
    "a second, brand new profile, run last. The discriminator between 'the profile carried "
    "something' and 'Mojeek stopped challenging this address during the run'."
)

PHASE_COLD_QUERIES = [
    "python asyncio tutorial",
    "rust borrow checker explained",
    "postgres index bloat",
    "sqlite wal mode",
]

PHASE_WARM_QUERIES = [
    "nginx reverse proxy config",
    "kubernetes ingress tls",
    "ffmpeg concat filter",
    "pandas groupby apply",
]

PHASE_FRESH_QUERIES = [
    "python asyncio tutorial",
    "rust borrow checker explained",
]


# ORCHESTRATOR

async def probe_workflow() -> None:
    carryover_profile = tempfile.mkdtemp(prefix=WARM_PROFILE_PREFIX)
    fresh_profile = tempfile.mkdtemp(prefix=FRESH_PROFILE_PREFIX)
    try:
        cold = await run_phase(PHASE_COLD, PHASE_COLD_DESCRIPTION, carryover_profile, PHASE_COLD_QUERIES)
        store_after_cold = snapshot_cookie_store(carryover_profile)
        await asyncio.sleep(GAP_BETWEEN_PHASES_S)
        store_before_warm = snapshot_cookie_store(carryover_profile)
        warm = await run_phase(PHASE_WARM, PHASE_WARM_DESCRIPTION, carryover_profile, PHASE_WARM_QUERIES)
        await asyncio.sleep(GAP_BETWEEN_PHASES_S)
        fresh = await run_phase(PHASE_FRESH, PHASE_FRESH_DESCRIPTION, fresh_profile, PHASE_FRESH_QUERIES)
        phases = [cold, warm, fresh]
        persistence = build_persistence_record(cold, warm, store_after_cold, store_before_warm)
        report = build_report_md(
            phases, persistence, count_live_requests(phases), GAP_BETWEEN_QUERIES_S, QUERY_BUDGET_S,
            PRIOR_SPEND_NOTE,
        )
        write_report(report, REPORT_DIR)
    finally:
        discard_profiles([carryover_profile, fresh_profile])


# FUNCTIONS

@dataclass
class Phase:
    name: str
    description: str
    profile_dir: str
    measurements: list = field(default_factory=list)


async def run_phase(name: str, description: str, profile_dir: str, queries: list[str]) -> Phase:
    phase = Phase(name=name, description=description, profile_dir=profile_dir)
    handle = await launch_browser(profile_dir)
    try:
        await verify_environment_reachable(handle, CONTROL_URL)
        for index, query in enumerate(queries):
            if index:
                await asyncio.sleep(GAP_BETWEEN_QUERIES_S)
            logger.warning("%s: query %d/%d: %s", name, index + 1, len(queries), query)
            measurement = await run_query(handle, query, build_search_url(query))
            logger.warning(
                "%s: %s -> challenge_served=%s verdict=%s total_ms=%s",
                name, query, measurement.challenge_served, measurement.verdict, measurement.total_ms,
            )
            phase.measurements.append(measurement)
    finally:
        await teardown(handle)
    return phase


def snapshot_cookie_store(profile_dir: str) -> dict:
    path = Path(profile_dir) / "Default" / "Cookies"
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {"path": str(path), "exists": True, "size_bytes": stat.st_size, "mtime": stat.st_mtime}


def build_persistence_record(cold: Phase, warm: Phase, store_after_cold: dict, store_before_warm: dict) -> dict:
    end_of_cold = cold.measurements[-1].cookies_after_settle if cold.measurements else []
    start_of_warm = warm.measurements[0].cookies_before if warm.measurements else []
    survived = sorted(
        {_cookie_identity(c)[0] for c in start_of_warm}
        & {_cookie_identity(c)[0] for c in end_of_cold}
    )
    identical_values = sorted(
        {_cookie_identity(c) for c in start_of_warm} & {_cookie_identity(c) for c in end_of_cold}
    )
    return {
        "cookie_store_file_after_phase_a": store_after_cold,
        "cookie_store_file_before_phase_c": store_before_warm,
        "mojeek_cookies_at_end_of_phase_a": end_of_cold,
        "mojeek_cookies_at_start_of_phase_c": start_of_warm,
        "names_present_on_both_sides_of_the_process_kill": survived,
        "names_whose_value_was_byte_identical_across_the_kill": [i[0] for i in identical_values],
        "session_scoped_at_end_of_phase_a": [c["name"] for c in end_of_cold if c["session_scoped"]],
        "persistent_at_end_of_phase_a": [c["name"] for c in end_of_cold if not c["session_scoped"]],
    }


def count_live_requests(phases: list[Phase]) -> int:
    return sum(len(phase.measurements) for phase in phases)


def discard_profiles(profile_dirs: list[str]) -> None:
    for profile_dir in profile_dirs:
        shutil.rmtree(profile_dir, ignore_errors=True)


def build_search_url(query: str) -> str:
    return SEARCH_URL.format(quote_plus(query))


def _cookie_identity(fingerprint: dict) -> tuple:
    return (
        fingerprint["name"], fingerprint["domain"], fingerprint["path"], fingerprint["value_sha256_12"]
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(probe_workflow())
