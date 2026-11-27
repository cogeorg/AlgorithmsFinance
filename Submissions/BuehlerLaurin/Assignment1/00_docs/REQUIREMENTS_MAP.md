# Requirement → evidence map
Update in every phase. A reviewer must be able to check each requirement here in one place.

Sources: `R §…` = package `README.md` section; `S<k>` = slide with footer `k/23` in `AlgorithmsFinance_Exercise1.pdf` (PDF page k+1). See `SPEC.md` for the full rules.

Current naming (2026-11-23): final B = B3r; B1 is explicitly registered.
The dated phase evidence below retains its original counts and labels. In
Phases 3-4, old B meant B1. Current registry coverage and fresh evidence are
recorded in [final fix verification](FINAL_FIX_VERIFICATION.md); dated registry checkpoints below remain historical.

Current registry-wide checks are linked in [final fix evidence](FINAL_FIX_VERIFICATION.md). References to four versions in the retained Phase 3b evidence describe that dated checkpoint; the current suite covers all seven registry keys.

## Model, interface, units
| ID | Requirement (short, with source) | Status | Evidence |
|---|---|---|---|
| R1 | Sequential single-venue BTC limit order book in Python, incl. own `FillMarketSell` (R §Task; S2) | All registered versions checked | A/B1 algorithm sources preserved; B2 OrderedDict levels and B3 lazy heap levels added; 64 contract cases per version, full Phase 3b evidence below. |
| R2 | Document modelling boundaries (no fees, balances, hidden orders, self-trade checks, delays, simultaneity; one venue; not production) (R §Task; S4) | Documented | [REPORT](REPORT.md) §1 and SPEC model boundaries; README current reference. |
| R3 | Integer `price_ticks` (0.01 USD/BTC) and `qty_units` (1e-8 BTC); integer matching/conservation; round only for display; USD = Σp·q / 1e10 (R §Integer units; S5) | All registered versions checked | `check_result_types_are_exact_ints`, `check_worked_example_book_and_proceeds`, `check_own_huge_values`; TRACE.md integer proceeds. |
| R4 | `seq` defines arrival order; never priority by id spelling (R §Integer units; S5) | All registered versions checked | `check_fifo_within_price`, `check_partial_maker_keeps_priority`; LIFO/id-priority/requeue mutants killed; SPEC.md A invariant argument. |
| R5 | Read JSON Lines (+ gzip) with stdlib `json`/`gzip`; replay in `seq` order from an empty book (R §Input files; S6) | All registered versions checked | Shared JSON/gzip reader; 15 CLI cases cover A/B/B1/B2/B3; sanity checks each B variant on all five supplied 10k files against A. |
| R6 | Event types LIMIT / MARKET_SELL / CANCEL with their required fields (R §Input files; S6) | All registered versions checked | Shared validator unchanged: 184 direct tests; 256 contract cases over four registry versions. |
| R7 | Provide `AddLimitOrder`, `CancelOrder`, `FillMarketSell`, an event dispatcher and book inspection; document signatures (R §Input files; S6) | All registered versions checked | `check_direct_methods_match_process`, `check_direct_methods_validate`, `check_direct_methods_reject_wrong_type`; SPEC.md API/N2. |
| R8 | Supply a command to replay a file (R §Input files) | Final registry/default implemented; fresh verification below | Replay defaults to B = B3r, accepts A/B/B1/B2/B3/B3r/B3r_fast explicitly; A is the baseline via --version A. Located single-line input diagnostics; SPEC/README commands/help updated. |
| R9 | Both versions accept the same event files and return equivalent results (R §Input files) | All registered versions checked in stated coverage | Three stateful machines (A vs each B), 64 contract cases per version and all supplied sanity result/final-book comparisons; intermediate full-stream coverage qualified below. |

## Matching, cancellation, validation
| ID | Requirement (short, with source) | Status | Evidence |
|---|---|---|---|
| R10 | Buy crosses iff limit ≥ best ask; sell crosses iff limit ≤ best bid; best price first, then arrival (R §Matching rules 1; S7) | All registered versions checked | `check_limit_at_touch_crosses`, `check_best_price_first`, `check_own_limit_at_touch`, `check_own_crossing_limit_*`; step checker in `contract.run`; all four verified in full Phase 3b evidence below. |
| R11 | Fill qty = min(incoming, resting) at the resting order's price; continue while crossing (R §Matching rules 2; S7) | All registered versions checked | `check_fill_at_maker_price`, `check_crossing_sell_at_maker_price`; step checker (min rule, maker price); all four verified in full Phase 3b evidence below. |
| R12 | Exhausted maker removed; partial maker keeps priority; residual limit rests at its limit behind earlier orders, rank = its `seq` (R §Matching rules 3; S7) | All registered versions checked | `check_partial_maker_keeps_priority`, `check_own_crossing_limit_buy`, `check_own_partial_then_another_sale`; all four verified in full Phase 3b evidence below. |
| R13 | `FillMarketSell`: highest bid first, FIFO per price, mutates live book; residual discarded, never rests (R §Matching rules 4; S4, S7, S9) | All registered versions checked | `check_market_*`, `check_own_sweep_levels`, `check_own_sell_sizes`, `check_own_market_larger_than_book`; all four verified in full Phase 3b evidence below. |
| R14 | Cancel removes exactly the remaining qty (also after partial fill); unknown / filled / cancelled → `not_found`, no change (R §Matching rules 5; S8) | All registered versions checked | `check_cancel_*`, `check_own_cancel_cases`, `check_own_interleaved_cancel_fill`; all four verified in full Phase 3b evidence below. |
| R15 | Reject invalid type/side, noninteger or nonpositive price/qty, duplicate live ids, nonincreasing `seq`; book unchanged (R §Matching rules 6; S8) | All registered versions checked | `check_rejects_*` (one per rule family), `check_validation_check_order`, `test_validation.py`, `check_own_invalid_fields`; all four verified in full Phase 3b evidence below. |
| R16 | Rejected events do not advance the last accepted `seq` (R §Matching rules 6; S8) | All registered versions checked | `check_rejected_event_does_not_advance_seq`, `_check_invalid_rows` (seq 3 still accepted after each rejection); all four verified in full Phase 3b evidence below. |
| R17 | Cancel of unknown target is valid (not rejected) (R §Matching rules 6) | All registered versions checked | `check_accepted_cancel_and_market_advance_seq`, `check_own_empty_book`; all four verified in full Phase 3b evidence below. |
| R18 | After each valid event: no crossed book, no nonpositive resting qty, no order stored twice; empty side allowed (R §Matching rules; S8) | All registered versions checked | `contract.assert_book` (I1-I4) after every event in every replay and in the stateful test; all four verified in full Phase 3b evidence below. |

