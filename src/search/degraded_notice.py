# INFRASTRUCTURE
import re

from src.search import status_error as SE
from src.search import status_timeout as ST

DEGRADED_ENGINE_FAILURE_RATIO: float = 0.30
BROWSER_REPAIR_COMMAND: str = "./venv/bin/python -m patchright install chromium"
BROWSER_NEVER_STARTED_PREFIX: str = "Failed to get browser ws address"
DROP_REASON_MAX_LEN: int = 120
_NAVIGATION_URL_PATTERN = re.compile(r"^Navigation to \S+ failed:")
_FAILURE_STATUSES: frozenset[str] = frozenset({
    SE.ERROR_BROWSER, SE.ERROR_HTTP, SE.ERROR_PARSE, SE.ERROR_OTHER,
    ST.TIMEOUT_WATCHDOG, ST.TIMEOUT_NONCOOP, ST.TIMEOUT_HTTPX,
})


# FUNCTIONS

def _prepend_degraded_notice(breakdown_text: str, engine_stats: dict) -> str:
    notice = _format_degraded_notice(engine_stats)
    if notice is None:
        return breakdown_text
    return f"{notice}\n\n{breakdown_text}"


def _format_degraded_notice(engine_stats: dict) -> str | None:
    total = len(engine_stats)
    failing = _failing_engines(engine_stats)
    if not total or len(failing) / total < DEGRADED_ENGINE_FAILURE_RATIO:
        return None
    lines = [f"Engine failures: {len(failing)}/{total} selected engines returned an error or timeout status."]
    lines += [_format_failing_line(name, status, drop_reason) for name, status, drop_reason in failing]
    if any(_is_browser_never_started(status, drop_reason) for _, status, drop_reason in failing):
        lines.append(f"Repair: {BROWSER_REPAIR_COMMAND}")
    return "\n".join(lines)


def _failing_engines(engine_stats: dict) -> list[tuple[str, str, str | None]]:
    return [
        (name, stats["status"], stats.get("drop_reason")) for name, stats in engine_stats.items()
        if stats["status"] in _FAILURE_STATUSES
    ]


def _format_failing_line(name: str, status: str, drop_reason: str | None) -> str:
    return f"  {name:<20} {status:<18} {_shorten_drop_reason(drop_reason)}".rstrip()


def _shorten_drop_reason(drop_reason: str | None) -> str:
    if not drop_reason:
        return ""
    if drop_reason.startswith(BROWSER_NEVER_STARTED_PREFIX):
        drop_reason = drop_reason.split(" ssl:default")[0]
    else:
        drop_reason = _NAVIGATION_URL_PATTERN.sub("Navigation failed:", drop_reason)
    return drop_reason[:DROP_REASON_MAX_LEN]


def _is_browser_never_started(status: str, drop_reason: str | None) -> bool:
    return status == SE.ERROR_BROWSER and bool(drop_reason) and drop_reason.startswith(BROWSER_NEVER_STARTED_PREFIX)
