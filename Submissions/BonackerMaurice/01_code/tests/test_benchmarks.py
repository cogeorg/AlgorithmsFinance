"""Tests for the measurement code: output schema on a tiny grid (fast; not a
benchmark) and the protocol itself (each segment times exactly what it claims)."""
import csv
import json
from pathlib import Path

import pytest

from benchmarks import memory, timing
from benchmarks.config import Grid, write_run_config
from benchmarks.environment import git_info, source_fingerprint
from benchmarks.run import redact
from search_algos import METHODS, Method

TINY = Grid(sizes=(10, 50), query_counts=(1, 3), repeats=2, min_measure_seconds=0.0005)


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# --- Output schema ------------------------------------------------------------------

def test_grid_skips_single_query_mixed():
    specs = TINY.specs()
    assert len(specs) == 2 * (3 + 2)  # q=3: three scenarios; q=1: no "mixed"
    assert not any(s.q == 1 and s.scenario == "mixed" for s in specs)


def test_timing_phase_writes_raw_and_summary(tmp_path):
    write_run_config(tmp_path, TINY, run_id="test")
    timing.run(tmp_path)
    raw = read_csv(tmp_path / "timings_raw.csv")
    summary = read_csv(tmp_path / "timings_summary.csv")
    datasets = read_csv(tmp_path / "datasets.csv")

    n_datasets = len(TINY.specs())
    assert len(datasets) == n_datasets
    assert len(raw) == n_datasets * len(METHODS) * 3 * TINY.repeats
    assert len(summary) == n_datasets * len(METHODS) * 3
    assert {r["segment"] for r in raw} == {"prepare", "query", "total"}
    assert {f'{r["method"]}_{r["version"]}' for r in raw} == {m.key for m in METHODS}
    assert all(float(r["elapsed_s"]) > 0 and int(r["calls_per_measurement"]) >= 1 for r in raw)
    for row in summary:
        assert float(row["min_s"]) <= float(row["median_s"]) <= float(row["max_s"])
    config = json.loads((tmp_path / "run.json").read_text())
    assert config["noop_call_s"] > 0 and config["noop_lambda_call_s"] > 0


def test_memory_phase_writes_rows(tmp_path):
    write_run_config(tmp_path, TINY, run_id="test")
    memory.run(tmp_path)
    rows = read_csv(tmp_path / "memory.csv")
    assert len(rows) == len(TINY.specs()) * len(METHODS)
    for r in rows:
        assert int(r["total_peak_bytes"]) >= int(r["total_current_bytes"]) >= 0
    assert "total_current_bytes" in json.loads((tmp_path / "run.json").read_text())["memory_baseline"]


def test_run_config_round_trip(tmp_path):
    write_run_config(tmp_path, TINY, run_id="test")
    cfg = json.loads((tmp_path / "run.json").read_text())
    assert cfg["run_id"] == "test"
    assert cfg["grid"]["sizes"] == [10, 50]
    assert {m["key"] for m in cfg["methods"]} == {m.key for m in METHODS}
    assert set(cfg["definitions"]) >= {"prepare", "query", "total", "elapsed_s", "memory"}


# --- Protocol: what each timed call contains -------------------------------------------

@pytest.fixture
def probe():
    """A method that counts its prepare and query calls."""
    counts = {"prepare": 0, "query": 0}

    def prepare(ids):
        counts["prepare"] += 1
        return set(ids)

    def query(state, queries):
        counts["query"] += 1
        return [q in state for q in queries]

    return Method("probe", "v1", "only", "Probe", "", prepare, query), counts


