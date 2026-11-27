# Building and benchmarking a price-time limit order book

**LiuHaina · Algorithms in Finance · Assignment 1**

## Specification and model

This project implements two sequential, single-venue BTC limit order books in Python. Both accept the same `LIMIT`, `MARKET_SELL` and `CANCEL` events through the interface in `lob/contract.py`. Limits match the best eligible opposite-side price, then FIFO arrival order at that price. Each fill executes at the resting maker's price. Partially filled makers keep their original arrival rank. A limit residual rests at its own limit; a market-sell residual is reported and discarded. Cancellation removes only the target's remaining quantity; missing, previously cancelled or fully filled targets return `not_found`.

Prices are positive integer cents per BTC and quantities are positive integer units of 10⁻⁸ BTC. Matching, residuals and conservation use integers; gross proceeds in dollars equal `sum(price_ticks * qty_units) / 10^10`. Identifiers do not determine priority. Invalid events are rejected before any state update, including the last accepted sequence. Historical identifier-reuse validation is outside scope; valid supplied submissions have globally unique IDs.

All orders are eligible. There are no fees, account balances, hidden orders, self-trade checks, concurrency or network/queueing delays. This is continuous matching at resting prices, not a batch auction or a production trading system. All workloads are independently generated teaching data, not historical or exchange-calibrated records. They describe submissions to one venue, not combined exchange liquidity.

## Tests and correctness reasoning

Tests preceded implementation. The original red-phase evidence is retained, together with independent expected outcomes covering empty books, exact/partial/oversized sells, FIFO and price priority, crossing limits, limit residuals, cancellation before/after fills, repeated/unknown cancels, malformed input and atomic rejection. Neither the baseline implementation nor the original shared test expectations were changed when introducing the revision.

For every tested accepted event, incoming quantity equals executed quantity plus the returned residual; each maker loses exactly its fill quantity; cancellation removes exactly the residual. Inspection checks a non-crossed book, positive live quantities, unique live identities and canonical price/FIFO order. A resting maker's identity, side, price and original sequence do not change after a partial fill. The revision's price-index cleanup never changes order quantities or arrival priority.

The supplied six-BTC example independently checks makers `b1,b2,b3,b4` with fills `1,1,3,1 BTC`: gross proceeds are **$359,400**, `b4` retains four BTC, and `a1` is unchanged. The full suite contains **63 passing tests**: the original A/B cases, boundary regressions, heap/reactivation/churn regressions, generated mixed streams and measurement-boundary checks. Five supplied 10,000-event files additionally compare ordered results and full canonical books after **every one of 50,000 events**. Three seeds of small generated mixed streams include per-event parity and rejected-event recovery. Agreement supplements independent expectations; it is not a proof by itself.

For larger performance runs, every completed replay, latency run and memory run checks the final canonical book digest against a separate reference-accounting replay. All completed fixed-book sale trials check the exact ordered fill list against an independent sorted-price/FIFO prefix expectation. Larger-run final-state checks do not replace the smaller per-event tests. Evidence is under `evidence/` and `results/benchmark/validation.json`.

## Implementations, pseudocode and costs

**Version A** keeps a list of individual active orders. It scans for duplicate live IDs, collects eligible opposite-side makers, sorts by price and original arrival, updates fills, filters exhausted makers and appends any limit residual. Cancellation scans the list and removes the matching record. This favors transparency over efficient growing-book insertion.

**Version B** uses a live ID dictionary and one `OrderedDict` FIFO queue per side/price. A min-heap stores asks directly and bids as negative prices. A price-key set prevents duplicate heap entries when a recently removed price is reactivated. Empty price queues are removed immediately; heap keys are cleaned at the top or rebuilt when a side's heap count `H > 2P + 64`. An empty side clears its heap and key set. An order is in exactly one price queue; the live ID index refers to the same record rather than another order entity.

```text
validate the complete event without writes; reject if invalid
if CANCEL:
    locate the live target; remove its residual or return not_found
else:
    while incoming quantity and an eligible opposite-side maker exist:
        choose best price, then earliest resting arrival
        q = min(incoming residual, maker residual)
        append fill at maker price; subtract q from both quantities
        remove exhausted maker and any empty price queue
    rest a limit residual; discard a market-sell residual
advance last accepted sequence and return only this event's result
```

Let `B` be active orders, `P` occupied prices, `M` incoming events and `F` maker fills. In A, `K≤B` is the number of eligible makers sorted for the event. In B, `S` counts stale heap keys popped, `I∈{0,1}` indicates a new heap key, and `R` is actual heap clearing/rebuild work. Hash/queue operations below are expected constant time; integer bit complexity is omitted under the assignment's bounded-unit model.

