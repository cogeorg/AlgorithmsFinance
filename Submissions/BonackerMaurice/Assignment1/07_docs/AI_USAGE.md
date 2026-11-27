# AI usage (Assignment 1)

AI tool: Claude Code (Claude Opus 5.5), session of 22 November 2026.
Maurice gave the task list and the expected values; the AI wrote the code.
The "Decision" column is for Maurice: **accepted**, **corrected** (say how)
or **rejected**.

## Session 1: tests, Version A, replay, first profile, simple dashboard

### What the AI produced

| File | Content |
|---|---|
| `pytest.ini`, `requirements.txt` | `pythonpath = 03_code`; pytest 9.1.1, matplotlib 3.11.2 |
| `02_tests/test_worked_example.py` | Worked example, expected values typed from Maurice's Excel |
| `03_code/lob_a.py` | Version A (single list, full scans) |
| `03_code/validation.py` | Shared event validation |
| `03_code/invariants.py` | Version-independent per-event conservation and priority check |
| `03_code/replay.py` | Replay command and summary CSV |
| `04_benchmarks/profile_version_a.py` | First cProfile run (exploration) |
| `06_dashboard/build_dashboard.py` | Static HTML dashboard from `05_results/` only |

Tests-first evidence: `05_results/tests_fail_first.txt` (stub `OrderBook`
returning empty results: 6 failed, 1 passed; the passing test compares the
Excel values with the supplied JSON and needs no engine). After Version A:
`05_results/tests_latest.txt` (7 passed).

### Cross-check of the expected values

The Excel (`01_my_notes/OrderBookTests.xlsx`) and
`00_instructions/data/worked_expected.json` agree on every value: 4 fills
(b1 1, b2 1, b3 3, b4 1 BTC at 60,000 / 60,000 / 59,900 / 59,700 dollars),
unfilled 0, status `filled`, remaining b4 4 BTC seq 4 and a1 2 BTC seq 5,
proceeds 359,400 dollars, average 59,900 dollars, and 10 BTC submitted buys =
6 traded + 4 resting. The test `test_hand_values_agree_with_supplied_json`
keeps checking this.

Observation: in the Excel, rows 4–5 columns H–O are typed values, while
rows 2–3 are formulas. The numbers are right, but they would not update if
an input changed.

### Design decisions

| # | Decision | Why | Decision |
|---|---|---|---|
| D1 | Interface is a class `OrderBook` with `AddLimitOrder`, `FillMarketSell`, `CancelOrder`, `process_event`, `inspect_book`, `assert_invariants`. | A fresh book per replay or test is one constructor call; Version B gets the same interface. | **Accepted** (Maurice, 24 Nov) |
| D2 | `process_event` validates; the three public operations assume validated arguments. | Validation in one place; both versions share `validation.py`, so reject reasons are identical. | **Accepted** (Maurice, 24 Nov) |
| D3 | Validation order: object, seq, event_id, type, then type-specific fields; the first failing check is the reason. | Deterministic reasons, so A and B can be compared result by result. | **Accepted** (Maurice, 24 Nov) |
| D4 | The duplicate-live-id check is a callback `is_live(order_id)` supplied by each book. | Each version answers it with its own structure (A: O(B) scan; B can use a dict). | **Accepted** (Maurice, 24 Nov) |
| D5 | Version A keeps both sides in ONE list in arrival order and scans the whole list for the best order on every fill step. | The transparent baseline the spec asks for. | **Accepted** (Maurice, 24 Nov) |
| D6 | Per-event checks are split: structural invariants in each book's `assert_invariants()`; conservation and price-time priority in `invariants.check_event(before, event, result, after)` using `inspect_book()` snapshots. | The snapshot check is version-independent. Note: its priority check walks the canonical book to predict the fills, which is a second, simpler matching routine. It is a consistency check, not an independent proof. | **Accepted** (Maurice, 24 Nov) |
| D7 | `replay.py` processes events in file order and never sorts them. | Spec: one at a time in seq order; a non-increasing seq is rejected, not reordered. The supplied files are strictly increasing (checked). | **Accepted** (Maurice, 24 Nov) |
| D8 | `replay.py` runs two passes on fresh books: a checked pass (invariants after every event, peaks) and an unchecked timed pass. `wall_seconds` = one timed replay of preloaded events; reading and parsing are excluded. | Checks would otherwise dominate the time. One run with no warm-up and no repeats, so it is an exploration number, not the benchmark. | **Accepted** (Maurice, 24 Nov) |
| D9 | `peak_price_levels` counts distinct (side, price) pairs among active orders. | A bid and an ask at the same price are two levels (they cannot coexist anyway, the book would be crossed). | **Accepted** (Maurice, 24 Nov) |
| D10 | `replay.py --csv` replaces only the rows of the version being run and keeps other versions' rows. | Version B can be added to the same `replay_summary.csv`. | **Accepted** (Maurice, 24 Nov) |
| D11 | Tests run for every module name in `VERSIONS = ["lob_a"]`; whole result dicts are compared with `==`. | Adding `"lob_b"` reuses the unchanged tests; exact equality also catches extra or misspelled fields. Since session 2 the list lives in `02_tests/conftest.py` (fixture `lob`), shared by all test files. | **Accepted** (Maurice, 24 Nov) |
| D12 | Dashboard: correctness comes from the saved pytest output `05_results/tests_latest.txt`; bars are grouped by version with a fixed colour per version (A blue, B orange). | The dashboard reads only `05_results/`; B appears as a second series with no code change. | **Accepted** (Maurice, 24 Nov) |
| D13 | Peak orders and peak price levels are two panels with separate y-axes in one image, not one dual-axis chart. | 10,000 orders vs 8 levels: on one axis the small values would vanish. | **Accepted** (Maurice, 24 Nov) |