@pytest.mark.parametrize("segment, per_call", [
    ("prepare", (1, 0)),   # preparation only
    ("query", (0, 1)),     # query batch only: preparation is never inside the timed loop
    ("total", (1, 1)),     # a fresh preparation every call: never "free"
])
def test_segments_time_exactly_what_they_claim(probe, segment, per_call):
    method, counts = probe
    fn = timing.make_fn(method, segment, [1, 2, 3], [2, 5])
    counts.update(prepare=0, query=0)  # building fn may prepare (query segment); not timed
    timing.measure(fn, 7)
    assert (counts["prepare"], counts["query"]) == (7 * per_call[0], 7 * per_call[1])


def test_query_segment_gets_a_fresh_state_per_repeat(probe):
    method, counts = probe
    states = []
    for _ in range(3):  # what the timing loop does once per repeat
        fn = timing.make_fn(method, "query", [1, 2, 3], [2])
        states.append(fn.args[0])
    assert counts["prepare"] == 3
    assert len({id(s) for s in states}) == 3


def test_calibration_reaches_target_duration(monkeypatch):
    # Fake clock (deterministic, independent of machine load): 10 us per call.
    monkeypatch.setattr(timing, "measure", lambda fn, calls: calls * 1e-5)
    calls = timing.calibrate(None, 0.002)
    assert calls * 1e-5 >= 0.002 * 1.25  # target reached, plus the 25% margin
    # A single call that already exceeds the target is not batched.
    monkeypatch.setattr(timing, "measure", lambda fn, calls: calls * 0.05)
    assert timing.calibrate(None, 0.01) == 1


def test_preflight_rejects_wrong_results_and_non_bools(probe):
    method, _ = probe
    timing.preflight([1, 2, 3], [2, 5], methods=[method])  # correct: passes
    wrong = Method("wrong", "v1", "only", "", "", lambda ids: ids, lambda s, qs: [False] * len(qs))
    ints = Method("ints", "v1", "only", "", "", set, lambda s, qs: [int(q in s) for q in qs])
    mutating = Method("mut", "v1", "only", "", "", lambda ids: ids.sort() or ids,
                      lambda s, qs: [q in s for q in qs])
    for bad in (wrong, ints, mutating):
        with pytest.raises(AssertionError):
            timing.preflight([3, 1, 2], [2, 5], methods=[bad])


def test_memory_traces_only_what_the_method_allocates():
    ids = list(range(10_000))  # built before tracing, so it must not be counted
    identity = Method("id", "v1", "only", "", "", lambda x: x, lambda s, qs: [])
    copying = Method("copy", "v1", "only", "", "", list, lambda s, qs: [])
    assert memory.trace_one(identity, ids, [1])["total_current_bytes"] < 512
    assert memory.trace_one(copying, ids, [1])["prepare_current_bytes"] >= 8 * len(ids)
    assert memory.baseline()["total_peak_bytes"] < 512


# --- Provenance and privacy ---------------------------------------------------------------

def test_git_info_outside_a_repository_is_unknown_not_clean(tmp_path):
    info = git_info(tmp_path)
    assert info["commit"] is None and info["dirty"] is None


def test_source_fingerprint_tracks_content_not_line_endings(tmp_path):
    (tmp_path / "search_algos").mkdir()
    module = tmp_path / "search_algos" / "x.py"
    module.write_bytes(b"a = 1\nb = 2\n")
    lf = source_fingerprint(tmp_path)["sha256"]
    module.write_bytes(b"a = 1\r\nb = 2\r\n")
    assert source_fingerprint(tmp_path)["sha256"] == lf
    module.write_bytes(b"a = 1\nb = 3\n")
    assert source_fingerprint(tmp_path)["sha256"] != lf


def test_redact_removes_home_folder_and_user_name():
    home = str(Path.home())
    text = (f"tmp_path = WindowsPath('{home.replace(chr(92), '/')}/AppData/x')\n"
            f"{home}\\file.py\n/tmp/pytest-of-someone/pytest-1\n")
    cleaned = redact(text)
    assert home not in cleaned and home.replace("\\", "/") not in cleaned
    assert "pytest-of-someone" not in cleaned and "~" in cleaned
