# Technical Report: Limit Order Book Implementation and Benchmarking

## Executive Summary

This project implements a sequential, single-venue limit order book with limit buys, limit sells, market sells, cancellations, maker-price execution, and FIFO priority within each price. Two independent implementations expose the same public interface. Version A is an audit-friendly baseline that stores active orders in one list and repeatedly scans and sorts it. Version B indexes active orders by identifier, groups them into FIFO price levels, and uses side-specific heaps to find the best price.

Correctness evidence comprises 51 deterministic and fixed-seed tests with zero failures, errors, or skips; the instructor's worked example; 15,000 event-by-event differential transitions over pre-generated streams; optimized-storage invariant tests; and isolated mutation checks. This is strong finite evidence, not a formal proof.

The main timing evidence is the warmed-primary experiment in `07_results/stage4e/warmed_primary.jsonl`. It covers five workload families, three sizes, three seeds, two engines, and five planned repetitions: 450 records across 90 configurations. Of these, 392 completed, 12 timed out, and 46 were explicitly skipped after a timeout. Version B substantially reduced replay time when the active book grew: for seed 42 at 10,000 events, the measured Version A/Version B speedups were 131.90x for buildup, 155.15x for crowded, 19.83x for mixed, and 114.84x for sweep. These values are workload-specific. Cancellation churn was a counterexample: Version A was faster at all three seed-42 sizes because the active book stayed near one order and Version B still paid indexing and heap-maintenance overhead.

Version B also used more traced Python memory on the 10,000-event buildup stream (2.305 MiB peak versus 0.851 MiB), illustrating the time-space trade-off. For liquidation, Version B constructed the starting book much faster, but Version A's direct sale operation was faster at 100% and 200% depth. The revision therefore improves the workloads it was designed for without dominating every operation.

All numerical claims below are derived from `07_results/processed/aggregated_results.json`, whose sources are integrity-checked by `07_results/results_manifest.json`. Warmed primary, supplementary cold-primary evidence, instrumented Stage 4E measurements, parsing measurements, and pilot evidence are kept analytically separate.

## 1. Problem and System Design

The book receives three event types:

- `LIMIT`: a buy crosses asks at or below its limit; a sell crosses bids at or above its limit. Any residual rests.
- `MARKET_SELL`: consumes bids from highest price downward and discards any unfilled residual.
- `CANCEL`: removes the entire remaining quantity of an active target, or returns `not_found`.

Prices are positive integer cents (`price_ticks`); quantities are positive integer units of 0.00000001 BTC (`qty_units`). Integer arithmetic supports exact conservation checks. Each accepted event has a positive, strictly increasing sequence number. Execution uses the resting maker's price. At equal prices, the earlier resting arrival sequence has priority, and a partially filled maker keeps that priority.

Both engines expose `process_event`, `AddLimitOrder`, `CancelOrder`, `FillMarketSell`, `canonical_snapshot`, and `last_accepted_seq`. Fill results contain maker and taker identifiers, price, and quantity in execution order. Snapshots list each active order separately in deterministic price-time order.

Shared `validation.py` performs only state-independent checks: event shape, required fields, exact integer types (therefore rejecting booleans), positive price and quantity, valid type and side, and nonempty string identifiers. Each engine independently checks its accepted sequence and duplicate live identifiers before mutation. A rejected event changes neither the book nor the last accepted sequence. An unknown cancellation is valid, returns zero cancelled quantity, and advances the accepted sequence.

The main invariants are:

1. Every active order has positive remaining quantity and appears once in engine state.
2. Resting bids and asks are not crossed after an accepted event.
3. Makers execute by best price and then original arrival sequence.
4. For a submission, incoming quantity equals executed quantity plus returned residual; only a limit residual may rest.
5. A maker loses exactly its executed quantity; cancellation removes exactly the recorded residual.
6. Execution prices are maker prices, and proceeds equal the integer sum of `price_ticks * qty_units`.

The model deliberately excludes fees, balances, hidden liquidity, self-trade prevention, networking, simultaneous events, and multiple venues. The synthetic streams are teaching data rather than calibrated exchange history. The implementation is not a production trading system.

## 2. Baseline and Revised Implementation

### 2.1 Version A: active-order list

