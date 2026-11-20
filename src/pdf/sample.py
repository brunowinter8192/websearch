# INFRASTRUCTURE
import math
import random
from pathlib import Path

from src.config import SAMPLE_SHARE
from src.pdf.batch_files import page_png
from src.pdf.manifest import book_path, load_manifest
from src.pdf.report import Report, WorkflowError
from src.pdf.sample_runs import (
    STATUS_OPEN, findings_path, load_runs, loop_ended, page_markers, run_dir, sampled_pages, text_sha, write_run,
)
from src.pdf.templates import page_range, read_template, require_filled, substitute

PROMPT_FILE_NAME = "prompt.md"
SAMPLE_BLOCK_PAGES = 50


# ORCHESTRATOR
def sample_workflow(batch_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    runs = load_runs(batch_path)
    require_new_run_allowed(manifest, runs)
    book = book_path(batch_path, manifest).read_text(encoding="utf-8")
    pages = draw_sample_pages(manifest, runs)
    run = write_new_run(manifest, batch_path, runs, pages, cut_excerpts(book, pages), book)
    return Report(format_summary(manifest, batch_path, run, runs), True)


# FUNCTIONS
def require_new_run_allowed(manifest: dict, runs: list[dict]) -> None:
    if runs and runs[-1]["status"] == STATUS_OPEN:
        raise WorkflowError("run_open", f"sample run {runs[-1]['run']} is still open, close it with pdf sample-close")
    if loop_ended(runs, manifest["pages"]):
        raise WorkflowError("loop_ended", f"the sample loop ended with run {runs[-1]['run']}, publish the book")


def draw_sample_pages(manifest: dict, runs: list[dict]) -> list[int]:
    rng = random.Random(f"{manifest['pdf_sha256']}:{len(runs) + 1}")
    done = sampled_pages(runs)
    drawn = []
    for first in range(1, manifest["pages"] + 1, SAMPLE_BLOCK_PAGES):
        last = min(first + SAMPLE_BLOCK_PAGES - 1, manifest["pages"])
        fresh = [page for page in range(first, last + 1) if page not in done]
        drawn += rng.sample(fresh, min(math.ceil(SAMPLE_SHARE * (last - first + 1)), len(fresh)))
    return sorted(drawn)


def cut_excerpts(book: str, pages: list[int]) -> list[dict]:
    markers = ordered_markers(book)
    regions = [excerpt_region(markers, len(book), page) for page in pages]
    excerpts: list[dict] = []
    for start, end, page in regions:
        if excerpts and start < excerpts[-1]["end"]:
            excerpts[-1]["end"] = max(end, excerpts[-1]["end"])
            excerpts[-1]["pages"].append(page)
        else:
            excerpts.append({"pages": [page], "start": start, "end": end})
    for excerpt in excerpts:
        excerpt["file"] = f"excerpt_{page_range(excerpt['pages'][0], excerpt['pages'][-1])}.md"
        excerpt["original"] = book[excerpt["start"]:excerpt["end"]]
    return excerpts


def ordered_markers(book: str) -> list[tuple[int, int]]:
    markers = page_markers(book)
    numbers = [page for page, _ in markers]
    if numbers != sorted(set(numbers)):
        raise WorkflowError("page_markers_out_of_order", "the page markers of the book are not in strictly rising order")
    return markers


def excerpt_region(markers: list[tuple[int, int]], length: int, page: int) -> tuple[int, int, int]:
    before = [offset for number, offset in markers if number < page]
    after = [offset for number, offset in markers if number > page]
    return (before[-1] if before else 0, after[0] if after else length, page)


def write_new_run(manifest: dict, batch_dir: Path, runs: list[dict], pages: list[int], excerpts: list[dict], book: str) -> dict:
    number = len(runs) + 1
    directory = run_dir(batch_dir, number)
    directory.mkdir(parents=True)
    for excerpt in excerpts:
        (directory / excerpt["file"]).write_text(excerpt["original"], encoding="utf-8")
    run = {"run": number, "status": STATUS_OPEN, "pages": pages, "book_sha256": text_sha(book), "excerpts": excerpts}
    write_run(batch_dir, run)
    (directory / PROMPT_FILE_NAME).write_text(render_sample_prompt(manifest, batch_dir, run), encoding="utf-8")
    return run


def render_sample_prompt(manifest: dict, batch_dir: Path, run: dict) -> str:
    directory = run_dir(batch_dir, run["run"])
    steps = [
        excerpt_steps(1 + 3 * index, batch_dir, directory / excerpt["file"], excerpt)
        for index, excerpt in enumerate(run["excerpts"])
    ]
    write_number = 1 + 3 * len(run["excerpts"])
    values = {
        "PDF": manifest["pdf"],
        "RUN": str(run["run"]),
        "PAGES": " ".join(str(page) for page in run["pages"]),
        "FINDINGS": str(findings_path(batch_dir, run)),
        "EXCERPT_STEPS": "\n".join(steps),
        "WRITE_NUMBER": str(write_number),
        "DONE_NUMBER": str(write_number + 1),
    }
    return require_filled(substitute(read_template("sample_prompt.md"), values))


def excerpt_steps(read_number: int, batch_dir: Path, path: Path, excerpt: dict) -> str:
    images = [str(batch_dir / page_png(page)) for page in excerpt["pages"]]
    values = {
        "READ_NUMBER": str(read_number),
        "IMAGE_NUMBER": str(read_number + 1),
        "EDIT_NUMBER": str(read_number + 2),
        "EXCERPT": str(path),
        "IMAGES": " ".join(images),
        "CHECK_PAGES": page_range(excerpt["pages"][0], excerpt["pages"][-1]),
    }
    return substitute(read_template("sample_excerpt_steps.md").rstrip("\n"), values)


def format_summary(manifest: dict, batch_dir: Path, run: dict, earlier: list[dict]) -> str:
    done = len(sampled_pages(earlier)) + len(run["pages"])
    return "\n".join([
        f"sample run {run['run']} open: {run_dir(batch_dir, run['run'])}",
        "pages: " + " ".join(str(page) for page in run["pages"]),
        "excerpts: " + " ".join(excerpt["file"] for excerpt in run["excerpts"]),
        f"prompt: {run_dir(batch_dir, run['run']) / PROMPT_FILE_NAME}",
        f"pages sampled after this run: {done} of {manifest['pages']}",
    ])