## Outputs
| ID | Requirement (short, with source) | Status | Evidence |
|---|---|---|---|
| R19 | Ordered fill list with `maker_id`, `taker_id`, `price_ticks`, `qty_units`, in execution order (R §Required results; S9) | All registered versions checked | step checker (fill fields, order = priority order); `check_worked_example_market_sell`; all four verified in full Phase 3b evidence below. |
| R20 | Submission result: `event_id`, `order_id`, `status`, `unfilled_qty_units`; limit `filled`/`resting` (R §Required results; S9) | All registered versions checked | step checker (status/unfilled); own dataset expected files; all four verified in full Phase 3b evidence below. |
| R21 | Market-sell status `filled` / `partial` / `unfilled`; residual never in the book (R §Required results; S9) | All registered versions checked | `check_market_sell_larger_than_depth_is_partial`, `check_market_residual_discarded`; all four verified in full Phase 3b evidence below. |
| R22 | Cancel result: `event_id`, `target_order_id`, `cancelled`/`not_found`, `cancelled_qty_units` (0 if not found) (R §Required results; S9) | All registered versions checked | step checker (cancel result); `check_cancel_not_found_cases`; all four verified in full Phase 3b evidence below. |
| R23 | Rejection result: `event_id` if available, `rejected`, a reason (R §Required results; S9) | All registered versions checked | `check_rejects_*`, `test_rejection_result_shape`; all four verified in full Phase 3b evidence below. |
| R24 | Return only the current event's fills; any retained history declared as extra storage (R §Required results) | All registered versions implemented | Books retain no event/fill history; sanity runner retains all returned result lists equally for untimed comparison, documented as runner storage. |
| R25 | Book inspection: active orders with side, price, remaining qty, arrival seq; bids price ↓ then arrival, asks price ↑ then arrival; compare ids + qty, not only depth (R §Required results; S9) | All registered versions checked | `contract.assert_book`, `check_snapshot_canonical_order`, `check_snapshot_is_a_copy`; all four verified in full Phase 3b evidence below. |

## Tests and correctness
| ID | Requirement (short, with source) | Status | Evidence |
|---|---|---|---|
| R26 | Worked example reproduces `worked_expected.json` (fills b1:1, b2:1, b3:3, b4:1 BTC; b4 keeps 4 BTC; ask unchanged; 359,400 USD) (R §Worked example; S3, S11) | All registered versions checked | Original worked example/result/proceeds expectations and TRACE unchanged; every registered implementation passes the same checks. |
| R27 | Tests written first and seen failing for missing/incorrect behaviour (R §Worked example; S11) | Phases 1-3b verified | Fresh registered B2/B3 stubs first failed 142 checks with NotImplementedError; full Phase 3b suite then reports 501 passed. Original red/green evidence retained. |
| R28 | Independent expected outcomes for the listed cases: empty book; one order; zero/negative/invalid input; sell < / = / > depth; several makers at one price; several levels; partial fill then another sale; cancel before/after partial or full fill; repeat/unknown cancel; crossing buys and sells; noncrossing residual limits; id order ≠ arrival order; long queue (R §Worked example; S11) | All registered versions checked | All 18 original own expected files unchanged; same check_own cases run per registry implementation. Internal cases also check A/plain/counted parity. |
| R29 | Conservation: incoming = fills + residual; maker loses exactly its fills; cancel removes exactly the residual; proceeds = Σ price·qty; discarded market residual not counted as liquidity (R §Worked example; S12) | All registered versions checked | step checker `contract.step_check` (C1-C6) after every event; all four verified in full Phase 3b evidence below. |
| R30 | Small generated tests; compare A and B after **every** event incl. ordered fills and canonical books (R §Worked example; S12) | Every-event comparisons for all current variants | 02_tests/test_stateful.py and test_fast_equivalence.py; [final fix evidence](FINAL_FIX_VERIFICATION.md); [independent B3r reference](../05_evidence/chat_reference/README.md). |
| R31 | Explain invariants for price-time priority and quantity conservation (R §Implement and revise; S12, S13) | All variants documented and checked | SPEC.md code arguments/invariants; internal pytest index/queue/heap/count checks where applicable; B1/B3 deque credits, B2 direct deletion, B3 price-key uniqueness. |

## Implementation and revision
| ID | Requirement (short, with source) | Status | Evidence |
|---|---|---|---|
| R32 | Version A: clear baseline (e.g. scanning/sorting a list of orders) (R §Implement and revise; S13) | A preserved and verified | A unchanged from committed baseline; 64 A contracts and real-version control pass in full Phase 3b suite. |
| R33 | Version B: justified data organisation or measured revision (R §Implement and revise; S13) | Final B = B3r | FINAL_SELECTION.md records candidate exclusions, B3r fallback and binding rejection of B3r_fast. All variants keep explicit registry names; SPEC gives code-based bounds and README the final map. |
| R34 | Own matching logic; no existing matching engine; library lists/dicts/queues/sorting/heaps allowed (R §Implement and revise; S13) | All variants implemented | Own standard-library matching logic; OrderedDict is used for B2 FIFO, deque for B1/B3; never plain dict FIFO. A/B1 untouched, B2/B3 share public semantics by inheritance. |
| R35 | Pseudocode + runtime/space for insertion, cancellation, market sell in the measured versions, using B, P, M, F; include validation, output construction, index updates, inactive entries, cleanup; state worst-case/expected/amortized (R §Implement and revise; S13) | All variant code arguments; official scaling Phase 4 | SPEC.md B2/B3 worst/expected/amortized time/space arguments include output, hash capacity, price shifts, deque credits and heap K=P+S_h; predictions recorded before sanity. |
| R36 | Preserve both versions; rerun unchanged tests after revision; add tests for found bugs without weakening expectations (R §Implement and revise; S13) | A/B1 and expectations preserved; coverage expanded | Contract.py, original data/expected files and A/B1/shared validator unchanged. Internal assertions promoted into pytest; stateful and CLI cases extended across all variants. |
| R37 | Record what changed and why, and AI suggestions accepted / corrected / rejected (R §Implement and revise; S13) | Decisions and AI corrections recorded | SPEC.md; [AI_LOG](AI_LOG.md); [FINAL_SELECTION](FINAL_SELECTION.md), including the binding rejected fast rematch. |

## Data
| ID | Requirement (short, with source) | Status | Evidence |
|---|---|---|---|
| R38 | Use only synthetic data; no historical exchange data; state it is not calibrated (R §Synthetic data, §What is shared; S15, S25) | documented | SPEC.md Model boundaries/Input domain; supplied data and explicitly own synthetic cases only; no real exchange data. |
| R39 | Generate larger inputs with the supplied generator **outside timing**; record commands + sha256 (R §Synthetic data; S16) | Phase 4a generated and hash-verified | 00_docs/DATA_MANIFEST.json: 114 entries / 105 files, exact commands and sha256; phase4a-generate-data and phase4a-manifest-verified evidence. Supplied generator unchanged. |

