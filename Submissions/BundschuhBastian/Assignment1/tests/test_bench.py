"""Tests for the benchmark code (bench/): rules from the README, percentile convention, limits."""
import csv
import gc
import json
import time
from pathlib import Path
from typing import Any

import pytest

import generate_orders
from bench import bench_counts as counters, bench_latency as latency, bench_time, common, liquidation
from bench.harness import run_limited
from lob import VERSIONS
from tools.gen_small import PROFILES, generate

ROOT = Path(__file__).resolve().parent.parent


# --- percentile convention: nearest rank --------------------------------------------------
def test_nearest_rank_percentiles():
    values = list(range(1, 101))                       # 1..100
    assert [common.percentile_nearest_rank(values, p) for p in (50, 95, 99)] == [50, 95, 99]
    assert common.percentile_nearest_rank([7], 99) == 7
    ten = list(range(10, 110, 10))
    assert common.percentile_nearest_rank(ten, 50) == 50      # rank ceil(5.0) = 5
    assert common.percentile_nearest_rank(ten, 51) == 60      # rank ceil(5.1) = 6
    assert common.percentile_nearest_rank(ten, 99) == 100
    assert common.percentile_nearest_rank(list(range(1, 21)), 95) == 19   # rank ceil(19.0)
    with pytest.raises(ValueError):
        common.percentile_nearest_rank([], 50)


def test_latency_summary_shapes():
    lat = list(range(1, 3001))
    s = latency.summarize(lat)
    w = s["windows"]
    assert w["ALL|all"]["p50_ns"] == 1500 and w["ALL|all"]["p99_ns"] == 2970
    assert w["ALL|first1000"]["n"] == 1000 and w["ALL|first1000"]["p50_ns"] == 500
    assert w["ALL|last1000"]["n"] == 1000 and w["ALL|last1000"]["p50_ns"] == 2500
    assert len(s["chunks"]) == 20 and sum(c["n"] for c in s["chunks"]) == 3000
    assert sum(s["hist_log2_ns"].values()) == 3000
    assert "LIMIT|all" not in w                                   # no types given: ALL only


def test_latency_split_by_event_type_and_short_streams():
    lat = [10, 20, 30, 40, 50, 60]
    types = ["LIMIT", "LIMIT", "CANCEL", "LIMIT", "CANCEL", "LIMIT"]
    w = latency.summarize(lat, types)["windows"]
    assert w["LIMIT|all"]["n"] == 4 and w["CANCEL|all"]["n"] == 2
    assert w["CANCEL|all"]["p50_ns"] == 30 and w["LIMIT|all"]["p95_ns"] == 60
    assert "MARKET_SELL|all" not in w                              # no such event: no row
    assert w["ALL|first1000"]["n"] == 6                             # stream shorter than 1,000


# --- stream list agrees with the checksum record ---------------------------------------------
def test_stream_list_matches_the_checksum_record():
    record = json.loads((ROOT / "results" / "generated_data_checksums.json").read_text())["files"]
    names = {common.stream_name(**spec) for spec in common.all_streams()}
    assert names == set(record) and len(names) == 55
    ordered = [s["events"] for s in common.all_streams()]
    assert ordered == sorted(ordered)                   # A at 100,000 is decided before 1,000,000


# --- rule 3: A on 1,000,000-event files -----------------------------------------------------------
def row(version="A", scenario="mixed", events="100000", status="ok", median="10.0"):
    return {"version": version, "scenario": scenario, "seed": "42", "events": events,
            "levels": "1000", "status": status, "median_seconds": median}


def test_rule_3_a_on_a_million_events():
    spec = {"scenario": "mixed"}
    assert bench_time.a_million_decision(spec, []) is not None                      # no result yet
    assert bench_time.a_million_decision(spec, [row(median="59.99")]) is None        # < 60 s: run
    reason = bench_time.a_million_decision(spec, [row(median="60.0")])                # = 60 s: not run
    assert reason is not None and "60.0 s" in reason
    assert bench_time.a_million_decision(spec, [row(median="400")]) is not None
    reason = bench_time.a_million_decision(spec, [row(status="stopped", median="")])
    assert reason is not None and "stopped" in reason
    assert bench_time.a_million_decision(spec, [row(scenario="sweep", median="1")]) is not None
    assert bench_time.a_million_decision(spec, [row(events="10000", median="1")]) is not None


# --- limit harness ------------------------------------------------------------------------------
def _replay_busy(events):
    for e in events:
        time.sleep(0.05)


