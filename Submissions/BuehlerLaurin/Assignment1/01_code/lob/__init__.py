"""Registry: METHODS = {(name, version): class}. Each call of a class gives a fresh empty book.

Final B = B3r. A and every measured variant keep their explicit names.
Public API (SPEC.md, Q1): AddLimitOrder, CancelOrder, FillMarketSell, process,
snapshot, best_bid, best_ask.
"""
from lob.book_a import OrderBookA
from lob.book_b import OrderBookB
from lob.book_b2 import OrderBookB2
from lob.book_b3 import OrderBookB3
from lob.book_b3r import OrderBookB3r
from lob.book_b3r_fast import OrderBookB3rFast

METHODS = {("lob", "A"): OrderBookA, ("lob", "B"): OrderBookB3r,
           ("lob", "B1"): OrderBookB,
           ("lob", "B2"): OrderBookB2, ("lob", "B3"): OrderBookB3,
           ("lob", "B3r"): OrderBookB3r, ("lob", "B3r_fast"): OrderBookB3rFast}
