"""Order book tests grouped by category, using Python assertions.

Run from Assignment1; the default mode compares both versions after each event:
    python -B test_order_book.py --implementation baseline
    python -B test_order_book.py --implementation revised
    python -B test_order_book.py --implementation compare
    python -B test_order_book.py --implementation compare --category market-sells

Category selectors: market-sells, price-time, limit-orders, cancellations,
validation, integration. Omitting --category runs all six categories.
Pytest can also discover the classes; its default mode is compare:
    python -m pytest -q test_order_book.py

Both versions implement process_event(event) and inspect_book(), returning
event-result dictionaries and {"bids": [...], "asks": [...]} book snapshots.
Public handlers AddLimitOrder(event), FillMarketSell(event) and CancelOrder(event)
accept the same full event dictionaries. Resting orders have order_id, side,
price_ticks, qty_units and arrival_seq. Bids sort by descending price then
arrival_seq; asks sort by ascending price then arrival_seq.

Prices, quantities and sequences must be positive built-in integers, excluding
booleans. event_id must be a nonblank string and results preserve its value.
Missing required fields and nonincreasing sequences are rejected without
changing the book or consuming the rejected sequence.

The external dispatcher exposes replay_file(path, book), for .jsonl and
.jsonl.gz files, returning results in input order. Invalid file paths and
malformed records raise informative exceptions.

Baseline uses list storage; Revised uses a FIFO deque per side and price.
Both preserve the same validation, integer units and price-time matching rules.
The same behavioral tests cover each implementation and comparison mode.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


BTC_UNITS = 100_000_000
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"


# Helpers build inputs and independently specified expected outputs only.
def limit_event(seq, order_id, side, price_ticks, qty_units):
    return {
        "seq": seq, "event_id": f"event{seq}", "type": "LIMIT",
        "order_id": order_id, "side": side,
        "price_ticks": price_ticks, "qty_units": qty_units,
    }


def market_sell_event(seq, order_id, qty_units):
    return {
        "seq": seq, "event_id": f"event{seq}", "type": "MARKET_SELL",
        "order_id": order_id, "qty_units": qty_units,
    }


def cancel_event(seq, target_order_id):
    return {
        "seq": seq, "event_id": f"event{seq}", "type": "CANCEL",
        "target_order_id": target_order_id,
    }


def expected_fill(maker_id, taker_id, price_ticks, qty_units):
    return {
        "maker_id": maker_id, "taker_id": taker_id,
        "price_ticks": price_ticks, "qty_units": qty_units,
    }


def resting_order(order_id, side, price_ticks, qty_units, arrival_seq):
    return {
        "order_id": order_id, "side": side, "price_ticks": price_ticks,
        "qty_units": qty_units, "arrival_seq": arrival_seq,
    }


class _RecordingBook:
    """Test double for comparison/path tests; contains no matching algorithm."""

    def __init__(self, result_mismatch_at=None, book_mismatch_at=None,
                 float_quantity_at=None):
        self.events = []
        self.snapshot_count = 0
        self.result_mismatch_at = result_mismatch_at
        self.book_mismatch_at = book_mismatch_at
        self.float_quantity_at = float_quantity_at

    def process_event(self, event):
        self.events.append(deepcopy(event))
        result = {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "status": "unfilled",
            "fills": [],
            "unfilled_qty_units": event["qty_units"],
        }
        if len(self.events) == self.result_mismatch_at:
            result["unfilled_qty_units"] += 1
        if len(self.events) == self.float_quantity_at:
            result["unfilled_qty_units"] = float(result["unfilled_qty_units"])
        return result

    def inspect_book(self):
        self.snapshot_count += 1
        if len(self.events) == self.book_mismatch_at:
            return {
                "bids": [resting_order("unexpected", "BUY", 10_000, 1, 1)],
                "asks": [],
            }
        return {"bids": [], "asks": []}


class _BookTests(unittest.TestCase):
    """Shared setup and assertions; this base class contains no test methods."""

    implementation = "compare"

    def setUp(self):
        from order_book import create_order_book

        # Every call returns fresh, explicitly selected book instances.
        self.book_type = lambda: create_order_book(self.implementation)
        self.book = self.book_type()

    def check_submission(self, result, event, status, fills, unfilled):
        assert result["event_id"] == event["event_id"]
        assert result["order_id"] == event["order_id"]
        assert result["status"] == status
        assert result["fills"] == fills
        assert result["unfilled_qty_units"] == unfilled
        assert type(result["unfilled_qty_units"]) is int
        for fill in result["fills"]:
            assert type(fill["price_ticks"]) is int
            assert type(fill["qty_units"]) is int

    def check_book(self, bids=(), asks=()):
        snapshot = self.book.inspect_book()
        assert snapshot["bids"] == list(bids)
        assert snapshot["asks"] == list(asks)

    def check_cancel(self, result, event, status, cancelled):
        assert result["event_id"] == event["event_id"]
        assert result["target_order_id"] == event["target_order_id"]
        assert result["status"] == status
        assert result["cancelled_qty_units"] == cancelled
        assert type(result["cancelled_qty_units"]) is int

    def check_rejected(self, event):
        before = deepcopy(self.book.inspect_book())
        result = self.book.process_event(event)
        assert result["status"] == "rejected"
        assert isinstance(result["reason"], str) and result["reason"].strip()
        if "event_id" in event:
            assert result["event_id"] == event["event_id"]
        assert self.book.inspect_book() == before

    def seed_two_sides(self):
        self.book.process_event(limit_event(1, "A", "BUY", 10_000, BTC_UNITS))
        self.book.process_event(limit_event(2, "Z", "SELL", 11_000, BTC_UNITS))


class TestMarketSells(_BookTests):
    """1. Market sells. Selector: market-sells."""

    def test_market_sell_one_btc_on_empty_book(self):
        """An empty book cannot fill a market sell or retain its residual."""
        book = self.book

        result = book.process_event({
            "seq": 1,
            "event_id": "event1",
            "type": "MARKET_SELL",
            "order_id": "sell1",
            "qty_units": BTC_UNITS,
        })
        remaining_book = book.inspect_book()

        assert result["status"] == "unfilled"
        assert result["fills"] == []
        assert result["unfilled_qty_units"] == BTC_UNITS
        assert remaining_book["bids"] == []
        assert remaining_book["asks"] == []


    def test_market_sell_one_btc_against_two_btc_bid(self):
        """Sell 1 BTC to A at $100, leaving A's remaining 1 BTC on the bid side."""
        book = self.book

        # A submits a bid for 2 BTC at $100 per BTC (10,000 cents).
        book.process_event({
            "seq": 1,
            "event_id": "event1",
            "type": "LIMIT",
            "order_id": "A",
            "side": "BUY",
            "price_ticks": 10_000,
            "qty_units": 2 * BTC_UNITS,
        })

        result = book.process_event({
            "seq": 2,
            "event_id": "event2",
            "type": "MARKET_SELL",
            "order_id": "sell1",
            "qty_units": BTC_UNITS,
        })
        remaining_book = book.inspect_book()

        assert result["status"] == "filled"
        assert result["fills"] == [{
            "maker_id": "A",
            "taker_id": "sell1",
            "price_ticks": 10_000,
            "qty_units": BTC_UNITS,
        }]
        assert result["unfilled_qty_units"] == 0
        assert remaining_book["bids"] == [{
            "order_id": "A",
            "side": "BUY",
            "price_ticks": 10_000,
            "qty_units": BTC_UNITS,
            "arrival_seq": 1,
        }]
        assert remaining_book["asks"] == []


    def test_market_sell_two_btc_against_two_btc_bid(self):
        """Sell 2 BTC to A at $100, fully consuming and removing A's bid."""
        book = self.book

        book.process_event({
            "seq": 1,
            "event_id": "event1",
            "type": "LIMIT",
            "order_id": "A",
            "side": "BUY",
            "price_ticks": 10_000,
            "qty_units": 2 * BTC_UNITS,
        })

        result = book.process_event({
            "seq": 2,
            "event_id": "event2",
            "type": "MARKET_SELL",
            "order_id": "sell1",
            "qty_units": 2 * BTC_UNITS,
        })
        remaining_book = book.inspect_book()

        assert result["status"] == "filled"
        assert result["fills"] == [{
            "maker_id": "A",
            "taker_id": "sell1",
            "price_ticks": 10_000,
            "qty_units": 2 * BTC_UNITS,
        }]
        assert result["unfilled_qty_units"] == 0
        assert remaining_book["bids"] == []
        assert remaining_book["asks"] == []

    def test_requested_quantity_larger_than_available_bids(self):
        self.book.process_event(
            limit_event(1, "A", "BUY", 10_000, 2 * BTC_UNITS)
        )
        event = market_sell_event(2, "sell1", 3 * BTC_UNITS)
        result = self.book.process_event(event)

        self.check_submission(
            result, event, "partial",
            [expected_fill("A", "sell1", 10_000, 2 * BTC_UNITS)],
            BTC_UNITS,
        )
        self.check_book()

    def test_resting_asks_unchanged_when_no_bids_are_available(self):
        self.book.process_event(
            limit_event(1, "A", "SELL", 11_000, 2 * BTC_UNITS)
        )
        event = market_sell_event(2, "sell1", BTC_UNITS)
        result = self.book.process_event(event)

        self.check_submission(result, event, "unfilled", [], BTC_UNITS)
        self.check_book(asks=[
            resting_order("A", "SELL", 11_000, 2 * BTC_UNITS, 1),
        ])