`BaselineOrderBook` stores every active order in `_orders`, a Python list. Duplicate detection and cancellation scan this list. A limit order filters all eligible opposite-side makers and sorts those references by price and arrival sequence. A market sell similarly collects all bids and sorts by decreasing price then arrival. Matching updates maker quantities in place; a final list comprehension removes exhausted makers. A residual limit is appended with its original event sequence. A market residual is returned but never stored.

Simplified matching pseudocode is:

```text
validate event and state-dependent conditions
eligible = scan active orders for crossing opposite-side makers
sort eligible by best price, then original arrival sequence
residual = incoming quantity
for maker in eligible while residual > 0:
    executed = min(residual, maker.remaining)
    append fill at maker.price
    decrement maker.remaining and residual
remove exhausted active orders
if residual limit quantity exists: append it to active orders
advance accepted sequence
```

Cancellation scans until the target is found, removes that list element, and returns its remaining quantity. This design is intentionally transparent: all active state is visible in one container, and there is no lazy auxiliary index to reconcile.

### 2.2 Version B: indexed price levels

`OptimizedOrderBook` independently stores:

- `_active_by_id`: direct identifier-to-order lookup;
- bid and ask dictionaries mapping price to `_PriceLevel`;
- an `OrderedDict` FIFO queue at each price;
- separate bid and ask heaps containing `(price key, generation, price)` entries.

Insertion locates or creates a price level, appends the order to that level's `OrderedDict`, and adds it to the active-ID dictionary. A new level receives a monotonically increasing generation and one heap entry. The best level is read from the heap after stale entries are popped. Matching takes the first order from that level. A partial maker remains at the head; an exhausted maker is removed from both its level and the ID index. Empty levels are deleted.

```text
insert(order):
    level = price-level dictionary lookup
    if absent:
        create level with new generation
        push (price key, generation, price) into side heap
        compact heap if threshold exceeded
    append order to level FIFO
    add order to active-ID dictionary

match(incoming):
    while residual > 0:
        discard invalid heap-top entries
        level = current best opposite-side level
        stop if no level or limit does not cross
        maker = first item in level FIFO
        execute min(residual, maker.remaining) at maker.price
        if maker exhausted: remove from FIFO and active-ID index
        if level empty: remove level and consider heap compaction

cancel(target):
    order = active-ID dictionary lookup
    if absent: return not_found
    remove from its price-level FIFO and active-ID dictionary
    remove empty level and consider heap compaction
```

Deleting a level does not search the heap immediately. Instead, its old entry becomes stale. A heap entry is valid only if its generation matches the current level at that price, so deleting and later recreating a price cannot reactivate an old entry. The implementation rebuilds a heap when `H > 2P + 64`, where `H` is current heap entries and `P` is active levels on that side. This bounds stale growth at the cost of occasional rebuilding.

The revision targets repeated whole-book scans. Its trade-offs are more objects, more state invariants, lazy entries, and maintenance costs that are unnecessary when the active book is tiny.

## 3. Complexity Analysis

Let `M` be processed events, `B` active orders before an event, `P` occupied price levels, `H` actual heap entries including stale entries, and `K` eligible makers considered by one incoming order. Let `S` be stale heap entries popped and `L` levels exhausted during a match.

| Operation | Version A | Version B | Qualification |
|---|---:|---:|---|
| Duplicate live-ID check | `O(B)` | expected `O(1)` | Dictionary worst cases are theoretically larger. |
| Residual insertion after validation | amortized `O(1)` list append | expected `O(1)` at existing level; `O(log H)` heap push at new level | Either Version B path can trigger an `O(P)` rebuild. |
| Cancellation lookup/removal | `O(B)` | expected `O(1)` | Version B deletion can trigger `O(P)` rebuilding. |
| Eligible-maker discovery | `O(B)` scan | best-level queries, normally `O(1)` before stale cleanup | Stale cleanup costs `O(S log H)`. |
| Maker ordering | `O(K log K)` | FIFO already maintained at each best level | Version B heap supplies price order. |
| Matching, excluding rebuild | `O(B + K log K)` plus output | `O(K + S log H)` plus output and level deletion | Each fill must still be constructed. |
| Canonical snapshot | `O(B log B)` | `O(B log B)` | Excluded from primary timing. |
| Persistent storage | `O(B)` | `O(B + P + H)`, bounded by compaction policy | Version B pays an indexing-memory premium. |