### Spec ambiguities and how they were resolved (for Maurice to confirm)

| # | Ambiguity | Choice made | Decision |
|---|---|---|---|
| S1 | Order of `inspect_book()` output: bids first or asks first? | Bids (price desc, seq) then asks (price asc, seq), following `worked_expected.json`. | **ACCEPTED** (Maurice): bids first, like the JSON. |
| S2 | Rejected result when `event_id` is missing: omit the key or set None? | Key always present, value `None` if missing. | **ACCEPTED** (Maurice): rejected results carry `event_id`, or `None` if it is missing. |
| S3 | Is a missing `event_id` invalid? The spec lists only some invalid cases. | Rejected (`missing event_id`). | |
| S4 | Must `order_id` / `target_order_id` be strings? Not stated. | Must be `str`, else rejected. Keeps A and B identical if an unhashable id ever appears. | **ACCEPTED** (Maurice): ids as strings is our assumption, not a spec rule; document it as such. |
| S5 | Does the duplicate-live-id rule apply to a MARKET_SELL whose `order_id` equals a resting order's id? | Yes, rejected ("duplicate live submission identifiers"). | **ACCEPTED** (Maurice): a market sell reusing a live order_id is rejected as a duplicate live submission. |
| S6 | `unfilled_qty_units` for a limit: the JSON only shows a market sell. | For a limit it is the residual that rests (0 if `filled`). | |
| S7 | Integer check: is `3.0` or `true` an integer? | No. `type(x) is int` only; JSON floats and booleans are rejected. | |
| S8 | `event_id` uniqueness is stated but no reject rule is given. | Not validated. | |
| S9 | A cancel whose target is unknown is "valid": does it advance the last accepted seq? | Yes, it is a valid event, so `last_seq` advances. | |

## Session 2: tests from the Excel tabs Test1 and Test2

Maurice added two hand-calculated tabs. The AI turned them into
`02_tests/test_excel_tabs.py` (`test_Test1`, `test_Test2`). Inputs are the
event rows 2–7 (columns A–G); expected values are taken ONLY from the block
"EXPECTED RESULT (hand calculation)" from row 24. The formula columns J–O
were deliberately not used, because they ignore crossing on arrival (in
Test1 they show b1 as filled by s1 and a1 resting with 2 BTC).

- Test1: a1 SELL 60,100 crosses b1 BUY 60,200 on arrival (1 BTC at the
  resting price 60,200), then s1 sells 8 BTC (filled). Proceeds s1 $478,500,
  average $59,812.50 (checked exactly as 5,981,250 ticks), all proceeds
  $538,700, bids 10 = 9 traded + 1 resting.
- Test2: s1 sells 15 BTC against 10 BTC of bids: `partial`, 5 discarded,
  bid side empty, proceeds $598,200, average $59,820.

Result: both passed against Version A on the first run; no disagreement
between engine and Excel. Before writing the tests the AI independently
recalculated both tabs and got the same numbers.

