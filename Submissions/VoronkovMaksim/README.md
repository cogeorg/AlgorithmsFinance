# Lab 1: Search for integer IDs

## Project Overview

This lab compares manual linear search, manual binary search, and Python hash-set membership for batches of integer-ID queries. Every method returns one Boolean per query in the original query order and leaves the input lists unchanged. Binary search sorts a copy; hash search builds a set. Both preparation costs count in the comparison.

## Algorithms

| Algorithm | How it works | Search time per query | Preparation time / extra space |
|---|---|---|---|
| Linear V1 | Scan IDs and stop at a match | O(n) worst case | O(1) / O(1) |
| Binary V1 | Sort a copy; recursively halve the search range | O(log n) | O(n log n) / O(n) for sorted copy |
| Binary V2 | Sort a copy; halve the range with a `while` loop | O(log n) | O(n log n) / O(n) for sorted copy |
| Hash V1 | Build a set; test set membership | O(1) average, O(n) worst case | O(n) average / O(n) |

`n` is the number of IDs. Binary V1 also uses O(log n) call-stack space per query; V2 uses O(1) auxiliary search space. Public functions are in `search.py` and reject non-list inputs, non-integer values, and Booleans with `TypeError`.

## Testing

`tests/` checks empty lists, singletons, unsorted IDs, duplicates, repeated queries, misses between and outside values, negative numbers, zero, and very large integers. Adversarial cases include nested lists, strings, floats, dictionaries, `None`, and Booleans. The same contract tests run for all four methods and check result type, order, length, and unchanged inputs. Generator tests check lengths, hit counts, uniqueness policy, reproducibility, and invalid parameters.

```python
ids = [7, 11, 7]
queries = [11, 9, 7]
# Expected: [True, False, True]
```

Final check on this checkout: **133 tests passed**. A separate manual audit found identical answers from all four methods on all 18 saved datasets and unchanged input lists. Passing tests and checks do not constitute mathematical proof.

## Synthetic Data

`synthetic_data.py` uses `random.Random(seed)` with seed **42**. `save_datasets.py` saves 18 fixed JSON files in `data/`: array sizes **1,000, 10,000, 100,000**, query counts **1, 100**, and **all-present, all-absent, mixed** scenarios. Duplicate IDs are allowed. The same saved IDs and ordered queries feed every method; no sorted list or set is saved. The requested mixed hit rate is 50%. With one query, round-half-up produces one hit, so its actual rate is 100%; with 100 queries, exactly 50 are hits. Existing files are checked against the seed rather than silently replaced.

## Performance Measurement

`benchmark.py` uses `time.perf_counter()` for elapsed time. Binary sorting and hash-set construction are preparation; linear preparation is zero. The query phase processes the whole query batch. For short work, multiple batches are timed together and divided by the batch count (for q=1/q=100: linear 100/1, binary 1000/100, hash 10000/1000). Each method is warmed up, then measured **five times** with fresh preparation. The median of each time column is used for comparison; median total need not equal the sum of the other two medians. Input generation, answer validation, and chart creation are outside the timed regions.

`results/timings.csv` contains 360 raw repeats and 72 median rows, with preparation, query-batch, and total times in **seconds**, plus seed, batch count, environment, and Git HEAD. `results/summary.csv` has 72 median rows in **milliseconds**. Timings vary by machine and load. No memory measurements were collected.

## Algorithm Revision

Binary V1 uses recursion; V2 uses iteration. This avoids recursive call overhead and reduces auxiliary **search** space from O(log n) to O(1), while preserving O(log n) search time. Both retain O(n) space for the sorted copy. The saved measurements should be used to judge speed for each scenario; the revision does not guarantee a faster total time.

## Dashboard

The static Matplotlib script reads `results/timings.csv` and produces three charts for each of six query scenarios. All **18 PNGs** are in `results/charts/`; each has four method lines, a legend, labeled axes, milliseconds, and array size on a labeled log scale. It also regenerates `results/summary.csv`. It does not rerun the benchmark.

## Reproducibility

From the repository root in Windows PowerShell, with Python 3.14 and its `py` launcher installed (`python -m venv .venv` also works when Python 3.14 is on `PATH`):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Submissions\VoronkovMaksim\requirements.txt
.\.venv\Scripts\python.exe -m pytest Submissions\VoronkovMaksim\tests -q
.\.venv\Scripts\python.exe Submissions\VoronkovMaksim\save_datasets.py
.\.venv\Scripts\python.exe Submissions\VoronkovMaksim\benchmark.py
.\.venv\Scripts\python.exe Submissions\VoronkovMaksim\dashboard.py
```

The saved run used **CPython 3.14.6**, **pytest 9.0.1**, **pandas 3.1.1**, and **Matplotlib 3.11.2** on **Windows 11 (build 26300), AMD64, Intel Family 6 Model 197**. Direct dependencies are pinned in `requirements.txt`. No account, credentials, or internet connection is needed after installation. The benchmark records Git HEAD `09efedda0e067b50ce3af070a3691c644eb3e9b9`, which **predates the final documentation**; record the final SHA with `git rev-parse HEAD` after committing manually. Saved results remain available without rerunning benchmarks.

## AI Assistance

Codex assisted with tests and synthetic data, the search implementations and binary revision, benchmarking, static charts, and this documentation. The initial first-index design was changed to the required Boolean batch interface; the Streamlit interface was later removed in favor of the requested Matplotlib files. Automated tests and manual checks were used to evaluate the result.
