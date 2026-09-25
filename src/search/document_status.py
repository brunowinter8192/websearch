# INFRASTRUCTURE
import time

from pydoll.protocol.network.events import NetworkEvent
from pydoll.protocol.network.types import ResourceType


# FUNCTIONS

async def start_document_status_capture(tab) -> list[int]:
    status_chain: list[int] = []
    main_frame_id = tab._target_id

    def _on_response(event: dict) -> None:
        params = event.get("params") or {}
        if params.get("type") != ResourceType.DOCUMENT:
            return
        if params.get("frameId") != main_frame_id:
            return
        status = (params.get("response") or {}).get("status")
        if status is not None:
            status_chain.append(status)

    await tab.enable_network_events()
    await tab.on(NetworkEvent.RESPONSE_RECEIVED, _on_response)
    return status_chain


def update_partial(partial: dict | None, status_chain: list[int], t0: float, facts: dict) -> None:
    if partial is None:
        return
    snapshot = attach_document_status(facts, status_chain)
    snapshot["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
    partial.clear()
    partial.update(snapshot)


def attach_document_status(diag: dict, status_chain: list[int]) -> dict:
    return {
        **diag,
        "document_status_chain": list(status_chain),
        "http_status": status_chain[-1] if status_chain else None,
    }