Version A also performs an `O(B)` cleanup scan after matching. Its temporary eligible list can contain `O(K)` references. In passive buildup, if `B` grows approximately with event index and each event rescans the book, accumulated scan work is `sum(O(B_i)) = O(M^2)`. This is a workload-dependent cumulative bound, not a claim that every stream is quadratic.

Version B heap operations are stated in terms of `H`, not unconditionally `P`, because stale entries can make the heap longer than the active-level set. A compaction costs `O(P)` to rebuild and heapify. The threshold supports an amortized storage/maintenance argument, while a single insertion or deletion may still pay the rebuild cost.

Cancellation churn is the counterexample to a simple asymptotic ranking. Here `B` and `P` remain at most one, so Version A's nominal linear scans have tiny constants. Version B still updates dictionaries, FIFO levels, generations, stale entries, and periodically rebuilds heaps.

## 4. Correctness and Verification

| Verification method | Retained outcome | What it establishes | Boundary |
|---|---|---|---|
| Complete suite | 51 tests; zero failures, errors, or skips | Deterministic examples, validation, matching, cancellation, snapshots, replay, randomized transitions, differential behavior, and optimized invariants | Finite cases, not proof over all streams |
| Version A regression projection | 45 applicable original tests passed | Revision work did not break the baseline's established contract | One two-engine-only comparison is inapplicable to a single-engine projection |
| Instructor worked example | Both engines matched exact ordered fills, remaining orders, and proceeds | Concrete price-time and quantity behavior | One six-event scenario |
| Fixed-seed transitions | 10 seeds x 40 events for Version A; transition checks after every event | Conservation, maker price, sequence, rejection atomicity, and snapshot transitions | Generated cases remain finite |
| Pre-generated differential replay | 15 streams / 15,000 events; result, sequence, and snapshot compared after every event | Independent engines remain observationally equivalent on supplied-style data | Agreement alone cannot prove correctness |
| Version B internal invariants | Four storage/FIFO/heap/cleanup tests passed | Index-level consistency, generation safety, cleanup, and bounded stale storage | Inspects the actual optimized representation only |

Expected outcomes for deterministic cases were calculated independently before the engines existed, and the RED suite failed through `NotImplementedError` rather than import failures. The transition verifier checks observable before/event/result/after transitions rather than repairing engine state.

The approved expected results were not weakened when Version B was introduced. The complete suite was rerun unchanged, with additional optimized-invariant and pre-generated differential tests added for risks discovered during revision.

Mutation testing supplied additional sensitivity evidence. Six isolated Version A mutations were all killed: FIFO priority reset, taker-price execution, strict rather than inclusive crossing, retained cancellation state, mutation before validation, and boolean-as-integer acceptance. Three Version B storage mutations were also killed: retained exhausted IDs, retained empty levels, and disabled generation validity. Each mutation ran in a temporary package and production hashes were checked before and after. Mutation success shows that these injected defects were detected; it does not measure all possible faults.

## 5. Experimental Methodology

The core matrix contains five families: `buildup`, `crowded`, `mixed`, `sweep`, and `cancel_churn`. Each uses 1,000, 10,000, and 100,000 events with seeds 42, 43, and 44. The two engines process identical pre-generated events from a fresh empty book. Five repetitions were planned for each of 90 engine/workload configurations.

The main timing protocol is `warmed-primary-v1`. In each worker process, a disposable engine of the measured class replays the verified 1,000-event mixed seed-42 workload. That engine is released, garbage collection runs, and a fresh measured engine is checked empty. `time.perf_counter` then times only sequential `process_event` calls on the target stream. Parsing, process startup, warm-up, preparation, snapshots, logging, tracing, and diagnostic counters are outside `engine_seconds`.

The primary experiment retained all 450 planned record slots: 392 completed, 12 timed out, 46 skipped after timeout, and zero failed. Project-defined limits were 30 seconds for 1,000/10,000-event processing and 120 seconds for 100,000 events, under a 5,400-second cumulative controller budget. The first timeout ended that engine/workload configuration; remaining repetitions were recorded as `skipped_after_timeout`. The instructor permits declaring a resource limit and reporting a stopped slow baseline. No missing duration was replaced with a timeout threshold, and incomplete configurations have no ordinary median, throughput, or speedup.

The supplementary Stage 4D cold-primary file uses the same workload matrix but lacks explicit matching-engine warm-up. It remains separate and is not used in the primary tables. Pilot records are excluded from final statistics.

