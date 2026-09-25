# INFRASTRUCTURE
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

TREE = Path(os.environ.get("DEV_TREE", Path(__file__).resolve().parents[2]))
EXTRACT_VALUE_MODULES = [
    ("dev/access_recovery/_dom.py", "extract_value"),
    ("dev/brave_return/_brave_probe_query.py", "_extract_value"),
    ("dev/browser_posture/_lib.py", "extract_value"),
    ("dev/mojeek_return/_mojeek_pydoll_probe_query.py", "_extract_value"),
    ("dev/mojeek_return/mojeek_challenge_capture.py", "_extract_value"),
    ("dev/search_pipeline/browser_probes/_date_availability_probe_browser.py", "_extract_value"),
    ("dev/search_pipeline/inspections/inspect_engine_dom.py", "_extract_value"),
    ("dev/search_pipeline/pydoll_fingerprint_probe.py", "_extract_value"),
    ("dev/search_pipeline/browser_probes/25_startpage_probe.py", "_extract_value"),
    ("dev/search_pipeline/browser_probes/26_brave_probe.py", "_extract_value"),
    ("dev/search_pipeline/browser_probes/27_brave_headed_lane_probe.py", "_extract_value"),
    ("dev/search_pipeline/browser_probes/28_bing_probe.py", "_extract_value"),
    ("dev/search_pipeline/browser_probes/29_yandex_probe.py", "_extract_value"),
]
DATE_MODULES = [
    "dev/news_pipeline/01_coindesk_discover.py",
    "dev/news_pipeline/exploration/01_coindesk_ui_probe.py",
    "dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py",
]
SECTION_MODULES = [
    "dev/news_pipeline/01_coindesk_discover.py",
    "dev/news_pipeline/exploration/03_coindesk_backfill_traversal.py",
]
PROXY_CHECK_CASES = [
    ("dev/news_pipeline/theblock/probe_curated_theblock_cf.py", "cffi", "m.check_proxy('http', '1.2.3.4:80')", "False"),
    ("dev/news_pipeline/theblock/probe_repo_cf_survey.py", "cffi", "m.check_proxy('http', '1.2.3.4:80')", "False"),
    ("dev/news_pipeline/theblock/acquire_pipe/p1_fetch.py", "cffi", "m.fetch_url('http', '1.2.3.4:80', 'https://x.test/', 'xml')", "('fail', b'')"),
    ("dev/news_pipeline/theblock/_pipe_theblock_cf.py", "cffi_requests", "m.cf_get('http://1.2.3.4:80', 'https://x.test/')", "(b'', 0)"),
]
POLL_MODULES = [
    "dev/news_pipeline/01_coindesk_discover.py",
    "dev/news_pipeline/exploration/05b_coindesk_warmth_probe.py",
    "dev/news_pipeline/exploration/_03_capture.py",
    "dev/news_pipeline/exploration/_04_capture.py",
    "dev/news_pipeline/exploration/_05_capture.py",
    "dev/news_pipeline/exploration/_06_capture.py",
]


# FUNCTIONS

@pytest.mark.parametrize("rel,name", EXTRACT_VALUE_MODULES)
def test_extract_value_reports_what_it_drops(rel, name):
    proc = run_child(rel, f"print('RESULT', repr(m.{name}({{}})))")
    assert "RESULT None" in proc.stdout
    assert "extract_value: dropped KeyError" in proc.stderr


@pytest.mark.parametrize("rel", DATE_MODULES)
def test_parse_url_date_reports_an_invalid_calendar_date(rel):
    proc = run_child(rel, "print('RESULT', repr(m.parse_url_date('https://x.test/2024/13/45/a')))")
    assert "RESULT None" in proc.stdout
    assert "parse_url_date: dropped" in proc.stderr
    assert "https://x.test/2024/13/45/a" in proc.stderr


@pytest.mark.parametrize("rel", SECTION_MODULES)
def test_extract_section_reports_a_url_without_the_host(rel):
    proc = run_child(rel, "print('RESULT', repr(m._extract_section('https://other.test/a')))")
    assert "RESULT 'unknown'" in proc.stdout
    assert "extract_section: dropped IndexError" in proc.stderr


def test_count_renderers_reports_unparsable_pgrep_output():
    code = textwrap.dedent("""
        import subprocess
        class R: stdout = 'not a number'
        m.subprocess.run = lambda *a, **k: R()
        print('RESULT', m._count_renderers())
    """)
    proc = run_child("dev/search_pipeline/24_pydoll_teardown_verify.py", code)
    assert "RESULT 0" in proc.stdout
    assert "count_renderers: dropped" in proc.stderr


def test_decode_altcha_payload_reports_an_undecodable_payload():
    proc = run_child("dev/mojeek_return/_mojeek_pydoll_probe_core.py", "print('RESULT', m._decode_altcha_payload('!!not-base64-json'))")
    assert "RESULT None" in proc.stdout
    assert "decode_altcha_payload: dropped" in proc.stderr


def test_extract_json_sample_reports_a_non_json_body():
    proc = run_child("dev/news_pipeline/exploration/_04_replay.py", "print('RESULT', m.extract_json_sample(b'<html>'))")
    assert "RESULT None" in proc.stdout
    assert "extract_json_sample: dropped" in proc.stderr