## Benchmarks
| ID | Requirement (short, with source) | Status | Evidence |
|---|---|---|---|
| R40 | M ∈ {1k, 10k, 100k}; seeds 42, 43, 44; all five workloads; same workload and limits for both versions (R §Benchmark experiments; S16) | Measured full official grid | [candidate session](../03_results/runs/20261122T012525Z_5eaeb03_phase4/) and [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): summary/timing/checks, five workloads at 1k/10k/100k and three seeds; [REPORT](REPORT.md) §6. |
| R41 | Try 1M events; declare time/memory limit; report stopped runs, never invent results (R §Benchmark experiments; S16) | 1M attempted; stopped cells reported | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): million rows in summary.csv/stops.csv; 600 s / 4 GiB limits; [REPORT](REPORT.md) §6 and §10; no imputed times. |
| R42 | Submission flood: construction + full replay scaling; active-order and price-level peaks (R §Benchmark experiments 1; S16, S17) | Measured construction/replay and live peaks | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): construction/replay in summary.csv and active_order_peak/price_level_peak in counts.csv; [REPORT](REPORT.md) §6–7; Scaling/Method & data tabs. |
| R43 | Large liquidation: same fresh bid book, 10 % (ceil, ≥ 1 unit) / 100 % / 200 %; count makers touched, levels visited, fills, unfilled; never reuse a depleted book (R §Benchmark experiments 2; S17) | Measured fresh-book liquidation | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): liquidation cells at 10/100/200 % with separate construction/query and fill/level counts; [REPORT](REPORT.md) §6; test_bench_pipeline.py. |
| R44 | Queue concentration: fixed initial order count, vary prices (e.g. 4 vs 1,000); correctness and speed (R §Benchmark experiments 3; S16) | Measured queue concentration | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): queue data at 4/1000 prices; [REPORT](REPORT.md) §6; test_bench_pipeline.py. |
| R45 | Cancellation churn: time and memory with few active orders; detect stale-entry / history growth (R §Benchmark experiments 4; S17, S20) | Measured cancellation/drift growth | [candidate session](../03_results/runs/20261122T012525Z_5eaeb03_phase4/) and [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): memory.csv curves; [REPORT](REPORT.md) §7 contrasts B3 history growth with B3r rebuild; qualified live-size bounds. |
| R46 | Operation counts in separate small diagnostic runs; counters separate from primary timing; no 1-D extrapolation without controlling depth, fills, mix (R §Benchmark experiments; S17, S18) | Separate operation-count instrumentation | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): counts.csv separate from primary timing; test_bench_pipeline.py public/counted parity; [REPORT](REPORT.md) §8. |
| R47 | `time.perf_counter`, warm-up, 5 repeats, every raw repeat + median; same pre-generated events; fresh empty book per replay (R §Time and latency; S18) | Protocol measured; A deviation explicit | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): timing.csv every repeat/warm-up and complete medians; B warm-up + five, A at 100k/1M single trial; [REPORT](REPORT.md) §6/§10; Method & data raw repeats. |
| R48 | Parsing (JSON/gzip) reported separately from engine replay; total application time optional; book construction/copying not hidden (R §Time and latency; S18) | Parse/construction/replay/total separated | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): timing.csv/summary.csv phase rows; [REPORT](REPORT.md) §6/§8; test_bench_pipeline.py. |
| R49 | Fixed-book sell tests: construction/reset separate; measured sell incl. matching, state updates, fill-list construction (R §Time and latency; S18) | Fixed-book sale measured separately | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): liquidation construction/replay and counts; fresh-book trial tests; [REPORT](REPORT.md) §6. |
| R50 | Exclude tests, printing, AI calls, dashboard rendering from timing (S18) | Non-engine work excluded by harness | bench.worker.measure wraps the timed callable; tests, journal I/O, sampled oracle checks and dashboard outside timing; [REPORT](REPORT.md) §6; test_bench_pipeline.py. |
| R51 | Throughput = events / replay seconds (R §Time and latency; S19) | Throughput reported for measured sizes | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): summary.csv throughput_events_s = replayed_events / median_s; [REPORT](REPORT.md) §6 and Throughput & latency tab. |
| R52 | Separate instrumentation run: per-event times, median / p95 / p99 with documented convention; split by event type; early vs late in floods; not from 1/throughput; state exclusions (queueing/network) (R §Time and latency; S19, S17) | Separate latency runs measured | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): latency.csv/log2 histograms, nearest-rank ALL/by-type/early/late; [REPORT](REPORT.md) §6; service-time exclusions explicit. |
| R53 | `tracemalloc` in a separate run: peak traced bytes, state what is included (input, book, fills, history) (R §Memory; S20) | Separate traced-memory runs measured | [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): memory.csv; [REPORT](REPORT.md) §7; parsed inputs/history excluded and current book/result included; guard regressions in test_bench_pipeline.py. |
| R54 | Book growth during insertion and after cancellation churn; explain stale entries / delayed cleanup (R §Memory; S20) | Insertion and post-churn curves measured | [candidate session](../03_results/runs/20261122T012525Z_5eaeb03_phase4/) and [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/): memory.csv; [REPORT](REPORT.md) §7 explains stale keys, pinned queue slots and heap cleanup. |
| R55 | Explain why traced allocation ≠ auxiliary space ≠ process/native memory; stream input if preloading too large, boundary explicit (R §Memory; S20) | Memory boundaries and 1M preload outcomes documented | [REPORT](REPORT.md) §7/§10; BENCHMARK_PLAN R55; successful B3r 1M cells and explicit stopped/error rows in [B3r/baseline session](../03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/); no RSS claim. |

