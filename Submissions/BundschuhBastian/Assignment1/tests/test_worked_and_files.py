"""The course's worked example, the replay command, the reader, and the five supplied files.

Expected results for the supplied files are derived from generate_orders.py, not from an
engine run:
  - buildup / crowded: bids are priced <= 6,000,000 and asks >= 6,000,100, so nothing
    ever crosses -> all 10,000 orders rest, no fills.
  - crowded: depth = randrange(4) -> 4 prices per side, 8 levels in total.
  - cancel_churn: every even seq cancels the order submitted just before it
    -> every cancel is "cancelled" and the book is empty at the end.
  - sweep: events 1-8000 are non-crossing limits, 8001-10000 are market sells. Bids only
    shrink through those sells, so all fills together = all bid units submitted, as long
    as the sells ask for more than that (they do: computed from the file in the test).
    Asks are never touched. Once the bids are gone, every later sell is "unfilled".
  - mixed: no closed-form result; only "no crash", invariants and conservation.
"""
import gzip
import json
from pathlib import Path

import pytest

from helpers import check_book, step

from lob.common import PARSE_ERROR_KEY, gross_value, load_events, proceeds_usd

DATA = Path(__file__).resolve().parent.parent / "data"


# --- worked example (6 BTC meet four resting buyers) --------------------------------------
def test_worked_example(book):
    events = load_events(DATA / "worked_example.jsonl")
    expected = json.loads((DATA / "worked_expected.json").read_text())
    results = [step(book, ev) for ev in events]
    assert [r["status"] for r in results[:5]] == ["resting"] * 5
    assert results[5] == expected["market_sell_result"]
    assert book.snapshot() == expected["remaining_orders"]
    assert gross_value(results[5]["fills"]) == expected["gross_proceeds_tick_units"]
    assert proceeds_usd(gross_value(results[5]["fills"])) == expected["gross_proceeds_usd"]


