# Algorithms in Finance — Joga Singh

## Goal
Compare linear search, binary search on a sorted copy,
and membership using a Python set.

## Synthetic data

Generate and print a reproducible case from this folder:

```powershell
python data/generate.py --n 10 --q 4 --hit-rate 0.5 --seed 42
```

`--n` sets the number of IDs, `--q` the number of ordered queries,
`--hit-rate` the requested fraction of present queries, and `--seed` the
random seed. The requested hit count is `int(q * hit_rate + 0.5)`. IDs are
non-negative integers sampled with replacement from `[0, 10*n]`, so
duplicates are allowed. Present queries are sampled from the IDs; absent
queries are negative integers sampled with replacement from `[-q, -1]`, and
query order is shuffled. Expected answers are calculated independently from
the generated IDs. The JSON metadata keeps both requested and actual hit
rates; with `q=1`, a 50% actual rate is impossible. The optional
`--output PATH` saves the same JSON and creates missing parent directories.

Negative absent queries are a controlled workload choice: their ordering and
values can influence binary-search performance.

## Specification tests

From this folder, run:

```powershell
python -m pytest -q
```

Implemented methods in `algorithms/search.py`:

- `linear_search` scans the ID list for each query.
- `binary_search` recursively searches a sorted copy using index bounds.
- `hash_membership` builds a set once and checks each query.

The initial implementation passes all 39 specification cases. The exact test
command and output are recorded in `results/tests_initial_implementation.txt`.
That passing initial version is preserved in `algorithms/search_v1.py`.

AI assistance: AI generated the initial algorithm implementation; its exact
passing version is preserved in `algorithms/search_v1.py`.

Review the worked method trace in `docs/walkthrough.md`.