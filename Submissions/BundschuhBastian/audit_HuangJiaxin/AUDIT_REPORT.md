# Audit of `Submissions/HuangJiaxin` (Lab Phase 2)

Auditor: Bastian Bundschuh. Audited by running the code, not by reading it alone.

## Target

| | |
|---|---|
| Folder | `Submissions/HuangJiaxin/` |
| Audited commit | `47ec3ae1c62af0c8ef142df5f11002d44fb3dc10` (last change to the folder; unchanged up to `main` at `e04b40c`) |
| Saved measurements | produced at `0be8421`; between `0be8421` and `47ec3ae` only labels in `membership.py` and `dashboard.py` changed ("Class 3" → "Class 2"), so the results belong to the audited code |
| My environment | CPython 3.13.18, Linux x86_64 (`logs/environment_auditor.txt`); the author measured with CPython 3.12.16 in Docker on Apple Silicon |

Nothing in the audited folder was edited. Every run used a separate checkout.

## Summary

The three membership methods are correct in every case I tried: their 122 tests, plus
180 independent edge-case checks of my own. The scripts and the dashboard run unmodified.
The problems are in the **measurement inputs and one performance claim**:

| # | Type | Finding | Severity |
|---|---|---|---|
| 1 | Bug (reproduced) | For q = 1, "hit rate 0.5 (mixed)" contains no present query, so it is the same input as "hit rate 0.0" | Medium: three result groups are mislabelled (timing, memory, break-even at q = 1) |
| 2 | Unsupported claim (reproduced) | "q = 1: `linear_v2` has the smallest total time" does not hold at n = 1,000. The saved data contradicts it for identical inputs, and a re-run does too | Medium |
| 3 | Bug (reproduced) | `make_queries` returns more than q queries when the hit rate is outside [0, 1] | Low: not used by any saved result |
| 4 | Bug (reproduced) | `make_queries`' "absent" queries can be present (odd IDs), and the function crashes for all-negative IDs | Low: her own IDs are even and ≥ 0 |
| 5 | Bug (reproduced) | The dashboard crashes with a raw traceback if one results file is missing | Low: robustness, for example in Docker with an empty results volume |

The other weaknesses are listed separately in "Shortcomings". They are not reproduced bugs.

## Bug 1: q = 1 "mixed" is actually "all absent"

**Target:** `data.py`, `make_queries` (`n_hit = round(q * hit_rate)`); this affects `benchmark.py`,
`memory.py`, `breakeven.py` and `dashboard.py`.

**Smallest example:**
```bash
cd Submissions/BundschuhBastian
.venv/bin/python -m pytest -q -s audit_HuangJiaxin/reproducers/repro_1_hit_rate_rounding.py
```
This fails on the audited commit (`logs/repro_1.txt`):
```
n=1000: hit_rate 0.5 -> [34525], hit_rate 0.0 -> [34525], hits = 0
AssertionError: n=1000: 'mixed' query equals the all-absent query
```

**Expected:** the README and the dashboard call the setting "0.5 (mixed)". `environment.json` lists
hit rates 1.0, 0.0 and 0.5 as three different settings. For q = 1, a batch with hit rate 0.5 should
not be the same batch as the all-absent one.

**Actual:** Python's `round` rounds halves to the nearest even number, so `round(1 × 0.5) = round(0.5) = 0`.
The single query is the same odd, absent ID as in the hit-rate-0.0 setting, for n = 1,000, 10,000
and 100,000. The README test `test_generator_hit_rate_is_exact` only checks q = 100, where
`round(50.0) = 50`.

**Impact:**
- All 18 timing rows with q = 1 and hit rate 0.5 measure the worst case of LinearSearch (a full scan).
  They are labelled "mixed".
- The memory rows for q = 1 are labelled "hit rate 0.5" but are all-absent too.
- The q = 1 point of the break-even curve is all-absent as well. For q = 3, `round(1.5) = 2` gives
  2 of 3 present (67 %), not 50 %.
- In the dashboard, "0.5 (mixed)" and "0.0 (all absent)" show different numbers for q = 1 although
  the input is identical. That difference is measurement noise; see Bug 2.

