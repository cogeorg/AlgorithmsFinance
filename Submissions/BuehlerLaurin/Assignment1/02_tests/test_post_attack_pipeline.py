"""New cases/prefill pipeline; the original Phase 4 tests remain untouched."""
import json
from pathlib import Path
import runpy

import pytest
from bench import core
from bench.catalog import post_attack_plans
from datagen.attack_cases import SCENARIOS, build

ATTACK = runpy.run_path(str(Path(__file__).resolve().parents[1]/"07_attack/gen_attack.py"))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_post_attack_builders_match_committed_attack_streams(scenario):
    pre, events = build(scenario, 12, burst=7)
    if scenario == "rotating_bursts":
        want = [], list(ATTACK["mem_rotating_bursts"](12, 7, 24))
    elif scenario == "pinned_dead":
        want = [], list(ATTACK["mem_pinned_dead"](12))
    else:
        want = ATTACK[scenario](12)
    assert (pre, events) == want
    for version in core.VERSIONS:
        a, b = core.make_book("A"), core.make_book(version)
        for event in pre+events:
            assert a.process(event) == b.process(event), (version, event)
            assert a.snapshot() == b.snapshot(), (version, event)


def test_post_attack_catalog_labels_modes_and_does_not_change_old_smoke():
    from bench.catalog import plans
    from bench.run_all import cases_for
    entries = post_attack_plans()
    assert len(entries) == 20 and {r["workload"] for r in entries} == set(SCENARIOS)
    assert all(r["registration"] == "added after Phase 4 from aif-attack" and r["own"] for r in entries)
    assert all(r["modes"] == ["memory"] for r in entries if r["workload"] in ("rotating_bursts", "pinned_dead"))
    assert all("latency" in r["modes"] for r in entries if r["workload"] == "spike_purge_at_threshold")
    assert not any("hash_full" in r["command"] for r in entries)
    smoke = cases_for("smoke", {"entries": plans()+entries})
    assert len(smoke) == 15 and all(c["size"] == 1000 and c["seed"] == 42 for c in smoke)


def test_prefill_is_separate_from_query_and_sample_is_not_empty():
    events = [{"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b",
               "side": "BUY", "price_ticks": 100, "qty_units": 3},
              {"seq": 2, "event_id": "e2", "type": "MARKET_SELL", "order_id": "t", "qty_units": 1}]
    case = {"part": "post_attack", "id": "test-prefill", "prefill_events": 1}
    book = core.prepare_book(case, events, "B3r")
    assert len(book.snapshot()) == 1
    assert core.workload_events(case, events) == events[1:]
    result = core.replay(book, core.workload_events(case, events))
    assert result["fills"][0]["maker_id"] == "b" and book.snapshot()[0]["qty_units"] == 2
    assert core.check_case(case, events, "B3r", True) == 2


@pytest.mark.parametrize("mode", ["timing", "latency", "memory", "counts"])
def test_prefilled_worker_modes_use_real_query(tmp_path, mode):
    import gzip
    import hashlib
    from bench.worker import run_job
    pre, work = build("spike_purge_at_threshold", 8)
    path = tmp_path/"spike.jsonl.gz"
    path.write_bytes(gzip.compress(("\n".join(json.dumps(e) for e in pre+work)+"\n").encode()))
    case = {"id": "prefilled-worker", "part": "post_attack", "label": "spike_purge_at_threshold",
            "workload": "spike_purge_at_threshold", "size": 8, "events": len(pre+work),
            "prefill_events": len(pre), "seed": 42, "levels": 8, "own": True,
            "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    journal = tmp_path/"records.jsonl"
    assert run_job({"case": case, "version": "B3r", "mode": mode, "journal": str(journal),
                    "limit_s": 20, "limit_bytes": 4*1024**3}) == 0
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    assert all(r["row"].get("replayed_events", 1) == 1 for r in records)
    if mode == "latency":
        rows = [r["row"] for r in records if r["kind"] == "latency"]
        assert all(r["n"] == 1 and r["max_ns"] > 0 for r in rows)
    if mode == "counts":
        rows = [r["row"] for r in records if r["kind"] == "counts"]
        assert any(r["phase"] == "construction" for r in rows)
        assert next(r["value"] for r in rows if r["phase"] == "replay" and r["counter"] == "fills") == 1
    if mode == "memory":
        samples = [r["row"] for r in records if r["kind"] == "memory" and r["row"]["measure"] == "curve"]
        assert samples[-1]["processed"] == len(pre+work)
        assert samples[-1]["live_orders"] == 8  # 1-unit sell partially fills a 2-unit maker.


def test_manifest_verification_is_idempotent_for_clean_session_start(tmp_path, monkeypatch):
    import gzip
    import hashlib
    import bench.catalog as catalog
    path = tmp_path/"fixture.jsonl.gz"
    path.write_bytes(gzip.compress(b"{}\n"))
    path.with_suffix(path.suffix+".metadata.json").write_text(json.dumps({
        "prefill_events": 0, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
    entry = {"id": "fixture", "path": str(path), "events": 1, "prefill_events": 0}
    (tmp_path/"00_docs").mkdir()
    monkeypatch.setattr(catalog, "ROOT", tmp_path)
    monkeypatch.setattr(catalog, "POST_MANIFEST", tmp_path/"manifest.json")
    monkeypatch.setattr(catalog, "load", lambda: {"entries": []})
    monkeypatch.setattr(catalog, "post_attack_plans", lambda: [dict(entry)])
    catalog.prepare_post_attack()
    before = (tmp_path/"00_docs/POST_ATTACK_MANIFEST.json").read_bytes()
    catalog.prepare_post_attack()
    assert (tmp_path/"00_docs/POST_ATTACK_MANIFEST.json").read_bytes() == before
