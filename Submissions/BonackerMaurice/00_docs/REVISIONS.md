# Revisions

Both versions of each revised method stay registered in
`01_code/search_algos/registry.py`, are tested by the same suite, and are measured on
identical inputs. `CURRENT` names the version that represents the submission.

| Method | v1 (original) | v2 (revised) | Current |
|---|---|---|---|
| LinearSearch | `list(ids)` copy, then an index-based `while` scan | no copy, direct `for` iteration | v2 |
| BinarySearch | `sorted()` copy, then a recursive search with early exit | `sorted()` copy, then an iterative lower-bound search | v2 |
| Hash membership | `set(ids)`, then `q in s` | (not revised) | v1 |

## Revision 1: LinearSearch v1 → v2

**What changed:**

1. `prepare` no longer copies the input. v1 made a defensive `list(ids)` so the
   caller's array "cannot change". The scan only reads, though, so the copy
   protects nothing. It costs O(n) time and about 8 bytes per element (one list
   of references) on every call.
2. The scan iterates directly (`for value in data`) instead of using an index
   (`while i < n: data[i] ... i += 1`). This removes the index arithmetic and
   the `data[i]` lookup per element. Python's list iterator does both in C.

**Expected effect:**

- `prepare` drops from O(n) to O(1).
- The traced memory for preparation drops from about 8n bytes to 0.
- The query batch gets faster by a constant factor, and the complexity stays
  O(n·q).

**Evidence:**

- **Source:** run `02_results/20261120-142828_8e8109a`, made from commit
  `8e8109a` with a clean tree. Values are medians of 5 repeats.
- **Dataset:** n = 100,000, q = 100, mixed.

| | v1 | v2 | v1 / v2 |
|---|---|---|---|
| `prepare` | 331.3 µs | 0.1 µs (harness-overhead level, `noop_call_s` = 64 ns) | n/a |
| `query` batch | 376.1 ms | 147.8 ms | **2.55×** |
| `total` | 371.3 ms | 157.4 ms | 2.36× |
| traced `prepare` peak | 781 KiB (8 bytes per ID) | 0 KiB | |

- **Across all 15 datasets,** the query-batch speed-up is 1.86–2.94× (median
  2.55), and v2 is faster in every dataset.
- **This is well outside the noise band.** The same-code control below ranges
  0.78–1.27.
- **The fitted slope stays about 1** (query batch: v1 1.03, v2 0.96). The
  revision changes the constant factor, not the complexity.

## Revision 2: BinarySearch v1 → v2

**What changed:** the recursive search `_contains_recursive(a, x, lo, hi)`
became an iterative lower-bound loop. The loop narrows to the first index whose
value is `>= x` and then checks that one index.

**Why:**

- Every recursive call costs a Python function call (a frame plus argument
  passing). The loop runs one comparison per iteration with no calls.
- The recursion depth is only about log₂ n (17 at n = 100,000), so v1 is
  correct here. The iterative form still removes any dependence on the
  recursion limit.

**Trade-off:** v1 can return early when `a[mid] == x`. v2 always runs about
⌈log₂ n⌉ + 1 iterations. The comparison should therefore look at
`all_present` separately from `all_absent`.

**Control:** `prepare` is the same function (`sorted`) in both versions. Their
`prepare` ratio should be about 1.0. Any deviation shows the measurement noise
level, and the dashboard shows it as the "same-code control".

**Evidence:**

The source is the same run as above. Query-batch medians at n = 100,000 and
q = 100:

| Scenario | v1 | v2 | v1 / v2 |
|---|---|---|---|
| all_present | 325.0 µs | 261.9 µs | 1.24× |
| all_absent | 213.4 µs | 165.0 µs | 1.29× |
| mixed | 184.6 µs | 154.3 µs | 1.20× |

- **Across all 15 datasets:** the speed-up is 1.10–1.53× (median 1.26), and v2 is
  faster in **15 of 15**.
- **Noise caveat:** a single ratio of this size lies inside the noise band of
  the same-code control. Binary `prepare` is identical code in v1 and v2, yet
  its v1/v2 ratio has a median of 1.08 and a range of 0.78–1.27.
- **Why the result still holds:** the evidence is the consistency. The revision
  is faster in every dataset, and v1 and v2 are measured interleaved under the
  same conditions.
- **Early exit:** the expected benefit of v1's early exit on `all_present` is at
  most a hint. The present speed-up is 1.24 against 1.29 for absent, which is
  within noise.
- **`total` does not show the revision:**
  - At n = 100,000, sorting takes about 17–20 ms, against 0.15–0.18 ms for the
    query batch.
  - The total v1/v2 ratio (0.88) is therefore prepare noise.
  - Memory is unchanged: the same sorted copy, with a 1,172 KiB traced peak
    including timsort's merge buffer.

## Tests rerun after the revision

The suite is parametrized over every registered method and version, so v1 and
v2 always run the same tests. Result: 674 passed, recorded in
`02_results/20261120-142828_8e8109a/tests.txt`.