**Suggested correction:** choose the q = 1 policy explicitly, for example
`n_hit = math.floor(q * hit_rate + 0.5)` (round half up, so q = 1 gives 1 present query).
Alternatively, drop "mixed" for q = 1 and say so. Add a test for q = 1 and q = 3. Then rerun the
measurements.

## Bug 2: "For a single query, LinearSearch is fastest" is not supported at n = 1,000

**Target:** the README, "Results summary" ("q = 1: `linear_v2` has the smallest total time") and
"Break-even analysis" ("For a single query, plain LinearSearch is fastest"), together with
`results/timing_summary.csv`, `timing_raw.csv` and `breakeven_curve.csv`.

**Smallest example:**
```bash
cd Submissions/BundschuhBastian
.venv/bin/python audit_HuangJiaxin/reproducers/repro_2_identical_input_timings.py   # exits with 1
.venv/bin/python audit_HuangJiaxin/reproducers/repro_2b_rerun_protocol.py           # about 10 s
```

**Evidence 1, the author's own saved data** (`logs/repro_2.txt`). Because of Bug 1, these three
measurements use the identical array and the identical single query (n = 1,000, q = 1):

| Method | benchmark, "hit 0.0" | benchmark, "hit 0.5" | `breakeven.py`, q = 1 | max/min |
|---|---|---|---|---|
| `linear_v2` | 9.65 µs | 22.06 µs | 9.28 µs | 2.4× |
| `hash` | 85.07 µs | 16.60 µs | 11.12 µs | 7.7× |
| `binary_v2` | 47.14 µs | 61.84 µs | 44.80 µs | 1.4× |

- The raw repeats of `hash` in one of these cells range from 43.7 to 387.3 µs, a 9× spread over 5 repeats.
- With the same input, the saved data names `linear_v2` the fastest method in one setting
  and `hash` in the other.

**Evidence 2, a re-run of the unmodified scripts on a second machine** (Linux x86_64,
`logs/environment_auditor.txt`; outputs in `logs/run_benchmark_quick.txt` and `logs/run_breakeven.txt`):
- At n = 1,000 and q = 1, `hash` has the smaller total in **all three** hit settings
  (0.017–0.020 ms vs 0.021–0.022 ms).
- `breakeven.py` gives q\* = 0.93 for `hash` at n = 1,000. That means building the set already pays
  off for a single query.
- For n = 10,000 and n = 100,000, `linear_v2` is fastest at q = 1, as the README says.
- The protocol itself is stable on that second machine (`logs/repro_2b_cloud_linux.txt`: max/min of the
  median over 10 reruns is 1.10× for `hash` and 1.30× for `linear_v2`). The large spread therefore
  comes from the saved Docker run, not from the code. The claim still depends on the machine and
  on n.

**Expected:** a general claim that holds for every n in the grid, or one that states its limits.

**Explanation and impact:** at n = 1,000, a full scan (about 10–20 µs) and building a set of
1,000 integers (about 11–17 µs) take almost the same time. Which one wins depends on the machine
and on noise. The claim is true for n ≥ 10,000 only. The saved run also has unexplained outliers
(387 µs and 322 µs for a block that otherwise takes about 15 µs). Garbage collection is not
controlled during timing. That is a possible cause, but I have not verified it.

**Suggested correction:**
- Restrict the claim to "n ≥ 10,000 on my machine" and report the n = 1,000 case as a tie.
- Show the spread (min–max of the repeats) next to the median in the dashboard.
- Consider `gc.disable()` during timed blocks and more repeats for blocks under 1 ms.

## Bug 3 (minor): `make_queries` ignores its own contract for invalid hit rates

**Target:** `data.py`, `make_queries`. The docstring says "q queries".

**Smallest example:**
`.venv/bin/python -m pytest -q audit_HuangJiaxin/reproducers/repro_3_generator_validation.py`
fails 3 of 3 cases (`logs/repro_3.txt`).

**Actual:** `make_queries(ids, 10, 1.5, 1)` returns 15 queries (all present). Hit rate −0.5 gives
15 absent queries, and hit rate 2.0 gives 20. A negative hit rate makes `q − n_hit` larger than q.

