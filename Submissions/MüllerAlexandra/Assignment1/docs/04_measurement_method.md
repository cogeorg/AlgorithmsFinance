# Measurement method

This protocol is fixed before Version A performance results are inspected and
before Version B is selected. Version A and Version B must use identical input
bytes, settings, limits, measurement boundaries, and result definitions.

## Symbols and scope

- `M`: incoming events processed.
- `B`: active individual orders.
- `P`: occupied price levels across both sides.
- `F`: maker fills returned by an incoming event.

The measurements describe sequential Python processing of synthetic events on
one machine. They are not exchange capacity, network latency, queueing latency,
or evidence about historical market behavior. Sequential replay alone cannot
establish the event rate at which a live venue would overload.

## Inputs

The five workload families are `buildup`, `crowded`, `mixed`, `sweep`, and
`cancel_churn`. The core matrix uses event counts 1,000, 10,000, and 100,000
with seeds 42, 43, and 44. The supplied 10,000-event seed-42 files are reused
directly. Other inputs are generated before measurement and stored outside
version control under `data/generated/`; commands, settings, metadata, and
checksums are retained.

The machine-readable input plan contains 45 core configurations: five workload
families crossed with 1,000, 10,000, and 100,000 events and seeds 42, 43, and
44. The five supplied 10,000-event seed-42 streams are reused byte-for-byte;
the other 40 are generated. One additional 10,000-event, seed-42 `buildup`
stream with four available levels supports the controlled comparison against
the supplied 1,000-level buildup stream. All 46 inputs are verified against
their settings, compressed byte counts, and SHA-256 checksums before timing.

One-million-event runs are attempted only after smaller pilots. A time and
memory limit will be recorded before those attempts and applied identically to
both versions. A stopped run remains in the results with its limit and reason;
missing results are never invented or extrapolated.

For the preregistered 1,000-, 10,000-, and 100,000-event tasks, each child
configuration has a 60-second wall-clock limit, applied identically to both
versions. A timeout produces a status record containing its command, input
settings, environment, code version, elapsed time, limit, and stopping reason;
it produces no fabricated measurement. Only a completed child result whose
phase, version, and input checksum match the task is promoted from its pending
path.

The formal plan contains 114 tasks per version: throughput and state-memory
measurements on all 46 inputs; latency on all nine core buildup inputs and the
five supplied 10,000-event scenario inputs, with their overlap counted once;
and retained-output memory on the nine core cancellation-churn inputs. Large
liquidation and diagnostic-count experiments remain separate so their heavy
instrumentation does not alter primary timing.

## Primary replay timing

Events are parsed and held in memory before the engine timer starts. Each
replay constructs a new empty book. Use `time.perf_counter` for construction
and replay timing. Preserve empty-book construction/reset time separately;
throughput uses replay time, while total engine time includes construction plus
replay. The replay region includes event validation, matching or cancellation,
state mutation, and construction of the current event result and fill list. It
excludes input generation, JSON/gzip parsing, printing, test assertions,
per-event inspection, AI calls, memory tracing, and dashboard work.

For every configuration:

1. Perform one untimed warm-up with a fresh book.
2. Perform five timed repeats, each with a fresh book.
3. Keep every raw elapsed time and throughput value.
4. Report the median elapsed time and median throughput.

Throughput is `M / replay_seconds`. Reading/parsing, input copying, and other
preparation costs are measured separately rather than treated as free. Full
application time additionally reports preparation, construction, and replay
under an explicit boundary.

## Processing-latency instrumentation

Per-event processing latency is collected in separate instrumented runs because
two clock calls per event add overhead. The event timer surrounds only
`process_event`. Raw integer nanoseconds retain both repeat and event indices.
After the configured untimed warm-ups, perform five measured repeats, each on a
fresh empty book. Report median, 95th percentile, and 99th percentile across
all retained samples overall and by event type. For submission floods, also
compare the first and last 10% of events.

Perform the configured untimed warm-up on a separate book, then create a new
empty book for the instrumented replay. Thus warm-up does not deplete or grow
the state used for the recorded early/late comparison.

Percentiles use the nearest-rank convention. Sort `N` samples and select the
one-based rank `ceil(p / 100 * N)`. The reciprocal of throughput is not reported
as latency.

Within every repeat, the early and late windows each contain
`max(1, ceil(0.10 * M))` events. Corresponding windows are then pooled across
repeats for their summaries. For very small smoke inputs these windows may
overlap; formal workloads are large enough that they are distinct.

## Memory instrumentation

Memory is measured in runs separate from primary timing using `tracemalloc`.
Inputs are preloaded before tracing, so their allocations are excluded. Report
current and peak traced Python bytes and state that these are neither total
process memory nor theoretical auxiliary space.

Two modes are distinguished:

- `memory_state`: do not retain the complete result history; include live book
  state, temporary matching allocations, and the current returned result.
- `memory_retained_output`: retain every returned result and fill list so output
  history is explicitly included.

