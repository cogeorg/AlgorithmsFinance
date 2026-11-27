"""Tests for the synthetic data generator."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datagen import DUPLICATE_POLICIES, HIT_RATES, generate  # noqa: E402

SIZES = [(0, 0), (0, 5), (1, 1), (1, 100), (7, 3), (1000, 1), (1000, 100), (5000, 100)]


@pytest.mark.parametrize("n,q", SIZES)
@pytest.mark.parametrize("hit_rate", HIT_RATES)
@pytest.mark.parametrize("duplicates", list(DUPLICATE_POLICIES))
def test_shape_and_hit_rate(n, q, hit_rate, duplicates):
    if n == 0 and hit_rate != "all-absent" and q > 0 and (q + 1) // 2 > 0:
        with pytest.raises(ValueError):
            generate(n, q, hit_rate, duplicates, seed=1)
        return
    d = generate(n, q, hit_rate, duplicates, seed=1)
    assert len(d.ids) == n and len(d.queries) == q and len(d.expected) == q
    ids = set(d.ids)
    assert d.expected == [x in ids for x in d.queries]      # expected is truthful
    hits = sum(d.expected)
    assert hits == {"all-present": q, "all-absent": 0, "mixed": (q + 1) // 2}[hit_rate]
    assert len(ids) == math.ceil(DUPLICATE_POLICIES[duplicates] * n)


def test_same_seed_same_data():
    a = generate(500, 50, "mixed", "some", seed=42)
    b = generate(500, 50, "mixed", "some", seed=42)
    assert a == b


def test_different_seed_different_data():
    a = generate(500, 50, "mixed", "some", seed=1)
    b = generate(500, 50, "mixed", "some", seed=2)
    assert a.ids != b.ids and a.queries != b.queries


def test_global_random_state_unused():
    import random
    random.seed(5)
    before = random.random()
    random.seed(5)
    generate(100, 10, seed=3)
    assert random.random() == before


def test_array_is_not_sorted_for_larger_n():
    d = generate(1000, 1, "all-present", "none", seed=7)
    assert d.ids != sorted(d.ids)


def test_absent_queries_reach_below_and_above_the_array():
    d = generate(2000, 2000, "all-absent", "none", seed=9)
    assert any(x < min(d.ids) for x in d.queries)
    assert any(x > max(d.ids) for x in d.queries)
    assert any(min(d.ids) < x < max(d.ids) for x in d.queries)


def test_duplicates_actually_repeat():
    d = generate(1000, 1, "all-present", "many", seed=4)
    assert len(set(d.ids)) == 100 and len(d.ids) == 1000


def test_settings_recorded():
    d = generate(10, 4, "mixed", "none", seed=11)
    assert d.settings == {"n": 10, "q": 4, "hit_rate": "mixed", "duplicates": "none",
                          "seed": 11, "id_universe": 110}


@pytest.mark.parametrize("bad", [dict(n=-1, q=1), dict(n=1, q=-1),
                                 dict(n=1, q=1, hit_rate="half"),
                                 dict(n=1, q=1, duplicates="lots")])
def test_bad_arguments(bad):
    with pytest.raises(ValueError):
        generate(**bad)
