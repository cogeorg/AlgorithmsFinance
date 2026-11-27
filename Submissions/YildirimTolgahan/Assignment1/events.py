"""Shared event envelope for all versions: file reading, validation, sequencing, result shapes.

Storage and matching are NOT here. Each version (book_a.py, book_b1.py, book_b.py)
implements its own data organization and its own matching loop behind three hooks,
_add_limit, _market_sell and _cancel, and keeps self._live, a dictionary keyed by the
identifiers that are currently active (used here for the duplicate check).

Each operation first tests "is this an ordinary valid event?" in one expression, because
that is what almost every event is; everything else (invalid input, or a direct call
without an arrival rank) takes the path below it, which works out the reason in a fixed
order of precedence.

Units: price_ticks are integer cents per BTC; qty_units are integer 1e-8 BTC.
"""
import gzip
import json
from pathlib import Path

BUY, SELL = "BUY", "SELL"
TICK_UNITS_PER_USD = 10_000_000_000      # (cents per BTC) x (1e-8 BTC) per dollar
QTY_UNITS_PER_BTC = 100_000_000
NO_SEQ = object()                        # direct cancel/market calls may omit an arrival rank


# ------------------------------------------------------------------ input
def open_text(path):
    """Text stream for a plain or gzip file. utf-8-sig also accepts a leading byte-order mark."""
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig")
    return path.open(encoding="utf-8-sig")


def iter_events(path):
    """Yield one parsed JSON value per non-blank line (plain or gzip-compressed).

    A line that is not JSON at all cannot be given to the book as an event, so it
    stops the replay with its line number instead of being skipped silently.
    Valid JSON of the wrong shape is yielded and rejected by the book.
    """
    with open_text(path) as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except (ValueError, RecursionError) as error:    # JSONDecodeError is a ValueError; so is
                    reason = getattr(error, "msg", None) or str(error) or type(error).__name__   # "too many digits"
                    raise ValueError(f"{path}: line {number} is not valid JSON ({reason})") from None


def read_events(path):
    return list(iter_events(path))


def iter_chunks(path, size):
    """Yield lists of at most `size` parsed events, so large files need not be preloaded."""
    chunk = []
    for event in iter_events(path):
        chunk.append(event)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


# ----------------------------------------------------------------- output
def gross_value(fills):
    """Exact gross value of a fill list in tick-times-quantity units."""
    return sum(fill["price_ticks"] * fill["qty_units"] for fill in fills)


def format_usd(tick_units):
    """Dollars with two decimals; the only place where a value is rounded (display)."""
    # Integer arithmetic, so the result is exact for values of any size (no decimal context limit).
    per_cent = TICK_UNITS_PER_USD // 100
    cents, rest = divmod(abs(tick_units), per_cent)
    if 2 * rest > per_cent or (2 * rest == per_cent and cents % 2):
        cents += 1                                   # round half to even
    sign = "-" if tick_units < 0 and cents else ""
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def rejected(event_id, reason):
    return {"event_id": event_id if type(event_id) is str and event_id else None,
            "status": "rejected", "reason": reason}