## Results, dashboard, submission
| ID | Requirement (short, with source) | Status | Evidence |
|---|---|---|---|
| R56 | Machine-readable CSV/JSON results: version, scenario, seed, event count, active/level peaks, requested sell qty, fill count, phase, repeat, elapsed s, traced peak bytes; timing vs memory runs distinguishable (R §Results and dashboard) | Full machine-readable results retained | Four sessions in [FINAL_SELECTION](FINAL_SELECTION.md): summary/timing/counts/memory/latency/stops/checks CSVs and decision JSON; Method & data shows repeats/settings. |
| R57 | Record Python, dependencies, machine, OS, code version, generator settings (R §Results and dashboard; S23) | Run metadata and generator provenance retained | Four sessions: env.json/spec_snapshot.md and source fingerprints; DATA_MANIFEST.json/POST_ATTACK_MANIFEST.json commands/hashes; [REPORT](REPORT.md) §11. |
| R58 | Dashboard loads saved results only (no rerun) (R §Results and dashboard; S22) | Phase 5 plus no-Git fallback | Default full-commit Git blobs; without Git/checkout, same allowlisted disk paths with an explicit unverified banner. No engine/benchmark imports or network data; telemetry off. Temporary-copy tests render all tabs without checkout and without Git. |
| R59 | Dashboard shows construction, replay and individual-sale scaling; A vs B; throughput and latency distributions; memory incl. post-cancellation; correctness table; workload settings; raw repeats; units; missing/stopped runs labelled (R §Results and dashboard; S22) | Nine tabs (Phase 5b) | AppTest smoke/interactions and numerical audit; final-selection-first layout, compact overview, scaling guides/toggles, separate memory panels, labelled GC/spike, selectable raw repeats/settings. Fresh Phase 5b evidence below; earlier checkpoints retained. |
| R60 | Explain at least one measured bottleneck with code, operation counts and complexity; revision need not win everywhere (R §Results and dashboard; S22) | Two bottlenecks explained | A per-fill rescan O(F·B), Q7 counters/exponent in measured A range; B1 far-end insert O(P) per change, counted movement and scaling. B3r cancel_churn loss and declared spike qualification displayed. |
| R61 | Submission path `Submissions/BuehlerLaurin/Assignment1/`; course folders and other students' work unchanged (R §Submit; S23) | Current branch scope verified | Fresh upstream/main...HEAD comparison: 0 paths outside Submissions/BuehlerLaurin/ against local upstream/main 43ff26c35cb9a27439b86ed5054e188639609903; [source/doc review](../05_evidence/final-fix-review.json). Earlier FINAL_CHECK_CODEX M3 used the older ref e04b40c. This audit performed no fetch or Git mutation. |
| R62 | Include both versions, tests, own generators and exact run commands (R §Submit; S23) | Implemented; Windows entry workflow verified | Explicit variants plus final B; run_all.ps1/run_all.sh show step commands, default 1k scratch smoke and confirmed Full option. Historical measurements unchanged. |
| R63 | Include saved raw results, environment/settings metadata, dashboard code, dependency versions (R §Submit; S23) | Present | Four committed sessions named in FINAL_SELECTION.md, raw CSVs/env/spec/checks; saved-file dashboard. Requirements pins unchanged; fresh local-venv run evidence below. |
| R64 | Short report: specification, correctness, runtime, memory, profiling, revision, limitations (R §Submit; S23) | Report complete with sourced claims | [REPORT](REPORT.md) §§1–11; REPORT_FACT_CHECK.md; committed independent reference/validator/profile evidence; [final fix evidence](FINAL_FIX_VERIFICATION.md) numerical review. |
| R65 | README: clean-environment run path, expected worked-example output, measured-data definitions (R §Submit; S23) | Working-file verification distinguished from committed HEAD | README Start here and current Detailed reference; [final fix evidence](FINAL_FIX_VERIFICATION.md) records exact HEAD-only and pre-commit overlay runs separately, worked output, dashboard and test evidence; Bash native runtime not certified. |
| R66 | Submitted commit identifier recorded (R §Submit; S23) | Human submission action: fill identifier at submission | README Submitted commit placeholder intentionally retained by Laurin; reviewed base 3e9ebfe recorded in the fix evidence. Not asserted complete before human submission. |
| R67 | No million-event datasets uploaded; generator commands + checksums instead (R §Submit; S23) | Committed-tree data hygiene checked | [technical acceptance hygiene](FINAL_CHECK_CODEX.md); [final fix evidence](FINAL_FIX_VERIFICATION.md); no generated/million-event inputs in the archive, generation commands/hashes retained. Tracked old smoke diagnostics are separately flagged; removal command proposed only. |
| R68 | No credentials or proprietary data in the public submission (R §Submit) | No credential-pattern matches; synthetic inputs | [technical acceptance hygiene](FINAL_CHECK_CODEX.md) and [final fix evidence](FINAL_FIX_VERIFICATION.md); regex/config review of submission, no real exchange/proprietary data; not a guarantee about arbitrary secrets/history. |
| R69 | Due 26 Nov 2026, 18:00:00h (R §Task, §Submit; S23) | Deadline recorded; human submission obligation | Due 26 November 2026, 18:00:00 (Europe/Berlin), per the assignment; recorded deadline is not proof of submission. |

## Optional / not required
| ID | Item (source) | Status | Note |
|---|---|---|---|
| O1 | Docker packaging (R §Submit; S23: optional) | out of scope | unless time remains |
| O2 | Peer audit (R §Submit: not required) | Independent audits completed | [Codex technical acceptance](FINAL_CHECK_CODEX.md), [Claude final review](FINAL_REVIEW_CLAUDE.md); this fix evidence responds to their scoped findings. Peer audit is optional. |
| O3 | Retaining full trade history (R §Required results: optional) | out of scope | not retained; would grow with M |




## Dated phase history

The following entries describe their recorded checkpoints, not current pending work.

## Phase 2 verification (2026-11-21, base `11d831b`, uncommitted)

All A/shared verification rows above refer to
[full test output](../05_evidence/20261121T222030Z_11d831b-dirty_phase2-all-tests.txt) and the
[complete failure classification](../05_evidence/20261121T222348Z_11d831b-dirty_phase2-results-summary-corrected-file-grouping.txt).
The run command is recorded in the evidence header; raw case results are in
`05_evidence/phase2-all-tests.xml`.

| Test file | Pass | Expected red (Phase 3) |
|---|---|---|
| `test_contract.py` | 64 A | 64 B |
| `test_validation.py` | 184 shared | 0 |
| `test_own_datasets.py` | 4 data | 0 |
| `test_replay.py` | 3 A CLI | 0 |
| `test_mutants.py` | 19 (17 mutants + 2 controls) | 1 B control |
| `test_stateful.py` | 0 | 1 A/B |
| Total | 274 | 66 |

All 17 mutants are runnable and killed by AssertionError in their named checks;
non-AssertionError failures are explicitly rejected by the mutation harness.
No unexpected red, warnings or skips. B and the stateful test remain unchanged
stubs/test source, respectively. Expected files and data generators are unchanged.
The table does not claim B correctness, A/B agreement, measured complexity,
bounded traced memory, benchmark results or fresh-environment reproducibility.
Those checks remain in their selected later phases.

## Phase 3 verification (2026-11-21, base `efee8d4`, uncommitted)

Full output: [340 passed](../05_evidence/20261121T224926Z_efee8d4-dirty_phase3-all-tests-green.txt).
[Per-file summary](../05_evidence/20261121T225246Z_efee8d4-dirty_phase3-results-summary.txt)
checks every XML case for absence of failure/error/skip.

| File | Passed | Failed |
|---|---|---|
| `test_contract.py` | 128 (64 per version) | 0 |
| `test_validation.py` | 184 | 0 |
| `test_mutants.py` | 20 (17 kills + naming + A/B controls) | 0 |
| `test_own_datasets.py` | 4 | 0 |
| `test_replay.py` | 3 | 0 |
| `test_stateful.py` | 1 | 0 |
| Total | 340 | 0 |

No warning, error or skipped cases. All 17 existing mutants remain killed;
mutation subclasses still target A as originally written, while both real-version
controls pass. No tests or expected results were modified for B.

The stateful differential compares A/B results, snapshots, invariants and
conservation after every generated event (configured max_examples=300,
stateful_step_count=60). Both versions also pass per-event step checks on the
first 1000 events of each supplied stream. The one-shot sanity checks every
result on all 50000 supplied events and all five final books; it does not
compare intermediate books over those complete 10k streams.

New standalone verifier (not a modification of `02_tests/`):
[internal/counter checks](../05_evidence/20261121T224429Z_efee8d4-dirty_phase3-internals-green.txt).
It exercises all 18 own expected files through A / B plain / B counted, checks
index/deque/price/count consistency, stale bounds, cancellation/fill compaction,
level deletion/recreation, id reuse, exact hand-counted work and counter atomicity.

Sanity, not a benchmark:
[one-shot output](../05_evidence/20261121T224807Z_efee8d4-dirty_phase3-sanity-not-a-benchmark.txt),
raw `03_results/runs/20261121T224807Z_efee8d4-dirty_phase3_sanity_not_benchmark/`
contains sanity.json, env.json and tests.txt. Formal repeated timings,
latency/memory/counter runs, official workload grid and fresh-venv checks remain
in their selected later phases. SPEC.md includes the pre-timing prediction and
allocated-dictionary-capacity limitation alongside the compaction credit bound.

## Phase 3b verification (2026-11-22 local, base `b5411d4`, uncommitted)

Full output: [501 passed](../05_evidence/20261121T234932Z_b5411d4-dirty_phase3b-all-tests-green.txt).
[Every-case coverage summary](../05_evidence/20261121T235750Z_b5411d4-dirty_phase3b-results-summary.txt).