**Impact:** low. The saved grid uses only 0, 0.5 and 1, so no result is affected. A later caller
would get wrong batch sizes without any error.

**Suggested correction:** `if not 0 <= hit_rate <= 1 or q < 0: raise ValueError(...)`, plus a test.

## Bug 4: "guaranteed absent" queries are not always absent

**Target:** `data.py`, `make_queries`. The docstring says "round(q * hit_rate) are present in ids,
the rest absent", and the README says absent queries are "guaranteed absent".

**Smallest example:**
`.venv/bin/python -m pytest -q audit_HuangJiaxin/reproducers/repro_4_absent_queries_not_absent.py`
fails 2 of 2 cases (`logs/repro_4.txt`).
- `make_queries([1, 3, 5, 7, 9, 11], 10, 0.0, seed=1)` returns `[21, 25, 3, 9, 3, 23, 5, 1, 11, 9]`.
  Hit rate 0.0 is requested, but **7 of 10** queries are present.
- `make_queries([-10, -4], 10, 0.5, seed=1)` raises `ValueError: empty range for randrange()`.
  Negative IDs are valid input under her own specification ("integer trade IDs").

**Explanation:** absent queries are drawn as odd numbers between 1 and `2 * max(ids) + 3`. That
guarantees absence only if every ID is even. If `max(ids)` is negative, the range is empty. The
function takes any ID list but relies silently on how `make_ids` builds its IDs.

**Impact:** low. Her saved results use only `make_ids` output (even and ≥ 0), so they are not
affected. The "exact hit rate" property is not a property of `make_queries` itself.

**Suggested correction:** draw absent candidates and reject the ones in `set(ids)` (as in a
rejection loop), with a range that also covers negative IDs. Alternatively, assert in
`make_queries` that all IDs are even and ≥ 0, and document that.

## Bug 5 (robustness): dashboard crashes when a results file is missing

**Target:** `dashboard.py`, lines 20–25 (five `pd.read_csv` calls without a check).

**Smallest example:**
`.venv/bin/python -m pytest -q audit_HuangJiaxin/reproducers/repro_5_dashboard_missing_file.py`
fails (`logs/repro_5.txt`). The test runs on a temporary copy of her folder, with
`results/breakeven_curve.csv` removed.

**Actual:** the page shows a Python traceback (`FileNotFoundError ... breakeven_curve.csv`), and
none of the other tabs render.

**Expected:** a message saying which file is missing and which script creates it. This
situation happens, for example, with her own Docker command
`docker run -v "$(pwd)/results:/app/results"` when the mounted folder lacks one file.

**Suggested correction:** check that the files exist at the top of `dashboard.py`. If one is
missing, show `st.error` with the command, then `st.stop()`.

## Shortcomings (documented, not reproduced as failures)

1. **The timed answers are not checked.** `benchmark.py` and `breakeven.py` only check that `ids`
   is unchanged. A wrong method would be timed without any notice. Comparing the answers with the
   expected list after the clock stops costs nothing in the timed region.
2. **Missing metadata for two result files.**
   - `memory.py` and `breakeven.py` write no Python version, machine or commit.
   - `environment.json` is written only by `benchmark.py`, so the code version behind
     `memory.csv` and `breakeven_*.csv` is not recorded.
   - `breakeven_curve.csv` keeps medians only, no raw repeats (slide 59: keep raw repeat values).
3. **Memory is a single run.** It has no repeats and no `gc.collect()` before tracing. On my
   machine the re-run gave byte-identical `memory.csv`, so in practice this is harmless.
4. **Running the benchmark overwrites the committed evidence.**
   - `benchmark.py --quick` replaces the full `results/` files (including `environment.json`) with
     a smaller grid.
   - There is no output-folder option, so a reviewer who tries it changes the files under review.
5. **`total_s` is computed, not measured.** It is the sum of two separately timed blocks. The
   README discloses this, and the summary agrees with the raw data exactly (`logs/summary_vs_raw.txt`: max difference
   0.0 for every column). I mention it only because it leaves out per-call overhead.
6. **Short blocks.** The `inner` count is calibrated from one cold call, so some blocks are shorter
   than the 2 ms target. For example, `linear` preparation is capped at 10,000 calls × about 40 ns,
   which is about 0.4 ms.

