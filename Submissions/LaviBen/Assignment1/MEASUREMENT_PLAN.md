# Measurement stages and reproducibility

## Status

Stages 7-9 are implemented and have current canonical evidence:

1. deterministic benchmark input preparation with settings and SHA-256;
2. primary timing, throughput, separate per-event latency, correctness and
   operation-count runs; and
3. fresh `tracemalloc` runs with explicit inclusion boundaries.

The tracked `results/` archive and generated `REPORT.md` were replaced after
the measurement-integrity audit. The current archive is revision 4 evidence
from clean commit `e3a5ee630b7d221722953b953bb9ae2c5cd9acc5` and contains
73 datasets plus 3,744 records. The earlier commit
`ffb474170b4849af850e31588f9a1a70dcf08da3` remains historical provenance only.

The runner refuses `--profile canonical` while the Assignment 1 tree is dirty.
The recorded run began from the clean committed tree, so its environment names
the code actually measured.

## Dataset grid

Canonical preparation creates:

- all five course workload families at `M = 1,000; 10,000; 100,000`, seeds
  `42`, `43`, and `44`, with 1,000 available price levels;
- queue-concentration inputs with the same event counts and seeds at 4 versus
  1,000 available prices; and
- bid-only liquidation setup books with the same event counts and seeds.

Every dataset is generated before timing and stored under ignored
`generated/benchmark/`. Its metadata records experiment, scenario, event
count, seed, levels, units, generator, compressed size, compressed SHA-256 and
canonical event SHA-256. One verified immutable event tuple is shared by both
versions. Generated large inputs remain outside Git.

Smoke preparation uses 1,000 events and seed 42 while retaining all five
families, both concentration cases and one liquidation setup:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/prepare_benchmarks.py --profile smoke
```

Canonical preparation, after the measurement code is committed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/prepare_benchmarks.py --profile canonical
```

## Timing and latency definitions

Run the provisional smoke measurements:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_benchmarks.py \
  --profile smoke \
  --output tmp/benchmark_smoke.json.gz
```

The canonical command executed from the clean tree was:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_benchmarks.py \
  --profile canonical \
  --time-limit-seconds 5 \
  --output results/raw_measurements.json.gz
```

The five-second operational limit applies independently and equally to every
version's replay repeat, latency run, bounded operation-count prefix,
liquidation correctness attempt, liquidation build/sale operation, and memory
run. Input parsing is measured but has no separate operational limit;
`application_total` is a derived sum and does not run under a new limit. The
finite limit lets quadratic baseline cases
produce explicit stopped evidence instead of making the grid impractical.
Completed smaller cases remain measured normally; stopped values are not
extrapolated.

Before that run, add one feasible million-event attempt without expanding the
entire grid to that size:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/prepare_benchmarks.py \
  --profile canonical --sizes 1000000 --seeds 43 --scenarios mixed \
  --skip-special --output-dir generated/million
cp generated/million/stream__mixed__m1000000__seed43__levels1000.jsonl.gz \
  generated/benchmark/
cp generated/million/stream__mixed__m1000000__seed43__levels1000.jsonl.gz.metadata.json \
  generated/benchmark/