| File | Passed | Failed |
|---|---|---|
| `test_contract.py` | 256 (64 per registry version) | 0 |
| `test_validation.py` | 184 | 0 |
| `test_mutants.py` | 22 (17 A kills + naming + 4 real controls) | 0 |
| `test_own_datasets.py` | 4 | 0 |
| `test_replay.py` | 15 | 0 |
| `test_b_internal.py` | 17 | 0 |
| `test_stateful.py` | 3 (A vs each B) | 0 |
| Total | 501 | 0 |

No warning/error/skipped cases. Original 17 mutants remain killed; the two new
in-memory compaction-equality / duplicate-heap-key probes are separate checks
with their own saved AssertionError evidence, not extra claims about that suite.
Internal compaction cases apply to B1/B3; B2 has physical-deletion/no-stale
assertions. All three get own expected-case and plain/counted parity checks.
Stateful machines use identical rules/assertions, configured 300 examples and
60 steps each, with per-event result/book/conservation comparisons. Supplied
contract prefixes remain 1000 events per file per implementation; full-file
sanity compares all results and final books, not intermediate full-file books.

Q11 completed: [manifest/copy hash](../05_evidence/20261121T233959Z_b5411d4_phase3b-q11-generator-sha.txt),
[new-copy reproduction](../05_evidence/20261121T234959Z_b5411d4-dirty_phase3b-copied-generator-reproduces.txt).
Supplied generator sha256:
`ef7f31545addf576e6071cc20a5930f3e2ed93bfef96d4968150fad763d7fe7d`.

[Four-version sanity, not a benchmark](../05_evidence/20261121T234816Z_b5411d4-dirty_phase3b-sanity-not-a-benchmark.txt):
one observation per version/file, fresh books, counters off, parse/setup separate,
all checks after timing. Raw sanity.json/env.json/tests.txt are in
`03_results/runs/20261121T234816Z_b5411d4-dirty_phase3b_sanity_not_benchmark/`.
All three B variants match A on each of the 50000 event results and five final
books. No final B is chosen. Formal grid/repeats/latency/memory/count measurements
remain Phase 4; adaptive switching only considered after Phase 4.

## Phase 4a verification (2026-11-22, base `5d8d15a`, uncommitted)

[Full suite](../05_evidence/20261122T005136Z_5d8d15a-dirty_phase4a-all-tests.txt):
517 passed in 176.97s, no failures/errors/skips/warnings. Original 501 tests
and all engine sources/expected inputs are unchanged; 16 new pipeline tests.
Per-file counts are recorded in AI_LOG.md. All 17 original mutants remain killed
and three A/B stateful machines retain every-event result/book/conservation checks.

[Final smoke verification](../05_evidence/20261122T005130Z_5d8d15a-dirty_phase4a-smoke-verified-final.txt):
216/216 cells OK, all four versions, 15 cases, only M=1000 / seed42. Raw data:
`03_results/runs/20261122T004602Z_5d8d15a-dirty_smoke/` (tests.txt,
verification.json, CSVs, env.json, spec snapshot, cell journals/jobs/logs).
988 raw timing rows, 208 phase summaries and separate instrumentation verified.

[Data manifest](DATA_MANIFEST.json): 114 entries / 105 physical gzip files,
all hashes verified, all generated outside measurement, large data ignored.
[Benchmark plan](BENCHMARK_PLAN.md) records selection fixed before measuring,
boundaries/limits, smoke observations, estimates and exact human long commands.
[Runtime estimate](RUNTIME_ESTIMATE.md) is smoke extrapolation only.

R40-R60 are not complete official-result claims: the full long grid, largest-M
robustness analysis, final B selection, bottleneck report and dashboard remain
pending. No 10k/100k/1M engine benchmark was run in this phase. No fresh-venv
reproduction is claimed. A source-pinned long-run session requires Laurin's
commit and explicit long-run command after review.

## Pre-long-run amendment (2026-11-22, base `6c2a8d1`)

SPEC.md and BENCHMARK_PLAN.md record Laurin's three decisions BEFORE long
measurements. R47/R48/R51 now have a declared baseline deviation: A at 100k/1M
uses one measured trial without warm-up, labelled A: single trial; small A and
all B candidates retain warm-up + five repeats. No previous smoke raw results
are retroactively altered. R33's fallback only allows targeted revisions if
all candidates fail robustness, with the same rules and all violations reported.

[Full suite](../05_evidence/20261122T011345Z_6c2a8d1-dirty_phase4a-amendment-all-tests.txt):
531 passed in 181.67s, no failures/errors/skips/warnings. Original 501 engine
tests and the original 16 pipeline cases remain; 14 schedule/reporting cases
were added with red/green evidence. B's repeat protocol remains unchanged.
Full large engine measurements, candidate selection and dashboard stay pending.

R37/R56/R57/R62/R63/R67: revised runtime/storage JSON and MD under
`00_docs/phase4_plan_20261122/`, updated wrapper/README, root CSV commit policy
and local-only jobs/journals/logs via .gitignore. Approximate full coverage:
2,032 workers / 6,112 files, only about 16 committed root artifacts. Already
tracked historical smoke internals are preserved, not untracked.
[Archive evidence](../05_evidence/20261122T011203Z_6c2a8d1-dirty_phase4a-archive-smoke.txt)
confirms the superseded smoke's 663 files / 6,847,781 bytes and every sha256
preserved under scratch. No deletion, long run or git mutation was executed.

## Post-attack B3r checkpoint (2026-11-22, base `958c8b4`)

This extends the earlier four-version rows to A/B1/B2/B3/B3r without changing
their contract assertions or independent expected files. Earlier phase counts
remain historical. [Final standard suite](../05_evidence/20261122T115638Z_958c8b4-dirty_b3r-all-tests-final.txt):
**644 passed in 200.94s**, no failures/errors/skips/warnings.

| Requirements | Current status / evidence |
|---|---|
| R1, R3-R26, R28-R29 | All five registered implementations pass 64 identical contract checks each (320); all18 own expected files also run event-by-event through B3r plain/counted internals. Original expectations and engine A/B1/B2/B3 sources unchanged. |
| R27, R36 | B3r/replay red90 failures -> targeted green368. New pipeline red12 -> green42; catalog idempotence red1 -> green13. Existing test sources/expected data unchanged. |
| R30 | Four stateful A-vs-B differentials, now including B3r, configured 300 examples/ 60 steps, compare results/books/invariants/conservation after every event. |
| R31, R33, R35 | SPEC D1 code argument: per-side heap bound 2*L+32, expected amortized rebuild O(1) per staled key, logical single-event O(L+S), with hash/retained-capacity/GC qualifications. No measured B3r speed/byte bound claimed. |
| R32, R34, R36 | B3r inherits B3's matching/FIFO/validation and changes only per-side heap rebuild. No B1/B2/B3 edits or plain-dict FIFO. |
| R37 | AI_LOG/SPEC record D1-D4, threshold example/brief inconsistency, attributed independent review and the catalog startup defect corrected with a regression. |
| R38-R39, R67 | New own generator/data are labelled added after Phase 4; POST_ATTACK_MANIFEST.json records134 entries / 125 gzip files, commands and sha256. Original manifest remains unchanged; generated files ignored. |
| R40-R45, R60 | Original Phase 4 run preserved. B3r original-grid and new-case long measurements remain pending. D2 saturation is a weakness; D4 additions cannot retroactively change B1/B2/B3 exclusions. Deep_book borderline3.05/2.80 recorded honestly. |
| R43, R47-R50 | New prefilled cases construct/reset each trial, timing query suffix separately; A baseline deviation unchanged, all B candidates warm-up+5. Existing primary protocol tests preserved. |
| R45-R46, R54 | Trap regressions use scan counters and forbid levels-dict iteration; both planted trap variants are killed by AssertionError. Real scan/cancel ratios 1.602 and 0.397, <=2. Drift bounds tested on both sides. Traced B3r growth studies await tonight. |
| R52-R53 | Small worker tests cover all four modes, including prefill/query separation, max_ns for one-event spike and complete construction+query memory curves; no long latency/memory result claimed. |
| R56-R57, R62-R63 | Tonight wrapper/plan preview: 15 batches,1296 workers; B3r all parts, old B variants only new cases, then A. Source/limits/data metadata and local-internals policy retained. Full saved B3r results still pending. |
| R65 | README documents B3r/replay/BOM/unbounded integer behavior and CPython hash attack numbers, with no price cap. Clean-venv and final report remain future work. |