def _worker_slow(conn):
    conn.send(("unit_start", "u"))
    _replay_busy([{"seq": n} for n in range(1, 1000)])
    conn.send(("unit_done", "u", None))


def _worker_ok(conn):
    conn.send(("unit_start", "u"))
    conn.send(("unit_done", "u", 42))
    conn.send(("data", "x"))


def _worker_error(conn):
    raise RuntimeError("boom")


def test_harness_stops_a_slow_replay_and_reports_progress():
    result = run_limited(_worker_slow, (), 1.0)
    assert result["outcome"] == "stopped" and result["stopped_tag"] == "u"
    assert 1.0 <= result["stopped_after_s"] < 3.0
    assert 10 <= result["events_done"] <= 30            # ~20 events of 50 ms in 1 s


def test_harness_normal_and_error():
    ok = run_limited(_worker_ok, (), 5.0)
    assert ok["outcome"] == "end" and ("unit_done", "u", 42) in ok["messages"]
    bad = run_limited(_worker_error, (), 5.0)
    assert bad["outcome"] == "error" and "boom" in bad["error"]


# --- timing protocol (rules 1 and 2) on a small stream written to a temp dir -----------------
@pytest.fixture
def small_stream(tmp_path, monkeypatch):
    spec: dict[str, Any] = dict(scenario="mixed", events=1000, seed=42, levels=1000)
    monkeypatch.setattr(common, "DATA", tmp_path)
    generate_orders.write_stream(common.stream_path(**spec),
                                 generate_orders.events("mixed", 1000, 42, 1000))
    monkeypatch.setattr(bench_time, "TIME_RAW", tmp_path / "time_raw.csv")
    return spec, tmp_path


def read(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def test_timing_normal_run_has_warmup_and_five_repeats(small_stream):
    spec, tmp = small_stream
    bench_time.run_one("B", spec, 600, 60, 5)
    raw = read(tmp / "time_raw.csv")
    assert [r["phase"] for r in raw] == ["warmup"] + ["timed"] * 5
    assert [r["repeat"] for r in raw][1:] == ["0", "1", "2", "3", "4"]
    assert {r["status"] for r in raw} == {"ok"} and {r["repeats"] for r in raw} == {"5"}
    times = sorted(float(r["elapsed_seconds"]) for r in raw[1:])
    assert {float(r["median_seconds"]) for r in raw} == {times[2]}     # median of the 5 timed
    assert float(raw[0]["parse_seconds"]) > 0
    assert (raw[0]["version"], raw[0]["events"], raw[0]["limit_seconds"]) == ("B", "1000", "600")


def test_timing_slow_first_replay_is_the_only_measurement(small_stream):
    spec, tmp = small_stream
    bench_time.run_one("A", spec, 600, 0.0, 5)           # threshold 0 s: every first replay is "slow"
    raw = read(tmp / "time_raw.csv")
    assert [r["phase"] for r in raw] == ["single"] and raw[0]["repeats"] == "1"
    assert raw[0]["status"] == "ok"
    assert float(raw[0]["median_seconds"]) == float(raw[0]["elapsed_seconds"])


def test_timing_stopped_run_skips_remaining_repeats(small_stream):
    spec, tmp = small_stream
    big: dict[str, Any] = dict(scenario="buildup", events=10000, seed=42, levels=1000)
    generate_orders.write_stream(common.stream_path(**big),
                                 generate_orders.events("buildup", 10000, 42, 1000))
    bench_time.run_one("A", big, 1.0, 60, 5)             # A needs several seconds here
    raw = read(tmp / "time_raw.csv")
    assert len(raw) == 1 and raw[0]["phase"] == "single"
    assert (raw[0]["status"], raw[0]["replay_status"], raw[0]["repeats"]) == ("stopped", "stopped", "0")
    assert raw[0]["median_seconds"] == "" and int(raw[0]["events_done"]) > 100
    assert float(raw[0]["elapsed_seconds"]) >= 1.0


class _CountingBook:
    """Stands in for an engine: counts books created and records whether gc was enabled."""
    created = 0
    gc_enabled: list[bool] = []

    def __init__(self):
        type(self).created += 1

    def process(self, event):
        type(self).gc_enabled.append(gc.isenabled())


class _Conn:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


def test_replay_runs_with_gc_enabled_and_a_fresh_book_each_time(tmp_path, monkeypatch):
    _CountingBook.created, _CountingBook.gc_enabled = 0, []
    path = tmp_path / "s.jsonl"
    path.write_text("".join(json.dumps({"seq": n}) + "\n" for n in range(1, 21)))
    loads = []
    real_load = bench_time.load_events
    monkeypatch.setattr(bench_time, "load_events", lambda p: loads.append(p) or real_load(p))
    monkeypatch.setitem(bench_time.VERSIONS, "X", _CountingBook)
    conn = _Conn()
    gc.enable()
    bench_time.time_worker(conn, "X", str(path), 60, 5)
    assert len(loads) == 1, "the file must be parsed once per run"
    assert _CountingBook.created == 6, "warm-up + 5 repeats, each with a fresh book"
    assert len(_CountingBook.gc_enabled) == 6 * 20 and all(_CountingBook.gc_enabled)
    assert gc.isenabled()
    done = [m for m in conn.messages if m[0] == "unit_done"]
    assert [m[1] for m in done] == ["first"] + [f"timed{r}" for r in range(5)]


def test_env_json_has_python_macos_machine_and_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "RESULTS", tmp_path)
    common.write_environment()
    env = json.loads((tmp_path / "env.json").read_text())
    assert env["python"].startswith("3.") and env["git_commit"] and len(env["git_commit"]) == 40
    assert env["platform"].startswith("macOS") and env["macos"] and env["mac_model_id"]
    assert "gc enabled" in env["timing"] and env["constants"]["limit_seconds"] == 600
    assert env["power_at_start"]["power_source"] in ("ac", "battery", "unknown")
    assert "low_power_mode" in env["power_at_start"]


