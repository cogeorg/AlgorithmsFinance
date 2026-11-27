import pytest

from benchmarks.metrics import (
    EventResultBookkeeping,
    ceil_percent,
    percentile_nearest_rank,
    replay_fresh,
    state_peak_replay,
    stopped_phase_row,
    summarize_seconds,
)
from benchmarks.run_benchmarks import (
    _candidate_phase_reasons,
    _case_manifest,
    _code_hashes,
    _config_id,
    _execution_priority,
    _make_queue_events,
    _phase_definition_hash,
    _phase_definition_id,
    _phase_jobs,
    _phase_rows_complete,
    _phase_settings_snapshot,
    _receive_worker_message,
    _run_one_configuration,
)
from orderbook.baseline import OrderBook as BaselineBook
from orderbook.revised import OrderBook as RevisedBook


@pytest.mark.parametrize(
    ("quantity", "percent", "expected"),
    [(1, 10, 1), (101, 10, 11), (101, 100, 101), (101, 200, 202)],
)
def test_ceil_percent_uses_integer_ceiling(quantity, percent, expected):
    assert ceil_percent(quantity, percent) == expected


def test_timing_summary_uses_median_and_nearest_rank_percentiles():
    values = list(range(1, 21))

    assert percentile_nearest_rank(values, 95) == 19
    assert percentile_nearest_rank(values, 99) == 20
    assert summarize_seconds([1.0, 3.0, 2.0], 10) == {
        "median_seconds": 2.0,
        "throughput_events_per_second": 5.0,
    }


@pytest.mark.parametrize("book_type", [BaselineBook, RevisedBook])
def test_replay_fresh_returns_independent_engine_state(book_type):
    first = replay_fresh(
        book_type,
        [
            {
                "seq": 1,
                "event_id": "add",
                "type": "LIMIT",
                "order_id": "bid",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 10,
            },
            {
                "seq": 2,
                "event_id": "partial",
                "type": "MARKET_SELL",
                "order_id": "sell",
                "qty_units": 5,
            },
        ],
    )
    second = replay_fresh(
        book_type,
        [
            {
                "seq": 1,
                "event_id": "add",
                "type": "LIMIT",
                "order_id": "bid",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 10,
            }
        ],
    )

    first.process_event(
        {
            "seq": 3,
            "event_id": "cancel",
            "type": "CANCEL",
            "target_order_id": "bid",
        }
    )
    assert first.inspect_book() == {"bids": [], "asks": []}
    assert second.inspect_book() == {
        "bids": [
            {
                "order_id": "bid",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 10,
                "seq": 1,
            }
        ],
        "asks": [],
    }


@pytest.mark.parametrize("book_type", [BaselineBook, RevisedBook])
def test_state_peak_replay_uses_event_results_without_book_inspection(
    book_type, monkeypatch
):
    def inspection_is_not_allowed(_book):
        pytest.fail("state peak tracking must not inspect the whole book")

    monkeypatch.setattr(book_type, "inspect_book", inspection_is_not_allowed)
    events = [
        {
            "seq": 1,
            "event_id": "first",
            "type": "LIMIT",
            "order_id": "first",
            "side": "BUY",
            "price_ticks": 100,
            "qty_units": 5,
        },
        {
            "seq": 2,
            "event_id": "second",
            "type": "LIMIT",
            "order_id": "second",
            "side": "BUY",
            "price_ticks": 100,
            "qty_units": 3,
        },
        {
            "seq": 3,
            "event_id": "third",
            "type": "LIMIT",
            "order_id": "third",
            "side": "BUY",
            "price_ticks": 99,
            "qty_units": 2,
        },
        {
            "seq": 4,
            "event_id": "sell",
            "type": "MARKET_SELL",
            "order_id": "sell",
            "qty_units": 6,
        },
        {
            "seq": 5,
            "event_id": "cancel",
            "type": "CANCEL",
            "target_order_id": "second",
        },
        {
            "seq": 6,
            "event_id": "not-found",
            "type": "CANCEL",
            "target_order_id": "missing",
        },
    ]

    result = state_peak_replay(book_type, events)

    assert result == {
        "active_order_peak": 3,
        "occupied_price_level_peak": 2,
        "state_peak_method": "event_result_shadow_bookkeeping",
        "state_peak_counts_are": "logical event-boundary counts",
        "final_active_orders": 1,
        "final_occupied_price_levels": 1,
    }


