"""The fast accept test must never accept an event the reference validate() rejects."""
import itertools
import random

from lob.common import is_valid_fast, validate

GOOD = {
    "LIMIT": {"seq": 5, "event_id": "e", "type": "LIMIT", "order_id": "o", "side": "BUY",
              "price_ticks": 10, "qty_units": 3},
    "MARKET_SELL": {"seq": 5, "event_id": "e", "type": "MARKET_SELL", "order_id": "o",
                    "qty_units": 3},
    "CANCEL": {"seq": 5, "event_id": "e", "type": "CANCEL", "target_order_id": "t"},
}
BAD_VALUES = [None, True, False, 0, -1, 1, 5, 6, 2**70, 1.0, 6.0, "", "x", "BUY", "SELL",
              "buy", "LIMIT", [], {}, (1,), b"o"]


class StrSub(str):
    pass


class LiveSet:
    """Container view of a liveness function (fuzz ids: "o", "x", "t" ...)."""

    def __init__(self, live):
        self.live = live

    def __contains__(self, order_id):
        return self.live(order_id)


def check(event, live):
    """`live` is a function id -> bool for validate(); the fast test gets the same ids as a set."""
    ref = validate(event, 4, live) is None
    fast = is_valid_fast(event, 4, LiveSet(live))
    assert not (fast and not ref), f"fast accepted, reference rejected: {event!r}"
    return ref, fast


def test_good_events_are_accepted_by_both():
    for ev in GOOD.values():
        assert check(ev, lambda _: False) == (True, True)


def test_every_single_field_corruption():
    for ev in GOOD.values():
        for key, bad in itertools.product(list(ev), BAD_VALUES + [StrSub("LIMIT"), StrSub("o")]):
            check({**ev, key: bad}, lambda _: False)
        for key in ev:                       # missing field
            check({k: v for k, v in ev.items() if k != key}, lambda _: False)
        check({**ev, "_parse_error": 1}, lambda _: False)
        check({**ev, "extra": 1}, lambda _: False)


def test_live_ids_and_non_dicts():
    for ev in (GOOD["LIMIT"], GOOD["MARKET_SELL"]):
        assert check(ev, lambda oid: True) == (False, False)
    for bad in (None, 1, "x", [], [GOOD["LIMIT"]], StrSub("x")):
        check(bad, lambda _: False)


def test_random_pairs_of_corruptions():
    rng = random.Random(1)
    for _ in range(20000):
        ev = dict(rng.choice(list(GOOD.values())))
        for _ in range(rng.randint(1, 3)):
            key = rng.choice(list(ev) + ["seq", "side", "type"])
            if rng.random() < 0.2:
                ev.pop(key, None)
            else:
                ev[key] = rng.choice(BAD_VALUES)
        check(ev, lambda oid: oid == "x")
