# Phase 1: synthetic data and correctness tests

This phase adds tests and small teaching streams only. The order-book implementations belong to the next phase.

## Shared test interface

Both future files, `20_Code/order_book_v1.py` and `20_Code/order_book_v2.py`, should expose an `OrderBook` class with:

- `process_event(event: dict) -> dict`, returning the fields specified in the project README, including only this event's ordered `fills` for submissions;
- `inspect_book() -> list[dict]`, returning active orders in canonical order: bids by decreasing price then arrival, asks by increasing price then arrival. Each order has `order_id`, `side`, `price_ticks`, `qty_units`, and `arrival_seq`.

The tests require input events to remain unchanged. This is an additional test-integrity check. Tests in all three categories run against both versions through one loader. Missing version files cause clear failures rather than a substitute implementation or a false pass.

## Input Robustness

| Test scenario | Input conditions | Expected behavior | Why it matters |
|---|---|---|---|
| Empty/minimal | Empty stream and book; one valid limit | Empty state or one resting order | Establishes basic state behavior |
| Missing/unknown fields | `{}`, absent type or required field, unknown type or side | `rejected`, reason, unchanged book and sequence | Prevents malformed input from corrupting state |
| Price and quantity boundaries | Zero, negative, float, string, Boolean, `None`; also one and very large integers | Invalid values rejected; positive integers accepted | Enforces the stated units without inventing a maximum |
| Sequence and duplicate live ID | Duplicate/decreasing/noninteger sequence; repeated active `order_id` | Rejected event leaves state and last accepted sequence unchanged | Prevents wrong arrival priority and duplicate active orders |

The assignment explicitly requires positive integer prices/quantities, increasing positive integer `seq`, valid event types/sides, and rejection without state changes. Treating Boolean values as invalid integers and requiring an unchanged input dictionary are additional robustness checks. Identifier types are unspecified in the assignment; the later project decision described in `VERSION_B.md` accepts nonempty strings and integers. Unknown and repeated valid cancellation targets return `not_found`, not `rejected`.

## Matching Correctness

| Test scenario | Input conditions | Expected behavior | Why it matters |
|---|---|---|---|
| Supplied worked example | Six-BTC market sell into four bids, plus an ask | Four fills in `b1,b2,b3,b4` order; 359,400 USD gross; exact residual book | Checks the instructor's primary reference |
| Sell sizes | Empty book; one bid; smaller, exact, and oversized sells | `unfilled`, `filled`, or `partial` as appropriate | Checks residual and maker removal |
| Price-time priority | Multiple prices; same-price queue; IDs out of alphabetical order; long queue | Best price first, then original arrival sequence | Catches sorting and FIFO mistakes |
| Partial fills and cancellation | Two sales; cancel before/after partial/full execution; repeat/unknown cancel | Maker retains priority; cancellation removes only residual | Checks state updates across events |
| Crossing limits and residuals | Incoming buys/sells that cross or do not cross | Execute at resting maker price; eligible residual rests | Checks continuous matching |
| Small generated streams | Five 80-event scenarios | Both versions return identical ordered results and canonical books after each event | Adds varied differential checks, alongside independent hand-calculated cases |

Every hand-calculated step checks the complete live book, including identities, remaining quantities, and original arrival ranks. Submission tests check `incoming quantity = sum(fills) + unfilled quantity`; the worked example checks exact integer proceeds. These checks are independent of either future implementation. Differential agreement is supplementary evidence, not an independent oracle.

## Market Behavior

| Test scenario | Input conditions | Expected behavior | Why it matters |
|---|---|---|---|
| No match/insufficient bids | Non-crossing buy and ask; market sells with no or too few bids | Limits rest; unfilled market amount is discarded | Prevents accidental resting of market orders |
| Economically unusual prices | One-tick bid; huge ask and crossing buy; low crossing sell | Positive integer prices accepted; fills use maker prices | No price bands appear in the specification |
| Long-lived order | Old unmatched ask through 20 unrelated market sells, then two cancels | Ask retains price, quantity, and arrival rank; first cancel removes it, second is `not_found` | Detects invented expiry or unintended state loss |

No automatic expiration, price bands, or time-in-force rules are specified. Tests do not add them.

## Synthetic streams and verification

The five supplied 10,000-event gzip files are reused unchanged. `test_synthetic_data.py` checks their event count, sequence order, event types, extracted copies, and all instructor-file checksums from `MANIFEST.json`.

Five new 80-event gzip streams were generated with the unchanged instructor generator, `--levels 20`:

| Scenario | Seed | File |
|---|---:|---|
| buildup | 42 | `10_Data/phase1_buildup_80_seed42.jsonl.gz` |
| crowded | 43 | `10_Data/phase1_crowded_80_seed43.jsonl.gz` |
| mixed | 44 | `10_Data/phase1_mixed_80_seed44.jsonl.gz` |
| sweep | 42 | `10_Data/phase1_sweep_80_seed42.jsonl.gz` |
| cancel_churn | 43 | `10_Data/phase1_cancel_churn_80_seed43.jsonl.gz` |

Each has a generator-created `.metadata.json` beside it. The data test checks every saved row against a fresh in-memory run with the same seed and checks the saved checksum and variation. The scenario constraints still apply: `cancel_churn` is intentionally alternating add/cancel, and `crowded` intentionally uses only four prices per side. Invalid inputs occur only in the robustness tests, never in these valid workload streams.

From the assignment root, run:

```sh
python -m unittest discover -s 30_Tests -p 'test_*.py'
```

To regenerate one stream, use the same pattern for each table row:

```sh
python 20_Code/generate_orders.py --scenario buildup --events 80 --levels 20 --seed 42 --out 10_Data/phase1_buildup_80_seed42.jsonl.gz
```

Only the synthetic-data checks can pass before Phase 2. The three order-book categories are expected to fail with a missing-version message until both implementations exist. Do not change expected outcomes to silence those failures.

### Phase 1 verification, 23 November 2026

- Verification used the installed Python 3.14.6 interpreter by its absolute path because `python` was not on this session's PATH. The commands above are the portable equivalents for a normal Python installation.
- `python -m unittest discover -s 30_Tests -p test_synthetic_data.py -v`: 3 tests passed. The manifest check confirms all instructor-supplied files retain their recorded bytes and SHA-256 values.
- `python -m unittest discover -s 30_Tests -p 'test_*.py'`: 19 test methods discovered; 3 data methods passed and the order-book methods produced 95 subtest failures, all at the explicit missing-version check for `order_book_v1.py` or `order_book_v2.py`. The many subtest failures reflect individual input values and version combinations, not 95 distinct observed engine bugs. No order-book logic has been run.

## Open specification points

- The README does not prescribe Python method signatures. The shared interface above is the test contract selected for this project.
- The assignment leaves identifier types unspecified; the current project policy is documented in `VERSION_B.md`. Whether a previously used but inactive `order_id` may be reused is also unspecified. Supplied valid submissions are globally unique; tests enforce only duplicate **live** IDs.
- The README requires a reason on rejections but does not prescribe exact reason text. Tests require a nonempty reason only.
