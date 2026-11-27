"""Light tests for the timing script (structure and correctness checks, not speed)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bench_time  # noqa: E402
from membership import METHODS  # noqa: E402


def tiny_run(**kwargs):
    params = dict(sizes=[50], query_counts=[1, 5], hit_rates=["mixed", "all-absent"],
                  repeats=3, target_s=0.0005, seed=1)
    params.update(kwargs)
    return bench_time.run_benchmark(**params)


def test_rows_cover_every_method_phase_and_repeat():
    raw, summary, datasets = tiny_run()
    configs = 1 * 2 * 2
    assert len(datasets) == configs
    assert len(summary) == configs * len(METHODS) * 3
    assert len(raw) == len(summary) * 3
    assert {r["phase"] for r in raw} == {"prepare", "query", "total"}
    assert {r["method"] for r in raw} == set(METHODS)
    assert {r["repeat"] for r in raw} == {1, 2, 3}


def test_summary_is_median_of_raw_repeats():
    import statistics
    raw, summary, _ = tiny_run()
    for row in summary:
        samples = [r["seconds_per_batch"] for r in raw
                   if all(r[key] == row[key] for key in
                          ("n", "q", "hit_rate", "method", "phase"))]
        assert len(samples) == 3
        assert row["median_seconds_per_batch"] == statistics.median(samples)
        assert all(s > 0 for s in samples)


def test_per_query_column_empty_for_prepare_only():
    raw, _, _ = tiny_run()
    for r in raw:
        if r["phase"] == "prepare":
            assert r["seconds_per_query"] == ""
        else:
            assert r["seconds_per_query"] == pytest.approx(r["seconds_per_batch"] / r["q"])


def test_wrong_answers_are_detected():
    """A broken method must make the benchmark fail, not report a time."""
    broken = lambda ids, queries: [True] * len(queries)          # noqa: E731
    original = bench_time.METHODS["hash_v1"]
    bench_time.METHODS["hash_v1"] = broken
    try:
        with pytest.raises(AssertionError):
            tiny_run(hit_rates=["all-absent"], methods=["hash_v1"])
    finally:
        bench_time.METHODS["hash_v1"] = original


def test_gc_is_enabled_afterwards():
    import gc
    tiny_run(sizes=[20], query_counts=[1], hit_rates=["mixed"])
    assert gc.isenabled()


def test_environment_has_required_fields():
    env = bench_time.environment()
    for key in ("python_version", "platform", "machine", "git_commit", "perf_counter"):
        assert key in env
