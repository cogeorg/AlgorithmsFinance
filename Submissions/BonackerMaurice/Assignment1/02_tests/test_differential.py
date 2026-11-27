"""Differential test A vs B-sorted vs B-heap on 300 seeded random streams.

Same streams as `python 02_tests/differential.py` (which also saves
05_results/differential_tests.csv). See differential.py for what is compared.
"""

import pytest

from differential import run_streams


@pytest.mark.source("differential: A vs B-sorted vs B-heap (300 generated streams)")
@pytest.mark.cross_version
def test_versions_agree_after_every_event():
    rows = run_streams(n_streams=300, first_seed=0)
    assert len(rows) == 300
    assert all(50 <= r["events"] <= 300 for r in rows)
    # The streams must actually exercise the interesting cases.
    assert sum(r["crossing_limits"] for r in rows) > 0
    assert sum(r["market_sells"] for r in rows) > 0
    assert sum(r["cancelled"] for r in rows) > 0
    assert sum(r["not_found"] for r in rows) > 0
    assert sum(r["rejected"] for r in rows) > 0
    failed = [(r["seed"], r["first_problem"]) for r in rows if r["result"] != "pass"]
    assert failed == []