The traced region begins before empty-book construction and ends immediately
after the last growth sample. It therefore includes book construction, live
state, matching temporaries, the current result, and the fixed set of growth
checkpoint records. Input parsing and the preloaded event tuple precede
tracing. Final canonical book inspection follows tracing and supplies active
order and occupied-level counts without inflating the recorded peak. Every
saved record carries these inclusion flags.

For cancellation churn, report final active orders, final occupied levels,
current bytes, and peak bytes. This reveals storage that grows with historical
events even when active depth is tiny.

For buildup, record memory as the book grows rather than only its final state.
Any stale entries, delayed cleanup, or storage that grows with all submissions
rather than active orders must be identified and explained.

If preloading becomes impractical, stream the input and record parsing
separately. The affected results must state the changed boundary and must not be
compared as though they used the preloaded protocol.

## Diagnostic and correctness run

Heavy counters and correctness checks are separate from primary timing and use
small diagnostic runs where appropriate. Record event-type counts, total fills,
rejected events, peak active orders, and peak occupied price levels. After
replay, require no rejection of supplied valid events and a positive, unique,
uncrossed canonical book. Do not call `inspect_book` after every event inside
primary timing because snapshot sorting and allocation would change the
measured workload.

Operation counts are interpreted together with `B`, `P`, `F`, and workload
mix. A one-dimensional event-count curve is not extrapolated without
controlling these other sources of work.

## Controlled stresses

### Submission flood

Process long uninterrupted workloads and record construction/replay behavior as
active depth grows. Compare early and late processing latency.

### Queue concentration

At a fixed initial order count, compare controlled books using approximately
four versus 1,000 available prices. Hold seed, side/quantity generation, and all
other settings as constant as the controlled generator permits. Record `B` and
`P` so conclusions do not rely on submitted count alone.

### Large liquidation

Construct a deterministic fresh bid book with total available quantity `Q`.
Independently test market sells requesting `ceil(0.10 * Q)` (at least one unit),
`Q`, and `2 * Q`. Rebuild the identical book for every repeat. Report book
construction/reset separately from the individual sale, and retain the sale's
returned fills during its memory measurement. Record requested, executed, and
unfilled quantity; makers touched; price levels visited; and fill count.

The fixed liquidation input has 1,000 individual bid makers distributed over
100 prices with a deterministic positive quantity cycle. Perform one untimed
warm-up and five measured repeats per sale size. The sale timer includes
matching, mutation, and fill-list construction. Separate `tracemalloc` sale
runs build the book before tracing, then retain the complete sale result while
reading current and peak Python-traced bytes; prebuilt-book allocations are
therefore explicitly excluded from those sale-memory numbers.

Small diagnostic replays use the five 1,000-event seed-42 core inputs. They
record event-type counts, fills, rejections, peak/final active orders and price
levels, plus final uniqueness, positive-quantity, and uncrossed-book checks.

## Saved records

Raw JSON records distinguish `throughput`, `latency`, `memory_state`,
`memory_retained_output`, and `diagnostic_counts`. As applicable, each record
contains:

- version, scenario, seed, event count, and price-level setting;
- phase, repeat, completion status, and stopped-run reason;
- preparation, construction/reset, replay, and total-application seconds;
- throughput and latency summaries;
- active-order and occupied-level peaks;
- requested, executed, and unfilled quantity plus fill count;
- current and peak traced bytes plus inclusion flags;
- generator settings and input checksum;
- Python, dependency, operating-system, machine, command, UTC, and code-version
  metadata.

Summaries are derived from raw records and never replace them. The dashboard
loads saved raw/summary results and never reruns an experiment when a view
changes.

Formal raw records are gzip-compressed JSON. Result files and timeout/failure
status files are separate. Environment metadata distinguishes changes to saved
outputs from changes to code, tests, methods, or configuration, so later tasks
do not appear to use modified code merely because earlier results exist.

The dashboard compares construction, replay, and individual-sale scaling for
both versions. It shows throughput, processing-latency distributions, memory
including post-cancellation state, correctness outcomes, workload settings,
raw repeats, units, and stopped or missing runs. At least one measured
bottleneck is explained using code, operation counts, and complexity. Version B
is not assumed to win every workload.

## Fairness and interpretation

Both versions receive the exact same inputs and use the same fresh-state rule,
warm-up count, repeat count, timer, instrumentation mode, and stopping limits.
Correctness failures invalidate the corresponding performance comparison. A
revision may improve one workload while losing time or memory on another; all
such trade-offs and stopped runs remain visible.

## Optional one-million-event extension

This extension was proposed only after the original Version A and Version B
114-task matrices had completed. It is therefore labelled post-hoc and is not
represented as part of the preregistered formal matrix.

The extension contains one seed-42 input for each of the five workload
families at `M = 1,000,000`, with 1,000 available prices. It measures
throughput only. Both versions receive the identical generated file, one
warm-up, five measured fresh-book repeats, and the same 60-second child-process
limit. A baseline timeout is retained as a stopped result, not replaced by an
estimate, and no speedup is computed when either version lacks a completed
timing.

Generated million-event JSONL files stay ignored. Their generator command,
settings, compressed byte count, and SHA-256 checksum are stored in a separate
input plan. Raw results and statuses live under `results/extension_1m/` so the
original 114-task result counts remain unchanged.
