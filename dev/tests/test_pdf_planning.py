# INFRASTRUCTURE
import pytest

from src.pdf.extract import PARALLEL_WORKERS, plan_batches


# FUNCTIONS

@pytest.mark.parametrize("pages, count, first, last", [
    (993, 20, (1, 50), (951, 993)),
    (1000, 20, (1, 50), (951, 1000)),
    (1001, 21, (1, 50), (1001, 1001)),
    (1050, 21, (1, 50), (1001, 1050)),
    (50, 1, (1, 50), (1, 50)),
    (51, 2, (1, 50), (51, 51)),
    (100, 2, (1, 50), (51, 100)),
])
def test_plan_batches_covers_every_page_in_fifties(pages, count, first, last):
    batches = plan_batches(pages)
    assert len(batches) == count
    assert batches[0] == first
    assert batches[-1] == last
    covered = [page for start, end in batches for page in range(start, end + 1)]
    assert covered == list(range(1, pages + 1))


def test_a_book_of_one_thousand_pages_fits_one_wave_of_workers():
    assert len(plan_batches(1000)) <= PARALLEL_WORKERS
    assert len(plan_batches(1001)) > PARALLEL_WORKERS


def test_parallel_workers_are_twenty():
    assert PARALLEL_WORKERS == 20
