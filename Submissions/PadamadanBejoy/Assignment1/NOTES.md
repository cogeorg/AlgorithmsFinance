# Notes – Assignment 1: Limit Order Book

## Environment
- Machine: MacBook Air, macOS (version: fill in from  → About This Mac)
- Python 3.14 (python.org installer, /Library/Frameworks/Python.framework/Versions/3.14)
- pytest 9.2.0 (installed with `python3 -m pip install pytest`)
- Editor: VS Code with Python extension (interpreter: Python 3.14)
- Note: assignment generator was checked with Python 3.11.9; I use 3.14.

## Project structure
- `orderbook/` – package with the two implementations
  - `version_a.py` – baseline (simple list of orders)
  - `version_b.py` – improved version (later)
- `tests/test_cases.py` – tests with hand-calculated expected results
- `data/` – supplied event files (worked example + five 10,000-event samples)
- `__init__.py` files mark `orderbook/` and `tests/` as packages so tests can
  import `from orderbook.version_a import OrderBook`.

## Design decisions
- Method names follow the spec: `AddLimitOrder`, `FillMarketSell`, `CancelOrder`,
  plus `process_event` (dispatcher) and `snapshot` (book inspection).
- Each method takes one event dictionary, exactly as read from the JSON Lines file.
- `snapshot()` returns a list of dicts with `order_id`, `side`, `price_ticks`,
  `qty_units`, `arrival_seq` – same shape as `remaining_orders` in
  `data/worked_expected.json`. Bids first (high→low price, then seq), then asks
  (low→high price, then seq).
- Module names lowercase (`version_a.py`), following PEP 8; avoids
  case-sensitivity problems on Linux.
- All prices/quantities kept as integers (cents, 1e-8 BTC units) to avoid
  floating-point rounding errors. Constant `BTC = 100_000_000` in tests for readability.

## Log
### Tue 24 Nov 2026
- Read the spec; worked through the worked example by hand
  (6 BTC sell → fills b1:1, b2:1, b3:3, b4:1 BTC; proceeds 359,400 USD; 4 BTC left on b4).
- Set up project folders and files in VS Code.
- Wrote a stub `OrderBook` class in `version_a.py` (every method raises
  `NotImplementedError`) so tests can import it and fail for the right reason.
- 21:03 – First test `test_one_limit_buy_rests_on_empty_book` written by me.
  Ran `python3 -m pytest -q` → `1 failed` (NotImplementedError), as expected (test first).

### Mistakes I made while writing expected values (useful for report)
- Price in dollars instead of cents: wrote 60_000, correct is 6_000_000 ticks.
- Wrote 1 for unfilled quantity: that is 1 unit (1e-8 BTC), not 1 BTC → use `1 * BTC`.
- Wrote `fills == 1`: `fills` is a list of trades, not a count → `[]` when nothing trades.
- Used "RESTED" / "filled": status must be the spec's exact word, "resting".
- Thought result has "no data" on an empty book: the result describes the
  incoming order, which always exists.

### Setup problems solved
- `No module named pytest` → installed pytest.
- `no tests ran` → test file was empty/not saved.
- Typed terminal command into the test file → SyntaxError; removed it.
- Import `from version_a import ...` failed → must be `from orderbook.version_a import ...`.
- `cannot import name 'OrderBook'` → version_a.py was empty; added the stub.
- VS Code's ▷ Run button runs a file as a program, not as tests; use
  `python3 -m pytest -q` in the terminal instead.

## AI usage
Tool: Claude (Anthropic), used as a guided tutor.
- Accepted: project folder layout; stub class with method names; the snapshot
  dictionary format (matched to worked_expected.json); using integers and a BTC constant.
- Corrected by AI (my own mistakes, see above): units in test expected values.
- Rejected/avoided: VS Code's built-in "Generate code" AI – not used.
- I write the tests' expected outcomes and the matching logic myself.
## Test tracker 
(TestTrack): https://claude.ai/artifact/7a9XPzEbRctmP5puBDbEYD
- 01:24 – Test 20: limit sell takes the best (highest) bid first; lower bid untouched.
  Lesson: "type" (LIMIT / MARKET_SELL / CANCEL) and "side" (BUY / SELL) are separate fields.
  pytest: 11 failed, as expected.
  ### Wed 25 Nov, morning
- Tests 9 (sweep across price levels), 21 (limit sell stops at its limit),
  cancel test (after partial fill + repeat cancel → not_found).
- Lessons: result holds only the CURRENT event's fills; a cancel's status is
  "cancelled" or "not_found"; event = input, result = output decided by our code.
- 13:29 – Version A step 1 (store orders, dispatcher, snapshot): 4 passed, 10 failed.
  New failures are AssertionErrors: tests catching missing matching logic.
  - GitHub fork: bpadamadan/AlgorithmsFinance (synced 25 Nov, up to date).
  ### Wed 25 Nov, evening
- .gitignore added; cache/system files removed from git.
- Validation (spec rule 6) in shared module orderbook/validation.py, used by both
  versions so they reject identically. Test for invalid input: 16 passed.
- Version B: per side {price: deque} (FIFO per price level), sorted price list
  (bisect.insort; best bid = last, best ask = first), index {order_id: order}
  for O(1) cancel lookup / duplicate check. Matching trade step identical to A.
- Same 16 tests pass on B unchanged (ORDERBOOK_VERSION=B python3 -m pytest -q).
- Added randomized comparison test: 20 seeds x 300 events, A and B results and
  snapshots compared after EVERY event → 17 passed.
- replay.py: `python3 replay.py <file> [--version A|B]`; worked example reproduces
  expected fills (b1, b2, b3, b4) and 2 remaining orders.
- Commits: e2a5a74 (Version A), 1ccf24c (validation), + tonight's.
- Quick check: buildup_10000 replay A 3.51 s vs B 0.09 s (incl. startup + file reading).
  Cause: A scans the whole book in is_live and _match for every event → ~quadratic.