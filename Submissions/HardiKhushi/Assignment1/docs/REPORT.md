# Sequential Bitcoin limit order book

## Specification and boundaries

This is a teaching model of one venue, processed sequentially. Prices are positive
integer cents per BTC, quantities positive integer 10^-8 BTC units, and sequence
numbers strictly increasing positive integers. All orders are eligible. There are
no fees, balances, hidden orders, self-trade prevention, delays or concurrency.
The synthetic submissions are neither historical nor calibrated exchange data.
This is not a production trading system.

A buy crosses the lowest ask at or below its limit; a sell crosses the highest bid
at or above its limit. Every execution uses the resting price and earlier arrival
at equal prices. A partial maker keeps its rank. Unfilled limits rest; unfilled
market sells are returned and discarded. Cancels remove only the remaining
quantity. Missing/filled/cancelled targets return `not_found`.

All validation runs before mutation or advancing `last_seq`. Invalid events,
including Boolean prices/quantities/sequence numbers, are rejected atomically.
Identifiers are nonempty strings. Duplicate *live submission* IDs are rejected,
including a market sell using a live ID. Global historical submission uniqueness
and unique event IDs are valid-input assumptions; historical IDs are not retained
just to validate reuse. A valid unknown cancellation does advance the sequence.
Missing fields receive a rejected result with a reason. Malformed JSON is an I/O
error, with a line number, rather than an engine event.

## Tests first and correctness evidence

The tests and supplied generator were present before either engine. The recorded
red run has 40 tests: three workload tests passed and 37 engine checks errored
because the modules were absent. `results/evidence/tests_before.json` records
that no engine Python file existed, the exit status, and SHA-256 test hashes.
Checkpoint `35125e8` precedes implementation. It is a real missing-code red run,
not a retroactive mutation demonstration.

Version A passed 21 applicable tests, with the revision comparison explicitly
skipped. Both versions subsequently passed 43 tests, including storage additions;
measurement-definition tests were added later. The original two test files and
their independently calculated expectations remain unchanged. The final counts
and independent second verification are recorded in `results/evidence/`.

Tests check exact ordered maker/taker fills, canonical identities and quantities,
integer proceeds, all required edge cases, invalid inputs without state changes,
and 400 makers at one price with a middle cancellation. A separate generated-sale
oracle sorts passive inputs and calculates expected fills independently. Fifteen
300-event generated streams (five families, three seeds) compare both results and
books **after every event** and check incoming, maker and cancellation conservation.
Agreement between engines is additional evidence, not a substitute for these
expected outcomes. Passing tests are not a formal proof.

For the worked six-BTC sale, makers b1/b2/b3/b4 fill 1/1/3/1 BTC. Four BTC remain
on b4; the two-BTC ask is unchanged. Proceeds are 3,594,000,000,000,000 tick-units,
or USD 359,400.00 after division by 10^10. No matching calculation uses floats.

## Algorithms and invariants

Version A (`orderbook/baseline.py`) stores a list of individual active orders.
It scans to reject a live duplicate, then repeatedly scans for the best eligible
opposite maker and removes exhausted entries from the list. This is deliberately
transparent and has no hidden library matching engine.

```text
process(event):
    validate the complete event without changing state
    if cancel: scan for target; remove its residual if active
    otherwise:
        while incoming remains:
            scan active orders for eligible best (price, original arrival)
            if none: break
            execute min(incoming, maker remaining) at maker price
            append fill; reduce both; remove exhausted maker
        append residual limit only; report market residual without storing it
    advance accepted sequence; return this event's result
```

Version B (`orderbook/revised.py`) has ascending occupied price lists on each
side, an `OrderedDict` FIFO queue per occupied price, and a live ID index. The
queue and index reference the same order object; each active identity belongs to
exactly one side/price queue. An index reference is not a second logical order.

```text
insert residual limit:
    create missing price queue; bisect and insert its price if needed
    append order to that queue and add its ID reference to the index
match:
    inspect minimum ask for buy, maximum bid for sell
    stop if no eligible price
    take first maker in that price queue; fill and update quantities
    remove exhausted maker from queue and ID index immediately
    remove empty price queue and its price immediately; repeat
cancel:
    find ID; unlink it from its queue and index
    remove empty queue/price; clear empty indexes to release capacity
```

Price lists contain exactly occupied prices. Queue insertion follows strictly
increasing accepted `seq`; partial fills do not unlink/reappend a maker. Therefore
the selected price and first queue order give price-time priority. Every fill
subtracts the identical positive minimum from incoming and maker quantities;
an exhausted maker is deleted and a positive residual limit is inserted once.
Cancellation removes precisely its current residual. These steps preserve
quantity conservation, positive resting quantities and unique queue membership.
Matching ends when opposite prices no longer cross, so resting bids and asks
cannot cross after a valid event. Rejection precedes all of these mutations.

