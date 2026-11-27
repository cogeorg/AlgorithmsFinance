"""Bug 1: for q = 1 the "mixed" hit rate 0.5 produces 0 present queries.

make_queries uses n_hit = round(q * hit_rate). Python rounds halves to the nearest
even number, so round(0.5) == 0. For q = 1 the "hit rate 0.5" query is therefore the
SAME absent query as "hit rate 0.0". This test FAILS on the audited commit.

Run from Submissions/BundschuhBastian/:
    .venv/bin/python -m pytest -q audit_HuangJiaxin/reproducers/repro_1_hit_rate_rounding.py
"""
import _target  # noqa: F401
from benchmark import SEED
from data import make_ids, make_queries


def test_q1_mixed_is_not_all_absent():
    for n in (1_000, 10_000, 100_000):                         # the benchmark grid
        ids = make_ids(n, SEED, "none")
        mixed = make_queries(ids, 1, 0.5, SEED)
        absent = make_queries(ids, 1, 0.0, SEED)
        hits = sum(x in set(ids) for x in mixed)
        print(f"n={n}: hit_rate 0.5 -> {mixed}, hit_rate 0.0 -> {absent}, hits = {hits}")
        # Expected by the README ("hit rate 0.5 (mixed)"): the mixed batch differs from
        # the all-absent batch. Actual: identical query, 0 hits.
        assert mixed != absent, f"n={n}: 'mixed' query equals the all-absent query"