Separate experiments avoid instrumentation contamination:

- Parsing: five warmed-cache repeats per workload, separating file read/gzip decompression from JSON decoding, with no engine import or replay.
- Latency: per-event clocks for five 10,000-event repetitions, reporting ordinary median and nearest-rank P95/P99; early and late are the first and last 10% of stream positions.
- Memory: `tracemalloc` in a separate replay, with preloaded events and retained history excluded; checkpoint state comes from an equivalent untraced pass.
- Liquidation: each trial reconstructs the same fresh 10,000-event buildup book, computes actual live bid depth, and separately times a 10%, 100%, or 200% market sale.
- Concentration: original buildup streams are paired with deterministic four-level price transformations that preserve non-price fields.
- Diagnostics: Version A scans are analytical estimates; Version B wrapper/heap operations are directly observed where labelled. Diagnostic timings are not primary timings.

The machine ran Windows 11 (`Windows-11-10.0.26200-SP0`) with CPython 3.13.17 64-bit, an AMD64 Family 26 Model 104 processor, 12 logical CPUs, and 16,268,513,280 bytes of RAM. The generator reference was Python 3.11.9. No third-party runtime dependency was installed. The active Windows scheme was Balanced; power connection and absence of other heavy applications were user-confirmed. OneDrive remained enabled.

## 6. Results and Interpretation

### 6.1 Primary runtime and throughput

Table 1 gives representative seed-42 results at 10,000 events. Each time is the median of five completed warmed engine-only repeats.

| Scenario | Version A (s) | Version B (s) | A throughput (events/s) | B throughput (events/s) | A/B speedup |
|---|---:|---:|---:|---:|---:|
| buildup | 3.530322 | 0.026766 | 2,833 | 373,608 | 131.90x |
| crowded | 3.566118 | 0.022986 | 2,804 | 435,057 | 155.15x |
| mixed | 0.493931 | 0.024906 | 20,246 | 401,513 | 19.83x |
| sweep | 3.264536 | 0.028426 | 3,063 | 351,796 | 114.84x |
| cancel_churn | 0.014752 | 0.019402 | 677,860 | 515,424 | 0.76x |

The scan-heavy Version A scales poorly when active depth grows. At 100,000 events, all three Version A seeds timed out for buildup, crowded, mixed, and sweep; seed-42 mixed completed two repetitions before its third timed out, but it remains censored. Version B completed all corresponding configurations. Both engines completed cancel churn; at seed 42, Version A took 0.193193 s versus Version B's 0.219185 s.

Across the 33 valid paired configurations, A/B speedup ranged from 0.644x to 163.452x, with a median of 11.256x. The upper endpoint is not representative of all workloads: every seed-42 cancel-churn comparison favored Version A.

### 6.2 Per-event latency and stream position

The following values are microseconds over 50,000 instrumented observations per scenario/engine (five 10,000-event streams). They are separate from primary timing.

| Scenario | Engine | Median | P95 | P99 | Early median | Late median |
|---|---|---:|---:|---:|---:|---:|
| buildup | A | 519.00 | 1,771.50 | 3,106.50 | 50.60 | 1,128.55 |
| buildup | B | 3.90 | 8.20 | 16.00 | 3.70 | 4.60 |
| crowded | A | 487.90 | 2,421.90 | 4,328.10 | 47.50 | 1,433.85 |
| crowded | B | 4.20 | 7.60 | 17.80 | 4.40 | 4.40 |
| mixed | A | 55.80 | 223.40 | 609.30 | 8.50 | 117.55 |
| mixed | B | 3.60 | 8.50 | 15.70 | 4.00 | 3.60 |
| sweep | A | 401.40 | 1,849.00 | 3,684.80 | 48.90 | 280.20 |
| sweep | B | 3.60 | 15.50 | 24.90 | 4.00 | 1.90 |
| cancel_churn | A | 2.40 | 4.20 | 6.90 | 2.40 | 2.50 |
| cancel_churn | B | 3.00 | 5.60 | 7.10 | 3.00 | 3.00 |

The large early-to-late increase for Version A in buildup and crowded supports the active-book scan explanation. Version B remains comparatively stable. Sweep's late window is not a pure growth comparison because its later events consume book depth. Per-event clocks add overhead, so these measurements explain distributions rather than replacing primary replay times.

