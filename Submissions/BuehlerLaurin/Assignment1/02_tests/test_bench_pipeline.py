"""Pipeline contract tests: limits/partial cells, counter parity and data plans."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from datagen.benchmark_own import rows


@pytest.mark.parametrize("kind", ["liquidation", "drift"])
def test_own_benchmark_inputs(kind):
    from lob import METHODS
    events = list(rows(kind, 100, 42))
    assert len(events) == 100 and events == list(rows(kind, 100, 42))
    assert [e["seq"] for e in events] == list(range(1, 101))
    book = METHODS[("lob", "A")]()
    for event in events:
        assert book.process(event)["status"] != "rejected"
    if kind == "liquidation":
        assert len(book.snapshot()) == 100 and all(e["type"] == "LIMIT" for e in events)
    else:
        assert len(book.snapshot()) <= 2


def test_counting_a_is_same_kernel_and_rejects_atomically():
    from bench.core import make_book
    from datagen.own_cases import C, L, M
    a, counted = make_book("A"), make_book("A", counted=True)
    events = [L(1, "z", "BUY", 100, 4), L(2, "a", "BUY", 100, 3), M(3, "s", 2),
              C(4, "z"), M(5, "t", 5), L(6, "bad", "BUY", 1, True)]
    for event in events:
        before = counted.counters.as_dict()
        ra, rb = a.process(dict(event)), counted.process(dict(event))
        assert ra == rb and a.snapshot() == counted.snapshot()
        if ra["status"] == "rejected":
            assert counted.counters.as_dict() == before
    assert counted.counters.fills == 2
    assert counted.counters.best_order_scans > 0


def test_phase_guard_stops_one_replay_without_waiting_for_whole_cell():
    from bench.guard import run_phased
    code = "import json,time; print(json.dumps({'bench_phase':'replay','action':'start'}),flush=True); time.sleep(2)"
    result = run_phased([sys.executable, "-c", code], 0.05)
    assert result["status"] == "stopped" and result["stopped_phase"] == "replay"
    assert result["wall_s"] < 1.5


def test_liquidation_quantities_and_fresh_books():
    from bench.core import prepare_book, sale_event, workload_events, replay
    case = {"part": "liquidation", "percent": 200}
    events = list(rows("liquidation", 20, 42))
    total = sum(e["qty_units"] for e in events)
    assert sale_event(events, 10)["qty_units"] == (total + 9) // 10
    first, second = prepare_book(case, events, "A"), prepare_book(case, events, "A")
    result = replay(first, workload_events(case, events))
    assert result["unfilled_qty_units"] == total
    assert len(second.snapshot()) == 20 and first.snapshot() == []


def test_catalog_smoke_is_exactly_one_seed_and_1000_events():
    from bench.catalog import plans
    from bench.run_all import cases_for
    entries = [{**p, "events": p["size"], "sha256": "sample"} for p in plans()]
    cases = cases_for("smoke", {"entries": entries})
    assert len(cases) == 15
    assert {c["size"] for c in cases} == {1000} and {c["seed"] for c in cases} == {42}
    assert {c["events"] for c in cases} == {1000}
    assert {c["part"] for c in cases} == {"official", "queue", "liquidation", "adversarial", "churn"}
    assert {c.get("percent") for c in cases if c["part"] == "liquidation"} == {10, 100, 200}
    assert len({c["id"] for c in cases}) == 15


def test_long_run_requires_explicit_flag():
    cp = subprocess.run([sys.executable, "run.py", "bench.run_all", "--part", "million"],
                        capture_output=True, text=True, timeout=10)
    assert cp.returncode != 0 and "--allow-long" in cp.stderr


def test_partial_cell_has_no_median_or_fake_time(tmp_path):
    from bench.harness import append_rows
    from bench.run_all import summarize
    rows = [{"case_id": "x", "version": "A", "phase": "replay", "repeat": i,
             "warmup": False, "seconds": t, "status": "ok", "replayed_events": 1000}
            for i, t in enumerate((1, 2, 3, 4))]
    rows.append({**rows[-1], "repeat": 4, "seconds": "", "status": "stopped"})
    append_rows(tmp_path/"timing.csv", rows)
    append_rows(tmp_path/"cells.csv", [{"case_id": "x", "version": "A", "mode": "timing", "status": "stopped"}])
    summary = summarize(tmp_path)
    assert summary[0]["median_s"] == "" and summary[0]["throughput_events_s"] == ""
    assert summary[0]["completed_repeats"] == 4 and summary[0]["status"] == "stopped"


def test_complete_cell_uses_five_repeat_median_and_ignores_warmup(tmp_path):
    from bench.harness import append_rows
    from bench.run_all import summarize
    rows = [{"case_id": "x", "version": "B1", "phase": "replay", "repeat": i,
             "warmup": False, "seconds": t, "status": "ok", "replayed_events": 1000}
            for i, t in enumerate((1, 2, 3, 4, 100))]
    rows.append({**rows[-1], "repeat": -1, "warmup": True, "seconds": 999})
    append_rows(tmp_path/"timing.csv", rows)
    append_rows(tmp_path/"cells.csv", [{"case_id": "x", "version": "B1", "mode": "timing", "status": "ok"}])
    summary = summarize(tmp_path)
    assert summary[0]["median_s"] == 3 and summary[0]["throughput_events_s"] == 1000/3


def test_memory_limit_records_stopped_without_fabricated_measurement(tmp_path):
    import gzip
    import hashlib
    from bench.worker import run_job
    path = tmp_path/"events.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for event in rows("liquidation", 20, 42):
            stream.write(json.dumps(event)+"\n")
    case = {"id": "memory-stop", "part": "official", "label": "test", "workload": "test",
            "size": 20, "events": 20, "seed": 42, "levels": 1000, "own": True,
            "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    journal = tmp_path/"out.jsonl"
    assert run_job({"case": case, "version": "B1", "mode": "memory", "limit_s": 10,
                    "limit_bytes": 1, "journal": str(journal)}) == 124
    records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    stopped = [r["row"] for r in records if r["kind"] == "stops"]
    assert stopped and stopped[-1]["status"] == "stopped"
    assert stopped[-1]["reason"] == "traced_peak_bytes" and stopped[-1]["seconds"] == ""


def test_counter_parity_for_every_version_on_original_own_files():
    from bench.core import VERSIONS, check_case
    from lob.replay import read_events
    from datagen.own_cases import CASE_NAMES
    for version in VERSIONS:
        for name in CASE_NAMES:
            events = list(read_events(Path("06_data/own")/(name+".jsonl")))
            check_case({"id": name, "part": "official"}, events, version, counted=True)


def test_regression_sample_checker_accepts_non_object_invalid_events():
    from bench.core import check_case
    assert check_case({"id": "null-event", "part": "official"}, [None], "A", counted=True) == 1


def test_regression_completed_over_limit_call_keeps_actual_phase_name():
    import time
    from bench.worker import ResourceStop, measure
    with pytest.raises(ResourceStop) as caught:
        measure("construction", lambda: time.sleep(0.01), 0.001)
    assert caught.value.phase == "construction"


def test_resume_rejects_changed_source_or_limits(tmp_path, monkeypatch):
    from argparse import Namespace
    import bench.run_all as runner
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner, "fingerprint", lambda: "same-source")
    (tmp_path/"scratch").mkdir()
    pointer = tmp_path/"scratch/bench_session_test.json"
    pointer.write_text(json.dumps({"source_sha256": "same-source", "run_dir": "run",
                                   "limit_s": 600, "limit_bytes": 1024}), encoding="utf-8")
    args = Namespace(session="test", part="smoke", limit_s=600, limit_bytes=1024)
    assert runner.get_run(args) == Path("run")
    args.limit_s = 1
    with pytest.raises(ValueError, match="limits changed"):
        runner.get_run(args)
    args.limit_s = 600
    monkeypatch.setattr(runner, "fingerprint", lambda: "changed-source")
    with pytest.raises(ValueError, match="source changed"):
        runner.get_run(args)


def test_duplicate_repeat_is_rejected(tmp_path):
    from bench.harness import append_rows
    row = {"case_id": "x", "version": "A", "phase": "replay", "repeat": 0, "seconds": 1}
    append_rows(tmp_path/"timing.csv", [row], unique_by=("case_id", "version", "phase", "repeat"))
    with pytest.raises(ValueError, match="duplicate row"):
        append_rows(tmp_path/"timing.csv", [row], unique_by=("case_id", "version", "phase", "repeat"))


def test_memory_curve_observer_does_not_retain_sample_allocations():
    from bench.harness import traced_curve
    curve = traced_curve(lambda state, event: None, None, list(range(1000)), every=10,
                         setup=lambda: None, observe=lambda state: (0, 0, 0, 0))
    assert curve[-1]["current_bytes"] - curve[1]["current_bytes"] < 4096
    assert curve[-1]["live_orders"] == 0


@pytest.mark.parametrize("version,size,expected", [
    ("A", 1000, (1, 5, "warm-up + 5 repeats")),
    ("A", 10000, (1, 5, "warm-up + 5 repeats")),
    ("A", 100000, (0, 1, "A: single trial")),
    ("A", 1000000, (0, 1, "A: single trial")),
    *[(v, size, (1, 5, "warm-up + 5 repeats"))
      for v in ("B1", "B2", "B3") for size in (100000, 1000000)],
])
def test_declared_baseline_schedule(version, size, expected):
    from bench.protocol import timing_plan
    assert timing_plan(version, size) == expected


def test_large_a_summary_is_explicit_single_trial(tmp_path):
    from bench.harness import append_rows
    from bench.run_all import summarize
    append_rows(tmp_path/"timing.csv", [{
        "case_id": "large", "version": "A", "size": 100000, "phase": "replay",
        "repeat": 0, "warmup": False, "seconds": 2, "status": "ok",
        "replayed_events": 100000, "repeats_requested": 1,
        "timing_protocol": "A: single trial"}])
    append_rows(tmp_path/"cells.csv", [{"case_id": "large", "version": "A",
                                      "mode": "timing", "status": "ok"}])
    row = summarize(tmp_path)[0]
    assert row["status"] == "ok" and row["repeats_requested"] == 1
    assert row["statistic"] == "single_trial" and row["timing_protocol"] == "A: single trial"
    assert row["median_s"] == 2 and row["throughput_events_s"] == 50000


@pytest.mark.parametrize("version,size,indices", [
    ("A", 100000, [0]), ("A", 10000, [-1, 0, 1, 2, 3, 4]),
    ("B1", 100000, [-1, 0, 1, 2, 3, 4]),
])
def test_worker_obeys_declared_trials_using_tiny_synthetic_input(tmp_path, version, size, indices):
    """Control-flow check: size label exercises policy; only 4 events are replayed."""
    import gzip
    import hashlib
    from bench.worker import run_job
    path = tmp_path/"tiny.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for event in rows("liquidation", 4, 42):
            stream.write(json.dumps(event)+"\n")
    case = {"id": "synthetic-policy", "part": "official", "label": "tiny-policy-test",
            "workload": "tiny-policy-test", "size": size, "events": 4, "seed": 42,
            "levels": 1000, "own": True, "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    journal = tmp_path/"out.jsonl"
    assert run_job({"case": case, "version": version, "mode": "timing", "limit_s": 10,
                    "limit_bytes": 4*1024**3, "journal": str(journal)}) == 0
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    replay_rows = [r["row"] for r in records if r["kind"] == "timing" and r["row"]["phase"] == "replay"]
    assert [r["repeat"] for r in replay_rows] == indices
    assert all(r["repeats_requested"] == len([i for i in indices if i >= 0]) for r in replay_rows)