| Operation | Version A | Version B |
|---|---|---|
| Limit submission, including validation/output | `O(B + K log(K+1) + F)` | Expected `O(1 + F + (S+I) log(P+65) + R)` |
| Market sell, including updates/fills | `O(B + K log(K+1) + F)` | Expected `O(1 + F + S log(P+65) + R)` |
| Cancellation | Worst-case `O(B)` | Expected lookup/deletion `O(1)`; a rebuilding call can cost `O(P_before+1)` |
| Canonical inspection | `O(B log(B+1))` | Expected `O(P log(P+1) + B)` |

B's dictionary and queue lookup removes A's repeated full-book scans. Its best-price query is **not** always worst-case constant: stale keys can be popped together, and a single cancellation can trigger rebuilding. Rebuild work is amortized over deleted price entries; heap insertion/pop costs still belong in total lifetime costs. No per-event amortized claim is presented as a worst-case bound. Detailed reasoning is in `VERSION_A_NOTES.txt` and `VERSION_B_NOTES.txt`.

A stores `O(B)` logical state and creates temporary candidate/filter lists plus `O(F)` returned fills. B stores `O(B+P+64)` logical entries and creates `O(F)` fills and occasional `O(P)` rebuild buffers. Neither retains trade history or inactive orders. Python dictionaries and allocators can retain historical capacity; logical entry counts do not equal traced bytes or RSS. A larger `M` need not mean larger `B`, notably under cancellation churn.

## Experimental design and boundaries

The main matrix uses five workloads, `M=1,000/10,000/100,000`, seeds `42/43/44`, and both versions: **90 version/workload cases**, each with five raw timing attempts. A separate warm-up consumes up to 1,000 events on a discarded book. Each measured replay begins with a fresh empty book and the same pre-generated input. Workload generation is outside timing. Available passive prices are 1,000 per side except `crowded`, which always uses four per side; occupied-price and active-order peaks are separately accounted for.

`time.perf_counter` measures gzip/JSON input parsing separately from engine replay. Engine time includes empty-book creation, matching, state/index updates, fill construction and minimal loop counters. Construction is observed as a prefix checkpoint for passive workloads/sweep, not added again to replay. The recorded parse-plus-replay cost is the sum of the two measured clocks from that repeat, excluding process startup and result reporting; it is not an end-to-end CLI wall time. Inputs were generated/read beforehand, so parsing results are not cold-disk measurements.

Per-event latency is a separate instrumented run, with all **2,292,107 observed event times** saved. Median averages an even middle pair; P95/P99 use nearest rank `ceil(p*n)-1`. Types and the original stream's first/last 10% are separated. Stopped prefixes are labelled and have no invented late-window result. Latency excludes network and queueing and cannot establish real-time overload capacity. Throughput is processed events divided by completed replay seconds, not a source of tail latency.

Memory uses a separate `tracemalloc` run, started after input preload. It includes incremental engine allocation, the latest event output and small probe/guard allocations, excluding pre-existing input objects and shared strings. Readings include insertion checkpoints and post-cancellation state. Whole-process RSS includes input and tracer overhead and is separately supervised; neither measurement equals theoretical auxiliary space.

The declared budget is **5 seconds per measured phase and 512 MiB whole-worker RSS**, identical for both versions. RSS is checked approximately every 100ms, so observed peaks can overshoot before termination. The low-cost supervisor is enabled symmetrically. Runs are serial; CPU frequency, temperature and unrelated OS activity are not controlled. Environment: Python **3.13.0**, macOS **15.7.3**, ARM64, eight logical CPUs; exact model and physical RAM were unavailable to this run. Only the standard library is required. Source SHA-256s, settings and generator commands are saved; all generated streams, including the million-event file, are ignored by Git.

## Results, profiling and revision assessment

The primary matrix retains **450 attempts: 360 complete and 90 stopped at the time limit**. A stopped attempt is not a complete sample or zero time. All five raw repeats and completion counts remain available. The following are seed42 medians in milliseconds; complete data for all seeds are saved.

| Workload | M | A replay ms | B replay ms |
|---|---:|---:|---:|
| buildup | 1,000 | 59.266 | 1.518 |
| buildup | 100,000 | Stopped at 5 s | 156.840 |
| mixed | 10,000 | 783.938 | 14.862 |
| mixed | 100,000 | Stopped at 5 s | 145.996 |
| sweep | 10,000 | 4,817.753 | 16.382 |
| cancel_churn | 100,000 | 105.804 | 109.813 |