Fresh original ATK-01 reproduction:
[4 passed](../05_evidence/20261122T120050Z_958c8b4-dirty_atk01-original-reproducer-fixed.txt),
using --runxfail to disable its archived strict-xfail marker without editing
the attack test. The default suite remains pytest.ini's complete 02_tests path.

Primary evidence links: [rebuild trap mutation probes](../05_evidence/20261122T115730Z_958c8b4-dirty_b3r-trap-mutation-probes.txt),
[new input preparation](../05_evidence/20261122T115051Z_958c8b4-dirty_post-attack-data-preparation.txt),
[nightly plan only](../05_evidence/20261122T115548Z_958c8b4-dirty_b3r-night-plan-only.txt).
No long engine measurements or final B3r selection have been executed here.

Additional verification: the unchanged committed attack suite was run with
`python -B -m pytest -p no:cacheprovider 07_attack -q --runxfail` (full command
in evidence): [1419 passed in 69.78 s](../05_evidence/20261122T120132Z_958c8b4-dirty_b3r-committed-attack-suite.txt).
--runxfail disables the archived strict ATK-01 markers, not assertions.
[Final scope/data/plan review](../05_evidence/20261122T120353Z_958c8b4-dirty_b3r-final-review.txt)
checks every standard XML case, protected paths, byte-stable real manifest
verification, all 20 input hashes and the 1296-worker nightly ordering.

## Optional B3r_fast gate (2026-11-22, base 3c95836)

The completed B3r session is committed; B3r stays final. SPEC/AI_LOG record the
acceptance rule BEFORE any fast benchmark: all correctness gates, at least 10%
lower official 100k geometric-mean time, no matched replay median more than 5%
higher. Correctness alone cannot promote the optional variant.

| Requirements | Optional variant evidence |
|---|---|
| R1, R3-R26, R28-R31, R36 | Every existing contract, own expected dataset, internal check, mutant control and A-vs-version stateful test runs for the registered fast class, unchanged. Added G2 covers every event of complete supplied/own files and all 32 attack families, counted/uncounted, plus B3r-vs-fast stateful. |
| R6, R15-R17 | User-authorized separate fast validator: ordinary builtin fields take a direct path, all other cases fall back to unchanged validate. G1: 1,797,952 return/callback-trace comparisons plus Hypothesis arbitrary JSON-like values, including bool/subclasses/missing/pairs and expected_type variants. |
| R27, R36-R37 | Stub red 192427Z -> G1/small-G2 green 192534Z. Callback retry red 193456Z -> green 193532Z. Saved-result boundary tests red 193053Z -> green 193351Z (10 pass). No old test/expected source changed. |
| R33-R35 | Same B3r constructor/records/deques/heaps/rebuild rules. Inline process dispatch and local bindings only; complexity/cleanup/memory limitations unchanged. No measured speedup or adoption claim. |
| R40-R57, R62-R63 | Plan-only previews 236 B3r_fast workers on official/post_attack. Stored B3r session is the reference. Same full timing protocol and separate diagnostics. Require57 timing pairs,15 score cells, matching inputs, complete repeats and source-bound correctness proof. |
| R65 | README/BENCHMARK_PLAN give the rule, scope/reference, exact preview/start commands and incomplete-data rejection. B3r remains final until performance evidence qualifies fast. |

[Full standard suite](../05_evidence/20261122T193624Z_3c95836-dirty_b3r-fast-all-tests.txt):
**848 passed in 648.79s**. This includes both required stateful gates and the
complete every-event comparisons; all original 17 mutants remain killed.
[Committed attack suite](../05_evidence/20261122T193657Z_3c95836-dirty_b3r-fast-attack-suite.txt):
**1697 passed in 79.31s**, including fast, --runxfail for archived fixed-bug markers.
[Gate sensitivity](../05_evidence/20261122T194115Z_3c95836-dirty_b3r-fast-gate-mutants.txt)
kills three temporary in-memory faults (unsafe bool validation, changed result
key order, counter drift), separately from the original 17 mutants.
[Plan-only](../05_evidence/20261122T193658Z_3c95836-dirty_b3r-fast-plan-only.txt):
official 180 +post_attack 56, only fast, no engine execution. Source/standard/
attack proof hashes are in `05_evidence/b3r_fast_correctness.json`.

## Binding rematch protocol (Laurin, 2026-11-22, BEFORE measurement)

R37/R47/R56/R57/R60/R65: SPEC, BENCHMARK_PLAN and AI_LOG record the session-noise
finding and corrected single-attempt method. The old cross-session rejection
and data remain unchanged. Same-session B3r/fast, timing only, global alternating
case order; warm-up+5. Require current correctness gates, 15 official 100k
geometric-mean ratio <= 0.90 and every workload x size median(seed ratios) <= 1.05.
No further re-measurement; no result claimed before the single actual attempt.

Implementation: bench/rematch_fast.ps1, minimal explicit runner interleaving,
and assess_rematch for atomic attempt claim and immutable JSON/Markdown output.
Synthetic checks cover numerical/statistical boundaries, ordering, default-path
preservation, incomplete/mismatched observations, duplicate claim and binding
decision preservation. No existing engine/test/expected file changes.
Plan-only: 114 timing workers (90 official+ 24 post_attack), 57 pairs, offsets 0/45;
no actual attempt consumed. Fresh current-source gates are recorded separately
at `05_evidence/b3r_fast_rematch_correctness.json`; old proof stays historical.

Fresh evidence: [848 standard tests](../05_evidence/20261122T205138Z_ddbc434-dirty_rematch-all-tests.txt),
[1,697 attack tests](../05_evidence/20261122T205139Z_ddbc434-dirty_rematch-attack-suite.txt),
[complete preview](../05_evidence/20261122T205140Z_ddbc434-dirty_rematch-plan-only-final.txt),
[synthetic binding checks](../05_evidence/20261122T205047Z_ddbc434-dirty_rematch-binding-checks.txt)
and [final source/proof/order review](../05_evidence/20261122T210349Z_ddbc434-dirty_rematch-final-review.txt).
Implementation/verification complete; actual binding measurement and performance
decision remain pending. The single real attempt has not been claimed.