def test_event_result_bookkeeping_ignores_rejections():
    tracker = EventResultBookkeeping()
    event = {
        "seq": 1,
        "event_id": "bad",
        "type": "LIMIT",
        "order_id": "bad",
        "side": "BUY",
        "price_ticks": 100,
        "qty_units": 1,
    }

    tracker.observe(event, {"status": "rejected"})

    assert tracker.summary()["active_order_peak"] == 0
    assert tracker.summary()["occupied_price_level_peak"] == 0


def test_queue_concentration_changes_realized_prices_not_order_quantities():
    concentrated = _make_queue_events(1000, 4, 42)
    spread = _make_queue_events(1000, 1000, 42)

    assert len(concentrated) == len(spread) == 1000
    assert [event["qty_units"] for event in concentrated] == [
        event["qty_units"] for event in spread
    ]
    assert len({event["price_ticks"] for event in concentrated}) == 4
    assert len({event["price_ticks"] for event in spread}) == 1000


def test_stopped_run_record_does_not_report_zero_elapsed_time():
    row = stopped_phase_row("stopped_timeout", 12.5, 2048)

    assert row["phase"] == "worker_stop"
    assert row["status"] == "stopped_timeout"
    assert row["elapsed_seconds"] is None
    assert row["duration_until_stop_seconds"] == 12.5
    assert row["peak_working_set_bytes_observed"] == 2048


def test_closed_worker_pipe_is_reported_as_ipc_error():
    class ClosedPipe:
        def poll(self, timeout=0):
            return True

        def recv(self):
            raise OSError("pipe closed")

    message = _receive_worker_message(ClosedPipe())

    assert message["kind"] == "ipc_error"
    assert "pipe closed" in message["error"]


def test_queue_attempt_ids_are_shortened_for_windows_paths():
    case = {"case_id": "queue_concentration_prices1000_M10000"}

    assert _config_id(case, "baseline") == "queue_prices1000_M10000__baseline"


def _small_workload_case(tmp_path):
    return {
        "case_id": "workload_mixed_M25_seed42",
        "experiment": "workload_replay",
        "scenario": "mixed",
        "seed": 42,
        "event_count": 25,
        "input_paths": [str(tmp_path / "events.jsonl")],
        "input_checksums": {"events.jsonl": "input-sha256"},
        "generator_settings": {
            "generator": "generate_orders.py",
            "scenario": "mixed",
            "events": 25,
            "seed": 42,
            "levels": 1000,
            "source": "generated",
        },
        "profile": True,
    }


def _compatible_primary_candidate(case, settings):
    code_hashes = _code_hashes()
    common = {
        "version": "baseline",
        "event_count": case["event_count"],
        "generator_settings": case["generator_settings"],
        "input_checksums": case["input_checksums"],
        "scenario": case["scenario"],
        "seed": case["seed"],
        "code_hashes": code_hashes,
        "measurement_definition_id": _phase_definition_id("engine_replay"),
        "measurement_definition_hash": _phase_definition_hash("engine_replay"),
        "phase_settings": _phase_settings_snapshot(
            "engine_replay", case, settings
        ),
    }
    rows = [
        {
            **common,
            "phase": "engine_replay",
            "repeat": repeat,
            "status": "completed",
        }
        for repeat in range(1, 6)
    ]
    rows.append(
        {
            **common,
            "phase": "engine_replay_summary",
            "status": "completed",
            "raw_repeats_seconds": [1, 2, 3, 4, 5],
        }
    )
    return {
        "source": "records/previous-phase.json",
        "attempt": 1,
        "rows": rows,
        "case": _case_manifest(case),
        "record": {},
    }


def test_continuation_rejects_input_or_phase_definition_mismatches(tmp_path):
    case = _small_workload_case(tmp_path)
    settings = {
        "timing_repeats": 5,
        "phase_budgets": {
            "primary": 300,
            "latency": 300,
            "memory": 300,
            "state_peaks": 300,
            "counters": 60,
            "profile": 60,
        },
        "counter_max_events": 1500,
        "profile_event_limit": 2000,
    }
    candidate = _compatible_primary_candidate(case, settings)

    assert _candidate_phase_reasons(
        "engine_replay",
        candidate,
        case,
        "baseline",
        settings,
        tmp_path,
        _code_hashes(),
    ) == []

    changed_input = dict(candidate)
    changed_input["rows"] = [dict(row) for row in candidate["rows"]]
    changed_input["rows"][0]["input_checksums"] = {"events.jsonl": "changed"}
    assert "input checksum differs" in _candidate_phase_reasons(
        "engine_replay",
        changed_input,
        case,
        "baseline",
        settings,
        tmp_path,
        _code_hashes(),
    )

    changed_definition = dict(candidate)
    changed_definition["rows"] = [dict(row) for row in candidate["rows"]]
    changed_definition["rows"][0]["measurement_definition_hash"] = "stale"
    assert "measurement definition hash differs" in _candidate_phase_reasons(
        "engine_replay",
        changed_definition,
        case,
        "baseline",
        settings,
        tmp_path,
        _code_hashes(),
    )