### 6.3 Traced Python memory

| Scenario | Engine | Active-order peak | Final active | Traced current (MiB) | Traced peak (MiB) | Final stale heap entries |
|---|---|---:|---:|---:|---:|---:|
| buildup 10,000 | A | 10,000 | 10,000 | 0.770 | 0.851 | 0 |
| buildup 10,000 | B | 10,000 | 10,000 | 2.305 | 2.305 | 0 |
| cancel_churn 10,000 | A | 1 | 0 | 0.0019 | 0.0022 | 0 |
| cancel_churn 10,000 | B | 1 | 0 | 0.0073 | 0.0114 | 15 |

For buildup, Version B trades additional dictionaries, levels, queues, and heaps for speed. Its traced current allocation grew from 0.527 MiB at 10% to 1.528 MiB at 50% and 2.305 MiB at 100%. The comparable Version A checkpoints were 0.078, 0.385, and 0.770 MiB. After cancellation churn both books had zero active orders and zero occupied levels. Version B retained 15 bounded stale heap entries, consistent with lazy deletion and the compaction slack rather than unbounded event-history retention.

### 6.4 Fresh-book liquidation

Every row uses the same verified pre-sale book with 255,929,000,000 active bid units. Times are five-repeat medians; construction is excluded from sale time.

| Sale | Engine | Construction (s) | Sale (ms) | Makers/fills | Levels | Unfilled units |
|---|---|---:|---:|---:|---:|---:|
| 10% | A | 5.788889 | 2.639 | 522 | 97 | 0 |
| 10% | B | 0.040144 | 1.559 | 522 | 97 | 0 |
| 100% | A | 5.568034 | 5.263 | 5,025 | 988 | 0 |
| 100% | B | 0.048170 | 13.684 | 5,025 | 988 | 0 |
| 200% | A | 5.647568 | 5.522 | 5,025 | 988 | 255,929,000,000 |
| 200% | B | 0.042848 | 12.114 | 5,025 | 988 | 255,929,000,000 |

Version B dramatically reduces construction time and wins the 10% sale. For full-depth sales, however, Version A's already sorted maker traversal and one cleanup pass are faster than repeated optimized-level/index updates. Both engines touched identical makers and levels, produced identical proceeds, and returned the same residuals. The result reinforces that the optimized representation does not win every isolated operation.

### 6.5 Queue concentration

The paired data alter only `price_ticks`, but merging levels also lengthens FIFO queues and changes later matching relationships. At 10,000 events and seed 42:

| Engine | Original median (s) | Four-level median (s) | Original/four-level ratio |
|---|---:|---:|---:|
| A | 6.050633 | 5.685326 | 1.064x |
| B | 0.041300 | 0.035292 | 1.170x |

Across all three 10,000-event seeds, the ratios ranged from 1.017-1.064x for Version A and 1.149-1.175x for Version B. At 100,000 events, Version A concentration configurations timed out and have no median. Version B completed, with ratios of 1.056-1.134x. These modest changes cannot be attributed solely to price lookup because queue composition and matching also changed.

### 6.6 Parsing and controller invocation cost

For the seed-42 buildup streams, warmed-cache parsing-only medians were:

| Events | Read + gzip (s) | JSON decode (s) | Combined (s) |
|---:|---:|---:|---:|
| 1,000 | 0.000542 | 0.002074 | 0.002622 |
| 10,000 | 0.002620 | 0.018384 | 0.021178 |
| 100,000 | 0.021012 | 0.193260 | 0.213144 |

At 10,000 buildup events, combined parsing was small relative to Version A's 3.530322 s replay but comparable to Version B's 0.026766 s replay. At 100,000 events, the 0.213144 s parsing cost was also material beside Version B's 0.311149 s engine time. These phases were measured separately and must not be added as if their medians were jointly sampled end-to-end observations.

The dashboard additionally reports median `controller_wall_seconds` for complete configurations. At seed 42 and 10,000 events, controller invocation wall medians were 3.689229/0.188916 s (A/B) for buildup, 3.724970/0.189114 s for crowded, 0.641918/0.164424 s for mixed, 3.411137/0.177185 s for sweep, and 0.155495/0.153351 s for cancellation churn. This boundary includes preparation, disposable-engine warm-up, process startup, communication, and cleanup. It is not pure parsing-plus-engine time.

