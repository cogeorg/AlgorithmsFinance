# Development log

This log follows the process from slide 58 in chronological order. The commands
run from `Submissions/BonackerMaurice/01_code/`, and file paths are relative to
it. Before the folders were numbered (section 8), the same commands ran from
`Submissions/BonackerMaurice/`.

## 1. Tests and generator specification first (2026-11-20)

The tests were written before any implementation:

- `tests/test_search.py` holds one parametrized suite that every registered
  method and version must pass. It covers:
  - empty arrays and queries
  - one entry
  - duplicates
  - unsorted and descending input
  - present and absent queries
  - query boundaries
  - repeated queries
  - negative and very large IDs
  - output order and type (`list` of `bool`)
  - unchanged input
  - the slide example
  - 40 seeded random cases checked against an independent reference
    (`q in list(ids)`)
  - inputs of 100,000 entries
  - identical `TypeError` behaviour on invalid input
- `tests/test_generator.py` checks that the generator:
  - is deterministic
  - uses the identical array for every q and scenario
  - produces exact hit counts
  - follows the duplicate policies
  - rejects invalid specs
- `tests/test_benchmarks.py` contains smoke tests of the timing and memory
  phases on a tiny grid.

## 2. The tests detect missing behaviour

All algorithm and generator functions were stubs (`raise NotImplementedError`),
and the benchmark modules did not exist yet:

```
$ python -m pytest -q --continue-on-collection-errors
ERROR tests/test_benchmarks.py          (ImportError: benchmarks.memory missing)
634 failed, 2 passed, 1 error in 8.73s
```

The 2 passing tests do not depend on any implementation. One checks the
registry's composition. The other checks the hand-written expected values
against the reference.

## 3. Implementation; all tests pass

```
$ python -m pytest -q
639 passed
```

## 4. The tests detect wrong behaviour (mutation check)

`tests/mutation_check.py` swaps one function at a time for a deliberately buggy
version, in memory only, and reruns `tests/test_search.py` in a fresh process:

```
$ python -m tests.mutation_check
KILLED   binary_v2 prepare forgets to sort          (49 failing tests)
KILLED   binary_v2 uses <= (upper bound)            (69 failing tests)
KILLED   binary_v1 recursion skips mid+1..hi        (48 failing tests)
KILLED   linear_v1 prepare sorts caller's array     (43 failing tests)
KILLED   linear_v2 skips the last element           (29 failing tests)
KILLED   linear_v2 answers unique queries only      (29 failing tests)
KILLED   hash answers in sorted query order         (52 failing tests)
KILLED   hash returns 1/0 instead of True/False     (18 failing tests)

8/8 mutants killed
```

The last mutant matters. Because `1 == True`, a plain equality check would
pass it, and only the `type(r) is bool` test catches it.

## 5. Hand trace of the slide example

The input is `ids = [7, 11, 7]` and `queries = [11, 9, 7]`, and the expected
result is `[True, False, True]`. **Verified by hand by Maurice (slide 58,
step 2):** he traced all three methods on paper and got the same result as the
tables below and the code.

**BinarySearch v2.** `prepare` returns the new list `[7, 7, 11]`, and `ids` is
unchanged. The invariant is `a[:lo] < x <= a[hi:]`.

| Query | Steps | Check | Result |
|---|---|---|---|
| `x = 11` | lo=0, hi=3 → mid=1: 7 < 11, lo=2 → mid=2: 11 ≥ 11, hi=2 → stop | `a[2] == 11` | True |
| `x = 9` | lo=0, hi=3 → mid=1: 7 < 9, lo=2 → mid=2: 11 ≥ 9, hi=2 → stop | `a[2] = 11 ≠ 9` | False |
| `x = 7` | lo=0, hi=3 → mid=1: 7 ≥ 7, hi=1 → mid=0: 7 ≥ 7, hi=0 → stop | `a[0] == 7` | True |

**LinearSearch v2:**

| Query | Scan | Result |
|---|---|---|
| `x = 11` | 7 ≠ 11, then 11 = 11 | True (2 comparisons) |
| `x = 9` | 7, 11, 7, end | False (3 comparisons) |
| `x = 7` | first element matches | True (1 comparison) |

**Hash.** `set(ids) = {7, 11}`, so `11 in s` is True, `9 in s` is False and
`7 in s` is True.

## 6. Revision

`linear_v1` → `linear_v2` and `binary_v1` → `binary_v2`. See
[REVISIONS.md](REVISIONS.md). The two versions of each method were drafted in
the same session. Both stay registered, and the same parametrized suite runs
against all five method/version pairs.

## 7. Newly discovered cases

These came from an AI pre-audit; the full table is in
[AI_USAGE.md](AI_USAGE.md). No expected result was weakened. Every finding
added tests:

- **Hit placement (generator):** these tests were added:
  - `test_hits_are_found_mid_array_on_average`, which checks that
    `mean_first_hit_frac` is in [0.45, 0.55] for every n and q
  - `test_mean_first_hit_frac_counts_first_occurrence`
  - `test_golden_checksums`
  - `test_query_order_is_shuffled`
  - `test_grid_skips_single_query_mixed`
- **NumPy integers:** `test_numpy_integers_rejected`. Previously binary v2
  returned `numpy.bool_`.
- **"By hand" rules:** these tests were added:
  - `test_search_procedures_do_not_use_library_search` (AST)
  - `test_binary_search_uses_logarithmic_comparisons`
  - `test_linear_search_scans_until_first_match`
  - `test_hash_lookup_does_not_scan`
  - `test_prepared_states`

  Two new mutants, a secretly linear binary search and a list-based hash, are
  killed.
- **Measurement protocol:** these tests were added:
  - `test_segments_time_exactly_what_they_claim`
  - `test_query_segment_gets_a_fresh_state_per_repeat`
  - `test_calibration_reaches_target_duration`
  - `test_preflight_rejects_wrong_results_and_non_bools`
  - `test_memory_traces_only_what_the_method_allocates`
- **Provenance and privacy:** these tests were added:
  - `test_git_info_outside_a_repository_is_unknown_not_clean`
  - `test_source_fingerprint_tracks_content_not_line_endings`
  - `test_redact_removes_home_folder_and_user_name`

```
$ python -m tests.mutation_check
10/10 mutants killed
```

## 8. Numbered folders

The folders were reorganised into `00_docs/`, `01_code/` and `02_results/` to
follow the course's numbering convention. The skeleton went in as PR #8, which
is merged. Only file locations changed, plus the path constants in
`benchmarks/config.py`, `benchmarks/run.py` and `dashboard/`. All 674 tests
pass in the new layout.

A flaky protocol test showed up while another benchmark ran on the same machine:
`test_calibration_reaches_target_duration` depended on machine load. It now uses
a fake clock, so it is deterministic. Its assertion was not weakened.

## 9. Dashboard simplified; large-n exploration

The first dashboard had nine tabs and was hard to read. Maurice decided to cut
it down to four (Overview, Runtime, Spot check, Details for auditors), with the
same content.

To test much longer lists than the slide grid, `explore/large_n.py` runs the
unchanged timing phase on n = 100k, 1M and 10M (q = 10). Run
`20261120-144435_2611dd1_large_quick` has the same source fingerprint as the
official run. The findings are in the README section "Exploration: up to 10
million IDs".
