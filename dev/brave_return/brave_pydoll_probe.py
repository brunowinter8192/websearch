# INFRASTRUCTURE
import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

from _brave_probe_launch import launch_browser, resolve_chromium_bundle_path, teardown
from _brave_probe_query import QUERY_BUDGET_S, run_query, verify_environment_reachable
from _brave_probe_report import build_report_md, write_report

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "md"

CONTROL_URL = "https://example.org/"
SEARCH_URL = "https://search.brave.com/search?q={}"

GAP_BETWEEN_QUERIES_S = 20.0
GAP_BETWEEN_PHASES_S = 20.0

COLD_PROFILE_PREFIX = "brave-probe-cold-"
EXTENSION_PROFILE_PREFIX = "brave-probe-extension-"
FRESH_PROFILE_PREFIX = "brave-probe-fresh-"

LIVE_BUDGET_CEILING = 20
BASE_PLAN_TOTAL = 10
EXTENSION_MAX = 4

BUDGET_NOTE_TEMPLATE = (
    "Live budget for this milestone: a hard ceiling of {ceiling} real requests against "
    "search.brave.com. Base plan: 4 (phase A) + 4 (phase C) + 2 (phase D) = {base} requests. "
    "One bounded extension is allowed by the brief: if phases A and C together produce zero "
    "button challenges, up to {extension} additional navigations on a third fresh profile may run "
    "before phase D, still inside the {ceiling}-request ceiling. Phase D always runs last. This "
    "run {extension_clause}."
)

PHASE_COLD = "A cold"
PHASE_WARM = "C warm after relaunch"
PHASE_EXTENSION = "B extension (zero button challenges in A+C)"
PHASE_FRESH = "D fresh control"

PHASE_COLD_DESCRIPTION = (
    "a brand new empty profile, one browser process, four queries in sequence."
)
PHASE_WARM_DESCRIPTION = (
    "the same profile directory as phase A, after a full teardown and a relaunch of Chrome. "
    "Production's shape: the profile persists on disk, the process does not."
)
PHASE_EXTENSION_DESCRIPTION = (
    "a third, brand new profile, run only because phases A and C together produced zero button "
    "challenges. Bounded to at most 4 queries by the brief."
)
PHASE_FRESH_DESCRIPTION = (
    "a second (or third, if the extension ran) brand new profile, run last. The discriminator "
    "between 'the profile carried something' and 'Brave stopped challenging this address during "
    "the run'."
)

PHASE_COLD_QUERIES = [
    "DS18B20 1-wire dropout compressor fridge",
    "postgres index bloat diagnosis",
    "rust borrow checker explained",
    "sqlite wal mode checkpoint",
]

PHASE_WARM_QUERIES = [
    "nginx reverse proxy config",
    "kubernetes ingress tls",
    "ffmpeg concat filter",
    "pandas groupby apply",
]

PHASE_EXTENSION_QUERIES = [
    "python asyncio tutorial",
    "how does dns work",
    "fastapi websocket reconnect",
    "argon2 memory hard hashing",
]

PHASE_FRESH_QUERIES = [
    "python asyncio tutorial",
    "rust borrow checker explained",
]


@dataclass
class Phase:
    name: str
    description: str
    profile_dir: str
    measurements: list = field(default_factory=list)


# ORCHESTRATOR

