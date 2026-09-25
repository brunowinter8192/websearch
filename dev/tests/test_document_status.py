# INFRASTRUCTURE
import pytest

from src.search.document_status import attach_document_status, start_document_status_capture


# FUNCTIONS

@pytest.mark.asyncio
async def test_collects_ordered_main_frame_document_statuses():
    tab = _FakeTab(target_id="T1")
    chain = await start_document_status_capture(tab)
    tab.fire({"params": {"type": "Document", "frameId": "T1", "response": {"status": 403}}})
    tab.fire({"params": {"type": "Document", "frameId": "T1", "response": {"status": 200}}})
    assert chain == [403, 200]


@pytest.mark.asyncio
async def test_ignores_non_document_resource_type():
    tab = _FakeTab(target_id="T1")
    chain = await start_document_status_capture(tab)
    tab.fire({"params": {"type": "Script", "frameId": "T1", "response": {"status": 200}}})
    tab.fire({"params": {"type": "XHR", "frameId": "T1", "response": {"status": 200}}})
    assert chain == []


@pytest.mark.asyncio
async def test_ignores_other_frames_iframe_documents():
    tab = _FakeTab(target_id="T1")
    chain = await start_document_status_capture(tab)
    tab.fire({"params": {"type": "Document", "frameId": "IFRAME_ID", "response": {"status": 200}}})
    assert chain == []


@pytest.mark.asyncio
async def test_setup_failure_propagates_instead_of_degrading_to_an_empty_chain():
    tab = _BrokenTab(target_id="T1")
    with pytest.raises(RuntimeError, match="cdp boom"):
        await start_document_status_capture(tab)


def test_last_entry_of_chain_is_http_status_not_first_hop():
    diag = {"marker": None}
    merged = attach_document_status(diag, [403, 302, 200])
    assert merged["http_status"] == 200
    assert merged["document_status_chain"] == [403, 302, 200]
    assert merged["marker"] is None


def test_empty_chain_yields_none_http_status_not_a_fabricated_default():
    merged = attach_document_status({}, [])
    assert merged["http_status"] is None
    assert merged["document_status_chain"] == []


def test_does_not_mutate_the_input_diag_dict():
    diag = {"marker": "captcha"}
    attach_document_status(diag, [200])
    assert diag == {"marker": "captcha"}


class _FakeTab:
    def __init__(self, target_id: str = "T1"):
        self._target_id = target_id
        self._callback = None

    async def enable_network_events(self):
        pass

    async def on(self, event_name, callback):
        self._callback = callback
        return 1

    def fire(self, event: dict) -> None:
        self._callback(event)


class _BrokenTab(_FakeTab):
    async def enable_network_events(self):
        raise RuntimeError("cdp boom")
