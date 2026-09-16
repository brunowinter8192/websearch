import pytest

from src.crawler.seed_feeders_scope import normalize_url, scope_and_dedup


# ---------------------------------------------------------------------------
# normalize_url — merge-vs-keep-distinct boundary (see seed_feeders_scope.py docstring)
# ---------------------------------------------------------------------------

def test_normalize_url_lowercases_scheme_and_host():
    assert normalize_url("HTTP://Example.COM/a") == "http://example.com/a"


def test_normalize_url_strips_default_port():
    assert normalize_url("https://example.com:443/a") == "https://example.com/a"
    assert normalize_url("http://example.com:80/a") == "http://example.com/a"


def test_normalize_url_keeps_non_default_port():
    assert normalize_url("https://example.com:8443/a") == "https://example.com:8443/a"


def test_normalize_url_collapses_empty_path_to_root():
    assert normalize_url("https://example.com") == "https://example.com/"


def test_normalize_url_drops_fragment():
    assert normalize_url("https://example.com/a#section") == "https://example.com/a"


def test_normalize_url_keeps_query_string_verbatim():
    assert normalize_url("https://example.com/a?page=2") == "https://example.com/a?page=2"


def test_normalize_url_keeps_non_root_trailing_slash_distinct():
    assert normalize_url("https://example.com/a/") == "https://example.com/a/"
    assert normalize_url("https://example.com/a/") != normalize_url("https://example.com/a")


def test_normalize_url_preserves_legacy_params_segment():
    # urlparse would split ";jsessionid=ABC" into its own .params field and drop it on rebuild;
    # normalize_url uses urlsplit specifically so this stays part of path (review note #3)
    assert normalize_url("https://example.com/a;jsessionid=ABC") == "https://example.com/a;jsessionid=ABC"


def test_normalize_url_raises_on_bad_port():
    with pytest.raises(ValueError):
        normalize_url("https://example.com:notaport/a")


# ---------------------------------------------------------------------------
# scope_and_dedup — host scope + the same merge boundary applied end-to-end
# ---------------------------------------------------------------------------

def test_scope_and_dedup_drops_foreign_host():
    urls = ["https://docs.example.com/a", "https://evil.example.org/a"]
    assert scope_and_dedup(urls, "docs.example.com") == ["https://docs.example.com/a"]


def test_scope_and_dedup_collapses_www_and_apex_keeping_first_seen():
    urls = ["https://www.example.com/a", "https://example.com/a"]
    result = scope_and_dedup(urls, "example.com")
    assert result == ["https://www.example.com/a"]


def test_scope_and_dedup_scope_check_ignores_www_on_seed_host_too():
    urls = ["https://www.example.com/a"]
    assert scope_and_dedup(urls, "www.example.com") == ["https://www.example.com/a"]


def test_scope_and_dedup_keeps_distinct_query_strings():
    urls = ["https://example.com/a?page=1", "https://example.com/a?page=2"]
    assert scope_and_dedup(urls, "example.com") == urls


def test_scope_and_dedup_keeps_distinct_http_vs_https():
    urls = ["http://example.com/a", "https://example.com/a"]
    assert scope_and_dedup(urls, "example.com") == urls


def test_scope_and_dedup_keeps_distinct_params_segment():
    urls = ["https://example.com/a;p=1", "https://example.com/a;p=2"]
    assert scope_and_dedup(urls, "example.com") == urls


def test_scope_and_dedup_merges_default_port_and_case_duplicates():
    urls = ["https://Example.com:443/a", "https://example.com/a"]
    assert scope_and_dedup(urls, "example.com") == ["https://example.com/a"]


def test_scope_and_dedup_merges_empty_path_and_root_slash():
    urls = ["https://example.com", "https://example.com/"]
    assert scope_and_dedup(urls, "example.com") == ["https://example.com/"]


def test_scope_and_dedup_drops_malformed_url_without_raising():
    urls = ["https://example.com:notaport/a", "https://example.com/b"]
    assert scope_and_dedup(urls, "example.com") == ["https://example.com/b"]


def test_scope_and_dedup_preserves_first_seen_order():
    urls = ["https://example.com/c", "https://example.com/a", "https://example.com/c"]
    assert scope_and_dedup(urls, "example.com") == ["https://example.com/c", "https://example.com/a"]