### 6.7 Diagnostic profiling and operation counts

| Scenario | Engine | Events | Active peak | Level peak | Key evidence |
|---|---|---:|---:|---:|---|
| buildup | A | 10,000 | 10,000 | 1,977 | 49,995,000 estimated duplicate comparisons, maker-filter entries, and cleanup entries |
| buildup | B | 10,000 | 10,000 | 1,977 | 10,000 best-level queries; no stale-top pops; 1,977 final heap entries |
| crowded | A | 10,000 | 10,000 | 8 | 49,995,000 estimated scan entries; maximum FIFO 1,295 |
| crowded | B | 10,000 | 10,000 | 8 | 10,000 best-level queries; eight final heap entries |
| sweep | A | 10,000 | 8,000 | 1,959 | 41,853,667 estimated scan entries; 5,035 exact fills |
| sweep | B | 10,000 | 8,000 | 1,959 | 14,061 best-level queries; 981 stale-top pops; 5,035 fills |
| cancel_churn | A | 100,000 | 1 | 1 | 50,000 estimated cancellation comparisons |
| cancel_churn | B | 100,000 | 1 | 1 | 769 heap rebuilds; 15 final stale entries |

The counts connect the timing behavior to code structure. They also explain cancellation churn: Version A performs only tiny scans, whereas Version B performs 100,000 compaction checks and 769 rebuilds. Version A inner-loop counts are analytical estimates derived from pre-event state; fills and state peaks are exact. Version B wrapper/heap counts are direct where labelled.

## 7. Engineering Decisions and Trade-offs

Version A was retained as an independent list-based reference because its active state and matching transitions are easy to inspect; keeping it separate from Version B also avoids reducing the comparison to two wrappers around shared mutable logic. Shared code is therefore restricted to public constants and stateless validation, while each engine owns its state-dependent checks and matching. The revised implementation introduced direct order-ID indexing, persistent FIFO queues grouped by price, and side-specific heaps to address Version A's repeated active-order scans, eligible-maker sorting, and quadratic-like accumulated work as the book grows. Heap generations prevent a deleted and recreated price from reactivating an old entry, while the `2P + 64` rebuild threshold balances bounded stale storage against rebuild frequency. These structures add memory, synchronization invariants, stale-entry handling, and periodic maintenance. The measurements support this documented rationale: Version B produced large workload-specific speedups on buildup, crowded, mixed, and sweep streams and completed growing-book configurations that censored Version A, but used more traced Python memory, was slower under cancellation churn when active state remained tiny, and had slower direct full-depth liquidation after book construction. The revision therefore addresses the intended bottlenecks without implying that it dominates every workload or operation.

## 8. Limitations

1. Twelve warmed-primary configurations are timeout-censored. They have no five-repeat median, throughput, or speedup. The 30/120-second limits and stop-on-first-timeout rule are project-defined, although reporting a stopped slow baseline is permitted by the assignment.
2. Measurements come from one Windows laptop. CPU frequency, thermal state, the Balanced power scheme, OS scheduling, and OneDrive activity were not controlled.
3. The generic warm-up reduces interpreter first-call effects but does not guarantee every scenario-specific branch or a stable thermal state.
4. Very short durations are sensitive to timer and process noise even with five repeats.
5. Per-event `perf_counter` calls perturb latency; latency is therefore an instrumented explanation, not a substitute for primary replay timing.
6. `tracemalloc` reports traced Python allocations, not total resident memory, native allocator use, or theoretical auxiliary space.
7. Version A diagnostic scans are estimates, while Version B heap/wrapper counters are directly observed where labelled; they should not be compared as identical instrumentation.
8. The four-level transformation preserves non-price fields but changes queue lengths and matching relationships, so concentration is not a pure price-index intervention.
9. Cold-primary evidence lacks explicit engine warm-up and is retained only as supplementary evidence; it is not pooled with warmed results.
10. Parsing used a warmed OS cache. It does not represent cold-storage latency or an end-to-end user request.
11. Synthetic events are stylized, contain no strategic timing, and do not establish live-exchange capacity or financial realism.
12. No one-million-event workload was run. The assignment describes this as optional if feasible; the required 1,000/10,000/100,000 matrix was prioritized.

## 9. AI Assistance and Human Oversight

