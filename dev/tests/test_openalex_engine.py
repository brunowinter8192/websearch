"""Tests for src/search/engines/openalex.py (2026 API migration + pdf_url threading).

No network — httpx.AsyncClient is monkeypatched with a fake client that records the request
params and returns a canned response, following the pattern established in test_seed_feeders.py.
Also covers the pdf_url chain through build_engine_pools (merge.py) and format_engine_pool
(cache.py), the same two links date.py had to be threaded through.
"""
import pytest

from src.search.cache import format_engine_pool
from src.search.engines.openalex import OpenAlexEngine, _extract_pdf_url, _parse_results
from src.search.merge import build_engine_pools
from src.search.result import SearchResult
import src.search.engines.openalex as openalex_mod


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeAsyncClient:
    """Records the last GET's params; returns a fixed response regardless of URL."""

    def __init__(self, response: _FakeResponse, capture: dict, *a, **kw):
        self._response = response
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None, **kwargs):
        self._capture["url"] = url
        self._capture["params"] = params
        return self._response


def _install_fake_client(monkeypatch, response: _FakeResponse) -> dict:
    capture: dict = {}
    monkeypatch.setattr(
        openalex_mod.httpx, "AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(response, capture, *a, **kw),
    )
    return capture


def _work(title="A Study", oa_url="https://openalex.org/W1", pdf_url="__unset__"):
    work = {
        "title": title,
        "ids": {},
        "doi": "https://doi.org/10.1/xyz",
        "id": oa_url,
        "abstract_inverted_index": None,
        "cited_by_count": 0,
        "publication_date": "2018-03-15",
    }
    if pdf_url != "__unset__":
        work["best_oa_location"] = {"pdf_url": pdf_url} if pdf_url is not None else None
    return work


# ---------------------------------------------------------------------------
# _extract_pdf_url / _parse_results
# ---------------------------------------------------------------------------

def test_extract_pdf_url_present():
    work = _work(pdf_url="https://mdpi.com/paper.pdf")
    assert _extract_pdf_url(work) == "https://mdpi.com/paper.pdf"


def test_extract_pdf_url_none_when_best_oa_location_null():
    work = _work(pdf_url=None)
    assert _extract_pdf_url(work) is None


def test_extract_pdf_url_none_when_location_present_but_pdf_url_null():
    work = _work()
    work["best_oa_location"] = {"pdf_url": None}
    assert _extract_pdf_url(work) is None


def test_parse_results_populates_pdf_url_field():
    works = [_work(pdf_url="https://sciencedirect.com/a/pdf")]
    results = _parse_results(works)
    assert len(results) == 1
    assert results[0].pdf_url == "https://sciencedirect.com/a/pdf"


def test_parse_results_pdf_url_none_when_absent():
    works = [_work(pdf_url=None)]
    results = _parse_results(works)
    assert results[0].pdf_url is None


# ---------------------------------------------------------------------------
# search_with_reason: 429 / api_key / mailto / per_page clamp
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_429_carries_http_status_but_reason_stays_none(monkeypatch):
    """429 used to surface a guessed EMPTY_BLOCK verdict; that verdict carried no information the
    observed HTTP status (already in diagnosis) did not already carry, so it is gone — reason is
    now None like every other empty branch, and the real fact (429) lives in diagnosis alone."""
    _install_fake_client(monkeypatch, _FakeResponse(429))
    engine = OpenAlexEngine()
    results, reason, diagnosis = await engine.search_with_reason("noise sleep", max_results=10)
    assert results == []
    assert reason is None
    assert diagnosis == {"http_status": 429}


@pytest.mark.asyncio
async def test_403_stays_plain_empty_no_reason_but_carries_http_status(monkeypatch):
    """403 keeps reason=None (unchanged status/reason semantics) but the diagnosis now carries the
    real observed HTTP status — the exact fact a bare EMPTY verdict used to discard."""
    _install_fake_client(monkeypatch, _FakeResponse(403))
    engine = OpenAlexEngine()
    results, reason, diagnosis = await engine.search_with_reason("noise sleep", max_results=10)
    assert results == []
    assert reason is None
    assert diagnosis == {"http_status": 403}


@pytest.mark.asyncio
async def test_success_with_results_has_no_diagnosis(monkeypatch):
    """A 200 response with non-empty results is a success path — diagnosis-free, no diagnose call paid for."""
    _install_fake_client(monkeypatch, _FakeResponse(200, {"results": [_work()]}))
    engine = OpenAlexEngine()
    results, reason, diagnosis = await engine.search_with_reason("query", max_results=10)
    assert len(results) == 1
    assert reason is None
    assert diagnosis is None


