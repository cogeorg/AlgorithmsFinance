"""Planted bugs for the fuzzer power check (own/attack).
The first five are verbatim copies of the mutants in campaign.py (which cannot be imported:
it runs its campaign at import time). The last two were added 2026-11-23 for the final
Version B, targeting what a lazy-heap / deque design gets wrong most easily."""
from oracle import Oracle


class Lifo(Oracle):
    def snapshot(self):
        k = lambda o: (o["price_ticks"], -o["arrival_seq"])  # noqa: E731
        return (sorted((o for o in self.live if o["side"] == "BUY"), key=lambda o: (-o["price_ticks"], -o["arrival_seq"]))
                + sorted((o for o in self.live if o["side"] == "SELL"), key=k))


class SeqOnReject(Oracle):
    def call(self, m, e):
        r = super().call(m, e)
        if r["status"] == "rejected" and isinstance(e, dict) and type(e.get("seq")) is int and e["seq"] > self.last_seq:
            self.last_seq = e["seq"]
        return r


class RestMarket(Oracle):
    def _submit(self, e):
        return super()._submit(e if e["type"] == "LIMIT" else {**e, "type": "LIMIT", "side": "SELL", "price_ticks": 1})


class StrictCross(Oracle):
    def _submit(self, e):
        if e["type"] == "LIMIT":
            p = e["price_ticks"] + (-1 if e["side"] == "BUY" else 1)
            r = super()._submit({**e, "price_ticks": p})
            for o in self.live:
                if o["order_id"] == e["order_id"]:
                    o["price_ticks"] = e["price_ticks"]
            return r
        return super()._submit(e)


class OneEntryCancelZero(Oracle):
    def _cancel(self, e):
        r = super()._cancel(e)
        if r["status"] == "cancelled" and len(self.live) > 40:
            r["cancelled_qty_units"] += 1
        return r


class StaleTouchAfterCancel(Oracle):
    """Lazy-index bug: after a cancel empties the best bid level, best_bid() keeps
    reporting the old price until the next submit (stale heap key not skipped)."""
    stale = None

    def _cancel(self, e):
        before = Oracle.best_bid(self)
        r = super()._cancel(e)
        if before is not None and Oracle.best_bid(self) != before:
            self.stale = before
        return r

    def _submit(self, e):
        self.stale = None
        return super()._submit(e)

    def best_bid(self):
        return self.stale if self.stale is not None else Oracle.best_bid(self)


class RequeuePartialMaker(Oracle):
    """Deque bug: a partially filled maker is popped and appended at the back of its
    level (loses time priority); arrival_seq in the snapshot stays unchanged."""
    def _submit(self, e):
        before = {o["order_id"]: o["qty_units"] for o in self.live}
        r = super()._submit(e)
        for o in self.live:
            if o["order_id"] in before and o["qty_units"] < before[o["order_id"]]:
                o["_prio"] = e["seq"]
        return r

    def snapshot(self):
        key = lambda o: o.get("_prio", o["arrival_seq"])  # noqa: E731
        bids = sorted((o for o in self.live if o["side"] == "BUY"), key=lambda o: (-o["price_ticks"], key(o)))
        asks = sorted((o for o in self.live if o["side"] == "SELL"), key=lambda o: (o["price_ticks"], key(o)))
        return [{k: v for k, v in o.items() if k != "_prio"} for o in bids + asks]


MUTANTS = [Lifo, SeqOnReject, RestMarket, StrictCross, OneEntryCancelZero,
           StaleTouchAfterCancel, RequeuePartialMaker]
