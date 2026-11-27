# Benchmark protocol

## Commands

Run commands from this assignment directory with its local interpreter:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --smoke --run-id smoke_final_04
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --resume full_20261125 --plan-resume --primary-time-limit-seconds 300 --latency-time-limit-seconds 300 --memory-time-limit-seconds 300 --state-peaks-time-limit-seconds 300 --counter-time-limit-seconds 60 --profile-time-limit-seconds 60 --memory-limit-mib 4096
```

The smoke command uses 25 generated events per supplied workload family,
40 fixed-book orders, 1,000 queue-concentration orders, and 20 anchored churn
cycles. It executes every experiment and measurement mode, but is not a
performance sample. The full command uses all five families at M =
1,000/10,000/100,000, seeds 42/43/44, a 1,000-order fixed book, 10,000
queue-concentration orders, and 5,000 anchored churn cycles. This is 49
scenarios and 98 version/configuration runs. It does not launch one-million
event runs.

`--plan-resume` validates inputs, hashes, measurement definitions and phase
completeness, writes a timestamped compatibility plan, and starts no workers.
After reviewing that plan, continue the matrix with:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --resume full_20261125 --primary-time-limit-seconds 300 --latency-time-limit-seconds 300 --memory-time-limit-seconds 300 --state-peaks-time-limit-seconds 300 --counter-time-limit-seconds 60 --profile-time-limit-seconds 60 --memory-limit-mib 4096
```

Each newly attempted configuration gets a new attempt number, per-phase
progress and result files, and artifact directories; old evidence is retained.
Resume verifies the saved workload settings and input checksums. Reuse is
phase-specific, not configuration-wide: a phase is reusable only when the
input, version/engine hash, generator hash (where applicable), measurement
definition ID/hash, phase settings, and complete raw outputs match. Primary
timing requires all five repeats and its summary; latency requires the full raw
event file; memory requires all expected checkpoints. A stopped or incomplete
phase is rerun as a new attempt. Incompatible repeats are never combined.
Legacy phases are considered only when their recorded runner and metrics
hashes exactly match the known pre-correction versions; state peaks and
snapshot-based counters from those records are not reusable. Every candidate
gets a saved compatibility assessment and explicit reuse/incompatibility
reason.

