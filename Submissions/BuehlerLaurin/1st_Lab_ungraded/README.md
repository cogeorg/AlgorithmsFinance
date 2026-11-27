# Membership search lab — Laurin Bühler

*Algorithms in Finance* (FIN71055), coding lab, Phase 1: implement and measure.

For every query in a list of integer queries, answer whether it occurs in an integer ID
array. One Boolean per query, in query order; the array is never modified. Three methods,
each in an original (v1) and a revised (v2) version, all checked by the same tests:

| Method | Preparation | Query | Total for q queries |
|---|---|---|---|
| `linear` | none (the input itself) | scan, stop at first match: O(n) | O(n·q) |
| `binary` v1 | sorted copy: O(n log n) | recursive, **slices the list**: O(n) per query | O(n log n + n·q) |
| `binary` v2 | sorted copy: O(n log n) | iterative lower-bound search: O(log n) | O(n log n + q log n) |
| `hash` | `set(ids)`: expected O(n) | set lookup: expected O(1) | expected O(n + q) |

Linear search and hash set are unchanged in v2 (see [Revision](#revision)).

## Commit to be audited

**Commit: `a5b36b6da949078018ae01cbaf9c1eabf430999e`** (short `a5b36b6`) on branch
`lab-buehler` of `github.com/laurinbuehler/AlgorithmsFinance` (pull request to
`cogeorg/AlgorithmsFinance`). All commands below run on that commit without editing any file.
(The later commit that only adds this hash to the README changes nothing else.)

## Layout

```
membership/     algorithms: __init__.py (interface, registry METHODS), original.py (v1), revised.py (v2)
datagen/        generator.py: seeded synthetic data (separate from algorithms and measurement)
bench/          env.py (machine + code version), timing.py, memory.py, binary_variants.py
results/raw/    timing results (CSV per repeat, summary CSV, env JSON)
results/memory/ tracemalloc results (same structure)
dashboard/      app.py (Streamlit, reads saved results only), data.py (loading)
tests/          test_membership.py, test_generator.py, test_bench.py, test_dashboard.py
docs/           REVISION.md (what changed, why, measured effect), AI_LOG.md (AI use)
LAB_SPEC.md     the lab specification with requirement IDs and our decisions on open points
```

## Setup (Windows, PowerShell)

Requires Python 3.11 or newer (developed and measured with CPython 3.13.15).
Create the virtual environment **outside OneDrive**, for example:

```powershell
py -3.13 -m venv "$env:USERPROFILE\.venvs\aif-lab"
& "$env:USERPROFILE\.venvs\aif-lab\Scripts\Activate.ps1"
cd Submissions\BuehlerLaurin
python -m pip install -r requirements.txt
```

`requirements.txt` pins the direct dependencies: `pandas==3.1.1`, `pytest==9.2.0`,
`streamlit==1.67.0`. Everything else is the standard library. All commands below are run
from `Submissions\BuehlerLaurin` with the environment activated.
(macOS/Linux: `python3 -m venv ~/.venvs/aif-lab && source ~/.venvs/aif-lab/bin/activate`.)

## Commands

| Task | Command | Time | Output |
|---|---|---|---|
| Tests | `python -m pytest -q` | ~15 s | console |
| Runtime benchmark | `python -m bench.timing` | ~1 min | `results/raw/timing_<UTC stamp>*` |
| Memory measurement | `python -m bench.memory` | ~20 s | `results/memory/memory_<UTC stamp>*` |
| Choice of v2 variant | `python -m bench.binary_variants` | < 1 min | `results/raw/binary_variants_<UTC stamp>*` |
| Dashboard | `python -m streamlit run dashboard/app.py` | – | http://localhost:8501 |

The dashboard only reads saved files. It opens the newest run measured on committed code
(`git_dirty = false`) and can switch to any other saved run. New benchmark runs add new
files; existing results are never overwritten.

### Expected test result

```
598 passed
```

| File | Tests | What |
|---|---:|---|
| `test_membership.py` | 523 | 65 tests × 8 implementations (6 registered method/versions + 2 v2 candidates) + 3 structural |
| `test_generator.py` | 55 | determinism, lengths, hit rates, absent queries really absent, duplicate policies |
| `test_bench.py` | 7 | timing and memory scripts write complete, labelled files; wrong results are rejected |
| `test_dashboard.py` | 13 | data loading, summary medians = medians of raw repeats, headless app runs |

Covered cases include the lab example (`[7, 11, 7]`, `[11, 9, 7]` → `[True, False, True]`),
empty array/queries, one entry, duplicates, unsorted input, negative IDs, present/absent,
first/last and min/max elements, output order, unchanged input (deep-copy comparison),
repeated queries on one prepared state, all arrays of length 0–5 over {0, 1, 2}, and random
cross-checks against a `set` oracle. A static test checks that the linear and binary search
code uses no `in` on a list, no `bisect` and no `.index()`. Passing tests are evidence of
correctness, not proof.

## Measurement definitions

**Inputs.** `datagen.generator.make_case(n, q, hit_rate, seed, duplicate_policy)`.
Grid: n ∈ {1,000, 10,000, 100,000}, q ∈ {1, 100}, hit rate ∈ {1.0 all-present, 0.0
all-absent, 0.5 mixed}. Seed `20261120`, duplicate policy `allow` (IDs drawn with
replacement from `2·x`, x < 2n, so about 21% of entries are repeats). Absent queries are odd
numbers (`2·x + 1`) from the same range: guaranteed absent and spread between the IDs.
Every method and version gets the identical `(ids, queries)` for a grid cell. All settings,
the realized hit rate and the number of distinct IDs are saved in the `_env.json` file.

**Time** (`bench/timing.py`). Unit: **seconds**. Clock: `time.perf_counter()`.

| Column | Definition |
|---|---|
| `prep_s` | one `prepare(ids)`: seconds per preparation (sorting, building the set) |
| `query_batch_s` | one `query(state, queries)`: seconds **per batch of q queries** |
| `query_per_query_s` | `query_batch_s / q`: seconds **per query** |
| `total_s` | `query(prepare(ids), queries)` timed as one block: seconds per preparation + batch |
| `prep_plus_query_s` | `prep_s + query_batch_s` of the same repeat (cross-check of `total_s`) |

- One untimed warm-up per block, then **5 repeats**; tables and the dashboard show the
  **median**, the raw CSV keeps every repeat.
- Short calls: a timed block repeats the call k times until it lasts ≥ 20 ms; the value is
  block time / k, and k is saved (`k_prep`, `k_query`, `k_total`). The loop overhead
  (about 4·10⁻⁸ s per call) is included and saved as `overhead_per_call_s`.
- Fresh preparation in every block: no sorted copy or set is reused across the timing of
  preparation. Garbage collection is off inside timed blocks (as in `timeit`). Methods run
  round-robin in a seeded random order per repeat.
- Not timed: data generation, result check against a `set` oracle (done after each timed
  block), file writing, printing, dashboard.

**Memory** (`bench/memory.py`). Unit: **bytes** (dashboard: KiB). Tool: `tracemalloc`, in
separate runs from timing, a fresh tracing run per measurement, 3 repeats (identical results).

| Phase | Traced | Input | Prepared structure | Output |
|---|---|:-:|:-:|:-:|
| `prepare` | `state = prepare(ids)` | no | yes | no |
| `query` | `result = query(state, queries)` (state built before tracing) | no | no | yes |
| `total` | both | no | yes | yes |

`current_bytes` = still allocated when read (state and result kept alive);
`peak_bytes` = maximum during the phase, including temporary objects. `tracemalloc` counts
Python allocations only; it is neither process memory (RSS) nor exactly auxiliary space.
For linear search the state *is* the caller's list (`state_is_input = True`): it allocates nothing.

**Environment.** Every run saves Python version, platform, CPU, timestamp, git commit and
a dirty flag (uncommitted changes at measurement time) in its `_env.json`.

## Results (official runs)

Timing: `results/raw/timing_20261120T144207Z*` (commit `42ecde7`, clean).
Memory: `results/memory/memory_20261120T144911Z*` (commit `8b10cd7`, clean).
Machine: Windows 11, CPython 3.13.15. Medians, n = 100,000, hit rate 0.5:

| | prep [s] | query batch, q = 100 [s] | total, q = 100 [s] | total, q = 1 [s] | query peak memory |
|---|---:|---:|---:|---:|---:|
| linear | ≈ 0 | 0.21 | 0.21 | **0.0008** | 0.9 KiB |
| binary v1 | 0.028 | 0.049 | 0.076 | 0.026 | 782 KiB |
| binary v2 | 0.029 | 0.00025 | 0.028 | 0.028 | 1.1 KiB |
| hash | 0.013 | 0.000004 | **0.011** | 0.012 | 0.9 KiB |

- With **one query, linear search** has the lowest total time: it needs no preparation.
  (Exception: n = 1,000 and all-absent, where scanning 1,000 elements costs about as much as
  building the set and the hash set is slightly ahead.)
- With **100 queries, the hash set** is fastest at every n. At n = 100,000 it already pays off
  after about 5 queries (12 ms to build vs. about 2.9 ms per absent linear scan).
- **Binary search never has the lowest total time** here: sorting costs about twice as much
  as building a set, and its O(log n) query is slower than a set lookup.
- Measured scaling matches the predicted complexities: linear query time grows ×10 per ×10
  in n, binary v2 per-query time grows only from about 1.4 to 2.5 µs (log n), hash lookups
  stay at about 40 ns.
- Noise: linear and hash are the same code in v1 and v2; their two measurements differ by
  typically 5–15%. Smaller differences between methods should not be interpreted.

The earlier run `timing_20261120T143759Z*` was measured on uncommitted code
(`git_dirty = true`) and is kept for transparency only.

## Revision

Details and all numbers: [docs/REVISION.md](docs/REVISION.md).

**What changed (binary search only).** v1 searched recursively and passed slices
`arr[:mid]` / `arr[mid+1:]` to each call, which copies up to half the list per step.
v2 keeps two indices `lo`, `hi` in the single sorted copy (no slices), uses a loop instead
of recursion, and is a lower-bound search: one `<` comparison per step and one `==` at the
end. Invariant: `state[:lo] < x <= state[hi:]`; at the end x is present if and only if
`lo < n and state[lo] == x`. The sorted copy itself stays: sorting in place would modify
the caller's array. Linear search and hash set were not changed.

**Why.** Slicing turns an O(log n) search into O(n) time and O(n) temporary memory per
query. Two iterative candidates (classic three-way comparison and lower bound) were
implemented and tested; the lower-bound version had the lower median in all 9 measured
cells (`bench/binary_variants.py`) and was chosen.

**Measured effect** (n = 100,000, q = 100): query batch about 190× faster (0.049 s →
0.00025 s), query peak memory 782 KiB → 1.1 KiB, total time about 2.7× faster
(0.076 s → 0.028 s; the unchanged sort is now most of the cost). With q = 1 the total time
does not change measurably. All tests pass for both versions.

## AI use

Developed with Claude Code (Claude Opus 5.5) under the rules in [AGENTS.md](AGENTS.md): the
AI wrote code and documents step by step; Laurin made the design decisions, reviewed each
step and ran all git commands. Every accepted, corrected or rejected AI suggestion is listed
in [docs/AI_LOG.md](docs/AI_LOG.md).

Docker packaging (optional in the lab) was not done.
