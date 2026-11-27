"""Measurement definitions checked against independently calculated small cases."""
import unittest
from benchmark import Observer, fixed_bids, median_summaries, percentile


class TestMeasurement(unittest.TestCase):
    def test_nearest_rank_percentiles(self):
        self.assertEqual(percentile([4,1,3,2], .5), 2)
        self.assertEqual(percentile(list(range(1,101)), .95), 95)
        self.assertEqual(percentile(list(range(1,101)), .99), 99)
        self.assertIsNone(percentile([], .5))

    def test_warmup_and_stopped_samples_do_not_enter_medians(self):
        rows = [dict(version="A",scenario="x",seed=42,event_count=1000,phase="replay",
                     repeat=i,status="ok",elapsed_seconds=t)
                for i,t in enumerate([999,1,2,3,4,5])]
        rows.append(dict(rows[-1],repeat=6,status="stopped",elapsed_seconds=100))
        result = median_summaries(rows)[0]
        self.assertEqual(result["repeats"], 5)
        self.assertEqual(result["elapsed_seconds"], 3)
        self.assertAlmostEqual(result["throughput_events_per_second"], 1000/3)

    def test_fresh_fixed_bid_input_determinism(self):
        rows = fixed_bids(30,4,42)
        self.assertEqual(rows, fixed_bids(30,4,42))
        self.assertTrue(all(r["side"]=="BUY" for r in rows))
        self.assertEqual(len({r["price_ticks"] for r in rows}),4)
        rows[0]["qty_units"] = 0
        self.assertGreater(fixed_bids(30,4,42)[0]["qty_units"],0)

    def test_observer_partial_fill_then_cancel(self):
        observer=Observer()
        observer.update(dict(type="LIMIT",order_id="b",side="BUY",price_ticks=100,qty_units=10),
                        dict(status="resting",fills=[],unfilled_qty_units=10))
        observer.update(dict(type="MARKET_SELL",order_id="s",qty_units=3),dict(
            status="filled",unfilled_qty_units=0,fills=[dict(maker_id="b",price_ticks=100,qty_units=3)]))
        observer.update(dict(type="CANCEL",target_order_id="b"),
                        dict(status="cancelled",cancelled_qty_units=7))
        self.assertEqual(observer.summary(),dict(active_order_peak=1,price_level_peak=1,
            active_orders_final=0,occupied_prices_final=0,fill_count=1,discarded_market_qty=0))