# ------------------------------------------------------------ book envelope
class LimitOrderBook:
    """Sequential single-venue book: validates, sequences and reports; subclasses store and match.

    An event is either rejected (nothing changes, last_seq included) or accepted
    (last_seq advances, the subclass hook runs). Only the current event's fills
    are returned; no trade history is kept.
    """
    version = ""

    def __init__(self):
        self.last_seq = 0        # arrival rank of the last accepted event
        self._live = {}          # order_id -> the version's own record of that active order

    # -- dispatcher
    def ProcessEvent(self, event):
        if not isinstance(event, dict):
            return rejected(None, "event must be a JSON object")
        get = event.get
        event_id = get("event_id")
        if type(event_id) is not str or not event_id:
            return rejected(None, "event_id must be a non-empty string")
        kind = get("type")
        if kind == "LIMIT":
            return self.AddLimitOrder(get("order_id"), get("side"), get("price_ticks"),
                                      get("qty_units"), get("seq"), event_id)
        if kind == "MARKET_SELL":
            return self.FillMarketSell(get("order_id"), get("qty_units"), event_id, get("seq"))
        if kind == "CANCEL":
            return self.CancelOrder(get("target_order_id"), event_id, get("seq"))
        return rejected(event_id, "type must be LIMIT, MARKET_SELL or CANCEL")

    def _seq_error(self, seq):
        if type(seq) is not int:                 # bool, float, str and None are not arrival ranks
            return "seq must be an integer"
        if seq <= self.last_seq:
            return "seq must exceed the last accepted seq"
        return None

    # -- the three named operations
    def AddLimitOrder(self, order_id, side, price_ticks, qty_units, seq, event_id=None):
        """Match against the opposite side, then rest any residual at price_ticks with rank seq."""
        if (type(seq) is int and seq > self.last_seq and type(order_id) is str and order_id
                and type(side) is str and (side == BUY or side == SELL)
                and type(price_ticks) is int and price_ticks > 0
                and type(qty_units) is int and qty_units > 0 and order_id not in self._live):
            self.last_seq = seq
            fills = []
            unfilled = self._add_limit(order_id, side == BUY, price_ticks, qty_units, seq, fills)
            return {"event_id": event_id, "order_id": order_id, "status": "resting" if unfilled else "filled",
                    "unfilled_qty_units": unfilled, "fills": fills}
        reason = self._seq_error(seq)            # something is wrong: find the first reason
        if reason is None:
            if type(order_id) is not str or not order_id:
                reason = "order_id must be a non-empty string"
            elif type(side) is not str or (side != BUY and side != SELL):
                reason = "side must be BUY or SELL"
            elif type(price_ticks) is not int or price_ticks <= 0:
                reason = "price_ticks must be a positive integer"
            elif type(qty_units) is not int or qty_units <= 0:
                reason = "qty_units must be a positive integer"
            else:
                reason = "order_id is already active"
        return rejected(event_id, reason)

    def FillMarketSell(self, order_id, qty_units, event_id=None, seq=NO_SEQ):
        """Sell into the bids, best price first then arrival; the unfilled residual is discarded."""
        if (type(seq) is int and seq > self.last_seq and type(order_id) is str and order_id
                and type(qty_units) is int and qty_units > 0 and order_id not in self._live):
            self.last_seq = seq
            fills = []
            unfilled = self._market_sell(order_id, qty_units, fills)
            status = "filled" if not unfilled else ("partial" if fills else "unfilled")
            return {"event_id": event_id, "order_id": order_id, "status": status,
                    "unfilled_qty_units": unfilled, "fills": fills}
        reason = None if seq is NO_SEQ else self._seq_error(seq)     # direct call without seq, or invalid
        if reason is None:
            if type(order_id) is not str or not order_id:
                reason = "order_id must be a non-empty string"
            elif type(qty_units) is not int or qty_units <= 0:
                reason = "qty_units must be a positive integer"
            elif order_id in self._live:
                reason = "order_id is already active"
        if reason is not None:
            return rejected(event_id, reason)
        if seq is not NO_SEQ:
            self.last_seq = seq
        fills = []
        unfilled = self._market_sell(order_id, qty_units, fills)
        status = "filled" if not unfilled else ("partial" if fills else "unfilled")
        return {"event_id": event_id, "order_id": order_id, "status": status,
                "unfilled_qty_units": unfilled, "fills": fills}

    def CancelOrder(self, target_order_id, event_id=None, seq=NO_SEQ):
        """Remove the target's remaining quantity if it is still active."""
        if type(seq) is int and seq > self.last_seq and type(target_order_id) is str and target_order_id:
            self.last_seq = seq
            removed = self._cancel(target_order_id)
            return {"event_id": event_id, "target_order_id": target_order_id,
                    "status": "cancelled" if removed else "not_found", "cancelled_qty_units": removed}
        reason = None if seq is NO_SEQ else self._seq_error(seq)
        if reason is None and (type(target_order_id) is not str or not target_order_id):
            reason = "target_order_id must be a non-empty string"
        if reason is not None:
            return rejected(event_id, reason)
        if seq is not NO_SEQ:
            self.last_seq = seq
        removed = self._cancel(target_order_id)
        return {"event_id": event_id, "target_order_id": target_order_id,
                "status": "cancelled" if removed else "not_found", "cancelled_qty_units": removed}

    # -- implemented by each version
    def _add_limit(self, order_id, is_buy, price, qty, seq, fills):
        raise NotImplementedError

    def _market_sell(self, order_id, qty, fills):
        raise NotImplementedError

    def _cancel(self, order_id):
        raise NotImplementedError

    def InspectBook(self):
        """Active orders: bids by falling price then arrival, then asks by rising price then arrival."""
        raise NotImplementedError
