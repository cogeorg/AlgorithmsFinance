# AI log

Tool: Claude (Claude Opus 5.5 in Phases 0-1, Claude Sonnet 5.5 from Phase 2), used as a tutor and coding assistant. Bastian sets the
specification decisions, the order of the phases and reviews every step. This log records
what was accepted, corrected or rejected, with evidence (commit hashes, test output).

## Phase 0: setup and specification

| Suggestion | Decision | Reason / evidence |
|---|---|---|
| Folder `Submissions/BundschuhBastian/Assignment1/`, same conventions as the lab (venv, pytest.ini, AI log) | accepted | course README; lab submission |
| `SPEC.md` with decision IDs D1-D19 and fixed reason codes, so A and B return identical results | accepted by Bastian | needed for exact A-vs-B comparison |
| D1: `bool` and float are not integers (`type(x) is int`) | accepted by Bastian | `isinstance(True, int)` is True in Python |
| D5: duplicate live ID check also for MARKET_SELL | accepted by Bastian | spec says "duplicate live submission identifiers" |
| Record decompressed sha256 in addition to the .gz sha256 | accepted | regenerating `mixed` seed 42 with Python 3.13 / zlib-ng gave a different .gz hash but identical decompressed content |

## Phase 1: tests first

Bastian's instruction: no "elegant" tests; concrete edge cases that could crash the code.

| Suggestion | Decision | Reason / evidence |
|---|---|---|
| `tests/helpers.py::step()`: after EVERY event check no mutation of the caller's event, I1-I3 (not crossed, qty > 0, id once, canonical order, best bid/ask agree), result keys, I4-I7 conservation, price-time order of fills | accepted | uses only the public interface, not `lob.common`, so shared-code bugs cannot hide |
| 86 bad events (non-dict input, `None`, `True`, `1.0`, `nan`, `inf`, unhashable lists/dicts as `type` / ids, lower-case side, missing fields), each sent into a book where a wrong accept WOULD trade | accepted | a missing check shows up as a changed book, not only a wrong status |
| D9 order tests (several errors in one event) | accepted | A and B must report the same reason |
| Hand-calculated matching/cancel cases incl. long queue (1000 orders, ids counting down), stale best price after emptying a level, cancel head/middle/tail, churn, huge ints | accepted | list in README "Tests" |
| Supplied-file tests with outcomes derived from `generate_orders.py` | corrected | first draft claimed the last `sweep` sale is `partial`. Checking the file showed the earlier sells (414,709,280,000 units) exceed all bids (205,760,000,000), so the last sale is `unfilled`. Test now computes this from the file |
| Red run against stubs | accepted | 328 tests: 2 passed (reader, implemented in Phase 0), all other failures/errors are `NotImplementedError` only: `docs/test_logs/phase1_red.txt` |
| Cross-check of the hand-calculated expected values with a throwaway naive engine kept OUTSIDE the repo | accepted | catches arithmetic slips in the tests before Phase 2; all 328 agreed. It is not a test oracle: no expected value was copied from it |

## Phase 2: Version A

| Suggestion | Decision | Reason / evidence |
|---|---|---|
| Version A as one list of `[id, price, qty, seq]` per side, every lookup a scan; shared `validate()` in `lob/common.py` | accepted | matches the agreed design; expected cost O(B) per insert and cancel. Commit 22b3da0 |
| First check of "all A tests pass" with `pytest -k "not B"` | corrected | `-k` is case-insensitive and also matched names such as "book", so it deselected 278 of 328 tests and only 50 ran. Re-checked by listing every failure and error: none outside `[B...]`; 163 `[A...]` tests passed |

## Phase 3: Version B and speed

Bastian's rules: correct B first (commit before optimizing), then one change at a time with a
cProfile first and before/after timings on `mixed` and `buildup` at 100,000 events, all tests green,
each step in `REVISIONS.md`.