def test_worked_example_by_hand(book):
    """Same example, numbers re-derived by hand (independent of worked_expected.json).

    1 BTC = 100,000,000 units; 60,000 USD = 6,000,000 ticks.
    b1 1 BTC @60,000 + b2 1 BTC @60,000 + b3 3 BTC @59,900 + b4 1 BTC @59,700 = 6 BTC
    USD: 60,000 + 60,000 + 179,700 + 59,700 = 359,400.
    """
    for ev in load_events(DATA / "worked_example.jsonl"):
        res = step(book, ev)
    btc = 100_000_000
    assert [(f["maker_id"], f["qty_units"] // btc) for f in res["fills"]] == [
        ("b1", 1), ("b2", 1), ("b3", 3), ("b4", 1)]
    assert gross_value(res["fills"]) == 359_400 * 10**10
    assert [(o["order_id"], o["qty_units"] // btc) for o in book.snapshot()] == [
        ("b4", 4), ("a1", 2)]


@pytest.mark.parametrize("version", ["A", "B"])
def test_replay_command_on_worked_example(version, capsys):
    from lob.replay import main
    assert main([str(DATA / "worked_example.jsonl"), "--version", version, "--quiet"]) == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["gross_value_usd"] == "359400.00"
    assert summary["status_counts"] == {"resting": 5, "filled": 1}
    assert [o["order_id"] for o in summary["remaining_orders"]] == ["b4", "a1"]


# --- reader (implemented in Phase 0) ----------------------------------------------------
def test_reader_handles_blank_bad_and_crlf_lines(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_bytes(b'{"seq":1}\r\n\n   \nnot json\n[1,2]\n"str"\n{"seq":2}')   # no final \n
    assert load_events(p) == [{"seq": 1}, {PARSE_ERROR_KEY: 4}, {PARSE_ERROR_KEY: 5},
                              {PARSE_ERROR_KEY: 6}, {"seq": 2}]


def test_reader_gzip_and_empty_file(tmp_path):
    gz = tmp_path / "x.jsonl.gz"
    with gzip.open(gz, "wt") as f:
        f.write('{"seq":1}\n{"seq":2}\n')
    assert load_events(gz) == [{"seq": 1}, {"seq": 2}]
    empty = tmp_path / "e.jsonl"
    empty.write_text("")
    assert load_events(empty) == []


def test_malformed_line_from_reader_is_rejected_not_crashed(book, tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text('{"seq":1,"event_id":"e1","type":"LIMIT","order_id":"b1","side":"BUY",'
                 '"price_ticks":100,"qty_units":1}\n{oops\n')
    results = [step(book, ev) for ev in load_events(p)]
    assert results[1] == {"event_id": None, "status": "rejected",
                          "reason": "malformed_event", "fills": []}


# --- supplied 10,000-event files: no crash + checks every 250 events ---------------------
def replay_checked(book, events, every=250):
    """Fast replay: cheap per-event checks, full invariant check every `every` events."""
    results = []
    for i, ev in enumerate(events, start=1):
        res = book.process(ev)
        assert isinstance(res, dict) and res["status"] != "rejected", (i, res)
        if "unfilled_qty_units" in res:                  # I4 on every submission
            assert sum(f["qty_units"] for f in res["fills"]) + res["unfilled_qty_units"] \
                == ev["qty_units"], (i, res)
        if i % every == 0 or i == len(events):
            check_book(book, book.snapshot())
        results.append(res)
    return results


def test_supplied_buildup(book):
    res = replay_checked(book, load_events(DATA / "buildup_10000.jsonl.gz"))
    assert all(r["status"] == "resting" and r["fills"] == [] for r in res)
    assert len(book.snapshot()) == 10_000


def test_supplied_crowded(book):
    res = replay_checked(book, load_events(DATA / "crowded_10000.jsonl.gz"))
    assert all(r["status"] == "resting" for r in res)
    snap = book.snapshot()
    assert len(snap) == 10_000
    assert len({(o["side"], o["price_ticks"]) for o in snap}) == 8


def test_supplied_cancel_churn(book):
    res = replay_checked(book, load_events(DATA / "cancel_churn_10000.jsonl.gz"))
    assert [r["status"] for r in res[1::2]] == ["cancelled"] * 5000
    assert book.snapshot() == []


def test_supplied_sweep(book):
    events = load_events(DATA / "sweep_10000.jsonl.gz")
    limits = [e for e in events if e["type"] == "LIMIT"]
    sells = [e for e in events if e["type"] == "MARKET_SELL"]
    assert len(limits) == 8000 and len(sells) == 2000          # build, then sweep
    bid_units = sum(e["qty_units"] for e in limits if e["side"] == "BUY")
    asks = [e for e in limits if e["side"] == "SELL"]
    assert sum(e["qty_units"] for e in sells[:-1]) > bid_units  # bids run out early

    res = replay_checked(book, events)
    sell_res = res[8000:]
    assert sum(f["qty_units"] for r in sell_res for f in r["fills"]) == bid_units
    assert book.best_bid() is None
    assert len(book.snapshot()) == len(asks)                    # asks untouched
    # status by remaining depth: once a sell is not fully filled, all later ones are unfilled
    first_short = next(i for i, r in enumerate(sell_res) if r["unfilled_qty_units"] > 0)
    assert sell_res[first_short]["status"] in ("partial", "unfilled")
    assert all(r["status"] == "unfilled" for r in sell_res[first_short + 1:])
    assert all(r["status"] == "filled" for r in sell_res[:first_short])
    assert res[-1] == {"event_id": events[-1]["event_id"], "order_id": events[-1]["order_id"],
                       "status": "unfilled", "unfilled_qty_units": events[-1]["qty_units"],
                       "fills": []}


def test_supplied_mixed(book):
    replay_checked(book, load_events(DATA / "mixed_10000.jsonl.gz"))