@pytest.mark.parametrize("rel,alias,call,expected", PROXY_CHECK_CASES)
def test_proxy_check_counts_the_request_error_it_drops(rel, alias, call, expected):
    code = textwrap.dedent(f"""
        import proxy_rejections
        def boom(*a, **k):
            raise m.{alias}.exceptions.ConnectionError('refused')
        class S:
            def __init__(self, **k): pass
            get = boom
        m.{alias}.Session = S
        print('RESULT', {call}, dict(proxy_rejections.REJECTIONS))
    """)
    proc = run_child(rel, code)
    assert f"RESULT {expected} {{'ConnectionError': 1}}" in proc.stdout


@pytest.mark.parametrize("rel,alias,call,expected", PROXY_CHECK_CASES)
def test_proxy_check_lets_an_unexpected_error_abort(rel, alias, call, expected):
    code = textwrap.dedent(f"""
        class S:
            def __init__(self, **k): pass
            def get(self, *a, **k): raise KeyError('bug')
        m.{alias}.Session = S
        try:
            {call}
            print('RESULT swallowed')
        except KeyError:
            print('RESULT aborted')
    """)
    assert "RESULT aborted" in run_child(rel, code).stdout


@pytest.mark.parametrize("rel", POLL_MODULES)
def test_chrome_poll_reports_the_last_connection_error(rel):
    code = textwrap.dedent("""
        import urllib.error
        def refuse(*a, **k):
            raise urllib.error.URLError('connection refused')
        m.urllib.request.urlopen = refuse
        m.time.sleep = lambda s: None
        try:
            m.wait_for_ws_url(1, timeout=0.05)
        except TimeoutError as exc:
            print('RESULT', exc)
    """)
    proc = run_child(rel, code)
    assert "last error: URLError" in proc.stdout


@pytest.mark.parametrize("rel", POLL_MODULES)
def test_chrome_poll_lets_a_malformed_reply_abort(rel):
    code = textwrap.dedent("""
        import io
        class R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        m.urllib.request.urlopen = lambda *a, **k: R(b'not json')
        m.time.sleep = lambda s: None
        try:
            m.wait_for_ws_url(1, timeout=5)
            print('RESULT swallowed')
        except ValueError:
            print('RESULT aborted')
    """)
    assert "RESULT aborted" in run_child(rel, code).stdout


def test_extract_cursor_reports_a_non_json_body():
    proc = run_child("dev/news_pipeline/exploration/_04_replay.py", "print('RESULT', m.extract_cursor(b'<html>'))")
    assert "RESULT (None, None)" in proc.stdout
    assert "extract_cursor: dropped" in proc.stderr


def test_audit_scan_lets_an_unparse_failure_abort(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text("import logging\nlogger = logging.getLogger()\nlogger.info('x')\n")
    code = textwrap.dedent(f"""
        def boom(node): raise RuntimeError('unparse failed')
        m.ast.unparse = boom
        from pathlib import Path
        try:
            m._scan_file(Path({str(source)!r}))
            print('RESULT swallowed')
        except RuntimeError:
            print('RESULT aborted')
    """)
    assert "RESULT aborted" in run_child("dev/logging/01_audit.py", code).stdout


def test_stop_browser_lets_a_stop_failure_abort():
    code = textwrap.dedent("""
        import asyncio
        class B:
            async def stop(self): raise RuntimeError('stop failed')
        try:
            asyncio.run(m.stop_browser(B()))
            print('RESULT swallowed')
        except RuntimeError:
            print('RESULT aborted')
    """)
    assert "RESULT aborted" in run_child("dev/search_pipeline/_capture_sorry.py", code).stdout


def test_docs_probe_close_failure_aborts_after_the_report_is_written():
    code = textwrap.dedent("""
        import asyncio
        from pathlib import Path
        written = []
        async def bad_close(): raise RuntimeError('close failed')
        m.close_browser = bad_close
        m.write_report = lambda *a, **k: written.append(1) or Path('/tmp/x.md')
        m.QUERIES = []
        try:
            asyncio.run(m._run_docs_queries([], {}))
            print('RESULT swallowed')
        except RuntimeError:
            print('RESULT aborted', len(written))
    """)
    proc = run_child("dev/search_pipeline/domain_probes/20_docs_probe.py", code)
    assert "RESULT aborted 1" in proc.stdout


def test_engine_health_levels_are_words():
    code = textwrap.dedent("""
        s = {'total': 100, 'timeout': 0, 'success_rate': 0.99, 'silent_fail_rate': 0.0, 'dom_fail': '', 'status_counts': {}}
        print('RESULT', m.classify_health(s))
        s2 = dict(s, success_rate=0.2)
        print('RESULT', m.classify_health(s2))
    """)
    proc = run_child("dev/search_pipeline/report_analysis/engine_health_audit.py", code)
    assert "RESULT ('GREEN', 'OK')" in proc.stdout
    assert "RESULT ('RED', 'BROKEN')" in proc.stdout


def run_child(rel: str, body: str) -> subprocess.CompletedProcess:
    path = TREE / rel
    code = textwrap.dedent(f"""
        import importlib.util, sys
        sys.path.insert(0, {str(path.parent)!r})
        sys.path.insert(0, {str(TREE)!r})
        spec = importlib.util.spec_from_file_location('probe_under_test', {str(path)!r})
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    """) + textwrap.dedent(body)
    return subprocess.run([sys.executable, "-c", code], cwd=TREE, capture_output=True, text=True, timeout=60)
