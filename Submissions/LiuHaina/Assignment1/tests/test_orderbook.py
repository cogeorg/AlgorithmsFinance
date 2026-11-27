"""Independent expected outcomes; quantities/prices below are integer units."""
import copy
import json
from pathlib import Path
import random
import unittest
from lob.version_a import OrderBook as VersionA
from lob.version_b import OrderBook as VersionB

DATA = Path(__file__).resolve().parents[1] / "data"


def limit(seq, oid, side="BUY", price=100, qty=5):
    return dict(seq=seq, event_id=f"e{seq}", type="LIMIT", order_id=oid,
                side=side, price_ticks=price, qty_units=qty)


def sell(seq, oid="t", qty=5):
    return dict(seq=seq, event_id=f"e{seq}", type="MARKET_SELL", order_id=oid, qty_units=qty)


def cancel(seq, oid):
    return dict(seq=seq, event_id=f"e{seq}", type="CANCEL", target_order_id=oid)


def order(oid, side="BUY", price=100, qty=5, seq=1):
    return dict(order_id=oid, side=side, price_ticks=price, qty_units=qty, arrival_seq=seq)


def fill(maker, taker="t", price=100, qty=5):
    return dict(maker_id=maker, taker_id=taker, price_ticks=price, qty_units=qty)


