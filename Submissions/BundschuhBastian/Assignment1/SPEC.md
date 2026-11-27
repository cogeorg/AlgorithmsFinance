# Specification and design decisions (Phase 0)

Assignment 1: build and benchmark a limit order book. Bastian Bundschuh.
Source of truth: `docs/ASSIGNMENT_README.md` (the course README) and
`docs/AlgorithmsFinance_Exercise1.pdf`. This file restates the rules in my own words and
records every decision where the spec leaves a choice. Both versions (A and B) follow
this file exactly, so they must return identical results.

Decision IDs (`D1`, `D2`, ...) are referenced from tests and the report.

---

## 1. Model and its boundaries

- One venue, one instrument (BTC/USD), events processed one at a time in `seq` order.
- Continuous matching at the resting order's price. No batch auction, no single clearing price.
- Out of scope, by assignment: fees, account balances, hidden/iceberg orders, self-trade
  checks, network delay, simultaneous events, market buys, order modification.
- The data are synthetic teaching data. They are not historical exchange records and are
  not calibrated to any exchange. This is not a production trading system.

## 2. Units (all integers)

| Field | Unit | Example |
|---|---|---|
| `price_ticks` | 1 tick = 0.01 USD per BTC | 6,000,000 = 60,000.00 USD |
| `qty_units` | 1 unit = 0.00000001 BTC (10^-8) | 100,000,000 = 1 BTC |
| fill value | `price_ticks * qty_units` (tick-units) | 6,000,000 x 100,000,000 = 6e14 |
| USD | sum of fill values / 10,000,000,000 | 3,594,000,000,000,000 -> 359,400.00 |
| `seq` | arrival rank, strictly increasing | 1 arrives before 2 |

Matching and conservation checks use integers only. Conversion to USD happens only for
display (D17).

## 3. Events

| Type | Required fields (besides `seq`, `event_id`, `type`) |
|---|---|
| `LIMIT` | `order_id`, `side` (`BUY`/`SELL`), `price_ticks`, `qty_units` |
| `MARKET_SELL` | `order_id`, `qty_units` |
| `CANCEL` | `target_order_id` |

Extra fields are ignored (D7).

## 4. Matching rules

1. A limit BUY crosses if `price_ticks >= best ask`. A limit SELL crosses if
   `price_ticks <= best bid`.
2. Take the best opposite price first. At that price, take the order with the smallest
   arrival `seq` first (FIFO). The spelling of `order_id` never decides priority.
3. Trade `q = min(incoming remaining, resting remaining)` at the **resting** order's price.
   Repeat while the order still crosses and both quantities are positive.
4. A resting order at 0 is removed. A partially filled resting order keeps its place in its queue.
5. A LIMIT residual rests at its own limit price with arrival rank = its own event `seq`.
6. `FillMarketSell` takes bids from the highest price down, in the same FIFO order. It changes
   the live book. Any residual is discarded and never rests.
7. Cancel removes the target's whole remaining quantity, also after a partial fill.

**Invariants after every accepted event** (checked in tests):
- I1: the book is not crossed, so `best_bid < best_ask` if both sides exist.
- I2: every resting quantity is > 0.
- I3: every active order is stored exactly once, on one side, at one price.
- I4: incoming quantity = sum of its fills + its returned residual.
- I5: each maker loses exactly the quantity of its fills.
- I6: a cancel removes exactly the target's remaining quantity.
- I7: proceeds = sum of `price_ticks * qty_units` over the fills.

---

## 5. Decisions where the spec leaves a choice

### Validation

| ID | Decision | Reason |
|---|---|---|
| D1 | A field counts as an integer only if `type(x) is int`. `True`/`False`, floats (also `6000000.0`), strings and `None` are rejected. | In Python, `bool` is a subclass of `int`, so `isinstance(True, int)` is `True`. The spec says "noninteger". |
| D2 | `seq` must be an integer (D1), > 0, and strictly greater than the last **accepted** `seq`. The start value of the last accepted `seq` is 0. | The spec says strictly increasing and positive; rejected events do not advance it. |
| D3 | `event_id` must be present and a non-empty string. Uniqueness of `event_id` is **not** checked. | The spec only requires that it exists ("event_id if available"). Duplicate `event_id` is not in the list of invalid events. |
| D4 | Unknown `type` (also `MARKET_BUY`) -> rejected. For a LIMIT, a `side` other than exactly `"BUY"` or `"SELL"` -> rejected (case-sensitive). | Spec rule 6. |
| D5 | `order_id` (LIMIT, MARKET_SELL) must be a non-empty string. If it equals the ID of a **currently active** order -> rejected as a duplicate live ID. This also applies to MARKET_SELL. Reusing the ID of an order that is already filled or cancelled is accepted. | The spec says "duplicate live submission identifiers"; historical reuse is out of scope. A market sell with a live ID would make the fill list ambiguous. |
| D6 | CANCEL: `target_order_id` must be a non-empty string. An unknown, filled, cancelled or market-sell target -> `not_found`, which is a **valid** event and advances `seq`. | Spec rule 5 and 6. |
| D7 | Extra or unknown fields are ignored. | Not forbidden by the spec. |
| D8 | A missing required field -> rejected. | Required fields are listed in the spec. |
| D9 | Checks run in this fixed order, and the **first** failure is the reason: parse -> `seq` -> `event_id` -> `type` -> type-specific fields in the order of the table below -> duplicate live ID. | Both versions must return the same reason. |