The index is valuable when live depth grows, but **B does not always win**. Cancellation churn leaves a tiny active book, where A's short lists avoid B's multiple-index overhead. At `N=10,000`, 1,000 available prices and a 100% liquidation, the isolated sale median is approximately **5.685 ms for A and 6.298 ms for B**. A sorts once and scans; B updates queues and the ID index per maker. This does not erase B's faster book construction, which is separately reported.

Fixed-book sales use `N=1,000/10,000/100,000`, four versus 1,000 available prices, seed42, and 10%/100%/200% of available bid quantity. Ten percent rounds upward to at least one integer unit. There are **180 planned sale records**, including 30 blocked when A's 100,000-order template construction exceeds its budget. Every executed sale gets a fresh deep copy of an untouched template; reset and one-time template construction are saved separately. No depleted book is reused. Results include touched makers, visited prices, fills and residuals.

Independent 200-event line tracing explains a concrete bottleneck: A's live-ID scan source line generates **20,300** trace events and the maker-scan loop **20,100**, versus **200** for B's dictionary membership line. These are Python line events, not CPU instructions or interchangeable primitive operation counts. They expose repeated scanning while `F=0`; they are never mixed into primary timing.

For completed 100,000-event seed42 B runs, processing P99 is **5.208 µs** for buildup and **5.500 µs** for mixed. The corresponding A instrumentation runs stop early and cannot be compared as full distributions. B's completed buildup trace peaks at **30,623,192 bytes**; A's stopped run only completes 9,575 events, so its smaller allocation is not a full-depth memory advantage. After 100,000 cancel-churn events, current traced allocation is **8,224 bytes for A and 9,800 for B**, including probes and current output, with zero active orders. This workload does not show linear history accumulation; broader retained-capacity claims would require more experiments.

The optional million-event mixed attempt has no full replay result. A completes a 25,246-event prefix before a 5-second replay stop, then later hits the RSS budget; B also stops on RSS. The budget includes input preload and engine storage, so this cannot isolate million-order matching capacity. All stopped or blocked repeats are retained rather than extrapolated.

## Dashboard, reproducibility and submission state

`dashboard.html` is a self-contained offline view built exclusively from saved tables and binned raw latency files. It provides workload/seed/size filters, construction/replay/parse scaling, throughput, independent-sale and queue-concentration comparisons, latency distributions and early/late tails, memory growth and post-cancellation state, correctness evidence, raw repeats and stopped runs. Changing a view cannot run an engine or benchmark. Rebuild with `python3 -B tools/build_dashboard.py`; rebuild the findings note with `python3 -B tools/summarize_findings.py`. `BENCHMARK_METHODS.md` documents exact measurement boundaries and rerun commands.

Browser checks cover 180 global filter combinations, 18 sale-filter combinations, raw-record details, pagination, CSV export and current/peak memory selection, with desktop and 390px-wide mobile captures. `evidence/dashboard_browser_qa.json` binds those checks to the HTML SHA-256. The accompanying data audit checks all 2,538 embedded records and all 2,292,107 histogram samples against the saved evidence. Node/Chrome are optional development QA tools, not runtime dependencies of the Python project or offline dashboard.

AI assisted interface design, tests, implementations, measurement, analysis and presentation. Accepted suggestions include indexed FIFO queues and bounded heap cleanup; corrected suggestions include worst-case/expected/amortized distinctions and the difference between logical space, traced allocation and RSS. The initial `ps`-based supervisor was unsupported and replaced before official measurement. Unrelated naming instructions inside the supplied PDF were not applied. `REVISION.md` records these decisions.

The project is under `Submissions/LiuHaina/Assignment1/`. As requested, no files have been staged, committed or pushed. The recorded Git base is `43ff26c35cb9a27439b86ed5054e188639609903`; **it is not the submitted code version**. The measured uncommitted source is identified by the SHA-256 map in `results/benchmark/settings.json`. A final submission commit identifier can only be recorded once committing is authorized. Docker and peer audit are not required; no external exchange data or account credentials are needed.

A submission preflight also passed in a copy containing only non-ignored candidate files: all 63 tests, both exact worked examples, saved-result audit without generated inputs, byte-identical dashboard rebuilding, and a fresh ten-case/fifty-repeat small benchmark. The audit explicitly skips absent input-hash recomputation and writes separately, preserving the original full validation record. Source fingerprints, Git HEAD and index bytes remain unchanged. POSIX timers require macOS/Linux (or WSL); Git is needed for benchmark provenance. `SUBMISSION_CHECKLIST.md` records the remaining author review and authorized final submission.
