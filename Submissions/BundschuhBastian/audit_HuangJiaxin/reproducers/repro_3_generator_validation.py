"""Bug 3 (minor): make_queries returns more than q queries for hit_rate outside [0, 1].

The docstring promises "q queries"; there is no input check. This test FAILS.
Not used by the benchmark grid (hit rates 0, 0.5, 1), so no saved result is affected.

Run from Submissions/BundschuhBastian/:
    .venv/bin/python -m pytest -q audit_HuangJiaxin/reproducers/repro_3_generator_validation.py
"""
import pytest

import _target  # noqa: F401
from data import make_ids, make_queries


@pytest.mark.parametrize("hit_rate", [1.5, -0.5, 2.0])
def test_returns_q_queries_or_rejects_hit_rate(hit_rate):
    ids = make_ids(100, seed=1)
    try:
        queries = make_queries(ids, 10, hit_rate, seed=1)
    except ValueError:
        return                                                 # rejecting is fine
    assert len(queries) == 10, f"hit_rate={hit_rate}: got {len(queries)} queries, not 10"