**Reason codes** (exact strings):

| Order | Check | Reason string |
|---|---|---|
| 0 | line is not a JSON object | `malformed_event` |
| 1 | `seq` missing / not int / <= 0 | `invalid_seq` |
| 2 | `seq` <= last accepted `seq` | `nonincreasing_seq` |
| 3 | `event_id` missing or not a non-empty string | `invalid_event_id` |
| 4 | `type` not LIMIT / MARKET_SELL / CANCEL | `unknown_type` |
| 5 | `order_id` missing or invalid (LIMIT, MARKET_SELL) | `invalid_order_id` |
| 6 | `side` missing or not BUY/SELL (LIMIT) | `unknown_side` |
| 7 | `price_ticks` missing / not int / <= 0 (LIMIT) | `invalid_price` |
| 8 | `qty_units` missing / not int / <= 0 (LIMIT, MARKET_SELL) | `invalid_qty` |
| 9 | `target_order_id` missing or invalid (CANCEL) | `invalid_target_order_id` |
| 10 | `order_id` is currently active | `duplicate_live_order_id` |

### Results (exact keys; tests compare whole dicts)

| ID | Decision |
|---|---|
| D10 | Every result is a dict and always has a `fills` list (empty for CANCEL and rejected events). A fill is `{"maker_id", "taker_id", "price_ticks", "qty_units"}` in execution order. |
| D11 | LIMIT result: `{"event_id", "order_id", "status", "unfilled_qty_units", "fills"}`. `status = "filled"` if nothing rests; otherwise `"resting"` (also when it did not trade at all). `unfilled_qty_units` = the quantity that rests (0 if filled). |
| D12 | MARKET_SELL result: same keys as D11. `status` is `"filled"` if residual = 0, `"partial"` if it traded but residual > 0, and `"unfilled"` if no fill. `unfilled_qty_units` = the discarded residual. This matches `data/worked_expected.json`. |
| D13 | CANCEL result: `{"event_id", "target_order_id", "status", "cancelled_qty_units", "fills": []}`. `status` is `"cancelled"` or `"not_found"` (then quantity 0). |
| D14 | Rejected result: `{"event_id", "status": "rejected", "reason", "fills": []}`. `event_id` is the value from the event if it is a non-empty string, otherwise `None`. |
| D15 | Book inspection `snapshot()` returns a list of `{"order_id", "side", "price_ticks", "qty_units", "arrival_seq"}`: first all bids (price descending, then `arrival_seq` ascending), then all asks (price ascending, then `arrival_seq` ascending). This matches `remaining_orders` in `data/worked_expected.json`. |
| D16 | No trade history is stored. Each result holds only the current event's fills. If a test needs history, the **test** collects it (it is not part of the engine's memory). |
| D17 | USD display: `proceeds_usd(total) = total / 10**10`, formatted with 2 decimals, rounding half up, computed with `decimal.Decimal` (never float). |
| D18 | Self-trades are allowed (no check), as the spec says. |
| D19 | There is no upper limit on price or quantity (Python integers have no overflow). |

---

## 6. Interface (both versions, same signatures)

Classes: `lob.version_a.OrderBookA` and `lob.version_b.OrderBookB`. Method names
follow the spec (`AddLimitOrder`, `CancelOrder`, `FillMarketSell`).

```python
book = OrderBookA()                 # fresh, empty book; last accepted seq = 0

book.process(event: dict) -> dict   # dispatcher: validate (D1-D9), then call one
                                    # of the three operations; updates last seq only
                                    # if the event is accepted
book.AddLimitOrder(event) -> dict   # LIMIT;       assumes a validated event (D11)
book.FillMarketSell(event) -> dict  # MARKET_SELL; assumes a validated event (D12)
book.CancelOrder(event) -> dict     # CANCEL;      assumes a validated event (D13)
book.snapshot() -> list[dict]       # canonical book (D15), O(B log B) at most
book.best_bid() -> int | None       # highest bid price, None if no bids
book.best_ask() -> int | None       # lowest ask price, None if no asks
```

Untrusted input must go through `process()`. The three operations are public for tests and
benchmarks, but they do not validate.

Validation is shared code (`lob/common.py`) used by both versions. Risk: a validation bug
would be the same in A and B, so the A-vs-B comparison cannot find it. The independent
hand-calculated tests in `tests/test_handcalc.py` must cover validation on their own.

Replay command (works once the engines exist):

```bash
.venv/bin/python -m lob.replay data/worked_example.jsonl --version A
```

It prints one JSON result per line, then the final snapshot and the total proceeds.

## 7. Notation for complexity (used in the report)

| Symbol | Meaning |
|---|---|
| M | number of incoming events in a stream |
| B | number of active (resting) orders at a moment |
| P | number of occupied price levels (on one side, or both if stated) |
| F | number of maker fills caused by one event |
| L | number of price levels emptied by one event |

More events (M) do not mean a bigger book (B). Example: `cancel_churn` has M = 10,000 but
B <= 1 most of the time.

## 8. Data integrity note

The supplied `.gz` files have SHA-256 values in their metadata. Regenerating the same
stream with another zlib version (for example Python 3.13 with zlib-ng) gives
**different `.gz` bytes but identical decompressed content**. Checked: `mixed`, 10,000
events, seed 42. `tools/verify_data.py` therefore reports both checksums: the `.gz`
file and the decompressed JSON Lines. The decompressed checksum is the one that proves
the data are the same.
