"""Shared validation, event dispatch, result formats and helpers for both versions.

Both versions inherit from OrderBookBase, so validation and result formatting are
identical; they differ only in how active orders are stored and searched.

Units (see ASSIGNMENT.md): price_ticks = integer cents per BTC, qty_units = integer
1e-8 BTC. All matching and conservation arithmetic uses Python integers.
"""
import gzip
import json

BUY = "BUY"
SELL = "SELL"


def _is_pos_int(x):
    # JSON true/false load as bool, and bool is a subclass of int: check the exact type.
    return type(x) is int and x > 0


def _is_id(x):
    return isinstance(x, str) and x != ""


class Order:
    """One active resting order. `seq` is its original arrival rank."""
    __slots__ = ("order_id", "side", "price", "qty", "seq")

    def __init__(self, order_id, side, price, qty, seq):
        self.order_id = order_id
        self.side = side
        self.price = price
        self.qty = qty
        self.seq = seq

    def as_dict(self):
        return {"order_id": self.order_id, "side": self.side, "price_ticks": self.price,
                "qty_units": self.qty, "arrival_seq": self.seq}


class OrderBookBase:
    """Public interface shared by Version A and Version B.

    process(event)        -> result dict; the event dispatcher (validates first)
    AddLimitOrder(event)  -> result dict for a LIMIT event
    FillMarketSell(event) -> result dict for a MARKET_SELL event
    CancelOrder(event)    -> result dict for a CANCEL event
    inspect_book()        -> active orders as dicts: bids (price desc, arrival asc),
                             then asks (price asc, arrival asc)
    storage_counts()      -> stored entries including any inactive ones (diagnostics)

    Events are dicts exactly as read from the JSON Lines files. Results:
      submission: {event_id, order_id, status, unfilled_qty_units, fills}
                  LIMIT status: filled | resting; MARKET_SELL: filled | partial | unfilled
      cancel:     {event_id, target_order_id, status, cancelled_qty_units}
                  status: cancelled | not_found
      rejected:   {event_id (None if unavailable), status: "rejected", reason}
    fills: [{maker_id, taker_id, price_ticks, qty_units}] in execution order; only the
    current event's fills are returned, no trade history is retained.
    """

    def __init__(self):
        self.last_seq = 0  # last *accepted* arrival rank

    # ---- engine-specific hooks (implemented by each version) ---------------------
    def _is_live(self, order_id):
        raise NotImplementedError

    def _limit(self, order_id, side, price, qty, seq):
        """Match, rest any residual; return (fills, unfilled_qty)."""
        raise NotImplementedError

    def _market_sell(self, order_id, qty):
        """Match against bids only; never rests; return (fills, unfilled_qty)."""
        raise NotImplementedError

    def _cancel(self, target_order_id):
        """Remove an active order; return its remaining qty, or None if not active."""
        raise NotImplementedError

    def inspect_book(self):
        raise NotImplementedError

    def storage_counts(self):
        raise NotImplementedError

    # ---- validation -----------------------------------------------------------------
    def validate(self, event):
        """Return None if the event is valid, otherwise a rejection reason. No mutation."""
        if not isinstance(event, dict):
            return "event is not a JSON object"
        seq = event.get("seq")
        if not _is_pos_int(seq):
            return "seq must be a positive integer"
        if seq <= self.last_seq:
            return f"nonincreasing seq: {seq} <= last accepted {self.last_seq}"
        if not _is_id(event.get("event_id")):
            return "missing or invalid event_id"
        kind = event.get("type")
        if kind == "LIMIT":
            if not _is_id(event.get("order_id")):
                return "missing or invalid order_id"
            if event.get("side") not in (BUY, SELL):
                return "side must be BUY or SELL"
            if not _is_pos_int(event.get("price_ticks")):
                return "price_ticks must be a positive integer"
            if not _is_pos_int(event.get("qty_units")):
                return "qty_units must be a positive integer"
            if self._is_live(event["order_id"]):
                return "duplicate live order_id"
            return None
        if kind == "MARKET_SELL":
            if not _is_id(event.get("order_id")):
                return "missing or invalid order_id"
            if not _is_pos_int(event.get("qty_units")):
                return "qty_units must be a positive integer"
            if self._is_live(event["order_id"]):
                return "duplicate live order_id"
            return None
        if kind == "CANCEL":
            if not _is_id(event.get("target_order_id")):
                return "missing or invalid target_order_id"
            return None
        return "unknown event type"

    # ---- dispatcher and typed entry points ------------------------------------------------
    def process(self, event):
        """Event dispatcher: validate, apply, advance last accepted seq, return result."""
        reason = self.validate(event)
        if reason is not None:
            return self._rejected(event, reason)
        kind = event["type"]
        if kind == "LIMIT":
            fills, unfilled = self._limit(event["order_id"], event["side"], event["price_ticks"],
                                          event["qty_units"], event["seq"])
            result = {"event_id": event["event_id"], "order_id": event["order_id"],
                      "status": "filled" if unfilled == 0 else "resting",
                      "unfilled_qty_units": unfilled, "fills": fills}
        elif kind == "MARKET_SELL":
            fills, unfilled = self._market_sell(event["order_id"], event["qty_units"])
            status = "filled" if unfilled == 0 else ("partial" if fills else "unfilled")
            result = {"event_id": event["event_id"], "order_id": event["order_id"],
                      "status": status, "unfilled_qty_units": unfilled, "fills": fills}
        else:
            cancelled = self._cancel(event["target_order_id"])
            result = {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                      "status": "not_found" if cancelled is None else "cancelled",
                      "cancelled_qty_units": 0 if cancelled is None else cancelled}
        self.last_seq = event["seq"]
        return result

    def AddLimitOrder(self, event):
        return self._typed(event, "LIMIT")

    def FillMarketSell(self, event):
        return self._typed(event, "MARKET_SELL")

    def CancelOrder(self, event):
        return self._typed(event, "CANCEL")

    def _typed(self, event, kind):
        if isinstance(event, dict) and event.get("type") != kind:
            return self._rejected(event, f"expected an event of type {kind}")
        return self.process(event)

    @staticmethod
    def _rejected(event, reason):
        event_id = event.get("event_id") if isinstance(event, dict) else None
        return {"event_id": event_id, "status": "rejected", "reason": reason}


# ---- helpers ---------------------------------------------------------------------------------
def gross_proceeds_tick_units(fills):
    """Sum of price_ticks * qty_units (exact integer). Divide by 1e10 for US dollars."""
    return sum(f["price_ticks"] * f["qty_units"] for f in fills)


def format_usd(tick_units):
    """Display only: integer tick-units -> dollars with two decimals (round half up)."""
    cents, rest = divmod(tick_units, 10**8)  # 1 cent = 1e8 tick-units (1e10 per dollar)
    if 2 * rest >= 10**8:
        cents += 1
    return f"{cents // 100}.{cents % 100:02d}"


def read_events(path):
    """Read a JSON Lines file (.jsonl or .jsonl.gz) into a list of event dicts."""
    path = str(path)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