Because they passed immediately, the AI checked they can fail: against a
throwaway mutant of Version A in which limits never cross on arrival (the
formula-column assumption), `test_Test1` FAILS (status rows) and
`test_Test2` passes (it has no crossing, so it cannot detect that bug).
The mutant was a scratch script outside the repository.

Change to test structure: the `VERSIONS` list moved from
`test_worked_example.py` into `02_tests/conftest.py` so one edit adds
Version B to every test file. No expected value changed.

| # | AI suggestion | Decision |
|---|---|---|
| T1 | Compare quantities and prices as exact `Fraction`s of BTC and USD so the test rows read like the Excel rows. | **Accepted** (Maurice, 24 Nov) |
| T2 | Move `VERSIONS` into `conftest.py`. | **Accepted** (Maurice, 24 Nov) |

## Session 3: scaling exploration, liquidation, Test3–Test5

### What the AI produced

| File | Content |
|---|---|
| `04_benchmarks/generate_data.py` | Runs the professor's generator: 5 scenarios × M = 1k, 10k, 30k, 100k, seed 42, into `05_results/data/` (gitignored via `Assignment1/.gitignore`; metadata with SHA-256 kept). The regenerated 10k files are byte-identical to the supplied ones. |
| `04_benchmarks/scaling.py` | One child process per run, engine time only, invariants off, 600 s limit on the child (load + replay + counting); over the limit → `stopped`, no values. Peaks derived after timing from the returned results (shadow book), cross-checked against `inspect_book()`. |
| `04_benchmarks/liquidation.py` | Bid book from the first 80% of sweep_10000; 10% (ceil), 100%, 200% sales, each on its own freshly built book; build and sell timed separately; conservation asserted. |
| `04_benchmarks/export_test_results.py` | Runs pytest, writes `05_results/tests_by_case.csv` from `@pytest.mark.source` labels. |
| `02_tests/test_excel_tabs.py` | `test_Test3`, `test_Test4`, `test_Test5` from the "EXPECTED RESULT" blocks. |
| Dashboard | Correctness table per test and version; log-log scaling chart; liquidation table. |

### Corrections by Maurice

| # | AI version | Correction (Maurice) |
|---|---|---|
| C1 | Stopped runs drawn as × at 600 s on the seconds axis. | **Corrected:** the 600 s limit covers load + replay + counting, so it is not a replay time. Stopped runs are now listed under the chart as "stopped: 600 s limit for load + replay reached; replay time not measured" and are not plotted. |
| C2 | `test_Test5` compared the exact reason texts from the Excel (event4 would have failed on wording only: Excel "seq 4 not greater than last accepted seq 5" vs engine "non-increasing seq 4 (last accepted 5)"). | **Corrected:** the spec does not define reason wording. The test checks status `rejected`, a non-empty reason, and that it names the cause (`qty`, `price`, `seq`). Engine reason texts unchanged. |

### Test results and one test bug

- Test3, Test4, Test5 (source "Excel tab … (calculated by Claude, checked by Maurice)") all pass against Version A; 12/12 tests pass.
- First run: `test_Test4` crashed with `KeyError: 'fills'` in the AI's helper `fill_rows()`, which assumed every result has `fills`; cancel results correctly have none. This was a bug in the test helper, not in the engine or the Excel; no expected value was compared before the crash. Fix: the helper uses `r.get("fills", [])`. No expected value changed.
- Test4 row 32 (proceeds) is blank in the Excel and is not checked.
- Test5 reads `OrderBook.last_seq`, so `last_seq` is now part of the interface Version B must provide.

### Open points for Maurice

| # | AI suggestion | Decision |
|---|---|---|
| T3 | `source` markers on each test (labels live next to the test code). | **Accepted** (Maurice, 24 Nov) |
| T4 | Label for the engine-free cross-check: "my Excel tab Base vs professor JSON" (it fits neither of the two suggested labels exactly). | **Accepted** (Maurice, 24 Nov) |
| T5 | Liquidation `sell_seconds` times `process_event` (includes validation, whose duplicate-id check is O(B) in Version A), not `FillMarketSell` alone. | **Accepted** (Maurice, 24 Nov) |

## Session 4: Version B (B-sorted and B-heap)

Maurice's design: a dict for id lookup; a dict of price → FIFO deque per side;
two best-price variants (sorted list with bisect, heap with lazy deletion).