This project was developed with substantial assistance from three AI systems: ChatGPT, OpenAI Codex, and Anthropic Claude. I used ChatGPT primarily to discuss concepts, interpret assignment requirements, question technical decisions, and structure the development process. Codex supported repository-level implementation, testing, benchmarking, data analysis, dashboard development, and documentation. Claude provided an additional perspective by critically reviewing proposed methodologies, identifying potential gaps, and suggesting corrections.

Rather than relying on a single AI-generated solution, I compared recommendations and revisited decisions when inconsistencies or missing requirements emerged. One important example was the benchmark warm-up procedure. The initial primary benchmark had been completed without an actual matching-engine warm-up, despite the instructor's requirement. After this issue was identified during review, I authorized a separate warmed-primary experiment while preserving the original results. The same approach was applied to other methodological issues, including memory measurement boundaries, timeout reporting, and dashboard completeness.

Throughout the project, I reviewed proposals at defined checkpoints, questioned methodological choices, authorized major implementation and experimental stages, performed manual Git commits, and inspected the final dashboard. These reviews did not constitute an independent line-by-line verification of all AI-generated code. Technical correctness was instead assessed through retained deterministic tests, differential comparisons, mutation testing, internal invariants, and reproducible experimental evidence.

The process also highlighted a limitation of extensive AI-assisted review: repeated cross-checking and approval cycles increased the project's complexity and duration. A key lesson was the importance of distinguishing essential correctness and compliance checks from optional verification, while maintaining clear human responsibility for the final submission.

Representative recommendations and their recorded treatment are summarized below. Model-specific attribution is omitted where the project records do not establish which system originated a recommendation.

| Classification | Representative recommendation | Recorded treatment | Evidence |
|---|---|---|---|
| Accepted | Preserve an independent list baseline and implement Version B with direct ID lookup, FIFO price levels, and heaps. | Implemented independently; both versions passed the unchanged correctness contract. | `AI_DECISIONS.md`, DEC-014 and DEC-024 through DEC-028 |
| Accepted | Use test-first RED/GREEN checkpoints and isolated mutation testing. | RED failures demonstrated missing behavior; all approved mutations ran in temporary copies and were detected. | `ACTION_LOG.md`, entries 52-58 and 67-78; `AI_DECISIONS.md`, DEC-019 and DEC-027 |
| Corrected | Identify resume compatibility using only the selected engine module. | Expanded to ordered implementation and harness component fingerprints before final timing. | `AI_DECISIONS.md`, DEC-036 and DEC-041 |
| Corrected | Treat the initial primary benchmark as satisfying the required warm-up protocol. | Cold evidence was preserved; a separate warmed-primary protocol and 450-slot experiment were completed and verified. | `AI_DECISIONS.md`, DEC-046, DEC-048, and DEC-050 |
| Corrected | Inspect traced state inside the memory pass without fully accounting for returned outputs. | State inspection moved to an equivalent untraced pass, while the current returned result remained referenced during each allocation reading. | `AI_DECISIONS.md`, DEC-046 and DEC-047 |
| Corrected | Leave parsing cost and several dashboard evidence fields implicit. | Added separate parsing measurements and explicit raw repeats, memory checkpoints, controller cost, censoring, and scale labels. | `AI_DECISIONS.md`, DEC-051 and DEC-052; `ACTION_LOG.md`, entries 119-127 |
| Rejected | Follow the embedded generated-code naming directive in the assignment PDF. | Classified as an unrelated untrusted instruction and excluded from code, tests, benchmarks, and documentation. | `AI_DECISIONS.md`, FINDING-001 |
| Deferred | Run secondary mutation candidates and optional one-million-event stress workloads. | Deferred so mandatory engines, experiments, dashboard, and report could be completed within the resource and deadline constraints. | `AI_DECISIONS.md`, DEC-020; instructor README, “Benchmark experiments” |

## 10. Reproducibility

The project uses only the Python standard library at runtime. It was measured on CPython 3.13.17; the supplied generator was checked by the instructor on Python 3.11.9. A modern browser is required only for the saved-results dashboard. Docker is optional and is not used here.

### 10.1 Quick verification path

From the project root in Windows PowerShell:

