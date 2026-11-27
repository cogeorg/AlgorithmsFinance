"""Bug 4: make_queries' "absent" queries are only absent when every ID is even and >= 0.

The docstring promises round(q * hit_rate) present queries and "the rest absent"; the README
says absent queries are "guaranteed absent". The function accepts any ID list, but it only
draws odd numbers from 1 .. 2*max(ids)+3. Both tests FAIL on the audited commit.
Her saved results are NOT affected (her own generator only produces even IDs >= 0).

Run from Submissions/BundschuhBastian/:
    .venv/bin/python -m pytest -q audit_HuangJiaxin/reproducers/repro_4_absent_queries_not_absent.py
"""
import _target  # noqa: F401
from data import make_queries


def test_odd_ids_hit_rate_zero_gives_no_hits():
    ids = [1, 3, 5, 7, 9, 11]
    queries = make_queries(ids, 10, 0.0, seed=1)
    hits = sum(x in set(ids) for x in queries)
    assert hits == 0, f"hit_rate 0.0 but {hits} of 10 queries are present: {queries}"


def test_negative_ids_are_accepted():
    ids = [-10, -4]                       # valid integer trade IDs per the specification
    queries = make_queries(ids, 10, 0.5, seed=1)   # ValueError: empty range for randrange()
    assert len(queries) == 10