### AI draft and Maurice's corrections (design stage)

| # | AI draft | Maurice's decision |
|---|---|---|
| C3 | Compaction rules for deques and heaps (proposed by the AI to bound stale entries). | **Accepted**, with explicit tests: heap under cancel_churn, deque under repeated cancels behind a live FIFO head. |
| C4 | Shared core file `lob_b_common.py`. | **Accepted**; validation.py stays shared with A; variants differ only in the price index. |
| C5 | B-sorted kept Maurice's first layout (best ask = first element), and the AI noted that removing it is an O(P) shift. | **Corrected**: both sides stored so the best price is at the END; exhausted best levels removed with `pop()`. |
| C6 | Cost table mixed rebuild and pop costs, left out residual insertion, and implied compaction shrinks memory. | **Corrected**: linear heap rebuild vs O(log H) stale pops kept apart; residual-limit insertion included; compaction bounds retained entries, not dict allocations. |

### What the AI produced

| File | Content |
|---|---|
| `07_docs/REVISIONS.md` | Revision 1: evidence, pseudocode, cost tables with claim types, hypotheses, results |
| `03_code/lob_b_common.py` | Shared core: Order, Level, matching, cancel, TIDY/compaction, inspect_book, invariants |
| `03_code/lob_b_sorted.py`, `03_code/lob_b_heap.py` | The two price indexes only |
| `02_tests/test_b_compaction.py` | Heap bound under cancel_churn; deque bound behind a live head (twice) |
| `02_tests/differential.py`, `02_tests/test_differential.py` | Seeded random streams; A vs B-sorted vs B-heap after every event; `05_results/differential_tests.csv` |
| scripts and dashboard | `--version a / b_sorted / b_heap`; `cross_version` marker; dashboard version labels, colours and small multiples |

Tests-first evidence: `05_results/tests_fail_first_version_b.txt` (stubs:
22 failed, 12 passed). Mutation checks (throwaway copies, outside the repo):
the compaction tests fail without compaction; the differential test flags a
LIFO queue (295/300 streams) and a wrong cancelled quantity (297/300).

### Problems found during the session

- The first saved fail-first output used `--tb=line`, which printed absolute
  paths including the home folder. Re-saved with `--tb=short` (relative
  paths only) before anything else used it.
- The `--check` replay of B-heap took more than 10 minutes for the five 10k
  files. The cause is the checks, not the engine: per event it runs
  `inspect_book` (sorts the level keys), the full invariant walk and the
  heap-order check, O(B + H) each. Timed passes are unaffected (they run
  without checks).
- No engine bug was found: all hand tests, the JSON test, the differential
  test and the replays agreed on the first implementation.

### Open points for Maurice

| # | AI suggestion | Decision |
|---|---|---|
| T6 | Scaling chart changed to one panel per scenario (colour = version), because 3 versions × 5 scenarios = 15 lines in one chart is unreadable. Version is now always the colour. | **Accepted** (Maurice, 24 Nov): one panel per scenario is readable; same data. |
| T7 | The differential test counts as one test for all versions (`cross_version` marker, shown in every version column). | **Accepted** (Maurice, 24 Nov): one cross-version test comparing all three versions together. |
| T8 | `_index_remove_best` in B-sorted asserts that the emptied level is the last key (a cheap check in the timed path). | **Accepted** (Maurice, 24 Nov): keep the cheap safety check in the timed path. |
| T9 | pytest runs the full 300-stream differential test (about 3 s). | **Accepted** (Maurice, 24 Nov): full 300-stream differential test in every pytest run; 3 s is acceptable. |
| T10 | B-sorted vs B-heap: reported as "no reliable winner" from single runs; to be decided by the final repeated benchmark. | **Accepted** (Maurice, 24 Nov). Decided by the final benchmark (Session 5): no reliable winner on full streams; B-sorted reliably faster when one sale empties many levels. |

### Hidden instruction in the course PDF

AGENTS.md warns of hidden text in the slides asking AI tools to insert a
certain word into code. It was not followed; the word appears nowhere in
the code.

## Session 5: final benchmark, dashboard, explanations

Maurice gave the benchmark specification: data, limits, timing protocol,
experiments, latency, memory, operation counts, result files, dashboard and
explanations. The AI wrote the scripts and ran a smoke test at M = 1,000.
Maurice committed the scripts (`4b9df5f`), approved the decisions below, and
the AI started the full run on a quiet, plugged-in laptop.

