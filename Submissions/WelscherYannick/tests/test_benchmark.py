"""Tests for the measurement code (not for the measured numbers)."""

import csv
import json

import pytest
from benchmark import COLUMNS, BenchConfig, measure_pair, run_benchmark, scenarios
from interface import Method
from registry import VERSIONS

TINY = BenchConfig(
    sizes=(10, 50), query_counts=(1, 5), hit_rates=(1.0, 0.0, 0.6),
    repeats=2, min_measure_s=1e-4, max_number=1000,
)


def _silent(*args, **kwargs):
    pass


def test_mixed_hit_rate_is_skipped_for_a_single_query():
    combos = [(s.n, s.q, s.hit_rate) for s in scenarios(TINY)]
    assert (10, 1, 0.6) not in combos
    assert (10, 5, 0.6) in combos
    assert len(combos) == 2 * (2 + 3)


def test_measure_pair_builds_fresh_state_and_queries_that_state():
    prepared, queried = [], []

    def prepare(ids):
        state = object()
        prepared.append(state)
        return state

    def query(state, queries):
        queried.append(state)
        return [False] * len(queries)

    res = measure_pair(Method("fake", prepare, query), [1, 2], [3], (3, 4, 2))

    assert len(prepared) == 3 + 2  # preparation phase + combined phase
    assert len(queried) == 4 + 2  # query phase + combined phase
    # The query batch is timed on the state built in this repeat.
    assert all(state is prepared[2] for state in queried[:4])
    # In the combined run every query gets the state prepared right before it.
    assert queried[4] is prepared[3] and queried[5] is prepared[4]
    assert res["prepare_s"] > 0 and res["query_batch_s"] > 0 and res["total_s"] > 0


def test_run_writes_one_raw_row_per_repeat_and_metadata(tmp_path):
    rows, metadata = run_benchmark(TINY, tmp_path, log=_silent)

    with open(tmp_path / "timing_raw.csv", newline="") as f:
        saved = list(csv.DictReader(f))
    n_scenarios = 10
    n_pairs = sum(len(methods) for methods in VERSIONS.values())  # versions x methods
    assert len(saved) == len(rows) == n_scenarios * n_pairs * TINY.repeats
    assert list(saved[0]) == COLUMNS
    assert all(float(r[c]) > 0 for r in saved for c in ("prepare_s", "query_batch_s", "total_s"))
    assert {r["repeat"] for r in saved} == {"0", "1"}

    mixed = [r for r in saved if r["q"] == "5" and r["hit_rate_target"] == "0.6"]
    assert mixed and all(float(r["hit_rate_actual"]) == 0.6 for r in mixed)

    with open(tmp_path / "timing_metadata.json") as f:
        meta = json.load(f)
    for key in ("python_version", "machine", "clock", "code", "config", "units", "scenarios"):
        assert key in meta
    assert len(meta["scenarios"]) == n_scenarios
    assert meta["config"]["repeats"] == 2


def test_wrong_result_stops_the_benchmark(tmp_path):
    wrong = Method("always_true", set, lambda s, queries: [True] * len(queries))
    with pytest.raises(RuntimeError, match="wrong result"):
        run_benchmark(TINY, tmp_path, versions={"bad": {"always_true": wrong}}, log=_silent)