async def probe_workflow() -> None:
    bundle_path = await resolve_chromium_bundle_path()
    logger.warning("Resolved Chromium bundle: %s", bundle_path)
    cold_profile = tempfile.mkdtemp(prefix=COLD_PROFILE_PREFIX)
    fresh_profile = tempfile.mkdtemp(prefix=FRESH_PROFILE_PREFIX)
    extension_profile = None
    all_profiles = [cold_profile, fresh_profile]
    try:
        cold = await run_phase(PHASE_COLD, PHASE_COLD_DESCRIPTION, cold_profile, PHASE_COLD_QUERIES, bundle_path)
        store_after_cold = snapshot_cookie_store(cold_profile)
        await asyncio.sleep(GAP_BETWEEN_PHASES_S)
        store_before_warm = snapshot_cookie_store(cold_profile)
        warm = await run_phase(PHASE_WARM, PHASE_WARM_DESCRIPTION, cold_profile, PHASE_WARM_QUERIES, bundle_path)
        phases = [cold, warm]
        extension_used = False
        if not any_challenge_served(cold) and not any_challenge_served(warm):
            extension_profile = tempfile.mkdtemp(prefix=EXTENSION_PROFILE_PREFIX)
            all_profiles.append(extension_profile)
            await asyncio.sleep(GAP_BETWEEN_PHASES_S)
            extension = await run_phase(
                PHASE_EXTENSION, PHASE_EXTENSION_DESCRIPTION, extension_profile,
                PHASE_EXTENSION_QUERIES[:EXTENSION_MAX], bundle_path,
            )
            phases.append(extension)
            extension_used = True
        await asyncio.sleep(GAP_BETWEEN_PHASES_S)
        fresh = await run_phase(PHASE_FRESH, PHASE_FRESH_DESCRIPTION, fresh_profile, PHASE_FRESH_QUERIES, bundle_path)
        phases.append(fresh)
        persistence = build_persistence_record(cold, warm, store_after_cold, store_before_warm)
        live_requests = count_live_requests(phases)
        budget_note = BUDGET_NOTE_TEMPLATE.format(
            ceiling=LIVE_BUDGET_CEILING, base=BASE_PLAN_TOTAL, extension=EXTENSION_MAX,
            extension_clause="used the extension" if extension_used else "did not need the extension",
        )
        report = build_report_md(
            phases, persistence, live_requests, GAP_BETWEEN_QUERIES_S, QUERY_BUDGET_S,
            budget_note, extension_used,
        )
        write_report(report, REPORT_DIR)
        if live_requests > LIVE_BUDGET_CEILING:
            logger.error("Live budget ceiling exceeded: %d > %d", live_requests, LIVE_BUDGET_CEILING)
    finally:
        discard_profiles(all_profiles)


# FUNCTIONS

def build_search_url(query: str) -> str:
    return SEARCH_URL.format(quote_plus(query))


async def run_phase(name: str, description: str, profile_dir: str, queries: list[str], bundle_path: Path) -> Phase:
    phase = Phase(name=name, description=description, profile_dir=profile_dir)
    handle = await launch_browser(profile_dir, bundle_path)
    try:
        await verify_environment_reachable(handle, CONTROL_URL)
        for index, query in enumerate(queries):
            if index:
                await asyncio.sleep(GAP_BETWEEN_QUERIES_S)
            logger.warning("%s: query %d/%d: %s", name, index + 1, len(queries), query)
            measurement = await run_query(handle, query, build_search_url(query))
            logger.warning(
                "%s: %s -> challenge_served=%s final_state=%s verdict=%s total_ms=%s",
                name, query, measurement.challenge_served, measurement.final_state,
                measurement.verdict, measurement.total_ms,
            )
            phase.measurements.append(measurement)
    finally:
        await teardown(handle)
    return phase


def any_challenge_served(phase: Phase) -> bool:
    return any(m.challenge_served for m in phase.measurements)


def snapshot_cookie_store(profile_dir: str) -> dict:
    path = Path(profile_dir) / "Default" / "Cookies"
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {"path": str(path), "exists": True, "size_bytes": stat.st_size, "mtime": stat.st_mtime}


def _cookie_identity(fingerprint: dict) -> tuple:
    return (
        fingerprint["name"], fingerprint["domain"], fingerprint["path"], fingerprint["value_sha256_12"]
    )


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
        "brave_cookies_at_end_of_phase_a": end_of_cold,
        "brave_cookies_at_start_of_phase_c": start_of_warm,
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(probe_workflow())