```

The same canonical runner then includes that dataset, applies the same limit
to both versions, and retains either completed or stopped evidence.

The report records the exact executable and argument vector actually used.
Canonical mode uses five raw repeats and reports their median; smoke mode uses
two repeats only to test the pipeline. Parsing and replay repeat counts must be
equal so every application-total repeat has an immutable one-to-one pair; the
runner rejects unequal settings before measurement.

- `input_read_parse`: gzip reading plus JSON decoding, measured separately.
- `engine_replay`: fresh empty-book construction plus the complete prepared
  event batch. Input generation and parsing are excluded.
- `application_total`: paired input reading/parsing plus engine replay (or
  paired parsing plus liquidation build and sale).
- `book_build`: fresh liquidation-book construction from every setup order.
- `individual_sale`: matching, state/index updates and fill-list construction
  for one 10%, 100%, or 200% sale against its own freshly built book.
- `build_plus_sale`: the corresponding construction and sale times combined.

Both versions receive the same inputs, warmup prefix, repeat count and
operational time limit. Completed replay, build, and sale clocks start only
after timeout-handler setup and stop before handler teardown. Each parse result
is released after its stop-clock and before the next repeat's start-clock;
each liquidation book, final result, and fills list is likewise released after
its clocks and before the next construction repeat. A stopped attempted run is
saved with elapsed time, completed event count and reason. A sale skipped
because its book build stopped is explicitly `attempted: false`, has
`elapsed_seconds: null`, and is never assigned an invented duration. Parsing,
latency, operation counting and memory tracing do not run inside primary
timing.

Full liquidation correctness results, canonical states, and fill lists are
reduced to compact comparison fields, released, and garbage-collected before
warmup, primary timing, or memory tracing begins.

For a timeout after an operation starts, the stopped duration ends at the
first exception-path clock read, after the timeout context has restored its
signal handler. If the context stops before the operation's start clock, the
attempted phase records zero elapsed time. These stopped-run semantics and the
completed-operation boundary are written into the saved settings. Corrected
runs also record `measurement_integrity_revision: 4`; clean reports with an
older revision are labeled superseded rather than canonical.

Every timing summary records expected, completed, stopped, and missing repeat
counts plus `completion_status` (`complete`, `partial`, `stopped`, or
`missing`). Partial or missing summaries remain visible with their exact repeat
coverage; they are never presented as if all five canonical repeats completed.

Latency instrumentation saves every per-event duration in nanoseconds and
reports nearest-rank median, 95th and 99th percentiles overall, by event type,
and for early versus late windows. Each window is the first or last 10% of the
instrumented stream, capped at 1,000 events. Nearest-rank means sorting `n`
samples and selecting rank `ceil(p/100*n)`, with minimum rank one. These are
in-process algorithm times, not network or queueing latency.
The dashboard renders an empirical cumulative distribution directly from the
saved `samples_ns`; it never reruns or reconstructs latency measurements.
Cross-seed report tables pool the saved event samples before applying the same
nearest-rank rule; they do not take medians of seed-level percentiles.

## Operation counts and correctness

Separate runs over the configured diagnostic prefix save event/status counts,
fills, filled quantity, market residual, active-order peak, occupied-price-level
peak and final book size. They record requested and processed event counts, use
the declared operational limit, and preserve stopped/partial evidence instead
of delaying a large benchmark without a bound. The cross-version per-event
result and canonical-book comparison uses that same wall-clock limit and emits
an explicit stopped correctness row if it cannot complete.

Liquidation records also save requested quantity, makers touched, price levels
visited and unfilled residual. Ordered results and canonical books are compared
between versions after every diagnostic event and after every liquidation
size.

Liquidation construction, sale, and final inspection share the declared
diagnostic limit; a version that cannot finish produces a labeled stopped
correctness row rather than an unbounded pre-measurement delay.

## Memory boundary

Input events are fully prepared before tracing. Each version and liquidation
size gets a fresh tracing run:

1. collect garbage;
2. start `tracemalloc`;
3. construct a fresh book and process the measured workload;
4. read current and peak traced bytes while the book and final returned output
   are alive; and
5. stop tracing.

The input tuple is excluded. The book, active indexes/price levels and final
output are included. Prior per-event outputs are not retained, matching the
engine's no-history design. Allocation checkpoints at 10%, 50%, and 100% show
growth and post-cancellation state. Their containers are allocated before
tracing; retained integer readings add negligible bookkeeping. Python
allocations observed by `tracemalloc` are included; native/process allocations
are not. A memory phase uses the same declared time limit and records
partial/stopped evidence rather than hanging.

## Smoke preflight and canonical evidence

The fresh revision-3 smoke report covers eight representative 1,000-event
datasets and contains 232 validated records, including 14,000 saved latency
samples. It validates repeat pairing, prefix-bounded diagnostics, strict schema
checks, and complete summaries with zero stops or missing repeats. Its dashboard
and report rebuild byte-for-byte. This remains provisional because the source
tree was dirty: every smoke report uses `provisional_smoke` and must not be
copied into canonical results.

The subsequent clean canonical run contains 73 datasets and 3,744 records.
All 76 completed correctness comparisons agree, 15 correctness attempts retain
declared stopped evidence, and the timing summaries contain zero missing
repeats. The one-million-event mixed case is present rather than silently
omitted. `REPORT.md`, `results/dashboard.html`, and the compressed raw report
are fingerprinted by `results/CHECKSUMS.json`.