@pytest.mark.asyncio
async def test_success_with_zero_results_carries_http_status(monkeypatch):
    """A 200 response that parses to zero results still returns WITHOUT results, so it carries the
    observed HTTP status even though reason stays None (unchanged)."""
    _install_fake_client(monkeypatch, _FakeResponse(200, {"results": []}))
    engine = OpenAlexEngine()
    results, reason, diagnosis = await engine.search_with_reason("query", max_results=10)
    assert results == []
    assert reason is None
    assert diagnosis == {"http_status": 200}


@pytest.mark.asyncio
async def test_api_key_sent_when_env_var_set(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "secretkey123")
    capture = _install_fake_client(monkeypatch, _FakeResponse(200, {"results": []}))
    engine = OpenAlexEngine()
    await engine.search_with_reason("query", max_results=10)
    assert capture["params"]["api_key"] == "secretkey123"
    assert "mailto" not in capture["params"]


@pytest.mark.asyncio
async def test_api_key_absent_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    capture = _install_fake_client(monkeypatch, _FakeResponse(200, {"results": []}))
    engine = OpenAlexEngine()
    await engine.search_with_reason("query", max_results=10)
    assert "api_key" not in capture["params"]
    assert "mailto" not in capture["params"]


@pytest.mark.asyncio
async def test_per_page_clamped_to_100(monkeypatch):
    capture = _install_fake_client(monkeypatch, _FakeResponse(200, {"results": []}))
    engine = OpenAlexEngine()
    await engine.search_with_reason("query", max_results=200)
    assert capture["params"]["per_page"] == 100


@pytest.mark.asyncio
async def test_per_page_untouched_when_under_cap(monkeypatch):
    capture = _install_fake_client(monkeypatch, _FakeResponse(200, {"results": []}))
    engine = OpenAlexEngine()
    await engine.search_with_reason("query", max_results=10)
    assert capture["params"]["per_page"] == 10


@pytest.mark.asyncio
async def test_search_base_method_returns_plain_list(monkeypatch):
    _install_fake_client(monkeypatch, _FakeResponse(200, {"results": [_work(pdf_url="https://x.com/p.pdf")]}))
    engine = OpenAlexEngine()
    results = await engine.search("query", max_results=10)
    assert len(results) == 1
    assert results[0].pdf_url == "https://x.com/p.pdf"


class _RaisingAsyncClient:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None, **kwargs):
        raise RuntimeError("simulated network failure")


@pytest.mark.asyncio
async def test_search_base_method_propagates_exception(monkeypatch):
    """2026-09-09: search()'s own try/except that swallowed exceptions into [] was removed — a
    code-standards violation (silently hiding an error affecting business logic). search() now
    inherits BaseEngine's plain delegation to search_with_reason and lets an exception through
    unchanged."""
    monkeypatch.setattr(openalex_mod.httpx, "AsyncClient", lambda *a, **kw: _RaisingAsyncClient())
    engine = OpenAlexEngine()
    with pytest.raises(RuntimeError):
        await engine.search("query", max_results=10)


# ---------------------------------------------------------------------------
# pdf_url chain: build_engine_pools (merge.py)
# ---------------------------------------------------------------------------

def test_build_engine_pools_preserves_pdf_url_on_winner():
    r = SearchResult(
        url="https://doi.org/10.1/x", title="T", snippet="S", engine="openalex", position=1,
        pdf_url="https://publisher.com/x.pdf",
    )
    pools = build_engine_pools([r])
    assert pools["openalex"][0].pdf_url == "https://publisher.com/x.pdf"


def test_build_engine_pools_pdf_url_none_when_absent():
    r = SearchResult(url="https://doi.org/10.1/y", title="T", snippet="S", engine="openalex", position=1)
    pools = build_engine_pools([r])
    assert pools["openalex"][0].pdf_url is None


# ---------------------------------------------------------------------------
# pdf_url chain: format_engine_pool (cache.py)
# ---------------------------------------------------------------------------

def test_format_engine_pool_renders_pdf_line_when_present():
    pool = [{"position": 1, "title": "T", "url": "https://doi.org/x", "pdf_url": "https://pub.com/x.pdf", "snippet": ""}]
    out = format_engine_pool(pool, "openalex", "q")
    lines = out.splitlines()
    url_idx = next(i for i, l in enumerate(lines) if l.startswith("   URL:"))
    assert lines[url_idx + 1] == "   PDF: https://pub.com/x.pdf"


def test_format_engine_pool_no_pdf_line_when_pdf_url_none():
    pool = [{"position": 1, "title": "T", "url": "https://doi.org/x", "pdf_url": None, "snippet": ""}]
    out = format_engine_pool(pool, "openalex", "q")
    assert "PDF:" not in out


def test_format_engine_pool_no_pdf_line_when_key_missing():
    # Simulates a pre-change cache entry written before pdf_url existed
    pool = [{"position": 1, "title": "T", "url": "https://doi.org/x", "snippet": ""}]
    out = format_engine_pool(pool, "openalex", "q")
    assert "PDF:" not in out
