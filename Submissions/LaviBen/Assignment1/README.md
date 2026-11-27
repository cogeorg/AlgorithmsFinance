# Assignment 1 - limit order book

- Student: Ben Lavi
- Submission path: `Submissions/LaviBen/Assignment1/`
- Branch: `lavi/assignment1-limit-order-book`
- Language target: Python 3.10+

## Current implementation status

The interface and expected behavior are frozen in `CONTRACT.md`. The supplied
generator and fixtures are copied byte-for-byte and recorded in
`fixtures/CHECKSUMS.json`.

Tests were written and run before either implementation; the original failing
run remains recorded in `TESTS_FIRST_BASELINE.md`. Both preserved versions now
exist:

- `BaselineOrderBook` transparently scans a list of individual active orders.
- `RevisedOrderBook` uses indexed FIFO price levels, an active-order index and
  sorted price keys with eager cleanup.

The complete post-audit suite passes. Both versions produce identical ordered
results and identical canonical books after every event in all five supplied
10,000-event streams.
This agreement supplements the independently calculated examples and
invariants; it is not a proof.

Run from this directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The suite includes a strict 50,000-event supplied-stream replay with canonical
state comparison after every event; that test can take several minutes. The
fresh-audit additions cover direct-method type safety, integer boundaries,
ask-side FIFO, residual priority, repeat pairing, bounded diagnostics,
object-lifecycle cleanup, strict report validation, missing-repeat disclosure,
saved-sample latency ECDF, pooled raw-repeat reporting, cross-record summary
reconciliation, canonical-evidence completeness, and root-level discovery. The
verified result is `Ran 71 tests` followed by `OK` (190.969 seconds on the
recorded development machine).

Replay the worked example with either version:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/replay.py \
  fixtures/worked_example.jsonl --version baseline --trace
PYTHONDONTWRITEBYTECODE=1 python3 tools/replay.py \
  fixtures/worked_example.jsonl --version revised --trace
```

Both traces fill makers `b1`, `b2`, `b3`, then `b4`, leave four BTC on `b4`,
leave the two-BTC ask unchanged and imply gross proceeds of `359400.00` USD.

The replacement canonical benchmark was run from clean measurement commit
`e3a5ee630b7d221722953b953bb9ae2c5cd9acc5`. It contains 73 datasets and
3,744 records, including the declared one-million-event mixed attempt. All 76
completed correctness rows agree; 15 bounded correctness attempts stopped,
and no timing summary is missing a repeat. The archive records five raw repeats,
latency samples, memory, operation counts, environment, settings, checksums and
explicit stopped/partial evidence. `dashboard.py` and `build_report.py` load
these saved results only; they never rerun benchmarks. Both builders require
`measurement_integrity_revision: 4` before granting clean evidence canonical
status.

Rebuild the two derived artifacts using:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 dashboard.py \
  --results results/raw_measurements.json.gz \
  --output results/dashboard.html
PYTHONDONTWRITEBYTECODE=1 python3 build_report.py \
  --results results/raw_measurements.json.gz \
  --output REPORT.md
```

The dashboard is dependency-free, works offline, exposes raw repeats,
settings, environment, stopped/missing evidence and diagnostic coverage,
renders a latency ECDF from saved `samples_ns`, and changes filters without
running measurement code. Both current artifacts rebuild byte-for-byte and are
fingerprinted in `results/CHECKSUMS.json`.

## Frozen public API

Both `BaselineOrderBook` and `RevisedOrderBook` expose:

- `ProcessEvent`
- `AddLimitOrder`
- `CancelOrder`
- `FillMarketSell`
- `InspectBook`
- read-only `last_accepted_seq`

All event and result field names, validation precedence, rejection reasons,
ordering rules, and invariants are defined in `CONTRACT.md` and exercised by
the same tests. Each named direct method accepts only its corresponding event
type. A completely valid event passed to the wrong direct method is rejected
atomically with `wrong_event_type_for_method` and does not advance sequence.

## Implement and revise evidence

`IMPLEMENTATION_NOTES.md` records pseudocode, invariants, runtime and space
reasoning, the meaningful data-structure revision, discovered validation and
measurement regressions, and AI-use decisions. The original 20-test suite
passed before the first algorithm regressions were added, and strict
supplied-stream comparison followed. Fresh-audit algorithm, measurement,
dashboard, and report regressions were likewise written and observed failing
before their implementation fixes; exact commands and results are preserved in
`REGRESSION_FIX_BASELINE.md`.

## Supplied teaching data

`tools/generate_orders.py`, the worked example, and the five compressed
10,000-event streams are unmodified teaching assets. They are synthetic and
not calibrated historical exchange data. Generated 100,000- and
1,000,000-event streams remain untracked. Their exact commands are in
`MEASUREMENT_PLAN.md`; the archived raw report records every dataset setting
and checksum, including one-million-event SHA-256
`ce4213a66317d9565327e231f8cc84aa5f04e01253ba225feff4f9be7db08120`.

The source package manifest also listed `.DS_Store`, but that file was absent
from the package and is intentionally not recreated or submitted.