| Suggestion | Decision | Reason / evidence |
|---|---|---|
| B = per side `price -> OrderedDict(order_id -> [qty, seq])`, sorted price list (asks stored as `-price`), index `order_id -> (is_bid, price)`, empty levels removed at once | accepted | 333 tests pass; replay output equals A on all five supplied 10,000-event files (2ef6e65) |
| `OrderedDict` instead of a plain dict for the FIFO queue | accepted (my choice, not in SPEC) | plain dict keeps deleted slots at the front, so finding the oldest order can get slow |
| First timing method (`gc` on, 5 repeats, before/after run in separate processes) | corrected | repeats ranged 0.26-0.36 s; a 12% gain was invisible. Replaced by `tools/ab_timing.py`: interleaved before/after, `gc` off during timing, 11 repeats, median, output compared |
| 1: `is_valid_fast()` in `common.py`; falls back to the reference `validate()` for the reason | accepted | mixed -12.6%, buildup -8.9%. Fuzz test `tests/test_validation_fast.py` checks it never accepts what `validate()` rejects (741407e). This touches shared code that CLAUDE.md calls the only guard: please review |
| 2: skip `_take` when the order cannot cross; inline `add` | accepted | -4.0% / -9.0% (e49a5ea) |
| 3: iterate the level instead of `next(iter(...))` | rejected | +0.5% / -1.2%, inside noise; reverted |
| 4: pass the order index (container) to `is_valid_fast` | accepted | -3.2% / -3.7% (e519381) |
| 5: inline validation into `process()` | rejected | +1.1% / +0.8%. Kept the A-vs-B fuzz test written for it (`tests/test_process_fuzz.py`; all reason codes and statuses occur) |
| 6: heap + lazy deletion instead of bisect | rejected | +4.5% / +7.0%; 333 tests passed but slower |
| 7: `__slots__` records | rejected | +1.5% / +4.2% |
| 8: tuple records | rejected | -1.1% / -2.4%, inside the ~2% noise |
| Run the other three scenarios at 100,000 events before pushing | accepted (Bastian's request) | all between 0.12 and 0.21 s; A and B identical on `cancel_churn` 100,000 (same checksum) |
| 9 (Bastian's candidate): `deque` of `[qty, seq, order_id]` per price level, lazy cancel (qty 0), live/dead counters, compaction when more than half is dead | accepted (kept), with a disclosed trade-off | buildup -15.9%, sweep -12.9%, crowded -12.5%; mixed +1.0%, cancel_churn +11.6% (interleaved runs, identical output). tracemalloc: no stale growth on cancel_churn; after 49,999 of 50,000 cancels 2.0 MB vs 4.9 MB. 388 tests pass |
| 10 (Bastian's candidate, 45 min limit): pool of up to 32 emptied levels per side, reused for new price levels | rejected | profile and microbenchmark first: allocation `[deque(), 0, 0]` is 0.116 microseconds more than `OrderedDict()` = about 40% of the cancel_churn regression. Pool: cancel_churn -1.9% to -3.7%, mixed -2.5% to -2.8%, buildup/crowded flat, but sweep +2.8% to +4.8% in all 3 runs, past the 2% limit. Code and pool tests reverted; cause of the sweep loss not found |
| Structure test `tests/test_version_b_structure.py` (private attributes: no empty level, live/dead counters, records <= 2·live, index == queues) after every event | accepted | A-vs-B results cannot see a dead record that is never removed. Two planted bugs (no compaction; `dead` not decremented) both fail the test |
| First `scen.py` timing of cancel_churn (0.1377 s vs 0.1221 s) | corrected into a proper comparison | that run was not interleaved, so I re-measured with `tools/ab_timing.py` twice: +12.9% and +10.3%. The regression is real and is stated in REVISIONS.md |

Cumulative speed-up of kept steps 1, 2, 4 (before step 9; for the current B see REVISIONS.md: mixed -14.8%, buildup -37.7%, sweep -28.8%, crowded -35.0%, cancel_churn -15.4% vs the first correct B): mixed -19.0%, buildup -23.5% (0.1995 -> 0.1617 s and
0.2285 -> 0.1748 s). Numbers depend on this machine and are repeated in `REVISIONS.md`.

## Phase 4: own generator and A-vs-B equivalence

| Suggestion | Decision | Reason / evidence |
|---|---|---|
| `tools/gen_small.py`: stdlib-only, stateless generator with four profiles (`tight`, `wide`, `single_level`, `dirty`): small price and id pools, ids whose text order differs from arrival order, reused and duplicate live ids, unknown cancels, oversized market sells, `seq` gaps and non-increasing `seq`, corrupted and non-dict events | accepted | deterministic per seed (test); sample output checked by hand: a BUY reusing a live SELL id is rejected as `duplicate_live_order_id` |
| `tests/test_equivalence.py`: 40 seeds x 250 events x 4 profiles in lock step; both books go through `helpers.step()` (independent I1-I7) and then results, snapshots, best bid/ask must be equal after EVERY event | accepted | 12 new tests, 345 in total pass |
| Same comparison on the five supplied 10,000-event files | corrected to a cheaper check | a full snapshot after every event is O(M*B) on `buildup`/`crowded`. Now results and best prices are compared after every event, the full book every 200 events and at the end. Stated in the test docstring |
| Coverage test so the comparison cannot be vacuous | accepted | requires every status, all 11 reason codes, >=3 fills, fills over >=2 levels and 2 makers at one price to occur |
| Mutation check of the new tests (bugs planted in B, then restored; `git status` clean afterwards) | accepted | (1) touching prices no longer cross, (2) a partial fill moves the maker to the back of its queue, (3) cancel leaves an empty price level: all three fail. Mutation 1 fails with `crossed book: bid 104 >= ask 104` from the independent checker, not from a crash |
| My first mutation run | corrected | two `sed -i` commands failed on macOS (needs `-i ''`), so mutation 1 never ran and "4 passed" meant nothing. Redone with Python edits |
| Pyright: `__doc__.splitlines()` may be `None` | accepted | fixed with `(__doc__ or "")`; pyright reports 0 errors on the new files |

## Phase 5: benchmark data

| Suggestion | Decision | Reason / evidence |
|---|---|---|
| `bench/make_data.sh`: grid of 5 scenarios x M in {1000, 10000, 100000} x seeds {42, 43, 44} (45 files), 1,000,000 events for all five scenarios at seed 42, and a queue-concentration set (`buildup`, 100,000 events, `--levels` 4/16/64/256/4000, plus the 1000-level grid file) | accepted | assignment "Benchmark experiments"; 55 files, about 100 MB, 100 s to generate; all in the gitignored `data/generated/`; existing files are kept (`--force` regenerates) |
| One million events only with seed 42 | accepted (my choice) | assignment says "try one million if feasible"; 15 s per file; Bastian can add seeds in the script |
| `tools/hash_generated.py --write / --check`: sha256 of the `.gz` and of the decompressed text, plus Python / zlib / platform, in `results/generated_data_checksums.json` | accepted | `.gz` hash depends on zlib (1.2.11 here), the decompressed hash does not; `--check` reports a changed `.gz` hash with equal content as a note, not as a problem |
| `tests/test_generated_data.py`: regenerate every stream with at most 10,000 events in memory and compare with the record; the seed-42 10,000-event streams must equal the five supplied files; the record must list exactly the planned 55 names | accepted | 39 new tests, 384 in total pass, no big file needed on a fresh clone |
| Claim that `crowded` is `buildup --levels 4` (so "4 vs 1,000 prices" can use one scenario) | corrected from assumption to test | read from the generator code, then checked: identical decompressed hash at 100,000 events, and `crowded` equals `buildup --levels 4` at 2,000 events |

## Phase 6: benchmarks

| Suggestion | Decision | Reason / evidence |
|---|---|---|
| Limits and run rules (600 s per replay, > 60 s first replay = single measurement, A on 1M only if A at 100,000 took < 60 s, statuses ok/stopped/not_run/error) written into the README before any run | accepted (Bastian's decisions) | commit 4ada71e, before the first measurement |
| First draft: `gc` disabled during replays | corrected by Bastian | Bastian decided gc stays enabled (default Python behaviour). A first run with gc off was stopped after 33 runs and its files were discarded; no reported number comes from it. Recorded in README |
| Child-process harness: wall-clock limit, SIGUSR1 at the limit, events done read from the replay frame | accepted | tests: stop with progress, normal end, error |
| `bench_time.py`: parse once, fresh book per replay, `gc.collect()` before each replay, warm-up + 5 repeats, raw repeats + median | accepted | 18 bench tests at the time (gc enabled, one parse, fresh book, warm-up + 5, env.json) |
| Counters instrumentation restored `_best_index` as a plain function | corrected | the next plain replay raised `TypeError`; fixed with `staticmethod(...)`; test checks the restore |
| Timing run 1 (all 100 runs) | rejected by Bastian | B buildup 100,000 took 0.20 s for seeds 42 and 43 and 0.09 s for seed 44; the machine had changed state (in use, maybe battery). Kept as `time_raw_run1.csv`, never reported. Fix: start time and power state on every row, canary before and after every block, full grid repeated. Run 2: all 88 canaries 0.0764-0.0821 s, AC power. A buildup 100,000, stopped at 600 s in run 1, finished in 270 s in run 2 (about 2x slowdown in run 1) |
| 6b `bench_latency`, `bench_memory`, `bench_counts` (renamed from latency/memory/counters) with canary blocks | accepted | tests: 20 pass |
| Latency replay with gc disabled (first draft) | corrected | changed to gc enabled to match the timing runs; gc pauses now show up in the tail |
| `summarize()` with 20 chunks | corrected | the new test for streams shorter than 20 events found a `ValueError` (empty chunk); fixed |
| Bastian's gc test (B buildup 100,000, gc off) | accepted, extended | I ran gc off and gc on twice each, to see that spikes repeat. gc on: max 13.1 and 12.4 ms (events 91,228 and 44,613); gc off: 0.82 and 0.88 ms. The ~12 ms spikes are garbage collection. The peaks left with gc off (events 10,922, 21,845, 43,690, 87,381) were first a guess; Bastian named them order-index dict resizes at 2/3 capacity, and `sys.getsizeof` on a dict with 100,000 keys confirms resizes at exactly those insert counts |
| REVISIONS step 9: "memory is O(B), not O(number of submissions)" | corrected (my wrong claim, found in 6b) | the order index dict never shrinks: after 100,000 inserts and 99,999 cancels B holds 4.05 MB, 3.84 MB of it the index (`sys.getsizeof`); A holds 5.5 KB. Correct statement: queues <= 2*B records, whole book O(peak B). No engine change; docstring in `version_b.py` still says O(B) |
| 6c liquidation with gc disabled (old code) | corrected | changed to enabled; test checks gc stays on during a trial |
| 6c: "A only if within limit" at 100,000 bids | my reading, flagged to Bastian | A runs under the same 600 s limit (no 60 s gate). A finished: 38.7 s, 207.6 s, 210.5 s (single trials) |
| `A_idset` fairness variant (A + a set of live ids, in `bench/variants.py`, outside `lob/`) | accepted, labeled | 24 tests show identical results and a set equal to the live ids after every event. Result: the id set removes about half of A's time on buildup, crowded, mixed, sweep (10,000 events); A_idset is still 100-200x slower than B |
| My expectation that the id scan was the main cost (2/3 of the comparisons) | corrected by the measurement | counts: `scan_is_live` = n(n-1)/2 = 49,995,000 and `scan_best_index` about 25 M at 10,000 events, but removing the id scan saves about half of the time, because one best-price comparison costs more than one id comparison |
| Queue concentration | accepted | A flat at 270-285 s from 4 to 4,000 levels; B 0.0865 s to 0.0996 s |
| Cancel churn vs M | accepted | memory flat from 1,000 to 1,000,000 events (A 988 B, B 1,284 B after replay); time per event constant |
| Reading A's 1M `not_run` rows | note | A on mixed 1,000,000 ran (its 100,000 median was 32.9 s) and was stopped at 600 s; no value recorded |

## Phase 7: dashboard

| Suggestion | Decision | Reason / evidence |
|---|---|---|
| Streamlit app with 12 pages that only reads `results/` | accepted | `tests/test_dashboard.py`: every page renders, the code never imports `lob` or `bench` and never writes a file |
| No Streamlit lab found in the repo to copy | note | plain Streamlit with a page list in the sidebar |
| `design-taste-frontend` skill | used for restraint only | it is made for company websites; I took "no decoration, one system" and nothing else. A orange, B blue, A_idset light orange, everywhere |
| Faceted layered chart on the scaling page | corrected | Altair refused layered facets with data in the layers; data moved to the facet. Three panels per row were cut off at the right; narrower panels |
| Bar charts on a log axis | corrected | they rendered empty (no base on a log axis); replaced by dots on the log pages. Memory bars are linear |
| Code snippets on "Why A is slow" | accepted as static text | a test checks that every snippet line is in `lob/version_a.py` |
| Stopped and not-run markers | accepted | cross at the 600 s line and a diamond at the top, no value; the test checks that stopped runs have no median |
| Pyright | corrected | pandas/altair gave 146 type errors; four rules switched off inside the three dashboard files, 0 errors left there. 10 older errors in other files remain |
| Claim "A and B compared on streams up to 100,000 events" (REPORT section 3, Correctness page) | corrected in Phase 8b | the clean-clone check looked at `results/correctness.csv`: its 36 streams have 1,000, 5,000 and 10,000 events (195,000 compared events in total), none has 100,000. Both texts fixed |
| Screenshots with headless Chrome | partly done | 11 of 12 pages looked at (not Correctness); the last fixes (memory axis, counts chart, Overview deltas) were not re-shot |

## Accepted

## Corrected

## Rejected