## Final registry checkpoint (2026-11-23, base `dd88f22`)

The preceding rematch checkpoint is historical: Laurin committed the completed
binding rejection and FINAL_SELECTION.md. B3r is final. This task changes
registry/CLI selection and naming only, with no new measurement or engine change.

| Requirement | Current implementation and verification |
|---|---|
| R1, R7-R9, R33 | METHODS B and B3r both reference OrderBookB3r; B1 directly references the original OrderBookB. All seven names are accepted by replay. test_final_version checks exact registry and factory identity; test_replay checks plain/gzip CLI output and rejection order for every name. |
| R26, R28-R30 | B/B3r equality after every event on the worked example and all 18 own datasets, counters off/on; results, key order, snapshots, best quotes and counters compared. Own independent expected files are also checked. All registry names retain contracts, internals and A differential coverage. |
| R27, R36 | Red: 24 failures for the old alias and counter mismatches; targeted green: 129 passed. No expected result, contract assertion or engine algorithm changed. B1-specific tests/factories use B1 explicitly. |
| R37, R56-R57 | SPEC/README Final Version B map/commands, AI log and final selection follow-up updated. Historical B-labelled results retain their recorded labels/commit meaning; no changes under 03_results. |

Evidence: [alias red](../05_evidence/20261123T161747Z_dd88f22-dirty_final-b-alias-red.txt),
[targeted green](../05_evidence/20261123T161952Z_dd88f22-dirty_final-b-alias-green.txt),
[attack suite](../05_evidence/20261123T162213Z_dd88f22-dirty_final-b-attack-suite.txt)
(1,995 passed in 125.90 s), [full standard suite](../05_evidence/20261123T162212Z_dd88f22-dirty_final-b-all-tests.txt)
(983 passed in 909.96 s) and [final review](../05_evidence/20261123T163814Z_dd88f22-dirty_final-b-registry-review.txt).
Both suites are wholly green, with no skips. The standard run includes 448
contracts (64 per name), 60 final-alias/factory cases, 25 mutant/control cases
(all 17 mutants killed), 32 internal checks and seven stateful machines.
[Verification JSON](../05_evidence/final-b-registry-verification.json) stores
current source and suite XML hashes plus every test-file/class count.
Registry task complete; no measurement or change to the committed selection.

## Phase 5 dashboard checkpoint (2026-11-23, base `87ed911`)

Course README Results and dashboard, lines 124-130, was read and mapped to the
eight-tab updated task. No engine, generator, expected file, dependency pin or
03_results change is part of this phase. External concurrent attack files are
not modified or proposed for this commit.

| Coverage | Dashboard implementation / saved evidence |
|---|---|
| R48-R49, R59 scaling | Official log-log views and measured-range exponents; separate Q7 construction and 10/100/200% sale;1M table, A stops/scope. |
| R33, R37, R59 comparison | Final B3r selection, all explicit historical variants, same-input ratios and reported robustness outcomes; both fast comparisons, binding 0.873 score/1.068 loss displayed unchanged. |
| R51-R52, R59 distributions | Events/replay seconds; actual latency_histogram.csv bins; exact p50/p95/p99/max by type/segment, early/late selections, explicit declared spike. |
| R53-R55, R59 memory | Peaks/includes, insertion curves, final churn state, B3/B3r drift; sampled peak/live normalization labelled. |
| R26-R30, R59 correctness | Committed proof/XML hashes, suites/counts,17 mutant kills, stateful/own/worked checks, per-worker checks.csv, attributed independent reference and attack report. |
| R56-R58, R63 provenance | Each chart/table has source captions and recorded commits; raw repeats/settings/checksums/env; generator commands reconstructed and labelled. Git HEAD blob loading excludes dirty/untracked results. |
| R60 bottleneck | Code excerpts + counts + complexity + measured exponents;500,500 A scans on1k full liquidation and20bn B1 shifts at100k independently cross-checked in audit. |

Targeted evidence: [16 dashboard gates](../05_evidence/20261123T190241Z_87ed911-dirty_dashboard-verified.txt)
and [all-eight-tab numerical audit](../05_evidence/20261123T190442Z_87ed911-dirty_dashboard-values-audit.txt)
with [traceable values](../05_evidence/dashboard-audit.json). Full standard
suite and final protected-file review follow below when complete.

Final fresh evidence: [999 standard tests](../05_evidence/20261123T190332Z_87ed911-dirty_dashboard-all-tests.txt)
passed in 785.23 s, including 16 dashboard cases, all 448 contracts and all 17
mutant kills. [Latest-HEAD dashboard checks](../05_evidence/20261123T191536Z_337cc61-dirty_dashboard-current-head-smoke.txt)
passed 16/16 after the external attack addendum commit. Both suites have no
failures/skips. [Final review](../05_evidence/20261123T191653Z_337cc61-dirty_dashboard-final-review.txt)
and [verification JSON](../05_evidence/dashboard-verification.json) bind source
and suite hashes and verify protected code/data/results. The audit is rerunnable
as `python 04_dashboard/verify_saved.py`; [submission-path evidence](../05_evidence/20261123T191421Z_337cc61-dirty_dashboard-reproducible-audit.txt).
R58-R60 complete in the stated tested coverage. No new measurement or change
to the final selection; unrelated 07_attack work excluded from this checkpoint.

## Pre-report robustness checkpoint (2026-11-23, base `47c0048`)

| Requirement / decision | Implementation and tests |
|---|---|
| R58 / dashboard portability | Git checkout remains the default source. Missing executable or unavailable HEAD selects a rooted disk store with the same allowlist, traversal protection, top warning and unverified provenance captions. Two real temporary submission copies contain no .git/engine code and render all eight tabs in separate processes; missing-checkout/missing-Git modes both tested. |
| R8 / final-B default | No --version instantiates actual OrderBookB3r through registry B; factory spy catches accidental A selection. CLI output/help/default tests, explicit A and all names retained by original tests. |
| R5, R8 / input diagnostics | Physical-line ReplayInputError, one stderr line and non-zero CLI exit, no traceback. Tests cover malformed JSON, invalid UTF-8, UTF-16 BOM/LE/BE and second BOM, plain/gzip, blank lines, valid prefix output and TextIO read-ahead. |
| R9, R15, R36 / valid behaviour | No engine/shared-validator/existing assertion/expected/data/result changes. Positive cases retain leading BOM, CRLF/bare CR, gzip, 5,000-digit quantities and a BOM inside a JSON string. Semantic event rejections remain normal JSON output. |

Test-first [red](../05_evidence/20261123T193220Z_47c0048-dirty_robustness-red.txt):
24 failed /4 passed under the old behaviour. [Targeted green](../05_evidence/20261123T193940Z_47c0048-dirty_robustness-targeted.txt):
93 passed (28 new regressions plus all existing replay/dashboard cases).
[Attack suite](../05_evidence/20261123T194432Z_47c0048-dirty_robustness-attack-suite.txt):
1,995 passed in 95.10 s. Full standard suite/final review follow below.

