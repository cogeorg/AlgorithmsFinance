"""Shared public replay kernel used by timing, instrumentation and pipeline tests."""
from copy import deepcopy
from lob import METHODS
from lob.book_a import OrderBookA
from lob.book_b import OperationCounters

VERSIONS = ("A", "B1", "B2", "B3", "B3r", "B3r_fast")


class BaselineCounters(OperationCounters):
    __slots__ = ("best_order_scans", "orders_scanned", "id_scan_records", "cancel_scan_records")

    def __init__(self):
        for name in OperationCounters.__slots__ + self.__slots__:
            setattr(self, name, 0)

    def as_dict(self):
        return {name: getattr(self, name) for name in OperationCounters.__slots__ + self.__slots__}


class CountingA(OrderBookA):
    """Diagnostic adapter; all mutation/matching results delegate to unchanged A.

    Scan counters describe the original A work. Extra observer scans (id/cancel
    location and occupied-price peaks) are diagnostic overhead, never timed.
    """
    def __init__(self):
        super().__init__()
        self.counters = BaselineCounters()
        self._matching = False

    def _best_index(self, orders, side):
        if self._matching:
            self.counters.best_order_scans += 1
            self.counters.orders_scanned += len(orders)
        return super()._best_index(orders, side)

    def _match(self, event, side, limit):
        self._matching = True
        try:
            return super()._match(event, side, limit)
        finally:
            self._matching = False

    def _scan_length(self, target):
        visited = 0
        for orders in (self.bids, self.asks):
            for order in orders:
                visited += 1
                if order["order_id"] == target:
                    return visited
        return visited

    def _is_live(self, order_id):
        self.counters.id_scan_records += self._scan_length(order_id)
        return super()._is_live(order_id)

    def _cancel(self, event):
        self.counters.cancel_scan_records += self._scan_length(event["target_order_id"])
        return super()._cancel(event)

    def process(self, event):
        before = self.counters.as_dict()
        result = super().process(event)
        if result["status"] == "rejected":
            for name, value in before.items():
                setattr(self.counters, name, value)
            return result
        c = self.counters
        c.accepted_events += 1
        field = {"LIMIT": "limit_events", "MARKET_SELL": "market_sell_events", "CANCEL": "cancel_events"}[event["type"]]
        setattr(c, field, getattr(c, field) + 1)
        c.fills += len(result.get("fills", ()))
        c.makers_touched += len(result.get("fills", ()))
        c.unfilled_qty_units += result.get("unfilled_qty_units", 0)
        c.active_order_peak = max(c.active_order_peak, len(self.bids) + len(self.asks))
        c.price_level_peak = max(c.price_level_peak, len({(r["side"], r["price_ticks"])
                                                       for orders in (self.bids, self.asks) for r in orders}))
        return result


def make_book(version, counted=False):
    if counted and version == "A":
        return CountingA()
    cls = METHODS[("lob", version)]
    return cls(count_operations=True) if counted else cls()


def replay(book, events):
    last = None
    for event in events:
        last = book.process(event)
    return last


def sale_event(events, percent):
    qty = sum(e["qty_units"] for e in events)
    return {"seq": events[-1]["seq"] + 1, "event_id": "liquidation-sale",
            "type": "MARKET_SELL", "order_id": "liquidation-sale",
            "qty_units": max(1, (qty * percent + 99) // 100)}


def prepare_book(case, events, version, counted=False):
    book = make_book(version, counted)
    replay(book, construction_events(case, events))
    return book


def construction_events(case, events):
    if case["part"] == "liquidation":
        return events
    return events[:case.get("prefill_events", 0)]


def workload_events(case, events):
    if case["part"] == "liquidation":
        return [sale_event(events, case["percent"])]
    return events[case["prefill_events"]:] if "prefill_events" in case else events


def live_stats(book):
    if hasattr(book, "orders"):
        levels = len(book.bids.levels) + len(book.asks.levels)
        heaps = sum(len(side.heap) for side in (book.bids, book.asks) if hasattr(side, "heap"))
        return len(book.orders), levels, heaps, max(0, heaps - levels) if heaps else 0
    return len(book.bids) + len(book.asks), -1, 0, 0


def check_case(case, events, version, counted=False):
    """Bounded prefix+tail sample; compare every result/book before measurement."""
    if "prefill_events" in case:
        def bounded(rows):
            return rows if len(rows) <= 64 else rows[:32]+rows[-32:]
        sample = bounded(construction_events(case, events)) + bounded(workload_events(case, events))
        a, b = make_book("A"), make_book(version, counted)
        for event in sample:
            ra, rb = replay(a, [deepcopy(event)]), replay(b, [deepcopy(event)])
            assert ra == rb, (version, case["id"], event, ra, rb)
            assert a.snapshot() == b.snapshot(), (version, case["id"], event)
        return len(sample)
    sample = events if len(events) <= 128 else events[:64] + events[-64:]
    a = prepare_book(case, sample, "A")
    b = prepare_book(case, sample, version, counted)
    for event in workload_events(case, sample):
        ra, rb = replay(a, [deepcopy(event)]), replay(b, [deepcopy(event)])
        assert ra == rb, (version, case["id"], event, ra, rb)
        assert a.snapshot() == b.snapshot(), (version, case["id"], event)
    return len(sample)
