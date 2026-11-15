# INFRASTRUCTURE
from src.pdf.extract import draw_control_pages, plan_batches

SEED = "a" * 64


# FUNCTIONS

def test_every_batch_gets_ceil_of_ten_percent_of_its_pages():
    batches = plan_batches(85)
    pages = draw_control_pages(batches, SEED)
    assert len([page for page in pages if 1 <= page <= 50]) == 5
    assert len([page for page in pages if 51 <= page <= 85]) == 4
    assert pages == sorted(pages)
    assert len(set(pages)) == len(pages)


def test_a_nine_page_scan_gets_exactly_one_control_page():
    pages = draw_control_pages(plan_batches(9), SEED)
    assert len(pages) == 1
    assert 1 <= pages[0] <= 9


def test_a_full_wave_draws_one_hundred_pages_spread_over_every_batch():
    batches = plan_batches(1000)
    pages = draw_control_pages(batches, SEED)
    assert len(pages) == 100
    assert all(any(first <= page <= last for page in pages) for first, last in batches)


def test_same_seed_draws_the_same_pages_and_another_seed_differs():
    batches = plan_batches(500)
    assert draw_control_pages(batches, SEED) == draw_control_pages(batches, SEED)
    assert draw_control_pages(batches, SEED) != draw_control_pages(batches, "b" * 64)