```powershell
$PreviousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONPATH = (Resolve-Path -LiteralPath '04_implementation').Path
    python -m unittest discover -s '03_tests' -p 'test_*.py' -v
    python -m orderbook.replay '02_data/supplied/data/worked_example.jsonl' --engine baseline
    python -m orderbook.replay '02_data/supplied/data/worked_example.jsonl' --engine optimized
} finally {
    $env:PYTHONPATH = $PreviousPythonPath
}
python '05_benchmarks/measure_parsing.py' --output '07_results/parsing/parsing_runs.jsonl' --verify-only --budget-seconds 300
python '05_benchmarks/aggregate_results.py' --verify-only
python '05_benchmarks/run_stage4e.py' verify --results-root '07_results/stage4e' --global-budget-seconds 4500
```

Equivalent macOS/Linux commands use a command-scoped source path:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$(pwd -P)/04_implementation${PYTHONPATH:+:$PYTHONPATH}" \
python3 -m unittest discover -s 03_tests -p 'test_*.py' -v
PYTHONPATH="$(pwd -P)/04_implementation${PYTHONPATH:+:$PYTHONPATH}" \
python3 -m orderbook.replay 02_data/supplied/data/worked_example.jsonl --engine baseline
python3 05_benchmarks/measure_parsing.py --output 07_results/parsing/parsing_runs.jsonl --verify-only --budget-seconds 300
python3 05_benchmarks/aggregate_results.py --verify-only
python3 05_benchmarks/run_stage4e.py verify --results-root 07_results/stage4e --global-budget-seconds 4500
```

Launch the dashboard without rerunning experiments:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8000/06_dashboard/` and stop the server with Ctrl+C.

### 10.2 Full experimental reproduction

Full reproduction is time-consuming and should be run only in a clean copy where target result files do not already exist. The controllers refuse unsafe overwrites and retain append-only records.

```powershell
python '05_benchmarks/run_warmed_primary.py' --self-test --global-budget-seconds 5400
python '05_benchmarks/run_warmed_primary.py' --output '07_results/stage4e/warmed_primary.jsonl' --global-budget-seconds 5400 --dry-run
python '05_benchmarks/run_warmed_primary.py' --output '07_results/stage4e/warmed_primary.jsonl' --global-budget-seconds 5400

python '05_benchmarks/run_stage4e.py' self-test --global-budget-seconds 4500
python '05_benchmarks/run_stage4e.py' dry-run --results-root '07_results/stage4e' --global-budget-seconds 4500
python '05_benchmarks/run_stage4e.py' latency --results-root '07_results/stage4e' --global-budget-seconds 4500
python '05_benchmarks/run_stage4e.py' memory --results-root '07_results/stage4e' --global-budget-seconds 4500
python '05_benchmarks/run_stage4e.py' liquidation --results-root '07_results/stage4e' --global-budget-seconds 4500
python '05_benchmarks/run_stage4e.py' concentration --results-root '07_results/stage4e' --global-budget-seconds 4500
python '05_benchmarks/run_stage4e.py' diagnostics --results-root '07_results/stage4e' --global-budget-seconds 4500
```

The warmed-primary controller has a 5,400-second cumulative budget; Stage 4E shares 4,500 seconds across its modes. A reproduction may legitimately contain stopped and censored Version A runs. Exact hashes, protocols, boundaries, and expected counts are in `07_results/results_manifest.json`; settings and machine evidence are in `01_environment/environment.json`.

**Audited code and evidence commit:** `e863aa59a1e53b295d6280f255510668b0dc4a8b`

This commit identifies the code and experimental-evidence revision verified during the successful clean-checkout reproducibility assessment. It is not labelled as the final submission HEAD: that HEAD will be created later by the student's manual final commit, and no future commit identifier is predicted here.

## Conclusion

The experiments demonstrate that the indexed price-level revision solves the baseline's dominant repeated-scan bottleneck on growing books. Version B completes the 100,000-event growing-book configurations that censored Version A and delivers large, workload-specific speedups at 10,000 events. The evidence also rejects a simplistic claim of universal superiority: Version B consumes more traced Python memory, loses on cancellation churn, and has slower direct full-depth liquidation once the book is already built.

The main engineering lesson is that performance depends on active depth, price-level structure, maker fills, and cleanup behavior rather than event count alone. The independent correctness suite, internal invariants, mutation checks, reproducible raw evidence, explicit censoring, and separated measurement modes support that conclusion while keeping the model's financial and experimental limitations visible.