## Runtime and space reasoning

Let B be active orders before an event, P occupied prices, F maker fills in that
event, L price levels exhausted, and M submitted events. These are different:
in alternating cancellation churn M grows while B is at most one. Hash operations
below have expected/amortized costs and assume bounded identifier/integer sizes;
Python integers and strings have their own size-dependent costs.

| Operation | A: list | B: queues/index/sorted prices |
| --- | --- | --- |
| Validate a submission | O(B) live-ID scan | Expected O(1) live-ID lookup |
| Passive limit, existing price | O(B), including validation/matching scans | Expected/amortized O(1) |
| Add a new occupied price | O(B) overall | O(log P) search plus O(P) array shifts |
| Cancel | O(B) scan and list shifts | Expected O(1) if queue survives; O(P) if deleting a price |
| Market sell | O((F+1)B), including scans/removals | Conservative O(F + L P + log P) plus validation/output; see qualification below |
| Inspect canonical book | O(B log B) time; O(B) new storage | O(B log B) time; O(B) new storage |

For Version B a market sell exhausts *highest bids*, so the price-array deletion
is at its end: absent occasional array resizing/cleanup, the tighter amortized
bound is O(1 + F + L log P), including binary searches and F output records.
Crossing buys can delete the first ask price and shift the array, so general
limit matching uses the conservative O(F + L P), plus any new-price insertion.
These claims include index/queue updates and fill construction. Array resizing,
hash-table rehashing and empty-index `clear()` are occasional cleanup costs;
an individual last deletion can release capacity reflecting a larger historical
book. Constant expected hash lookup is not a deterministic worst-case guarantee.

Version A has O(B) live storage and O(F) returned fills. Version B has O(B+P)
logical live storage for orders, references, queues and prices, plus O(F) output.
Neither retains the stream, all submissions, or trade history. There are no
inactive tombstones. Python dictionary/OrderedDict allocated capacity and the
allocator may reflect a historical peak while a container remains nonempty;
logical O(B+P) is not a promise that current traced bytes shrink after each delete.
Empty queues disappear and empty ID/side maps are cleared, so alternating
add/cancel does not accumulate entries. Check the measured churn checkpoints.
Preloaded input storage is O(M) and is explicitly outside traced engine memory.

## Experimental protocol

The primary matrix is M=1,000/10,000/100,000, seeds 42/43/44, five families and
both versions. Generator inputs are created outside timing, with checksums and
exact commands in `results/inputs.json`; generated files are ignored by Git.
Passive prices use 1,000 available prices per side; crowded uses four. Engine
replay starts from an empty book every trial with the same preloaded events.
Results are saved in `measurements.jsonl`, not copied from the previous search lab.

`time.perf_counter` measures one full warmup (repeat 0) and five raw repeats.
Successful timing summaries use only repeats 1..5; partial groups retain their
actual count and are not labelled complete five-repeat results. Replay includes
engine creation, validation, matching, updates and last-result construction. It
excludes JSON/gzip parsing, counters, tracing, reporting, and destruction of the
returned final book after the timed call. Input read/decompression/JSON parsing
has its own five-repeat phase. Streamed application timing includes parsing and
the engine, for seed 42. Construction is measured independently on passive
buildup/crowded streams and the first 80% of sweep. Its event_count identifies
the parent stream; sweep construction actually processes floor(0.8 M) events.

Fixed bid books use B=1,000/10,000/100,000, seed 42, and 4 versus 1,000 available
prices. The identical book is independently rebuilt before each 10/100/200%
liquidation, warmup and repeat; 10% rounds up to at least one integer unit.
Reset/construction is timed separately. Sell timing includes matching, mutations
and ordered fill-list creation. Saved outcomes include requested quantity,
makers touched, filled prices, fill count, residual and integer proceeds.
All five sale repeats must conserve the independently known initial quantity.

All phases have the same four-second **per-trial** wall deadline for both
versions. A stopped warmup prevents repetitions of that phase; no missing
samples are invented. Other phases are still independently attempted. Traced
engine allocation has a 256 MiB budget checked every 1,000 events in separate
memory runs. There is no hard process-RSS cap. Preloading is limited to 200,000
events. A one-million-event cancel-churn feasibility experiment streams input,
with separate parsing and application timing and the same deadline. It is not
presented as engine-only timing. The other million-event families are explicitly
not attempted within this declared memory/experiment scope.

