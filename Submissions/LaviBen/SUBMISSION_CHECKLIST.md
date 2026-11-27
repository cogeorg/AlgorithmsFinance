# Submission checklist and correctness notes

- Student: **Ben Lavi**
- Submission folder: **`Submissions/LaviBen/`**
- Implementation language: **Python 3.10+**

## Requirement-to-evidence map

| Requirement | Status | Evidence |
|---|---:|---|
| Implement linear search manually | Complete | `linear_search` in `search_algorithms.py` |
| Implement binary search manually on a sorted copy | Complete | `binary_search_recursive_v1` and revised `binary_search` |
| Implement standard-library hash-set membership | Complete | `hash_set_membership` |
| Return one Boolean per query in the same order | Complete | Shared case table and output-type assertions in `tests/test_search_algorithms.py` |
| Leave the supplied array unchanged | Complete | Copy comparisons for every shared case; tuple-input test |
| Run the same tests against all methods | Complete | `ALL_IMPLEMENTATIONS` drives every shared case |
| Cover empty arrays and empty queries | Complete | `CASES` entries `both empty`, `empty array`, and `empty queries` |
| Cover one entry | Complete | Present and absent one-entry cases |
| Cover duplicates and unsorted input | Complete | Required `[7, 11, 7]` example and boundary duplicate case |
| Cover present and absent queries | Complete | Every nonempty shared case mixes or isolates hits and misses |
| Check output order | Complete | Repeated-query case has a deliberately mixed expected sequence |
| Check the required example | Complete | `[7, 11, 7]`, `[11, 9, 7]` -> `[True, False, True]` |
| Write tests before implementation | Complete | Failing baseline with exit code `1` in `DEVELOPMENT_LOG.md` |
| Keep synthetic data separate | Complete | `synthetic_data.py`; algorithm and benchmark modules only import it |
| Generate larger deterministic inputs | Complete | `generate_search_case` with local seeded `Random` |
| Trace a small example | Complete | Step-by-step trace in `DEVELOPMENT_LOG.md` |
| Run every test after implementation | Complete | Seven-test version-1 run and final ten-test run |
| Make and preserve a revision | Complete | Recursive v1 retained; public binary search revised to iterative v2 |
| Add newly discovered tests | Complete | Boundary misses, zero queries, and 0%/100% hit-rate cases |
| Record what changed and why | Complete | Revision section in `DEVELOPMENT_LOG.md` |
| Explain AI suggestions | Complete | Accepted, corrected, and rejected lists in `DEVELOPMENT_LOG.md` |
| Measure performance | Complete | `benchmark.py` plus recorded JSON/CSV results |
| Build a runtime dashboard | Complete | `dashboard.py` and `results/runtime_dashboard.html` |
| Fix inputs before comparing methods | Complete | One immutable tuple pair and SHA-256 per manifest case |
| Use `n={1k,10k,100k}` and `q={1,100}` | Complete | Default benchmark matrix and input manifest |
| Include present, absent, and mixed queries | Complete | `SCENARIOS` and requested/realized hit-rate fields |
| Measure preparation, query batch, and combined time | Complete | Raw and summary timing columns |
| Save environment and code version | Complete | JSON metadata with Python, machine, Git, and source hash |
| Save raw measurements and units | Complete | `results/raw_timings.csv` in ns; JSON and summary CSV document units |
| Save generator settings per case | Complete | `results/input_manifest.json` with seed, rates, policy, and SHA-256 |

## Correctness reasoning

Passing tests are useful evidence, but they do not prove correctness. The
following arguments explain why each procedure satisfies the contract.

### Linear search

For one query, after the first `k` IDs have been inspected, `found` is true if
and only if the query has appeared among those `k` IDs. The loop either stops
when equality is observed or inspects every ID. It therefore returns true
exactly when the query occurs in the input. The outer loop appends one result
for each query from left to right, so output order and length match the query
sequence.

### Binary search

`sorted(ids)` creates a new sorted list, leaving the caller's sequence
unchanged. At the start of every iterative step, if the query exists in the
sorted list, it is within the inclusive interval `[low, high]`:

- equality at `middle` proves membership;
- if the middle value is smaller, sorted order excludes indices through
  `middle`, so setting `low = middle + 1` preserves the invariant; and
- if the middle value is larger, sorted order excludes indices from `middle`
  onward, so setting `high = middle - 1` preserves the invariant.

Each nonterminal step strictly shrinks the interval. If it becomes empty, the
invariant implies the query is absent. The recursive version uses the same
interval argument; the iterative revision changes control flow, not results.

### Hash-set membership

Python constructs `set(ids)` containing exactly the distinct input values.
Testing each query against that set therefore returns true exactly for present
IDs. Queries are evaluated by a list comprehension in their original order.
Set construction reads the input but does not mutate it.

## Reproduction commands

Run from `Submissions/LaviBen/`:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q .
python3 benchmark.py
python3 dashboard.py
```

Expected test result: **11 tests pass**. Runtime values can vary by machine;
correctness results must not.

## Scope and limitations

- Inputs are documented as integer sequences; runtime type validation is not
  added because it is outside the assignment contract.
- Hash-table lookup has expected constant-time behavior, not a universal
  worst-case guarantee.
- Recorded timings are reproducible measurements for one environment, not
  proof of general performance.
- Phase 2 auditing of another student's project remains a separate future
  deliverable.
