"""Stateful differential test with Hypothesis: Version A vs Version B after EVERY event.

Random sequences of limits, market sells, cancels (incl. unknown and repeated targets),
id reuse and invalid events go to both versions. After every event it asserts:
  * identical results (incl. ordered fills) and identical canonical books (A == B);
  * contract.assert_book on both books (invariants I1-I4, best bid/ask);
  * contract.step_check on A (price-time priority, maker price, conservation C1-C6),
    so a fault shared by both versions is still caught.
Hypothesis shrinks a failure to a minimal event sequence.

A and B share lob/validation.py, so A == B cannot catch a validation bug: the invalid-
event rules below assert the expected outcome ("rejected", book unchanged) directly,
and each validation rule also has its own contract check and direct test.
Narrow prices (95-105) and small quantities (1-5) make crossings, long queues, partial
fills and exhausted levels common.
"""
from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

import contract
from lob import METHODS

A_CLS = METHODS[("lob", "A")]
B_VARIANTS = [(key, impl) for key, impl in sorted(METHODS.items()) if key[1] != "A"]


def live_ids(book) -> list[str]:
    """Order ids currently resting in `book` (from the public snapshot)."""
    return [r["order_id"] for r in book.snapshot()]


PRICES = st.integers(min_value=95, max_value=105)
QTY = st.integers(min_value=1, max_value=5)
REUSE_POOL = st.sampled_from(["r1", "r2", "r3"])     # small pool: live duplicates and reuse are common


class DifferentialMachine(RuleBasedStateMachine):
    B_CLS = METHODS[("lob", "B1")]

    def __init__(self):
        super().__init__()
        self.a, self.b = A_CLS(), self.B_CLS()
        self.seq = 0
        self.ids: list[str] = []

    def _send(self, event: dict) -> dict:
        before = self.a.snapshot()
        ra, rb = self.a.process(dict(event)), self.b.process(dict(event))
        assert ra == rb, f"results differ for {event}:\nA={ra}\nB={rb}"
        sa, sb = contract.assert_book(self.a), contract.assert_book(self.b)
        assert sa == sb, f"books differ after {event}:\nA={sa}\nB={sb}"
        contract.step_check(before, event, ra, sa)
        if ra.get("status") != "rejected":
            self.seq = event["seq"]
        return ra

    def _next(self) -> int:
        return self.seq + 1

    @rule(side=st.sampled_from(["BUY", "SELL"]), price=PRICES, qty=QTY)
    def limit(self, side, price, qty):
        s = self._next(); oid = f"o{s}"; self.ids.append(oid)
        self._send({"seq": s, "event_id": f"e{s}", "type": "LIMIT", "order_id": oid,
                    "side": side, "price_ticks": price, "qty_units": qty})

    @rule(oid=REUSE_POOL, side=st.sampled_from(["BUY", "SELL"]), price=PRICES, qty=QTY)
    def limit_from_reuse_pool(self, oid, side, price, qty):
        """Rejected as duplicate while the id is live, accepted as a new order otherwise."""
        s = self._next(); was_live = oid in live_ids(self.a); self.ids.append(oid)
        r = self._send({"seq": s, "event_id": f"e{s}", "type": "LIMIT", "order_id": oid,
                        "side": side, "price_ticks": price, "qty_units": qty})
        assert (r["status"] == "rejected") == was_live, f"live-duplicate rule broken for {oid}: {r}"

    @rule(qty=st.integers(min_value=1, max_value=20))
    def market_sell(self, qty):
        s = self._next()
        self._send({"seq": s, "event_id": f"e{s}", "type": "MARKET_SELL",
                    "order_id": f"m{s}", "qty_units": qty})

    @precondition(lambda self: self.ids)
    @rule(data=st.data())
    def cancel(self, data):
        s = self._next()
        target = data.draw(st.sampled_from(self.ids + ["unknown"]))
        self._send({"seq": s, "event_id": f"e{s}", "type": "CANCEL", "target_order_id": target})

    @precondition(lambda self: self.ids)
    @rule(data=st.data())
    def cancel_twice(self, data):
        """Second cancel of the same target must be not_found (asserted directly, not only A == B)."""
        target = data.draw(st.sampled_from(self.ids))
        for k in range(2):
            s = self._next()
            r = self._send({"seq": s, "event_id": f"e{s}", "type": "CANCEL", "target_order_id": target})
            if k == 1:
                assert r.get("status") == "not_found", f"second cancel of {target} -> {r}"
                assert target not in live_ids(self.a), f"{target} still live after two cancels"

    # ---- invalid events: rejected by BOTH versions, book and last accepted seq unchanged
    def _reject(self, event: dict) -> None:
        r = self._send(event)
        assert r.get("status") == "rejected", f"not rejected: {event} -> {r}"

    @rule(field=st.sampled_from(["price_ticks", "qty_units"]),
          bad=st.sampled_from([0, -1, 1.5, 1.0, True, False, "7", None]))
    def invalid_number(self, field, bad):
        s = self._next()
        ev = {"seq": s, "event_id": f"bad{s}", "type": "LIMIT", "order_id": f"x{s}",
              "side": "BUY", "price_ticks": 100, "qty_units": 1}
        ev[field] = bad
        self._reject(ev)

    @rule(side=st.sampled_from(["buy", "HOLD", "", None]))
    def invalid_side(self, side):
        s = self._next()
        self._reject({"seq": s, "event_id": f"bad{s}", "type": "LIMIT", "order_id": f"x{s}",
                      "side": side, "price_ticks": 100, "qty_units": 1})

    @rule(kind=st.sampled_from(["MARKET_BUY", "limit", "", None]))
    def invalid_type(self, kind):
        s = self._next()
        self._reject({"seq": s, "event_id": f"bad{s}", "type": kind, "order_id": f"x{s}",
                      "side": "BUY", "price_ticks": 100, "qty_units": 1})

    @precondition(lambda self: self.seq > 0)
    @rule(back=st.integers(min_value=0, max_value=3))
    def non_increasing_seq(self, back):
        s = max(1, self.seq - back)          # equal to or smaller than the last accepted seq
        self._reject({"seq": s, "event_id": f"bad{s}-{back}", "type": "LIMIT", "order_id": f"y{s}-{back}",
                      "side": "SELL", "price_ticks": 100, "qty_units": 1})

    @rule(data=st.data())
    def duplicate_live_id(self, data):
        live = live_ids(self.a)
        assert sorted(live) == sorted(live_ids(self.b)), "live id sets differ between A and B"
        if not live:
            return                            # book is empty right now: no live id to duplicate
        s = self._next()
        kind = data.draw(st.sampled_from(["LIMIT", "MARKET_SELL"]))
        ev = {"seq": s, "event_id": f"dup{s}", "type": kind, "order_id": data.draw(st.sampled_from(live)),
              "qty_units": 1}
        if kind == "LIMIT":
            ev.update(side="BUY", price_ticks=100)
        self._reject(ev)

    @invariant()
    def books_valid(self):
        assert contract.assert_book(self.a) == contract.assert_book(self.b)


for _key, _impl in B_VARIANTS:
    _machine = type(f"DifferentialMachine_{_key[1]}", (DifferentialMachine,),
                    {"B_CLS": _impl, "__module__": __name__})
    _case = _machine.TestCase
    _case.settings = settings(max_examples=300, stateful_step_count=60, deadline=None)
    globals()[f"TestDifferential_{_key[1]}"] = _case
del _key, _impl, _machine, _case