def test_rows_have_start_time_and_power_state_and_canary_goes_to_its_own_file(small_stream,
                                                                              monkeypatch):
    spec, tmp = small_stream
    monkeypatch.setattr(bench_time, "CANARY_RAW", tmp / "canary_raw.csv")
    monkeypatch.setattr(bench_time, "CANARY_SPEC", spec)
    bench_time.run_one("B", spec, 600, 60, 5)
    raw = read(tmp / "time_raw.csv")
    assert all(r["start_utc"].endswith("+00:00") for r in raw)
    assert all(r["power_source"] in ("ac", "battery", "unknown") for r in raw)
    assert all("low_power_mode" in r for r in raw)
    args = bench_time.argparse.Namespace(limit_seconds=600, slow_first_seconds=60, repeats=5)
    bench_time.canary("blk", "before", args)
    canary = read(tmp / "canary_raw.csv")
    assert {(r["block"], r["canary_point"], r["version"]) for r in canary} == {("blk", "before", "B")}
    assert len(canary) == 6 and len(read(tmp / "time_raw.csv")) == len(raw)   # primary file untouched


# --- counters: instrumentation must not change behaviour and must restore the engines ----------
@pytest.mark.parametrize("version", ["A", "B"])
def test_counters_do_not_change_results_and_restore_engines(version):
    for profile in ("tight", "wide", "dirty"):
        events = generate(5, 300, profile)
        plain, _ = counters._replay_counted(version, events, False)
        counted, counts = counters._replay_counted(version, events, True)
        again, _ = counters._replay_counted(version, events, False)       # after restore
        assert counted == plain == again
        assert counts.get("fills", 0) == sum(len(r["fills"]) for r in plain)


def test_counters_values_on_a_hand_case():
    ev = [{"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "a", "side": "BUY",
           "price_ticks": 100, "qty_units": 5},
          {"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "b", "side": "BUY",
           "price_ticks": 101, "qty_units": 5},
          {"seq": 3, "event_id": "e3", "type": "MARKET_SELL", "order_id": "s", "qty_units": 7},
          {"seq": 4, "event_id": "e4", "type": "CANCEL", "target_order_id": "a"}]
    _, a = counters._replay_counted("A", ev, True)
    _, b = counters._replay_counted("B", ev, True)
    assert a["fills"] == b["fills"] == 2 and a["levels_visited"] == b["levels_visited"] == 2
    # A: is_live scans: e1 empty book (0), e2 sees [a] (1), e3 sees [a, b] (2) -> 3
    assert a["scan_is_live"] == 3 and a["best_index_calls"] == 2
    assert a["scan_best_index"] == 1 + 0                # book [a, b] -> 1 comparison, then [a] -> 0
    assert a["scan_cancel"] == 1                        # e4: "a" is the only record left
    assert b["key_inserts"] == 2 and b["levels_dropped"] == 2