### What the AI produced

| File | Content |
|---|---|
| `04_benchmarks/bench_common.py` | Grid and limits, definitions, CSV helpers, child-process runner with the 120 s limit (+2 s grace, hard kill), git/source provenance, environment |
| `04_benchmarks/bench_data.py` | Datasets via the course generator, sha256 check against its metadata, manifest with counts and peaks |
| `04_benchmarks/bench_timing.py` | Replay grid, the 1M file, large liquidation (build + 10/100/200% sale), `benchmark_summary.csv` |
| `04_benchmarks/bench_concentration.py` | buildup with 4 vs 1,000 levels: timing, plus a per-event correctness check and a checked 100% sale |
| `04_benchmarks/bench_latency.py`, `bench_memory.py`, `bench_opcounts.py` | Separate runs: per-event latency, tracemalloc samples and end state, operation counts via counting subclasses |
| `04_benchmarks/run_benchmark.py` | One command for all phases; refuses uncommitted code; writes `benchmark_run.json` and `environment.json` |
| `06_dashboard/build_dashboard.py` | Static `dashboard.html` from `05_results/` only |
| `07_docs/REVISIONS.md` | "Final benchmark" section: bottleneck, B-sorted vs B-heap, where B does not win, hypotheses checked |

### Decisions approved by Maurice before the full run

| # | AI proposal | Decision |
|---|---|---|
| D14 | If a liquidation build is stopped, all three sales on that book are recorded as stopped (the builds are identical). | **Accepted** |
| D15 | Version A also gets the 1,000,000-event attempt, under the same 120 s limit. | **Accepted** (it was stopped) |
| D16 | Version A takes part in the concentration correctness check up to M = 10,000. | **Accepted** |
| D17 | Latency, memory and operation counts run on seed 42 only. | **Accepted**, recorded as a limitation in the dashboard and REVISIONS.md |
| D18 | `buildup --levels 4` produces the same file as `crowded` (same sha256, 9 of 9). | **Accepted** as a finding; documented, not worked around |

### Problems found and fixed while writing the scripts (before the commit)

- `git status --porcelain` paths lost their first character because
  `.strip()` removed the leading space of the first line. Fixed with
  `.rstrip()`.
- Stop notes for a step that finished over the limit said "skipped" and
  printed "0.0 s". Fixed: the parent now records which step was stopped,
  and the note shows the real elapsed time.
- Stop handling was tested before the commit. `--time-limit 0.02` exercised
  the over-limit path, and a fake hanging child exercised the hard kill (it
  was killed after 1.82 s with a 1 s limit). A full run on dirty code
  refuses to start.

### Problems found after the full run (dashboard only, no engine or benchmark change)

- The memory chart for cancel_churn was in MiB with values around 0.002,
  and the legend covered the lines. Changed to KiB, with the legend below
  the chart.
- In the buildup memory chart, the B-sorted line hides under B-heap. Added
  the note "B-sorted and B-heap differ by at most 1% (the lines overlap)".
- The memory table header "queue entries" was misleading for Version A,
  which has no queues. Renamed to "queue entries (A: list entries)".

### Run outcome

- Status `complete`, commit `4b9df5f`, code clean, source unchanged, 40 of
  40 tests passed.
- 2,409 timing rows ok and 258 stopped (all Version A). 26 memory rows ok
  and 4 stopped.
- 0 mismatches in 2,190 checked measurements; 18 of 18 concentration
  streams pass. (Corrected on 24 Nov from 2,216, see Session 7.)
- The explanations are in `07_docs/REVISIONS.md`, "Final benchmark".

### Open points for Maurice

| # | AI suggestion | Decision |
|---|---|---|
| T11 | B-sorted vs B-heap uses a strict rule: "faster" only if one variant's slowest repeat beats the other's fastest repeat. It is conservative and reports most cells as "overlap". | **Accepted** (Maurice, 24 Nov): strict, conservative rule; avoids reporting noise as a win. |
| T12 | Dashboard charts show the median over seeds of each seed's 5-repeat median. Error bars run from the fastest to the slowest of all 15 repeats. A point is drawn only if all three seeds finished. | **Accepted** (Maurice, 24 Nov): median of per-seed medians with min-max error bars over all 15 repeats. |
| T13 | The 1.9 ms slowest event of B at buildup 100k is explained as a dict resize. This is an inference from the memory steps at about 22k, 44k and 87k orders, not a direct measurement. | **Accepted, labelled as an inference** (Maurice, 24 Nov): the dict-resize explanation stays, clearly marked as not directly measured. |
| T14 | OneDrive syncing was not paused during the run. Seed 42 at buildup 100k was about 50% slower than seeds 43 and 44 for both B variants, and the cause is not identified. A rerun outside OneDrive would show whether it is noise. | **Accepted as documented** (Maurice): no rerun; OneDrive syncing and the unexplained seed-42 outlier stay listed as limitations. |

