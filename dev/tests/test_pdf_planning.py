# INFRASTRUCTURE
import pytest

from src.pdf.extract import plan_batches, worker_limit

GIB = 1024 ** 3


# FUNCTIONS

@pytest.mark.parametrize("pages, count, first, last", [
    (993, 25, (1, 40), (961, 993)),
    (1000, 25, (1, 40), (961, 1000)),
    (1050, 27, (1, 40), (1041, 1050)),
    (40, 1, (1, 40), (1, 40)),
    (41, 2, (1, 40), (41, 41)),
    (80, 2, (1, 40), (41, 80)),
])
def test_plan_batches_covers_every_page_in_forties(pages, count, first, last):
    batches = plan_batches(pages)
    assert len(batches) == count
    assert batches[0] == first
    assert batches[-1] == last
    covered = [page for start, end in batches for page in range(start, end + 1)]
    assert covered == list(range(1, pages + 1))


@pytest.mark.parametrize("available_gb, batch_count, expected", [
    (17.2, 25, 9),
    (40.0, 25, 20),
    (40.0, 2, 2),
    (9.5, 25, 1),
    (6.0, 25, 1),
])
def test_worker_limit_follows_free_ram_and_is_capped(available_gb, batch_count, expected):
    assert worker_limit(int(available_gb * GIB), batch_count) == expected