# --- liquidation -------------------------------------------------------------------------------
def test_sale_quantity_rounding():
    assert [liquidation.sale_quantity(1005, n, d) for _, n, d in liquidation.FRACTIONS] == \
        [101, 1005, 2010]                                                 # ceil(100.5) = 101
    assert [liquidation.sale_quantity(1, n, d) for _, n, d in liquidation.FRACTIONS] == [1, 1, 2]
    assert liquidation.sale_quantity(10, 1, 10) == 1 and liquidation.sale_quantity(11, 1, 10) == 2
    assert liquidation.sale_quantity(3 * 10**15, 1, 10) == 3 * 10**14      # no float rounding


class _NullConn:
    def send(self, msg):
        pass


@pytest.mark.parametrize("scenario", ["buildup", "crowded"])
def test_liquidation_trials_agree_between_versions_and_are_fresh(scenario):
    rows = liquidation.bid_events(scenario, 300)
    assert len(rows) == 300 and all(r["side"] == "BUY" for r in rows)
    assert [r["seq"] for r in rows] == sorted(r["seq"] for r in rows)
    total = sum(r["qty_units"] for r in rows)
    for name, num, den in liquidation.FRACTIONS:
        qty = liquidation.sale_quantity(total, num, den)
        sale = {"seq": rows[-1]["seq"] + 1, "event_id": "liq", "type": "MARKET_SELL",
                "order_id": "liq", "qty_units": qty}
        outcomes = {}
        for version in ("A", "B"):
            first = liquidation._trial(VERSIONS[version], rows, sale, _NullConn(), "t")
            second = liquidation._trial(VERSIONS[version], rows, sale, _NullConn(), "t")
            assert first["digest"] == second["digest"], "a trial must start from a fresh book"
            outcomes[version] = first
        for key in ("digest", "makers", "levels", "unfilled", "status"):
            assert outcomes["A"][key] == outcomes["B"][key]
        assert outcomes["B"]["unfilled"] == max(0, qty - total)
        assert outcomes["B"]["status"] == ("filled" if qty <= total else "partial")


def test_scenarios_of_the_plan_are_complete():
    assert common.SCENARIOS == ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
    assert common.LIMIT_SECONDS == 600 and common.SLOW_FIRST_SECONDS == 60
    assert common.TIMED_REPEATS == 5 and common.A_MILLION_THRESHOLD == 60
    assert set(PROFILES)                                  # generator profiles still importable


# --- Phase 6c ----------------------------------------------------------------------------------
@pytest.mark.parametrize("profile", sorted(PROFILES))
@pytest.mark.parametrize("seed", range(6))
def test_a_idset_variant_gives_the_same_results_as_a_after_every_event(profile, seed):
    from bench.variants import OrderBookAIdSet
    plain, variant = VERSIONS["A"](), OrderBookAIdSet()
    for event in generate(seed, 300, profile):
        assert variant.process(event) == plain.process(event)
        assert variant.snapshot() == plain.snapshot()
        assert variant._live == {r["order_id"] for r in plain.snapshot()}       # set = live ids


def test_a_idset_is_labeled_and_does_not_replace_version_a():
    from bench.variants import NAME, OrderBookAIdSet
    assert NAME == "A_idset" and OrderBookAIdSet.name == "A_idset"
    assert "A_idset" not in VERSIONS and VERSIONS["A"].name == "A"


def test_liquidation_trial_keeps_gc_enabled():
    rows = liquidation.bid_events("buildup", 50)
    sale = {"seq": rows[-1]["seq"] + 1, "event_id": "liq", "type": "MARKET_SELL",
            "order_id": "liq", "qty_units": 1}
    states = []

    class Conn:
        def send(self, msg):
            states.append(gc.isenabled())
    liquidation._trial(VERSIONS["B"], rows, sale, Conn(), "t")
    assert states and all(states)


def test_flood_table_matches_the_peak_file(tmp_path, monkeypatch):
    from bench import bench_flood
    monkeypatch.setattr(bench_flood, "OUT", tmp_path / "flood.csv")
    assert bench_flood.main() == 0
    flood = read(tmp_path / "flood.csv")
    peaks = [r for r in read(common.RESULTS / "workload_peaks.csv")
             if r["scenario"] in ("buildup", "crowded")]
    assert len(flood) == len(peaks) and {r["scenario"] for r in flood} == {"buildup", "crowded"}
    assert all(int(r["peak_active_orders_B"]) <= int(r["events"]) for r in flood)