class Cases:
    def setUp(self):
        self.book = self.factory()

    def apply(self, event):
        before = copy.deepcopy(self.book.inspect_book())
        previous_seq = self.book.last_seq
        result = self.book.process_event(event)
        after = self.book.inspect_book()
        if result["status"] == "rejected":
            self.assertEqual(after, before)
            self.assertEqual(self.book.last_seq, previous_seq)
            self.assertTrue(result.get("reason"))
            self.assertEqual(result.get("event_id"), event.get("event_id"))
            return result
        self.assertEqual(self.book.last_seq, event["seq"])
        self.assertEqual(result["event_id"], event["event_id"])
        self.assertEqual(len(after), len({o["order_id"] for o in after}))
        self.assertTrue(all(o["qty_units"] > 0 for o in after))
        bids = [o for o in after if o["side"] == "BUY"]
        asks = [o for o in after if o["side"] == "SELL"]
        self.assertEqual(after, sorted(bids, key=lambda o: (-o["price_ticks"], o["arrival_seq"]))
                         + sorted(asks, key=lambda o: (o["price_ticks"], o["arrival_seq"])))
        if bids and asks:
            self.assertLess(bids[0]["price_ticks"], asks[0]["price_ticks"])
        old = {o["order_id"]: o for o in before}
        new = {o["order_id"]: o for o in after}
        if event["type"] == "CANCEL":
            target = event["target_order_id"]
            quantity = old.get(target, {}).get("qty_units", 0)
            self.assertEqual(result["target_order_id"], target)
            self.assertEqual(result["status"], "cancelled" if quantity else "not_found")
            self.assertEqual(result["cancelled_qty_units"], quantity)
            self.assertEqual(after, [o for o in before if o["order_id"] != target])
        else:
            fills = result["fills"]
            self.assertEqual(result["order_id"], event["order_id"])
            self.assertEqual(sum(f["qty_units"] for f in fills) + result["unfilled_qty_units"], event["qty_units"])
            executed = {}
            for f in fills:
                maker = old[f["maker_id"]]
                self.assertEqual(f["taker_id"], event["order_id"])
                self.assertEqual(f["price_ticks"], maker["price_ticks"])
                self.assertGreater(f["qty_units"], 0)
                self.assertNotEqual(maker["side"], event.get("side", "SELL"))
                executed[f["maker_id"]] = executed.get(f["maker_id"], 0) + f["qty_units"]
            for oid, record in old.items():
                remaining = record["qty_units"] - executed.get(oid, 0)
                self.assertEqual(new.get(oid, {}).get("qty_units", 0), remaining)
                if remaining:
                    self.assertEqual(new[oid], dict(record, qty_units=remaining))
            rests = event["type"] == "LIMIT" and result["unfilled_qty_units"] > 0
            self.assertEqual(set(new) - set(old), {event["order_id"]} if rests else set())
            if rests:
                self.assertEqual(new[event["order_id"]], order(event["order_id"], event["side"],
                    event["price_ticks"], result["unfilled_qty_units"], event["seq"]))
            status = ("resting" if rests else "filled") if event["type"] == "LIMIT" else (
                "filled" if result["unfilled_qty_units"] == 0 else "partial" if fills else "unfilled")
            self.assertEqual(result["status"], status)
        return result

    def check(self, event, status, residual, fills):
        result = self.apply(event)
        expected = dict(event_id=event["event_id"], order_id=event["order_id"], status=status,
                        unfilled_qty_units=residual, fills=fills)
        self.assertEqual({k: result[k] for k in expected}, expected)
        return result

    def test_empty_book(self):
        self.assertEqual(self.book.inspect_book(), [])
        self.check(sell(1, qty=3), "unfilled", 3, [])

    def test_one_order(self):
        self.check(limit(1, "b"), "resting", 5, [])
        self.assertEqual(self.book.inspect_book(), [order("b")])

    def test_smaller_equal_oversized_sale(self):
        for qty, status, residual, traded, remaining in [(2,"filled",0,2,3), (5,"filled",0,5,0), (8,"partial",3,5,0)]:
            with self.subTest(qty=qty):
                self.book = self.factory()
                self.apply(limit(1,"b"))
                self.check(sell(2,qty=qty),status,residual,[fill("b",qty=traded)])
                self.assertEqual(self.book.inspect_book(), [order("b",qty=remaining)] if remaining else [])

    def test_fifo_not_identifier(self):
        self.apply(limit(1,"z",qty=2))
        self.apply(limit(2,"a",qty=3))
        self.check(sell(3,qty=4),"filled",0,[fill("z",qty=2),fill("a",qty=2)])
        self.assertEqual(self.book.inspect_book(),[order("a",qty=1,seq=2)])

    def test_multiple_prices_best_bid_first(self):
        self.apply(limit(1,"low",price=90,qty=4))
        self.apply(limit(2,"high",price=110,qty=2))
        self.check(sell(3,qty=3),"filled",0,[fill("high",price=110,qty=2),fill("low",price=90,qty=1)])

    def test_partial_fill_keeps_priority(self):
        self.apply(limit(1,"first"))
        self.apply(limit(2,"second"))
        self.apply(sell(3,"t1",2))
        self.check(sell(4,"t2",4),"filled",0,[fill("first","t2",qty=3),fill("second","t2",qty=1)])
        self.assertEqual(self.book.inspect_book(),[order("second",qty=4,seq=2)])

    def test_cancel_active_repeated_unknown(self):
        self.apply(limit(1,"b"))
        self.apply(cancel(2,"b"))
        self.apply(cancel(3,"b"))
        self.apply(cancel(4,"missing"))
        self.assertEqual(self.book.inspect_book(),[])

    def test_cancel_partially_filled(self):
        self.apply(limit(1,"b"))
        self.apply(sell(2,qty=2))
        self.assertEqual(self.apply(cancel(3,"b"))["cancelled_qty_units"],3)

    def test_cancel_fully_filled(self):
        self.apply(limit(1,"b"))
        self.apply(sell(2))
        self.assertEqual(self.apply(cancel(3,"b"))["status"],"not_found")

    def test_crossing_buy_best_ask_resting_price(self):
        self.apply(limit(1,"expensive","SELL",110,4))
        self.apply(limit(2,"cheap","SELL",105,2))
        self.check(limit(3,"buyer","BUY",110,3),"filled",0,
                   [fill("cheap","buyer",105,2),fill("expensive","buyer",110,1)])
        self.assertEqual(self.book.inspect_book(),[order("expensive","SELL",110,3,1)])

    def test_crossing_sell_residual(self):
        self.apply(limit(1,"b",qty=2))
        self.check(limit(2,"s","SELL",95,5),"resting",3,[fill("b","s",100,2)])
        self.assertEqual(self.book.inspect_book(),[order("s","SELL",95,3,2)])

    def test_crossing_sell_fully_filled(self):
        self.apply(limit(1,"b",price=110,qty=5))
        self.check(limit(2,"s","SELL",100,2),"filled",0,[fill("b","s",110,2)])

    def test_buy_limit_stops_residual_fifo(self):
        self.apply(limit(1,"existing",qty=2))
        self.apply(limit(2,"expensive","SELL",105,3))
        self.check(limit(3,"new",qty=4),"resting",4,[])
        self.check(sell(4,qty=3),"filled",0,[fill("existing",qty=2),fill("new",qty=1)])
        self.assertEqual(self.book.inspect_book(),[order("new",qty=3,seq=3),order("expensive","SELL",105,3,2)])

    def test_buy_crosses_then_rests_at_own_price(self):
        self.apply(limit(1,"ask","SELL",95,2))
        self.check(limit(2,"buy","BUY",100,5),"resting",3,[fill("ask","buy",95,2)])
        self.assertEqual(self.book.inspect_book(),[order("buy","BUY",100,3,2)])

    def test_sell_limit_stops(self):
        self.apply(limit(1,"bid",price=90))
        self.check(limit(2,"ask","SELL",95,2),"resting",2,[])

    def test_same_price_asks_fifo(self):
        self.apply(limit(1,"z","SELL",100,2))
        self.apply(limit(2,"a","SELL",100,2))
        self.check(limit(3,"buyer","BUY",100,3),"filled",0,[fill("z","buyer",100,2),fill("a","buyer",100,1)])

    def test_invalid_inputs_leave_state_and_sequence(self):
        cases = []
        for field in ("price_ticks","qty_units"):
            for value in (0,-1,1.5,"5",None,True):
                e = limit(2,"bad")
                e[field] = value
                cases.append(e)
        cases += [sell(2,"bad",v) for v in (0,-1,1.5,"5",None,True)]
        cases += [limit(2,"bad",s) for s in ("HOLD","buy","")]
        cases += [dict(seq=2,event_id="bad",type="UNKNOWN")]
        for e in cases:
            with self.subTest(event=e):
                self.book = self.factory()
                self.apply(limit(1,"b"))
                self.assertEqual(self.apply(e)["status"],"rejected")
                self.apply(cancel(2,"b"))

    def test_duplicate_live_id_rejected_before_matching(self):
        self.apply(limit(1,"b"))
        self.assertEqual(self.apply(limit(2,"b","SELL",100,2))["status"],"rejected")
        self.assertEqual(self.apply(sell(2,"b",2))["status"],"rejected")
        self.apply(cancel(2,"b"))

    def test_nonincreasing_sequence(self):
        self.apply(limit(3,"b"))
        for seq in (3,2,0):
            self.assertEqual(self.apply(cancel(seq,"b"))["status"],"rejected")
        self.apply(cancel(4,"b"))

    def test_long_queue_cancel_middle(self):
        for i in range(200):
            self.apply(limit(i+1,f"q{200-i}",qty=1))
        self.apply(cancel(201,"q100"))
        expected = [fill(f"q{200-i}",qty=1) for i in range(200) if i != 100]
        self.check(sell(202,qty=250),"partial",51,expected)
        self.assertEqual(self.book.inspect_book(),[])

    def test_generated_fifo_independent_prefix_expectation(self):
        rng = random.Random(42)
        quantities = [rng.randint(1,9) for _ in range(25)]
        for i,q in enumerate(quantities,1):
            self.apply(limit(i,f"g{i}",qty=q))
        expected = [fill(f"g{i}",qty=q) for i,q in enumerate(quantities[:12],1)] + [fill("g13",qty=1)]
        self.check(sell(26,qty=sum(quantities[:12])+1),"filled",0,expected)

    def test_public_methods(self):
        self.book.AddLimitOrder(limit(1,"b"))
        r = self.book.FillMarketSell(sell(2,qty=2))
        self.assertEqual(r["fills"],[fill("b",qty=2)])
        r = self.book.CancelOrder(cancel(3,"b"))
        self.assertEqual((r["status"],r["cancelled_qty_units"]),("cancelled",3))

    def test_official_example_and_proceeds(self):
        expected = json.loads((DATA/"worked_expected.json").read_text())
        events = [json.loads(s) for s in (DATA/"worked_example.jsonl").read_text().splitlines()]
        for e in events:
            r = self.apply(e)
        self.assertEqual({k:r[k] for k in expected["market_sell_result"]},expected["market_sell_result"])
        self.assertEqual(self.book.inspect_book(),expected["remaining_orders"])
        gross = sum(f["price_ticks"]*f["qty_units"] for f in r["fills"])
        self.assertEqual(gross,3594000000000000)
        self.assertEqual(gross,expected["gross_proceeds_tick_units"])
        self.assertEqual(gross//10**10,359400)


class TestVersionA(Cases, unittest.TestCase):
    factory = VersionA


class TestVersionB(Cases, unittest.TestCase):
    factory = VersionB


class TestDifferential(unittest.TestCase):
    def test_compare_after_every_event(self):
        a,b = VersionA(),VersionB()
        events = [limit(1,"z",qty=3),limit(2,"a",qty=2),limit(3,"ask","SELL",105,4),
                  sell(4,"t1",4),cancel(5,"a"),cancel(6,"missing"),
                  limit(7,"cross","BUY",110,6),sell(8,"t2",5),
                  limit(9,"invalid",qty=0),limit(9,"valid",qty=1)]
        for e in events:
            self.assertEqual(a.process_event(copy.deepcopy(e)),b.process_event(copy.deepcopy(e)))
            self.assertEqual(a.inspect_book(),b.inspect_book())
            self.assertEqual(a.last_seq,b.last_seq)


if __name__ == "__main__":
    unittest.main()