def test_continuation_requires_all_five_primary_repeats(tmp_path):
    case = _small_workload_case(tmp_path)
    candidate = _compatible_primary_candidate(
        case,
        {
            "timing_repeats": 5,
            "profile_event_limit": 2000,
            "counter_max_events": 1500,
        },
    )
    candidate["rows"] = candidate["rows"][:-2]

    complete, reason = _phase_rows_complete(
        "engine_replay", candidate["rows"], case, {}, tmp_path
    )

    assert not complete
    assert "five completed repeats" in reason


def test_heavy_diagnostics_are_limited_to_small_representative_case():
    settings = {"counter_max_events": 1500}
    representative = {
        "experiment": "workload_replay",
        "event_count": 1000,
        "sell_quantities": [],
        "profile": True,
    }
    other_small_case = {**representative, "profile": False}
    large_case = {**representative, "event_count": 10000}

    assert {"counters", "profile"} <= set(
        _phase_jobs(representative, settings)
    )
    assert not ({"counters", "profile"} & set(
        _phase_jobs(other_small_case, settings)
    ))
    assert not ({"counters", "profile"} & set(
        _phase_jobs(large_case, settings)
    ))


def test_execution_priority_runs_required_experiments_and_small_sizes_first():
    cases = [
        {"experiment": "workload_replay", "event_count": 100000, "scenario": "mixed", "seed": 42},
        {"experiment": "cancellation_churn", "event_count": 100, "scenario": "churn", "seed": 42},
        {"experiment": "queue_concentration", "event_count": 1000, "scenario": "queue_1000_prices", "seed": 42},
        {"experiment": "fixed_liquidation", "event_count": 1001, "scenario": "fixed_bid_book", "seed": 42},
        {"experiment": "workload_replay", "event_count": 1000, "scenario": "mixed", "seed": 42},
    ]

    ordered = sorted(cases, key=_execution_priority)

    assert [case["experiment"] for case in ordered] == [
        "fixed_liquidation",
        "queue_concentration",
        "cancellation_churn",
        "workload_replay",
        "workload_replay",
    ]
    assert [case["event_count"] for case in ordered[-2:]] == [1000, 100000]


def test_phase_statuses_are_recorded_independently(tmp_path, monkeypatch):
    case = _small_workload_case(tmp_path)
    (tmp_path / "records").mkdir()
    monkeypatch.setattr(
        "benchmarks.run_benchmarks._phase_jobs",
        lambda _case, _settings: ["engine_replay", "latency"],
    )

    def run_phase(
        _run_dir, _case, _version, phase, attempt, _settings, _budget
    ):
        assert attempt == 1
        return {
            "status": "completed" if phase == "engine_replay" else "stopped_timeout",
            "record_file": f"records/{phase}.json",
            "duration_until_stop_seconds": 0.1,
            "rows": [],
        }

    monkeypatch.setattr("benchmarks.run_benchmarks._run_one_phase", run_phase)
    plan = {
        "phases": [
            {
                "phase": "engine_replay",
                "status": "reusable",
                "source": "records/prior.json",
                "reason": "compatible",
            },
            {"phase": "latency", "status": "pending"},
        ]
    }

    record = _run_one_configuration(
        tmp_path,
        case,
        "baseline",
        {
            "phase_budgets": {
                "primary": 300,
                "latency": 300,
                "memory": 300,
                "state_peaks": 300,
                "counters": 60,
                "profile": 60,
            },
            "memory_limit_mib": 4096,
        },
        plan,
    )

    assert record["status"] == "partial"
    assert record["phase_statuses"]["engine_replay"]["status"] == "reused"
    assert record["phase_statuses"]["latency"]["status"] == "stopped_timeout"