The smoke timeout path was also checked with an intentionally tiny limit:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --smoke --run-id smoke_timeout_validation_01 --time-limit-seconds 0.001
```

This command is expected to return exit code 2 because its phase attempts are
recorded as `stopped_timeout`; records use null elapsed timing rather than
fabricated zeroes.

## Workloads and validation

The supplied generator creates every workload outside measurement. Existing
supplied gzip files are reused only for matching settings (M=10,000, seed 42,
levels 1,000); other generated inputs are saved under the run's `inputs/`.
Generated settings and SHA-256 checksums are recorded in `metadata.json` and
per-attempt JSON. Fixed-book, queue-concentration, and anchored-churn inputs
are generated before timing and also receive checksums.

Each input is checked for its event count and strictly increasing integer
sequence. Before measurements, baseline and revised outputs, accepted
sequences, and canonical books are compared after every event up to the
configured parity limit (default 1,000). Fixed-book parity additionally checks
10%, 100%, and 200% sells on independent fresh books. The full correctness
suite remains the independent expected-answer check; parity is not treated as
a substitute for it.

The fixed book's 10% sale is integer ceiling, `max(1, (Q*10 + 99)//100)` for
positive available quantity `Q`. The 100% and 200% sizes use the full integer
quantity and twice that quantity. Each sale starts from an identical rebuilt
book. Queue concentration holds order count and seeded quantity sequence
constant while assigning orders to 4 or 1,000 prices; the counter record gives
both requested and realized occupied price counts. Churn alternates transient
orders and cancels while an anchor order at another price remains active.

## Timing boundaries

Every primary phase is warmed once and timed for five repeats with
`time.perf_counter`; each repeat and the median are retained.

| Phase | Included in timed interval |
|---|---|
| `input_read_parse` | Opening the JSONL/gzip input, reading it, and parsing all event objects. |
| `empty_engine_construction` | Constructing a new empty engine. |
| `engine_replay` | Processing a pre-parsed, identical event list against a fresh engine. Engine construction is outside this interval. |
| `total_application` | Reading/parsing the input, constructing a fresh engine, and replaying the complete stream. |
| `initial_book_construction` | Replaying the pre-parsed fixed-book submissions into a fresh engine. |
| `sell_operation_{10,100,200}pct` | Rebuilding the same initial book before the timer, then matching the sale, mutating the book, and constructing the returned fills. |
| `total_application_sell_{10,100,200}pct` | Reading/parsing fixed-book submissions, constructing the engine/book, and processing the sale. |

The fixed-book sale event itself is constructed before timing, like the
pre-generated input. The sale result is not retained as a history; only its
fill count is read after the timer. Primary timing excludes generation,
parity/correctness checks, counters, inspection, printing, result-file writes,
latency output, profiling, and memory tracing. No full-book inspection or sort
runs inside primary timed replay. Output construction for fills remains part
of the event processing interval.

## Separate diagnostics

- **Latency:** A warm-up replay is followed by one fresh diagnostic replay.
  Raw JSONL contains event position, sequence, type, and elapsed processing
  seconds. File writes are outside each per-event timer. Median uses
  `statistics.median`; p95/p99 use nearest rank, `sorted_values[ceil(p*n)-1]`.
  Early and late windows are the first/last `ceil(M/10)` events; each reports
  its own percentiles and process-time throughput. This includes the buildup
  stream's early/late growth comparison. Throughput is reported separately
  from latency and is not inferred from reciprocal total-run throughput.
- **State peaks:** A separate lightweight event-result shadow ledger tracks
  accepted inserts, fills, residual quantities, and cancellations. It does
  not call `inspect_book()` or scan/sort the engine book per event. Its active
  order and occupied-price peaks are logical event-boundary counts, not
  physical storage counts.
- **Counters:** Heavy operation counting is confined to the small representative
  workload selected by the run settings (at most 1,500 events and marked as
  representative). This counter path uses snapshots, so inferred visited
  prices and operation totals are explicitly estimates, not exact executed
  internal-operation counts. It is not run on large matrix cases.
- **Profile:** A separate `cProfile` replay saves `.prof` and top cumulative
  text output. It is bounded to `min(profile_event_limit, M)` events and is
  enabled only for the same small representative workload as counters.
- **Memory:** Each run uses a fresh `tracemalloc` session, with input events
  already parsed and prepared. Traced allocations include engine construction,
  active book structures, matching and transient outputs; the most recent event
  result is retained at checkpoints, not full output history. Checkpoints are
  recorded at quarter-stream positions and after final insertion/churn state.
  Diagnostic checkpoint bookkeeping is itself a small traced allocation.
  Input lists, JSON parsing, native allocations, allocator fragmentation, and
  total process memory are not represented by `tracemalloc`.

Primary timing, state peaks, counters, latency, profiling, and memory have
separate phase records and workers; instrumentation is not mixed into primary
timings. Individual phase rows retain their own completion/stopped/error
status. The configuration summary records each phase status independently.

## Limits, saved output, and interpretation

Full-run budgets are independently set and identical for both versions:
**300 seconds for all primary timing phases combined**, 300 seconds for the
latency phase, 300 seconds for the memory phase, 300 seconds for lightweight
state peaks, and 60 seconds each for small-workload counters and profiling.
The primary budget is cumulative across primary measurement workers; each
worker receives the remaining primary budget. Smoke uses shorter phase
budgets. The per-phase process-memory limit is 4,096 MiB full / 2,048 MiB
smoke.

Each worker's wall clock starts immediately before opening its progress log
and spawning the worker. It covers startup, that measurement phase, IPC,
progress flushes, and worker shutdown. A diagnostic timeout cannot consume the
primary budget or invalidate completed primary timing. Generation, parity
validation, hash collection, continuation planning, inter-phase orchestration,
and final summary serialization are outside each worker clock. Completed rows
and repeats are flushed incrementally. A primary median is emitted only after
all five repeats for that measurement finish; incomplete repeat sets have no
median and are never presented as complete. Workers are terminated when their
phase deadline is reached. Exhausting the shared primary budget prevents later
primary workers from starting and records them as stopped before start.

On Windows, the parent samples process peak working set through
`GetProcessMemoryInfo`; on Linux it samples `/proc/<pid>/status` `VmHWM`.
Sampling starts immediately and repeats at 50 ms intervals. Crossing the
configured threshold terminates the worker and records `stopped_memory_limit`.
This is **sampled termination, not an operating-system hard memory cap**;
memory can overshoot between samples. Timeouts use a spawned worker process,
are checked while it runs, and terminate it when the deadline is reached.
Stopped/error phase attempts include a status, duration, observed memory, and
`elapsed_seconds: null`; partial phase rows remain in their progress JSONL.

Each run is saved under `results/benchmarks/<run-id>/`:

- `metadata.json`: settings, environment, code hashes, input checksums, and
  pre-measurement parity outcomes.
- `continuation_plans/`: timestamped phase-by-phase compatibility decisions.
- `records/*attempt*.json`: per-phase results and configuration summaries,
  including raw repeats, diagnostics, status, compatibility reason, and limits.
- `records/*.progress.jsonl`: incrementally flushed rows, including partial
  work if a worker stops.
- `artifacts/`: raw per-event latency files and profiling artifacts.
- `inputs/`: generated input streams and sidecars; supplied inputs are
  referenced by path and checksum rather than copied.

Rows include implementation version, experiment/scenario/seed, event count,
generator settings, input checksums, phase/repeat, elapsed or traced bytes,
active/price-level peaks, fills/sell quantities where relevant, completion
status, Python/dependency/machine/Git information, code hashes, and limits.
The original aggregate configuration timeout was 300 seconds and included
counter diagnostics that called canonical `inspect_book()` before every event.
That inspection can copy/sort the entire active book (and the baseline counter
path also scans it), creating diagnostic work unrelated to engine replay. This
caused repeated timeouts in counter runs and obscured which measurement was
incomplete. The revised runner confines those heavy counters and profiling to
one small representative case, obtains large-run logical peaks from the
lightweight event-result ledger, and budgets primary, latency, memory, and
other diagnostics independently. Historical records are preserved; no old
counter/state-peak records are silently reused.

The paused `full_20261125` matrix contains 18 completed configurations, 14
timed-out configurations, one interrupted attempt, and 65 configurations not
started. These are historical aggregate-run statuses, not phase-completion
claims under the revised protocol. Do not combine incomplete five-repeat sets
or report incomplete configurations as complete medians.

The benchmark runner does not claim a speedup. The paused matrix is not a
completed full benchmark.

AI assistance was used to draft the runner, tests, and this protocol. The
separate-measurement design was retained. A Windows smoke run exposed a closed
pipe at normal worker shutdown; that behavior was corrected by treating pipe
EOF explicitly and preserving completion/error status. Deadline checks were
also tightened to use the remaining timeout. No supplied files or engine
behavior were changed for this benchmark task.