Fresh completion evidence: [1,027 standard tests](../05_evidence/20261123T194432Z_47c0048-dirty_robustness-all-tests.txt)
passed in 713.57 s, including all 28 new regressions, all 16 original dashboard
checks, 448 contracts and all 17 mutant kills. Both suites are nonempty and
wholly green (no skips). [Final review](../05_evidence/20261123T201613Z_47c0048-dirty_robustness-final-review.txt)
and [verification JSON](../05_evidence/robustness-verification.json) record
source/XML hashes and unchanged protected sources/expectations/results. No new
measurements or dependency changes; all three requested fixes complete.

## Phase 5b clarity checkpoint (2026-11-25, base c4cfc25)

| Requirement / requested clarity change | Implementation and evidence |
|---|---|
| R37, R59 / final selection first | Full committed decision in the first tab; CSV-derived candidate geomeans and sourced violations; both original fast outcomes, including the literal-filter qualification. AppTest verifies tab order and complete rendered document. |
| R59 / compact Overview | Three metrics, one 5-by-3 scenario/size table, one chart and cancel_churn loss; links to selection/raw/settings. Ratios are seed medians with conservatively rounded lower bounds. AppTest checks structure and CSV arithmetic. |
| R48-R49, R59 / readable charts | How to read under every chart; axes/units, scale, point aggregation and takeaway. Scaling linear/log-log toggle and labelled dashed slope-1/2 guides; reference math and rendered axis specifications tested. |
| R53-R55, R59 / memory | Independent B3 and other-version panels, separate y-scales, linear/log-y toggle. Stale-key growth/rebuild explained. Exact retained/peak samples unchanged. |
| R51-R52, R59 / latency | Histogram-adjacent ATK-P7 GC explanation (including non-GC allocation costs), same GC policy; distinct algorithmic spike warning/case label with CSV-derived maximum. |
| R56-R59 / raw repeats and settings (S22) | Case/version/phase selector exposes every raw timing row, seconds, marked warm-up, adjacent validated median or A single trial; workload settings include command/parameters, origin, SHA-256 and per-version protocol. |
| R58-R59 / preserved detail and provenance | Original 50-row detail, 1,091-row repeat completeness and 180-row non-OK coverage frames moved unchanged to Method & data; AppTest compares every value. Source captions, missing/stopped/scope labels and no-Git modes retained. |
| R60 / bottleneck | Existing code/counter/complexity explanations retained with new How to read captions; no new performance claim or measurement. |

[Final targeted suite](../05_evidence/20261125T115403Z_c4cfc25-dirty_clarity-dashboard-pass.txt):
49 passed in 47.91 s (21 dashboard plus 28 robustness, including both no-Git
copies). [Standard suite](../05_evidence/20261125T114813Z_c4cfc25-dirty_clarity-all-tests.txt):
1,032 passed in 769.35 s, no skips/failures. The standard run began before final
display/test-adapter cleanup; the final targeted run proves the completed UI.
The unchanged engine contracts, differentials and all 17 mutant kills remain
green. [Nine-tab audit](../05_evidence/clarity-audit.json) and
[final review](../05_evidence/20261125T120134Z_c4cfc25-dirty_clarity-final-review.txt)
trace displayed values, source/XML hashes, counts and protected-file checks;
[verification JSON](../05_evidence/clarity-verification.json) records suite stages.
Earlier audits/results remain intact. No new measurements/data/engine changes.

## Submission workflow/report checkpoint (2026-11-25, base d885f6e)

| Requested task | Implementation / verification |
|---|---|
| R37/R59 / fast in the same comparison | Six candidate table/bar rows. B3r and fast use binding same-session geomeans; older fast row explicitly cross-session. Sourced ratio 0.873, 25/27 faster, 26/27 within bound, 1k loss 1.068; older 0.887 rejection preserved. New AppTest plus all old assertions unchanged. |
| R64 / factual-only report check | REPORT_FACT_CHECK.md lists every old/new/source change; JSON ledger reconstructs the final report exactly from HEAD, proving no additional edits. SPEC invariant/complexity references, paths and commands checked; 91 numeric records from committed results. Correct 17 kills distinguished from two rebuild-trap scenarios. |
| R62/R65 / one-command entry points | run_all.ps1 and run_all.sh, step comments/-m commands, fail-fast, local venv setup, full tests, worked expected-file check, scratch-only 1k smoke and dashboard. NoDashboard options for terminal use. Full opt-in prints estimate/requires confirmation; A scope/protocol retained. |
| R56-R57/R65 / data provenance | submission_tools data uses recorded generator commands; checks source/content hashes, reports archive differences, records actual local hashes; committed manifests untouched. Smoke uses unchanged copied code and existing pipeline; 108 worker/sample checks verified. |
| R65-R66 / Start here | 437 words: one command per OS, outputs/pass count, final B/selection, section-6 headlines/loss/bounds, individual commands, regeneration/checksums, long-run duration/commands, folder map and submitted-commit placeholder. Prior detail retained exactly. |

[Fresh default PowerShell run](../05_evidence/20261125T132117Z_d885f6e-dirty_handoff-run-all.txt):
exit 0; new .venv/install; **1,033 passed in 778.59 s**, worked example OK,
108/108 smoke workers, explicit NoDashboard exit. [Full XML](../05_evidence/handoff-all-tests.xml).
[Bash syntax](../05_evidence/20261125T132027Z_d885f6e-dirty_handoff-bash-syntax.txt):
exit 0. [Final helper smoke](../05_evidence/20261125T144429Z_d885f6e-dirty_handoff-smoke-final.txt):
108 workers plus 108 sample checks, no non-1k worker. This tests the last local
catalog/line-ending handling correction; all outputs stay in ignored scratch.
[Report arithmetic](../05_evidence/handoff-report-check.json) and
[final review](../05_evidence/20261125T150020Z_d885f6e-dirty_handoff-review-final.txt)
verify factual-only edits, exact source preservation, all old assertions,
catalog totals and untouched protected files. [Verification JSON](../05_evidence/handoff-verification.json)
records hashes/counts. No engine/test-expectation/historical-result change,
new long measurement or final-selection reassessment. Bash verified by syntax
only; Full and actual submission remain human actions.

## Primary selection/session-effect checkpoint (2026-11-25, base 5785e9f)

R37/R59: selection now uses five primary-session bars, a six-row blank-safe
table (including the older 0.887 cross-session comparison and the binding
0.873/25-of-27/26-of-27 rejection), and a second grouped primary-versus-binding
chart with ratios above each group. All four run folders/commits remain
explicit. Captions match Laurin's requested text; the obsolete count remark
is gone. No change to stored data, measurements, engines or the final decision.

[22 dashboard tests](../05_evidence/20261125T154659Z_5785e9f-dirty_selection-primary-dashboard.txt)
pass, including actual rendered bar datasets versus independent CSV geomeans,
annotations, table blanks/outcomes/provenance and both captions.
[Two no-Git copy tests](../05_evidence/20261125T155536Z_5785e9f-dirty_selection-primary-portability.txt)
pass. [Saved-file review](../05_evidence/20261125T161049Z_5785e9f-dirty_selection-primary-review.txt)
and [verification JSON](../05_evidence/selection-primary-verification.json) bind
source/XML hashes, all five primary values, both pairs/ratios and the protected
file checks. This is presentation verification, not a new benchmark.