class TestPriceTimePriority(_BookTests):
    """2. Price-time priority. Selector: price-time."""

    def test_better_bid_price_precedes_earlier_arrival(self):
        self.book.process_event(limit_event(1, "A", "BUY", 10_000, BTC_UNITS))
        self.book.process_event(limit_event(2, "Z", "BUY", 10_100, BTC_UNITS))
        event = market_sell_event(3, "sell1", BTC_UNITS)

        self.check_submission(
            self.book.process_event(event), event, "filled",
            [expected_fill("Z", "sell1", 10_100, BTC_UNITS)], 0,
        )
        self.check_book(bids=[
            resting_order("A", "BUY", 10_000, BTC_UNITS, 1),
        ])

    def test_bid_fifo_follows_arrival_not_identifier_spelling(self):
        self.book.process_event(limit_event(1, "Z", "BUY", 10_000, BTC_UNITS))
        self.book.process_event(limit_event(2, "A", "BUY", 10_000, BTC_UNITS))
        event = market_sell_event(3, "sell1", 2 * BTC_UNITS)

        self.check_submission(
            self.book.process_event(event), event, "filled", [
                expected_fill("Z", "sell1", 10_000, BTC_UNITS),
                expected_fill("A", "sell1", 10_000, BTC_UNITS),
            ], 0,
        )
        self.check_book()

    def test_partially_filled_maker_retains_priority_for_next_sale(self):
        self.book.process_event(
            limit_event(1, "Z", "BUY", 10_000, 2 * BTC_UNITS)
        )
        self.book.process_event(limit_event(2, "A", "BUY", 10_000, BTC_UNITS))
        first = market_sell_event(3, "sell1", BTC_UNITS)

        self.check_submission(
            self.book.process_event(first), first, "filled",
            [expected_fill("Z", "sell1", 10_000, BTC_UNITS)], 0,
        )
        self.check_book(bids=[
            resting_order("Z", "BUY", 10_000, BTC_UNITS, 1),
            resting_order("A", "BUY", 10_000, BTC_UNITS, 2),
        ])

        second = market_sell_event(4, "sell2", BTC_UNITS)
        self.check_submission(
            self.book.process_event(second), second, "filled",
            [expected_fill("Z", "sell2", 10_000, BTC_UNITS)], 0,
        )
        self.check_book(bids=[
            resting_order("A", "BUY", 10_000, BTC_UNITS, 2),
        ])

    def test_sale_walks_price_levels_in_descending_order(self):
        self.book.process_event(limit_event(1, "A", "BUY", 9_900, BTC_UNITS))
        self.book.process_event(limit_event(2, "B", "BUY", 10_100, BTC_UNITS))
        self.book.process_event(limit_event(3, "C", "BUY", 10_000, BTC_UNITS))
        event = market_sell_event(4, "sell1", 2 * BTC_UNITS + BTC_UNITS // 2)

        self.check_submission(
            self.book.process_event(event), event, "filled", [
                expected_fill("B", "sell1", 10_100, BTC_UNITS),
                expected_fill("C", "sell1", 10_000, BTC_UNITS),
                expected_fill("A", "sell1", 9_900, BTC_UNITS // 2),
            ], 0,
        )
        self.check_book(bids=[
            resting_order("A", "BUY", 9_900, BTC_UNITS // 2, 1),
        ])

    def test_resting_asks_obey_fifo(self):
        self.book.process_event(limit_event(1, "Z", "SELL", 10_000, BTC_UNITS))
        self.book.process_event(limit_event(2, "A", "SELL", 10_000, BTC_UNITS))
        event = limit_event(
            3, "buy1", "BUY", 10_100, BTC_UNITS + BTC_UNITS // 2
        )

        self.check_submission(
            self.book.process_event(event), event, "filled", [
                expected_fill("Z", "buy1", 10_000, BTC_UNITS),
                expected_fill("A", "buy1", 10_000, BTC_UNITS // 2),
            ], 0,
        )
        self.check_book(asks=[
            resting_order("A", "SELL", 10_000, BTC_UNITS // 2, 2),
        ])

    def test_long_queue_preserves_fifo_with_reversed_identifiers(self):
        count = 256
        ids = [f"bid{rank:04d}" for rank in range(count, 0, -1)]
        for seq, order_id in enumerate(ids, start=1):
            self.book.process_event(limit_event(seq, order_id, "BUY", 10_000, 1))

        event = market_sell_event(count + 1, "sell1", count)
        self.check_submission(
            self.book.process_event(event), event, "filled",
            [expected_fill(order_id, "sell1", 10_000, 1) for order_id in ids],
            0,
        )
        self.check_book()


class TestLimitOrders(_BookTests):
    """3. Limit orders. Selector: limit-orders."""

    def test_crossing_buy_uses_resting_ask_prices_and_rests_residual(self):
        self.book.process_event(limit_event(1, "A", "SELL", 10_000, BTC_UNITS))
        self.book.process_event(limit_event(2, "B", "SELL", 9_900, BTC_UNITS))
        event = limit_event(3, "buy1", "BUY", 10_050, 3 * BTC_UNITS)

        self.check_submission(
            self.book.process_event(event), event, "resting", [
                expected_fill("B", "buy1", 9_900, BTC_UNITS),
                expected_fill("A", "buy1", 10_000, BTC_UNITS),
            ], BTC_UNITS,
        )
        self.check_book(bids=[
            resting_order("buy1", "BUY", 10_050, BTC_UNITS, 3),
        ])

    def test_crossing_sell_uses_resting_bid_prices_and_rests_residual(self):
        self.book.process_event(limit_event(1, "A", "BUY", 10_100, BTC_UNITS))
        self.book.process_event(limit_event(2, "B", "BUY", 10_000, BTC_UNITS))
        event = limit_event(3, "sell1", "SELL", 9_950, 3 * BTC_UNITS)

        self.check_submission(
            self.book.process_event(event), event, "resting", [
                expected_fill("A", "sell1", 10_100, BTC_UNITS),
                expected_fill("B", "sell1", 10_000, BTC_UNITS),
            ], BTC_UNITS,
        )
        self.check_book(asks=[
            resting_order("sell1", "SELL", 9_950, BTC_UNITS, 3),
        ])

    def test_equal_prices_cross_with_no_residual_after_exact_fill(self):
        for incoming_side, resting_side in (("BUY", "SELL"), ("SELL", "BUY")):
            with self.subTest(incoming_side=incoming_side):
                self.book = self.book_type()
                self.book.process_event(
                    limit_event(1, "A", resting_side, 10_000, BTC_UNITS)
                )
                event = limit_event(2, "incoming", incoming_side, 10_000, BTC_UNITS)

                self.check_submission(
                    self.book.process_event(event), event, "filled",
                    [expected_fill("A", "incoming", 10_000, BTC_UNITS)], 0,
                )
                self.check_book()

    def test_noncrossing_limits_remain_on_their_respective_sides(self):
        bid = limit_event(1, "A", "BUY", 10_000, BTC_UNITS)
        ask = limit_event(2, "B", "SELL", 10_100, 2 * BTC_UNITS)
        self.check_submission(
            self.book.process_event(bid), bid, "resting", [], BTC_UNITS,
        )
        self.check_submission(
            self.book.process_event(ask), ask, "resting", [], 2 * BTC_UNITS,
        )
        self.check_book(
            bids=[resting_order("A", "BUY", 10_000, BTC_UNITS, 1)],
            asks=[resting_order("B", "SELL", 10_100, 2 * BTC_UNITS, 2)],
        )


class TestCancellations(_BookTests):
    """4. Cancellations. Selector: cancellations."""

    def test_cancel_before_any_execution(self):
        self.book.process_event(
            limit_event(1, "A", "BUY", 10_000, 2 * BTC_UNITS)
        )
        event = cancel_event(2, "A")
        self.check_cancel(
            self.book.process_event(event), event, "cancelled", 2 * BTC_UNITS,
        )
        self.check_book()

    def test_cancel_only_remaining_quantity_after_partial_fill(self):
        self.book.process_event(
            limit_event(1, "A", "BUY", 10_000, 2 * BTC_UNITS)
        )
        self.book.process_event(market_sell_event(2, "sell1", BTC_UNITS))
        event = cancel_event(3, "A")

        self.check_cancel(
            self.book.process_event(event), event, "cancelled", BTC_UNITS,
        )
        self.check_book()

    def test_repeat_cancellation_returns_not_found_and_zero_quantity(self):
        self.book.process_event(limit_event(1, "A", "BUY", 10_000, BTC_UNITS))
        self.book.process_event(cancel_event(2, "A"))
        event = cancel_event(3, "A")

        self.check_cancel(self.book.process_event(event), event, "not_found", 0)
        self.check_book()

    def test_cancel_fully_filled_order_returns_not_found(self):
        self.book.process_event(limit_event(1, "A", "BUY", 10_000, BTC_UNITS))
        self.book.process_event(market_sell_event(2, "sell1", BTC_UNITS))
        event = cancel_event(3, "A")

        self.check_cancel(self.book.process_event(event), event, "not_found", 0)
        self.check_book()

    def test_unknown_cancellation_is_valid_and_advances_sequence(self):
        event = cancel_event(1, "unknown")
        self.check_cancel(self.book.process_event(event), event, "not_found", 0)
        self.check_book()

        # Sequence 1 was accepted, even though there was no order to cancel.
        self.check_rejected(limit_event(1, "A", "BUY", 10_000, BTC_UNITS))
        next_event = limit_event(2, "A", "BUY", 10_000, BTC_UNITS)
        self.check_submission(
            self.book.process_event(next_event), next_event,
            "resting", [], BTC_UNITS,
        )
        self.check_book(bids=[
            resting_order("A", "BUY", 10_000, BTC_UNITS, 2),
        ])

    def test_cancelling_ask_preserves_other_active_orders(self):
        self.book.process_event(
            limit_event(1, "A", "SELL", 11_000, 2 * BTC_UNITS)
        )
        self.book.process_event(limit_event(2, "B", "BUY", 10_000, BTC_UNITS))
        self.book.process_event(limit_event(3, "C", "SELL", 12_000, BTC_UNITS))
        event = cancel_event(4, "A")

        self.check_cancel(
            self.book.process_event(event), event, "cancelled", 2 * BTC_UNITS,
        )
        self.check_book(
            bids=[resting_order("B", "BUY", 10_000, BTC_UNITS, 2)],
            asks=[resting_order("C", "SELL", 12_000, BTC_UNITS, 3)],
        )

    def test_cancelling_middle_of_queue_preserves_other_orders_fifo(self):
        for seq, order_id in enumerate(("Z", "M", "A"), start=1):
            self.book.process_event(
                limit_event(seq, order_id, "BUY", 10_000, BTC_UNITS)
            )
        cancel = cancel_event(4, "M")
        self.check_cancel(
            self.book.process_event(cancel), cancel, "cancelled", BTC_UNITS,
        )
        self.check_book(bids=[
            resting_order("Z", "BUY", 10_000, BTC_UNITS, 1),
            resting_order("A", "BUY", 10_000, BTC_UNITS, 3),
        ])

        sell = market_sell_event(5, "sell1", 2 * BTC_UNITS)
        self.check_submission(
            self.book.process_event(sell), sell, "filled", [
                expected_fill("Z", "sell1", 10_000, BTC_UNITS),
                expected_fill("A", "sell1", 10_000, BTC_UNITS),
            ], 0,
        )
        self.check_book()


class TestValidation(_BookTests):
    """5. Validation and exact integers. Selector: validation."""

    def test_large_integer_prices_and_quantities_remain_exact(self):
        price = 2**53 + 1
        quantity = 2**53 + 7
        self.book.process_event(limit_event(1, "A", "BUY", price, quantity))
        self.check_book(bids=[
            resting_order("A", "BUY", price, quantity, 1),
        ])
        event = market_sell_event(2, "sell1", quantity - 1)
        result = self.book.process_event(event)

        self.check_submission(
            result, event, "filled",
            [expected_fill("A", "sell1", price, quantity - 1)], 0,
        )
        self.check_book(bids=[resting_order("A", "BUY", price, 1, 1)])
        trade = result["fills"][0]
        assert type(trade["price_ticks"]) is int
        assert type(trade["qty_units"]) is int
        remaining = self.book.inspect_book()["bids"][0]
        assert type(remaining["price_ticks"]) is int
        assert type(remaining["qty_units"]) is int
        assert type(result["unfilled_qty_units"]) is int

    def test_invalid_numeric_values_rejected_without_changing_book(self):
        self.seed_two_sides()
        invalid_values = (
            0, -1, 1.5, 1.0, "1", True, False, None,
            float("nan"), float("inf"), complex(1, 0),
            Decimal("1"), Fraction(1, 1), [], {}, (1,), b"1",
        )
        examples = (
            (limit_event(3, "bad", "BUY", 10_000, BTC_UNITS), "price_ticks"),
            (limit_event(3, "bad", "BUY", 10_000, BTC_UNITS), "qty_units"),
            (market_sell_event(3, "bad", BTC_UNITS), "qty_units"),
        )
        for template, field in examples:
            for value in invalid_values:
                with self.subTest(type=template["type"], field=field, value=value):
                    event = dict(template)
                    event[field] = value
                    self.check_rejected(event)

    def test_unknown_event_types_and_sides_rejected(self):
        self.seed_two_sides()
        for value in ("UNKNOWN", "", None, 0, True, [], {}):
            with self.subTest(event_type=value):
                event = market_sell_event(3, "bad", BTC_UNITS)
                event["type"] = value
                self.check_rejected(event)
        for value in ("HOLD", "buy", "", None, 0, True, [], {}):
            with self.subTest(side=value):
                self.check_rejected(
                    limit_event(3, "bad", value, 10_000, BTC_UNITS)
                )

    def test_missing_required_fields_rejected(self):
        self.seed_two_sides()
        templates = (
            limit_event(3, "bad", "BUY", 10_000, BTC_UNITS),
            market_sell_event(3, "bad", BTC_UNITS),
            cancel_event(3, "A"),
        )
        for template in templates:
            for field in template:
                with self.subTest(event_type=template["type"], missing=field):
                    event = dict(template)
                    del event[field]
                    self.check_rejected(event)

    def test_duplicate_live_submission_ids_rejected(self):
        self.seed_two_sides()
        duplicates = (
            limit_event(3, "A", "BUY", 9_900, BTC_UNITS),
            limit_event(3, "A", "SELL", 10_000, BTC_UNITS),
            market_sell_event(3, "A", BTC_UNITS),
        )
        for event in duplicates:
            with self.subTest(event_type=event["type"], side=event.get("side")):
                self.check_rejected(event)

    def test_nonincreasing_or_invalid_arrival_sequences_rejected(self):
        self.seed_two_sides()
        for seq in (
            2, 1, 0, -1, 3.0, 3.5, "3", True, False, None,
            float("nan"), float("inf"), complex(3, 0),
            Decimal("3"), Fraction(3, 1), [], {},
        ):
            with self.subTest(seq=seq):
                self.check_rejected(
                    limit_event(seq, "bad", "BUY", 9_900, BTC_UNITS)
                )

        # On an empty book, True and 1.0 would pass a loose positive-number check.
        for seq in (True, False, 1.0, "1", None):
            with self.subTest(first_seq=seq):
                self.book = self.book_type()
                self.check_rejected(
                    limit_event(seq, "bad", "BUY", 10_000, BTC_UNITS)
                )

    def test_rejected_event_does_not_consume_arrival_sequence(self):
        self.book.process_event(limit_event(1, "A", "BUY", 10_000, BTC_UNITS))
        self.check_rejected(market_sell_event(2, "sell1", 0))
        event = market_sell_event(2, "sell1", BTC_UNITS)

        self.check_submission(
            self.book.process_event(event), event, "filled",
            [expected_fill("A", "sell1", 10_000, BTC_UNITS)], 0,
        )
        self.check_book()


    def test_invalid_event_id_values_rejected(self):
        self.seed_two_sides()
        for event_id in ("", " ", "\t", None, 0, False, 1.5, [], {}):
            with self.subTest(event_id=event_id):
                event = market_sell_event(3, "sell1", BTC_UNITS)
                event["event_id"] = event_id
                self.check_rejected(event)

    def test_event_id_values_preserved_for_every_result_kind(self):
        bid = limit_event(1, "A", "BUY", 10_000, 2 * BTC_UNITS)
        bid["event_id"] = "client-limit-009"
        self.check_submission(
            self.book.process_event(bid), bid, "resting", [], 2 * BTC_UNITS,
        )

        sell = market_sell_event(2, "sell1", BTC_UNITS)
        sell["event_id"] = "client-sale-204"
        self.check_submission(
            self.book.process_event(sell), sell, "filled",
            [expected_fill("A", "sell1", 10_000, BTC_UNITS)], 0,
        )

        cancel = cancel_event(3, "A")
        cancel["event_id"] = "client-cancel-071"
        self.check_cancel(
            self.book.process_event(cancel), cancel, "cancelled", BTC_UNITS,
        )

        unknown = cancel_event(4, "unknown")
        unknown["event_id"] = "client-cancel-unknown"
        self.check_cancel(
            self.book.process_event(unknown), unknown, "not_found", 0,
        )

        invalid = market_sell_event(5, "bad", 0)
        invalid["event_id"] = "client-rejected-sale"
        self.check_rejected(invalid)
        empty_sell = market_sell_event(5, "sell2", BTC_UNITS)
        empty_sell["event_id"] = "client-empty-sale"
        self.check_submission(
            self.book.process_event(empty_sell), empty_sell,
            "unfilled", [], BTC_UNITS,
        )
        self.check_book()

    def test_reference_file_paths_are_present(self):
        assert PROJECT_DIR.is_dir()
        for name in ("worked_example.jsonl", "worked_expected.json"):
            path = DATA_DIR / name
            assert path.is_file(), f"Missing assignment reference file: {path}"

    def test_external_dispatcher_validates_file_paths(self):
        from dispatcher import replay_file

        recorder = _RecordingBook()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            unsupported = root / "orders.txt"
            unsupported.write_text("", encoding="utf-8")
            cases = (
                (root / "missing.jsonl", FileNotFoundError),
                (root / "missing.jsonl.gz", FileNotFoundError),
                (root, IsADirectoryError),
                (unsupported, ValueError),
            )
            for path, error_type in cases:
                with self.subTest(path=str(path)):
                    with self.assertRaises(error_type) as caught:
                        replay_file(path, recorder)
                    assert str(path) in str(caught.exception)
                    assert recorder.events == []

    def test_external_dispatcher_closes_file_when_handler_fails(self):
        from dispatcher import replay_file

        class FailingBook:
            def process_event(self, event):
                raise RuntimeError("Handler failed.")

        with TemporaryDirectory() as directory:
            path = Path(directory) / "orders.jsonl"
            path.write_text(
                json.dumps(market_sell_event(1, "sell1", BTC_UNITS)) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "Handler failed"):
                replay_file(path, FailingBook())
            path.unlink()
            assert not path.exists()

    def test_external_dispatcher_reports_path_and_line_for_invalid_records(self):
        from dispatcher import replay_file

        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.jsonl"
            for record in ('{"broken":', "[]", "null"):
                with self.subTest(record=record):
                    path.write_text("\n" + record + "\n", encoding="utf-8")
                    recorder = _RecordingBook()
                    with self.assertRaises(ValueError) as caught:
                        replay_file(path, recorder)
                    assert str(path) in str(caught.exception)
                    assert ":2:" in str(caught.exception)
                    assert recorder.events == []


class TestIntegration(_BookTests):
    """6. Integration and book state. Selector: integration."""

    def test_inspect_empty_book(self):
        self.check_book()

    def test_inspect_both_sides_in_canonical_price_time_order(self):
        events = (
            limit_event(1, "bid_low", "BUY", 9_900, BTC_UNITS),
            limit_event(2, "bid_Z", "BUY", 10_000, BTC_UNITS),
            limit_event(3, "ask_high", "SELL", 11_200, BTC_UNITS),
            limit_event(4, "ask_Z", "SELL", 11_000, BTC_UNITS),
            limit_event(5, "bid_A", "BUY", 10_000, BTC_UNITS),
            limit_event(6, "ask_A", "SELL", 11_000, BTC_UNITS),
        )
        for event in events:
            self.book.process_event(event)

        self.check_book(
            bids=[
                resting_order("bid_Z", "BUY", 10_000, BTC_UNITS, 2),
                resting_order("bid_A", "BUY", 10_000, BTC_UNITS, 5),
                resting_order("bid_low", "BUY", 9_900, BTC_UNITS, 1),
            ],
            asks=[
                resting_order("ask_Z", "SELL", 11_000, BTC_UNITS, 4),
                resting_order("ask_A", "SELL", 11_000, BTC_UNITS, 6),
                resting_order("ask_high", "SELL", 11_200, BTC_UNITS, 3),
            ],
        )

    def test_call_each_public_handler_directly(self):
        bid = limit_event(1, "A", "BUY", 10_000, 2 * BTC_UNITS)
        self.check_submission(
            self.book.AddLimitOrder(bid), bid, "resting", [], 2 * BTC_UNITS,
        )
        self.check_book(bids=[
            resting_order("A", "BUY", 10_000, 2 * BTC_UNITS, 1),
        ])

        sell = market_sell_event(2, "sell1", BTC_UNITS)
        self.check_submission(
            self.book.FillMarketSell(sell), sell, "filled",
            [expected_fill("A", "sell1", 10_000, BTC_UNITS)], 0,
        )
        self.check_book(bids=[
            resting_order("A", "BUY", 10_000, BTC_UNITS, 1),
        ])

        cancel = cancel_event(3, "A")
        self.check_cancel(
            self.book.CancelOrder(cancel), cancel, "cancelled", BTC_UNITS,
        )
        self.check_book()

    def test_dispatch_limit_market_sell_and_cancel_on_one_book(self):
        bid = limit_event(1, "A", "BUY", 10_000, 2 * BTC_UNITS)
        self.check_submission(
            self.book.process_event(bid), bid, "resting", [], 2 * BTC_UNITS,
        )
        self.check_book(bids=[
            resting_order("A", "BUY", 10_000, 2 * BTC_UNITS, 1),
        ])

        sell = market_sell_event(2, "sell1", BTC_UNITS)
        self.check_submission(
            self.book.process_event(sell), sell, "filled",
            [expected_fill("A", "sell1", 10_000, BTC_UNITS)], 0,
        )
        self.check_book(bids=[
            resting_order("A", "BUY", 10_000, BTC_UNITS, 1),
        ])

        cancel = cancel_event(3, "A")
        self.check_cancel(
            self.book.process_event(cancel), cancel, "cancelled", BTC_UNITS,
        )
        self.check_book()

    def test_replay_professors_six_btc_reference_example(self):
        with (DATA_DIR / "worked_example.jsonl").open(encoding="utf-8") as stream:
            events = [json.loads(line) for line in stream if line.strip()]
        with (DATA_DIR / "worked_expected.json").open(encoding="utf-8") as stream:
            expected = json.load(stream)
        for event in events:
            result = self.book.process_event(event)

        final = expected["market_sell_result"]
        self.check_submission(
            result, events[-1], final["status"], final["fills"],
            final["unfilled_qty_units"],
        )
        self.check_book(
            bids=[row for row in expected["remaining_orders"] if row["side"] == "BUY"],
            asks=[row for row in expected["remaining_orders"] if row["side"] == "SELL"],
        )
        # Independent arithmetic anchors the supplied reference fixture.
        assert result["fills"] == [
            expected_fill("b1", "s1", 6_000_000, BTC_UNITS),
            expected_fill("b2", "s1", 6_000_000, BTC_UNITS),
            expected_fill("b3", "s1", 5_990_000, 3 * BTC_UNITS),
            expected_fill("b4", "s1", 5_970_000, BTC_UNITS),
        ]
        proceeds = sum(
            fill["price_ticks"] * fill["qty_units"] for fill in result["fills"]
        )
        assert proceeds == 3_594_000_000_000_000  # $359,400.
        assert proceeds == expected["gross_proceeds_tick_units"]

    def test_invariants_after_every_event_in_small_generated_streams(self):
        from generate_orders import SCENARIOS, events

        for scenario in SCENARIOS:
            for seed in (42, 43, 44):
                with self.subTest(scenario=scenario, seed=seed):
                    self.book = self.book_type()
                    for event in events(scenario, count=40, seed=seed, levels=5):
                        with self.subTest(seq=event["seq"]):
                            before = deepcopy(self.book.inspect_book())
                            result = self.book.process_event(event)
                            after = self.book.inspect_book()
                            self.check_event_conservation(event, result, before, after)
                            self.check_book_invariants(after, event["seq"])

    def test_explicit_baseline_and_revised_selection(self):
        from order_book import (
            BaselineOrderBook, ComparedOrderBook, RevisedOrderBook,
            create_order_book,
        )

        baseline = create_order_book("baseline")
        revised = create_order_book("revised")
        assert type(baseline) is BaselineOrderBook
        assert type(revised) is RevisedOrderBook
        assert type(baseline) is not type(revised)
        for book in (baseline, revised):
            for name in ("process_event", "inspect_book", "AddLimitOrder",
                         "FillMarketSell", "CancelOrder"):
                assert callable(getattr(book, name, None))

        compared = create_order_book("compare")
        assert isinstance(compared, ComparedOrderBook)
        assert type(compared.baseline) is BaselineOrderBook
        assert type(compared.revised) is RevisedOrderBook
        assert compared.baseline is not compared.revised
        with self.assertRaises(ValueError):
            create_order_book("unknown")
        with self.assertRaises(ValueError):
            ComparedOrderBook(baseline, baseline)

    def test_compare_mode_checks_results_and_book_after_every_event(self):
        from order_book import ComparedOrderBook

        baseline, revised = _RecordingBook(), _RecordingBook()
        book = ComparedOrderBook(baseline, revised)
        events = [
            market_sell_event(seq, f"sell{seq}", BTC_UNITS)
            for seq in (1, 2, 3)
        ]
        original = deepcopy(events)
        for count, event in enumerate(events, start=1):
            result = book.process_event(event)
            assert result["event_id"] == event["event_id"]
            assert baseline.snapshot_count == count
            assert revised.snapshot_count == count
        assert baseline.events == original
        assert revised.events == original
        assert events == original

    def test_compare_mode_detects_transient_result_mismatch(self):
        from order_book import ComparedOrderBook

        baseline = _RecordingBook()
        revised = _RecordingBook(result_mismatch_at=2)
        book = ComparedOrderBook(baseline, revised)
        book.process_event(market_sell_event(1, "sell1", BTC_UNITS))
        with self.assertRaisesRegex(AssertionError, "event2.*result mismatch"):
            book.process_event(market_sell_event(2, "sell2", BTC_UNITS))
        assert len(baseline.events) == len(revised.events) == 2
        assert baseline.snapshot_count == revised.snapshot_count == 2

    def test_compare_mode_detects_transient_book_mismatch(self):
        from order_book import ComparedOrderBook

        baseline = _RecordingBook()
        revised = _RecordingBook(book_mismatch_at=2)
        book = ComparedOrderBook(baseline, revised)
        book.process_event(market_sell_event(1, "sell1", BTC_UNITS))
        with self.assertRaisesRegex(AssertionError, "event2.*book state mismatch"):
            book.process_event(market_sell_event(2, "sell2", BTC_UNITS))
        assert len(baseline.events) == len(revised.events) == 2
        assert baseline.snapshot_count == revised.snapshot_count == 2

    def test_compare_mode_detects_numeric_type_mismatch(self):
        from order_book import ComparedOrderBook

        book = ComparedOrderBook(
            _RecordingBook(), _RecordingBook(float_quantity_at=1)
        )
        with self.assertRaisesRegex(AssertionError, "result mismatch"):
            book.process_event(market_sell_event(1, "sell1", BTC_UNITS))

    def test_compare_mode_allows_different_rejection_explanations(self):
        from order_book import ComparedOrderBook

        class RejectingBook(_RecordingBook):
            def __init__(self, reason):
                super().__init__()
                self.reason = reason

            def process_event(self, event):
                super().process_event(event)
                return {
                    "event_id": event["event_id"],
                    "status": "rejected",
                    "reason": self.reason,
                }

        baseline = RejectingBook("Baseline validation rejected the quantity.")
        revised = RejectingBook("Revised validation: quantity must be positive.")
        book = ComparedOrderBook(baseline, revised)
        result = book.process_event(market_sell_event(1, "bad", 0))
        assert result["status"] == "rejected"
        assert baseline.snapshot_count == revised.snapshot_count == 1

    def test_external_dispatcher_replays_jsonl_file(self):
        self.check_external_replay(compressed=False)

    def test_external_dispatcher_replays_jsonl_gz_file(self):
        self.check_external_replay(compressed=True)

    def check_external_replay(self, compressed):
        from dispatcher import replay_file

        events = [
            limit_event(1, "A", "BUY", 10_000, 2 * BTC_UNITS),
            market_sell_event(2, "sell1", BTC_UNITS),
            cancel_event(3, "A"),
        ]
        event_ids = ["source-limit-A", "source-market-sell", "source-cancel-A"]
        for event, event_id in zip(events, event_ids):
            event["event_id"] = event_id
        content = "".join(json.dumps(event) + "\n" for event in events)

        with TemporaryDirectory() as directory:
            suffix = ".jsonl.gz" if compressed else ".jsonl"
            source = Path(directory) / ("orders with spaces" + suffix)
            if compressed:
                with gzip.open(source, "wt", encoding="utf-8") as stream:
                    stream.write(content)
                results = replay_file(source, self.book)
            else:
                source.write_text(content, encoding="utf-8")
                results = replay_file(str(source), self.book)

        assert len(results) == 3
        assert [result["event_id"] for result in results] == event_ids
        self.check_submission(
            results[0], events[0], "resting", [], 2 * BTC_UNITS,
        )
        self.check_submission(
            results[1], events[1], "filled",
            [expected_fill("A", "sell1", 10_000, BTC_UNITS)], 0,
        )
        self.check_cancel(results[2], events[2], "cancelled", BTC_UNITS)
        self.check_book()

    def check_event_conservation(self, event, result, before, after):
        """Account for every maker change, residual and cancellation."""
        prior_orders = before["bids"] + before["asks"]
        expected_after = {
            order["order_id"]: deepcopy(order) for order in prior_orders
        }

        if event["type"] == "CANCEL":
            removed = expected_after.pop(event["target_order_id"], None)
            quantity = 0 if removed is None else removed["qty_units"]
            status = "not_found" if removed is None else "cancelled"
            self.check_cancel(result, event, status, quantity)
        else:
            fills = result["fills"]
            remaining = event["qty_units"]
            incoming_side = (
                "SELL" if event["type"] == "MARKET_SELL" else event["side"]
            )
            # Every fill must debit a real opposite-side maker at its own price.
            for fill in fills:
                assert fill["taker_id"] == event["order_id"]
                maker = expected_after[fill["maker_id"]]
                assert maker["side"] != incoming_side
                assert type(fill["price_ticks"]) is int
                assert fill["price_ticks"] == maker["price_ticks"]
                assert type(fill["qty_units"]) is int
                assert 0 < fill["qty_units"] <= min(remaining, maker["qty_units"])
                if event["type"] == "LIMIT":
                    if incoming_side == "BUY":
                        assert fill["price_ticks"] <= event["price_ticks"]
                    else:
                        assert fill["price_ticks"] >= event["price_ticks"]
                maker["qty_units"] -= fill["qty_units"]
                remaining -= fill["qty_units"]
                if maker["qty_units"] == 0:
                    del expected_after[fill["maker_id"]]

            assert type(result["unfilled_qty_units"]) is int
            assert result["unfilled_qty_units"] == remaining
            if event["type"] == "LIMIT":
                status = "filled" if remaining == 0 else "resting"
                if remaining:
                    expected_after[event["order_id"]] = resting_order(
                        event["order_id"], event["side"], event["price_ticks"],
                        remaining, event["seq"],
                    )
            else:
                status = "filled" if remaining == 0 else (
                    "partial" if fills else "unfilled"
                )
                # An unfilled market residual is never added to expected_after.
            self.check_submission(result, event, status, fills, remaining)

        actual_orders = after["bids"] + after["asks"]
        actual_after = {order["order_id"]: order for order in actual_orders}
        assert len(actual_after) == len(actual_orders)
        assert actual_after == expected_after

    def check_book_invariants(self, snapshot, last_seq):
        bids, asks = snapshot["bids"], snapshot["asks"]
        assert bids == sorted(
            bids, key=lambda order: (-order["price_ticks"], order["arrival_seq"])
        )
        assert asks == sorted(
            asks, key=lambda order: (order["price_ticks"], order["arrival_seq"])
        )
        if bids and asks:
            assert bids[0]["price_ticks"] < asks[0]["price_ticks"]
        for side_name, side in (("bids", "BUY"), ("asks", "SELL")):
            for order in snapshot[side_name]:
                assert order["side"] == side
                assert type(order["price_ticks"]) is int and order["price_ticks"] > 0
                assert type(order["qty_units"]) is int and order["qty_units"] > 0
                assert type(order["arrival_seq"]) is int
                assert 0 < order["arrival_seq"] <= last_seq


# These are the exact category selectors used by --category.
CATEGORIES = {
    "market-sells": TestMarketSells,
    "price-time": TestPriceTimePriority,
    "limit-orders": TestLimitOrders,
    "cancellations": TestCancellations,
    "validation": TestValidation,
    "integration": TestIntegration,
}


def main(argv=None):
    from order_book import IMPLEMENTATIONS

    parser = argparse.ArgumentParser(description="Run order book tests by category.")
    parser.add_argument(
        "--category", choices=["all", *CATEGORIES], default="all",
        help="Run one category, or all categories (default: all).",
    )
    parser.add_argument(
        "--implementation", type=str.lower, choices=IMPLEMENTATIONS,
        default="compare",
        help="Select Baseline, Revised or compare both after each event (default).",
    )
    args = parser.parse_args(argv)
    classes = (
        CATEGORIES.values() if args.category == "all"
        else [CATEGORIES[args.category]]
    )
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for test_class in classes:
        test_class.implementation = args.implementation
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
