# INFRASTRUCTURE
import json
from pathlib import Path

from src.crawler.deep_dive_closing import (
    backup_classes, build_closing_record, collection_facts, cut_facts, deep_dive_closing_workflow,
    failed_facts, index_facts, parse_cut_file,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deep_dive"
DOMAIN = "sre.google"


# FUNCTIONS

def test_parse_cut_file_counts_passages_lines_and_files_of_a_single_line_class():
    facts = parse_cut_file((FIXTURES / "cut_book_footer_sample.md").read_text(encoding="utf-8"))

    assert facts == {"passages": 4, "lines": 4, "files": 1}


def test_parse_cut_file_counts_lines_from_the_header_ranges():
    facts = parse_cut_file((FIXTURES / "cut_book_toc_sample.md").read_text(encoding="utf-8"))

    assert facts == {"passages": 2, "lines": 104, "files": 2}


def test_index_facts_read_the_done_line_of_a_real_index_log():
    facts = index_facts(FIXTURES / "index_sre_sample.log")

    assert facts["done"] == {"files": 205, "chunks": 3222, "skipped": 997, "adopted": 0}
    assert facts["errors"] == []


def test_index_facts_keep_the_error_line_and_have_no_done_line():
    facts = index_facts(FIXTURES / "index_busy_error.log")

    assert facts["done"] is None
    assert len(facts["errors"]) == 1 and facts["errors"][0].startswith("Error: rag busy")


def test_index_facts_report_a_missing_log_as_absent(tmp_path):
    facts = index_facts(tmp_path / "missing_index.log")

    assert facts["log_exists"] is False
    assert facts["done"] is None


def test_cut_facts_take_the_class_from_the_file_name(tmp_path):
    (tmp_path / "cut_site_footer_sre.google.md").write_text("a_b.md:1-2\nx\ny\n", encoding="utf-8")
    (tmp_path / "cut_book_toc_sre.google.md").write_text("a_b.md:5-5\nz\n", encoding="utf-8")
    (tmp_path / "cut_site_footer_other.org.md").write_text("c.md:1-1\nq\n", encoding="utf-8")

    facts = cut_facts(tmp_path, DOMAIN)

    assert facts == {
        "book_toc": {"passages": 1, "lines": 1, "files": 1},
        "site_footer": {"passages": 1, "lines": 2, "files": 1},
    }


def test_failed_facts_distinguish_a_missing_dir_from_an_empty_one(tmp_path):
    assert failed_facts(tmp_path / "none_failed") == {"dir_exists": False, "count": 0, "names": []}
    empty = tmp_path / "empty_failed"
    empty.mkdir()
    assert failed_facts(empty) == {"dir_exists": True, "count": 0, "names": []}
    (empty / "blocked.md").write_text("x", encoding="utf-8")
    assert failed_facts(empty) == {"dir_exists": True, "count": 1, "names": ["blocked.md"]}


def test_backup_classes_list_only_pre_backup_directories(tmp_path):
    (tmp_path / "sre.google_PRE_images_BACKUP").mkdir()
    (tmp_path / "sre.google_PRE_site_header_BACKUP").mkdir()
    (tmp_path / "sre.google_PRE_other_BACKUP.txt").write_text("", encoding="utf-8")
    (tmp_path / "other.org_PRE_images_BACKUP").mkdir()

    assert backup_classes(tmp_path, DOMAIN) == ["images", "site_header"]


def test_collection_facts_count_copied_files_and_index_sidecars(tmp_path):
    work, collection = tmp_path / "work", tmp_path / "collection"
    work.mkdir()
    collection.mkdir()
    for name in ("a.md", "b.md", "c.md"):
        (work / name).write_text("x", encoding="utf-8")
    for name in ("a.md", "b.md", "other.md"):
        (collection / name).write_text("x", encoding="utf-8")
    (collection / "a.json").write_text("{}", encoding="utf-8")

    assert collection_facts(work, collection) == {"copied": 2, "with_index_sidecar": 1}
    assert collection_facts(work, tmp_path / "no_collection") is None


def test_closing_record_has_null_for_every_missing_source(tmp_path):
    record = build_closing_record(DOMAIN, "https://sre.google/", "websearch-pages", "need",
                                  tmp_path / "idx.log", tmp_path, tmp_path / "collection")

    assert record["discovered"] is None and record["kept"] is None
    assert record["work_files"] is None and record["collection_files"] is None
    assert record["cuts"] == {} and record["backups"] == []
    assert record["failed"]["dir_exists"] is False
    assert record["index"]["log_exists"] is False


def test_closing_workflow_reads_a_deep_dive_tree_and_writes_one_record(tmp_path, monkeypatch):
    tmp_dir, documents = tmp_path / "tmp", tmp_path / "documents"
    log_file = tmp_path / "deep_dive_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_DEEP_DIVE_LOG_PATH", str(log_file))
    (tmp_dir / DOMAIN).mkdir(parents=True)
    (documents / "websearch-pages").mkdir(parents=True)
    (tmp_dir / f"{DOMAIN}_urls.txt").write_text("https://sre.google/\nhttps://sre.google/a\nhttps://sre.google/b\n", encoding="utf-8")
    (tmp_dir / f"{DOMAIN}_urls_culled.txt").write_text("https://sre.google/\nhttps://sre.google/a\n\n", encoding="utf-8")
    for name in ("sre_google.md", "sre_google_a.md"):
        (tmp_dir / DOMAIN / name).write_text("<!-- source: x -->\nbody", encoding="utf-8")
        (documents / "websearch-pages" / name).write_text("body", encoding="utf-8")
    (documents / "websearch-pages" / "sre_google.json").write_text("{}", encoding="utf-8")
    (tmp_dir / "websearch-pages_index.log").write_text((FIXTURES / "index_sre_sample.log").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_dir / f"cut_images_{DOMAIN}.md").write_text("sre_google.md:5-5\n![x](y)\n", encoding="utf-8")

    deep_dive_closing_workflow(DOMAIN, "https://sre.google/", "websearch-pages", "SLI material", None, tmp_dir, documents)

    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["record_type"] == "closing"
    assert (record["discovered"], record["kept"]) == (3, 2)
    assert record["work_files"] == {"count": 2, "bytes": 2 * len("<!-- source: x -->\nbody")}
    assert record["collection_files"] == {"copied": 2, "with_index_sidecar": 1}
    assert record["cuts"] == {"images": {"passages": 1, "lines": 1, "files": 1}}
    assert record["index"]["done"]["files"] == 205
    assert record["info_need"] == "SLI material"
    assert record["host"] == "sre.google"