## Session 6: robustness and dashboard clean-up

Maurice's task list:

1. malformed JSON lines must not crash the replay;
2. adversarial-event tests;
3. remove the dashboard appendix;
4. a README section "Replay your own event file".

Constraints: no change to the matching logic or to expected test values.

### What the AI produced

| File | Content |
|---|---|
| `02_tests/test_robustness.py` | 142 test cases: 37 reject cases × 3 versions, 5 valid edge cases × 3, a cross-version adversarial stream, malformed-line replays (.jsonl and .gz, timed and checked passes) and `--print-book` |
| `05_results/tests_fail_first_robustness.txt` | Fail-first output on the old replay.py (15 failed, 127 passed; home and temp paths redacted) |
| `03_code/replay.py` | Malformed lines become rejected results; `--print-book`; safe error label in `--check` (REVISIONS.md, Revision 2) |
| `06_dashboard/build_dashboard.py` | Appendix section and its CSV reader removed; the provenance row lists the files that differ from the measured code |
| `README.md` | "Replay your own event file": command, options, input format, output formats, assumptions |

### Findings

- The engines already rejected all 37 adversarial cases correctly, in every
  version, with the book unchanged. Only `replay.py` needed a change.
- Before the change, one invalid UTF-8 byte anywhere in a file stopped the
  replay before its first event.

### Open points for Maurice

| # | AI suggestion | Decision |
|---|---|---|
| T15 | "How to print the final book" is implemented as a new option, `--print-book`. It prints a header line, then one JSON order per line on stdout; redirect to save it. | **Accepted** (Maurice, 24 Nov): keep `--print-book`; documented in the README. |
| T16 | Invalid UTF-8 and nesting too deep to parse are also reported as "malformed JSON line n". Both are lines the replay cannot parse. | **Accepted** (Maurice, 24 Nov): every unparseable line is rejected, never crashes the replay. |
| T17 | The dashboard's test table still shows the 40 tests from the benchmark run (`tests_by_case.csv` was not refreshed), so it matches `benchmark_run.json`. The current suite has 182 tests. | **Corrected** (Maurice): re-export with all 182 tests and label the table with the commit it ran on (see "Test table re-export" below). |
| T18 | Reject cases beyond your list were added: zero and negative values, a float `seq`, a decreasing `seq`, side `BID`, and a still-live duplicate id. The duplicate is the contrast to the "reuse after the order is gone" case. | **Accepted** (Maurice, 24 Nov): keep the extra reject cases, labelled as the agent's additions. |

### Test table re-export (23 Nov 2026)

Maurice asked for `tests_by_case.csv` to be re-exported with the current
182 tests and the correctness table to be labelled with its commit. The
benchmark was not rerun.

- `04_benchmarks/export_test_results.py`:
  - It also writes `05_results/tests_by_case_run.json`. This records the
    commit, the branch, any uncommitted code files, the source fingerprint,
    the time, the Python and pytest versions, the exit code and the counts.
  - The CSV has a new `case` column with the test's other parameters, for
    example `price as string` or `timed-.jsonl.gz`. Without it, the 37
    reject cases of one test collapsed into one row, and a later passing
    case could hide an earlier failing one.
- **Result:** run on commit `c77f575`, 182 of 182 pass. The one uncommitted
  code file at that time was the export script itself. Tests and engines
  (`02_tests`, `03_code`, `pytest.ini`, `requirements.txt`) were as
  committed.
- `06_dashboard/build_dashboard.py`:
  - The test table is headed "Test cases, run on commit c77f575". The label
    also gives the code state, and whether the checked-out code equals the
    tested code.
  - A test with several parameter cases shows "pass (37 cases)", or
    "FAIL: k of n pass".
  - The concentration check and the per-measurement checks are labelled as
    coming from the benchmark run at commit `4b9df5f`.