Depth peaks and output fingerprints are measured in separate diagnostic replays.
The baseline is compared when its diagnostic completes; timeouts are not labelled
correctness failures or passes. Small M=1,000 runs record work counters separately.
Counter fields that say `upper_bound` are deliberately upper bounds, not exact
early-exit counts. Matching scans and shifted-entry counts explain actual work.

Per-event latency runs have engine instrumentation disabled, timer reads around
each process call, and buffered samples written only after the replay. They cover
all M<=10,000 cases plus 100,000-event buildup/churn at seed 42. The main replay
timer has no per-event timers. Nearest-rank percentiles sort n samples and select
ceil(p*n)-1 without interpolation. Histograms and percentiles can be regenerated
from `latency_raw.csv.gz`. Early/late mean the first/last 10% of the full batch;
a stopped prefix has no late statistic. Sampling/timer overhead and scheduler
noise still affect these diagnostic observations. They measure algorithm
processing, not network/queueing latency or overload capacity. Throughput is
M divided by replay seconds; its reciprocal is not a tail-latency estimate.

Memory is one separate tracemalloc replay per configuration. Inputs are already
allocated before tracing; retained engine state, transient Python allocations,
the current result/fills and small checkpoint records are included. The result
stays alive at the reading. Checkpoints at 1/10%/50%/100% track growth and
post-churn bytes, active/stored orders, prices and stale entries. These values
are not total process/native memory or theoretical auxiliary space. Stopped
allocation runs do not produce a completed-memory result.

## Results, profiling and revision

The executed matrix contains 90 primary configurations and 48 stopped timed
trials across all phases. In 33 complete paired replay configurations, B was
faster in 24 and slower in all nine churn cases. The median baseline/B ratio is
26.15 across these pairs; censoring excludes the largest slow-baseline cases.
At 100,000 buildup events, seed 42, B's replay median is 0.098105 s; A's warmup
stopped at the four-second deadline. In the million-event streaming churn
experiment, five-repeat application medians are 1.508710 s (A), 1.610197 s (B),
with separate streamed parsing median 0.822022 s. These include different
measurement boundaries and must not be compared as engine-only timings.

At M=1,000 buildup seed 42, A counted 499,500 matching-list entries scanned plus
499,500 live-ID scan upper-bound entries, with zero fills. B counted 1,000 ID
lookups, 995 best-price reads and 77,049 price-array entries shifted. Churn ended
with zero active/stored/stale entries at all measured sizes; seed-42 current
traced allocation at 100,000 events was 1,728 bytes (A), 1,896 bytes (B).

See `results/FINDINGS.md` for conclusions calculated from this machine's saved
raw measurements, including actual stop counts and paired timing comparisons.
The dashboard shows those measurements without replaying events. The growth
mechanism follows the source: each passive insertion in A performs a live-ID scan
and an opposite-maker scan over a growing list. M passive submissions therefore
accumulate quadratic scan work even though F=0. Small diagnostic operation counts
measure these scans. B replaces them with a hash lookup and constant-time best
price inspection, paying price-list maintenance only when P changes. This is
operation-count profiling; no function profiler is claimed.

Queue concentration holds B fixed while varying available prices. Longer queues
and fewer price insertions can change relative costs. Cancellation churn keeps
B tiny; the baseline can be competitive, and the revised queues/index have
overhead. Observed regressions and stopped trials must remain visible. No revised
version is assumed to win universally. Exact ratios belong to this machine,
interpreter, workload, clock resolution and allocator behavior, not an exchange.

The source snapshot includes engine commit `3276644` plus SHA-256 fingerprints
of the actual benchmark harness and tests in `results/environment.json`; the
harness was uncommitted while measurements ran. Later documentation/dashboard
commits do not retroactively become measurement source versions. All accepted,
corrected and rejected AI suggestions are recorded in `AI/DECISIONS.md`.

## Limitations and reproducibility

This is one machine, with sequential configuration order, no randomized order,
CPU pinning, confidence intervals or control of unrelated OS activity. Deadline
censoring means large baseline medians may be absent; do not extrapolate missing
values. The revised sorted-price representation is suited to the bounded P in
these workloads, not a universal best organization. The million-event trial is
one workload/seed and includes parsing. Memory uses Python tracing, not RSS.
The initial PDF review used extracted text rather than rendered layout, because
Poppler was unavailable; preserved source PDF and README define the requirements.
The student must review and understand the AI-assisted submission. Clean staged
or committed-export verification is local and does not establish reproducibility
on another operating system or a remote fresh clone. Docker and peer audit are
optional/not required here; neither is claimed.
