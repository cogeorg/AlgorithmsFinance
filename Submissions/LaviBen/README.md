# Search Algorithms — LaviBen

- **Student:** Ben Lavi
- **Required folder name:** `LastnameFirstname` -> `LaviBen`
- **Language:** Python 3.10+

Tests-first implementation and runtime comparison of three ways to answer
ordered membership queries over integer IDs:

1. manual linear search;
2. manual binary search over a sorted copy; and
3. Python standard-library hash-set membership.

All methods return one Boolean per query in the original query order and leave
the supplied ID array unchanged. The recursive binary-search version is kept
beside the revised iterative version for direct comparison.

## Quick start

Python 3.10 or newer is sufficient; there are no third-party dependencies.

```bash
cd Submissions/LaviBen
python3 -m unittest discover -s tests -v
python3 benchmark.py
python3 dashboard.py
```

Open `results/runtime_dashboard.html` in a browser to inspect the generated
dashboard.

## Example

```python
from search_algorithms import binary_search, hash_set_membership, linear_search

ids = [7, 11, 7]
queries = [11, 9, 7]
expected = [True, False, True]

assert linear_search(ids, queries) == expected
assert binary_search(ids, queries) == expected
assert hash_set_membership(ids, queries) == expected
assert ids == [7, 11, 7]
```

## Implementations

| Function | Approach | Total time for `n` IDs and `q` queries | Extra working space* |
|---|---|---:|---:|
| `linear_search` | Scan IDs for each query | `O(nq)` | `O(1)` |
| `binary_search_recursive_v1` | Sort once, recursively halve each search range | `O(n log n + q log n)` | `O(n + log n)` |
| `binary_search` | Sort once, iteratively halve each search range | `O(n log n + q log n)` | `O(n)` |
| `hash_set_membership` | Build a set once, then perform membership lookups | Expected `O(n + q)` | `O(n)` |

\*Excluding the required `O(q)` result list. Hash-table lookup is expected
`O(1)` per query; adversarial collisions can make the worst case slower.

`sorted(ids)` creates the binary-search copy, so the caller's array is never
sorted in place. Linear and binary search procedures are implemented directly;
the core does not delegate to `list.index`, `bisect`, or another search helper.

## Tests-first evidence

The tests were created before either implementation module. The first run
exited with code `1` because `search_algorithms` and `synthetic_data` were
missing. Version 1 then passed all seven original tests. After review, boundary,
generator, and fixed-input benchmark cases were added; the final suite contains
eleven passing tests.

The shared cases cover:

- empty arrays and empty queries;
- one present or absent entry;
- duplicates and unsorted inputs;
- negative IDs, repeated queries, and boundary misses;
- present and absent queries in a deliberately mixed order;
- exact Boolean output order and type; and
- unchanged list and tuple inputs.

See [`DEVELOPMENT_LOG.md`](DEVELOPMENT_LOG.md) for the failing baseline, manual
trace, revision record, and AI-use disclosure. See
[`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) for the complete
requirement-to-evidence mapping and correctness arguments. Passing tests provide
evidence of expected behavior, not a proof of correctness.

## Synthetic data and measurement

`synthetic_data.py` uses a local seeded random generator and is independent of
both the algorithms and measurement code. IDs are sampled with replacement
from `max(1, n // 3)` possible values, so larger arrays intentionally contain
duplicates.

The benchmark fixes an 18-case matrix before timing:

- array entries `n in {1,000, 10,000, 100,000}`;
- query counts `q in {1, 100}`; and
- `all_present`, `all_absent`, and `mixed` query scenarios.

Each case is generated exactly once, converted to immutable tuples, and
fingerprinted with SHA-256. Every method and version receives that same object
pair. For `q=1`, a literal 50/50 mix is impossible; nearest-integer half-up
rounding produces one present query, and both the requested (`0.5`) and realized
(`1.0`) rates are saved.

Five repetitions rotate method order deterministically. The benchmark records:

- **preparation:** no index for linear search, sorting for binary search, and
  set construction for hash membership;
- **query batch:** the complete ordered query list; and
- **combined:** elapsed time spanning preparation and the complete batch.

Raw nanosecond timings, millisecond medians, seeds, generator settings, input
digests, Python and machine details, and Git/source versions are saved under
`results/`. `dashboard.py` turns the JSON into a self-contained HTML dashboard
without external JavaScript or plotting libraries. Timings describe one
machine and run; rerun the benchmark before making environment-independent
performance claims.

Recorded medians for `n=100,000`, `q=100`, mixed queries:

| Implementation | Preparation (ms) | Query batch (ms) | Combined (ms) |
|---|---:|---:|---:|
| Linear search | 0.065250 | 51.143791 | 51.227500 |
| Binary search recursive v1 | 10.468250 | 0.127834 | 10.596250 |
| Binary search iterative v2 | 10.557000 | 0.104333 | 10.673750 |
| Hash set membership | 1.876375 | 0.004750 | 1.882083 |

This run used Python `3.14.7` on `arm64` and clean submission code commit
`b122ea5`. Full machine fields, source SHA-256, and raw observations are in
`results/benchmark_results.json`.

## Project layout

| Path | Purpose |
|---|---|
| `search_algorithms.py` | Required methods and preserved recursive version |
| `synthetic_data.py` | Deterministic input generation |
| `benchmark.py` | Fixed-input preparation/query/combined measurement |
| `dashboard.py` | Self-contained HTML dashboard generation |
| `tests/` | Shared algorithm, generator, and pipeline tests |
| `results/benchmark_results.json` | Metadata, cases, raw timings, and summaries |
| `results/benchmark_results.csv` | Median preparation/query/combined summary |
| `results/raw_timings.csv` | Every repetition in raw nanoseconds |
| `results/input_manifest.json` | Seeds, hit rates, duplicate policy, and input digests |
| `results/runtime_dashboard.html` | Generated runtime dashboard |
| `DEVELOPMENT_LOG.md` | Test-first, trace, revision, and AI-use evidence |
| `SUBMISSION_CHECKLIST.md` | Requirement mapping and correctness reasoning |

## Phase 2 — Audit

The selected classmate implementation, reproduction steps, correctness
findings, and performance evidence will be added here during Phase 2.