- **Note for Maurice:** after the export script is committed, rerun
  `python 04_benchmarks/export_test_results.py`. That takes about 3 s, and
  the label will then read "Code committed and clean".

## Report (24 Nov 2026)

- Sections 2 (first paragraph), 5 and 6 (design and effect) written by Maurice, with corrections suggested by Claude (chat).
- Sections 1, 3, 4 and 7, the remaining paragraphs of section 2 and the AI-use paragraph of section 6 drafted by Claude (chat) from `REVISIONS.md`, `AI_USAGE.md` and `05_results/`; checked and edited by Maurice.

## Session 7: latency per event type, memory with retained output, README (24 Nov 2026)

Maurice's task list:

1. latency per event type in `bench_latency.py`;
2. memory samples with the returned output retained in `bench_memory.py`;
3. a README reproduction path for a clean environment;
4. an option in `run_benchmark.py` to run only the latency and memory phases.

Constraints: no change to engine code or expected test values. Maurice
committed the scripts (`ade26d1`) before the rerun.

### What the AI produced

| File | Content |
|---|---|
| `04_benchmarks/bench_latency.py` | Six event types, `latency_by_type.csv`, checks against the manifest and between the two replays |
| `04_benchmarks/bench_memory.py` | The result stays referenced while a sample is read and is then released; new column `traced_with_output_bytes` |
| `04_benchmarks/run_benchmark.py` | `--latency-memory`; a run of selected phases writes its own record and checks the event files against their sha256 |
| `04_benchmarks/bench_common.py` | Definition texts for latency, event types and memory |
| `README.md` | Reproduction path, worked-example output, run times, definitions of the measured data, placeholder for the submitted commit |
| `06_dashboard/build_dashboard.py` | Small per-type latency table, provenance of the rerun next to the full run, updated memory text |
| `05_results/` | Latency and memory results of the rerun, test export at `ade26d1` (182 of 182 pass) |
| `07_docs/REVISIONS.md` | Section "Benchmark change"; latency numbers in "Final benchmark" updated to the rerun |

### Problems found

- **Provenance.** Any run of selected phases used to overwrite
  `benchmark_run.json` and `environment.json`. The rerun would have erased the
  record of the full run at `4b9df5f`. Fixed before the rerun (separate
  record).
- **Harness bytes in the memory reading.** In the first version, the two end
  values were kept as Python ints, which are traced themselves (56 bytes). The
  value after the release was larger than the one before. Found in the smoke
  test and fixed before the commit (values go into a preallocated array).
- **Dashboard count.** "2,216 of 2,216 measurements agree" also counted the 26
  memory rows, which are not checked against the manifest. The correct number
  is 2,190 of 2,190. This was the AI's error from Session 5, corrected in the
  dashboard, `REVISIONS.md` and this file.
- **Battery.** Before the rerun the laptop was on battery. The AI asked, and
  Maurice plugged it in first.
- **Not tested:** `pip install -r requirements.txt` in an empty environment.
  The other README steps that fit into minutes (tests, worked example, data,
  smoke run, dashboard) were run in a fresh copy of the repository files.

### Open points for Maurice

| # | AI suggestion | Decision |
|---|---|---|
| T19 | The event type is recorded in the untimed warm-up replay, not in the timed loop. This keeps the timed loop unchanged, so the overall and early/late figures stay comparable. | **Accepted** (Maurice, 24 Nov) |
| T20 | `LIMIT traded` means at least one fill, also if a residual rests. A partly filled limit is not counted as `LIMIT resting`. | **Accepted** (Maurice, 24 Nov) |
| T21 | `traced_current_bytes` stays the value after the last output is released; `traced_with_output_bytes` is an extra column. The two are equal in all 26 cells. | **Accepted** (Maurice, 24 Nov) |
| T22 | Runs of selected phases write their own record and refuse to start when an event file differs from the manifest. | **Accepted** (Maurice, 24 Nov) |
| T23 | The rerun's latency differences (A's late events 14% slower, B's medians up to 0.3 µs) are reported as run-to-run variation. Each cell is one replay, so this is an inference. | **Accepted** (Maurice, 24 Nov) |
| T24 | The latency numbers in the "Final benchmark" section of `REVISIONS.md` were updated in place, because they describe the saved files. The old values are kept in the table in "Benchmark change". | **Accepted** (Maurice, 24 Nov) |