## Cases checked (all pass unless listed above)

- **Their suite:** `python -m pytest -q` gives 122 passed (`logs/their_tests.txt`, run in a separate
  checkout, unmodified).
- **My independent checks** (`reproducers/test_edge_cases.py`, 180 passed, all six methods):
  - empty ids, empty queries, both empty;
  - single entry present, and absent below and above it;
  - all-equal array; duplicates at both ends; descending input;
  - negative values and zero; integers up to 2^63;
  - repeated queries keep their order;
  - every position and every gap for n = 1 … 17;
  - input and query lists are not mutated;
  - repeated calls with another array in between;
  - 500 random arrays with many duplicates. Every answer is compared with Python's `in` on a list.
- **Scripts:** `benchmark.py --quick`, `memory.py` and `breakeven.py` run unmodified (exit code 0, `logs/run_*.txt`).
- **Dashboard:** `streamlit run dashboard.py` loads without exceptions in a headless run, for all
  12 combinations of q, hit rate and unit, and with an empty method selection.
- **Dashboard against raw data:** the medians recomputed from `timing_raw.csv` equal
  `timing_summary.csv` exactly (540 raw rows = 6 methods × 3 n × 2 q × 3 hit rates × 5 repeats).
- **README numbers against the saved results**, all consistent:
  - binary query batch 23.23 ms vs 0.140 ms (166×, "about 170×");
  - linear 219.5 vs 64.9 ms (3.38×);
  - `binary_v2` is 7.3× slower than `bisect_ref`;
  - the break-even table matches `breakeven_points.csv`, and the q\* values agree with where the
    measured curves cross.
- **Memory claims:** `hash` has the largest peak (6,144 KiB at n = 100,000). `binary_v1` is above
  `binary_v2` by about n references (1,563 vs 1,172 KiB), which fits the slice copies held along
  the recursion.
- **Preparation is not free:** a fresh structure is built in every repeat, and sorting and set
  construction are included in `prepare_s`.

## Limits of this audit

- Docker was not tested; the image was not built.
- My timings come from a Linux x86_64 cloud machine with Python 3.13, not the author's Apple
  Silicon machine with Python 3.12. Absolute numbers are not comparable; only relations and spreads are.
- I re-ran the full break-even grid and the quick benchmark grid, but not the full benchmark grid
  with n = 100,000 and all hit rates.
- The dashboard was checked headless (no exceptions, same numbers). I did not review the layout visually.
- Inputs outside the specification were not counted as bugs. One example: passing an iterator
  instead of a list makes the linear methods raise `TypeError` (`len()` of an iterator), while
  binary and hash work. The spec says `ids` is a list.

## Files in this audit

| Path | Content |
|---|---|
| `reproducers/repro_1_hit_rate_rounding.py` | failing test for Bug 1 |
| `reproducers/repro_2_identical_input_timings.py` | reads the saved results; exit code 1 shows Bug 2 |
| `reproducers/repro_2b_rerun_protocol.py` | reruns the unmodified timing protocol on one fixed input |
| `reproducers/repro_3_generator_validation.py` | failing test for Bug 3 |
| `reproducers/repro_4_absent_queries_not_absent.py` | failing tests for Bug 4 |
| `reproducers/repro_5_dashboard_missing_file.py` | failing test for Bug 5 (runs on a temporary copy) |
| `reproducers/test_edge_cases.py` | 180 passing independent checks (cases checked) |
| `reproducers/_target.py`, `conftest.py` | import the audited folder without copying or editing it |
| `logs/` | saved outputs of every command above, plus my environment |

All commands run from `Submissions/BundschuhBastian/` with that folder's `.venv`
(pytest and pandas; Bug 5 also needs streamlit). The audited folder must be at commit `47ec3ae`.

## Use of AI

Claude (Anthropic) ran the checks in a separate checkout, wrote the reproducers and drafted this
report. Every number above comes from the saved logs in `logs/`. I reviewed each finding,
checked Bug 1 by hand (`round(0.5)` is 0 in Python), and re-ran the reproducers on my own
machine before submitting.
