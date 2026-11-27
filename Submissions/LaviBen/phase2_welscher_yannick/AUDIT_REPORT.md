# Audit report: WelscherYannick

## Target and method

- Reviewer: Ben Lavi
- Review date: 2026-11-20
- Pull request: <https://github.com/cogeorg/AlgorithmsFinance/pull/23>
- Exact commit: `654516b585dd419ff63f37642d5c211891799fcb`
- Submission path: `Submissions/WelscherYannick/`
- Recorded measurement-code commit: `e32d0aad9b88aeafaf3a5d1564665503de6a2af0`

The PR commit was checked out in a separate clean clone. No audited file was
edited. Dependencies were installed into a temporary virtual environment, and
all destructive dashboard probes changed only a disposable copy under `/tmp`.

## Baseline reproduction

The supplied project built and ran successfully with its pinned dependencies
under CPython 3.14.7 on arm64 macOS:

- `pip check`: no broken requirements;
- supplied test suite: **230 passed in 22.22 seconds**;
- Streamlit server: health endpoint returned `ok`, root returned HTTP `200`;
- quick runtime pipeline: 270 rows written outside the repository;
- quick memory pipeline: 270 rows written outside the repository; and
- audited Git working tree remained clean.

An independent literal-answer probe covered empty IDs and queries, duplicates,
unsorted IDs, first and last matches, absent and repeated queries, repeated
calls on one prepared state, later mutation of the original IDs, mutation of
the prepared state by `query`, output type, and input mutation. All **90
assertions passed** across the nine registered method/version pairs. I did not
reproduce an algorithm-correctness failure.

The committed evidence is internally consistent:

- timing: 675 rows, 135 scenario/version/method groups, five repeats each;
- memory: 405 rows, 135 groups, three repeats each;
- all scenario fields agree between timing and memory data;
- timing units are seconds per call and memory units are bytes;
- every dashboard median/minimum/maximum matched an independent recomputation
  from `timing_raw.csv`; and
- every dashboard memory median matched `memory_raw.csv`.

## Reproduced defects and omissions

### 1. Required audit commit is not recorded

The README's `Commit for the audit` section ends with the literal statement
that it is a placeholder. It contains no full audit SHA or immutable tag.
The measurement metadata does record the older code commit `e32d0aa`, but that
is not a recorded immutable target containing the final README, dashboard,
tests, and saved artifacts at PR commit `654516b`.

This prevents a reviewer from identifying the one final version the assignment
asks them to audit without relying on the moving PR head.

Evidence: `README.md` lines 395-399 and the `audit section` check in
`reproduce_audit.py`.

### 2. Dashboard serves stale data after result files change

`dashboard/app.py` decorates a zero-argument `load()` function with
`@st.cache_data`. The cache key therefore contains no file path, modification
time, or content digest. Rerunning a benchmark while the Streamlit process is
open does not invalidate the cached frames.

Reproduction in a disposable copy:

1. Render the dashboard with `AppTest`.
2. Change the first raw `prepare_s` value from `2.53701923029e-05` to
   `123.456789`.
3. Rerun the same dashboard session.
4. The displayed raw table still shows `2.53701923029e-05`.

This conflicts with the README instruction that rerunning the benchmark
refreshes the numbers unless the user also clears the cache or restarts the
server, neither of which is documented.

Evidence: `dashboard/app.py` lines 31-42 and the cache probe in
`reproduce_audit.py`.

### 3. The versions filter is ignored by the revision-overview chart

The README says the filter row applies to all views and controls the versions
shown. After selecting only `v1`, the Runtime plots correctly reduce to v1,
but the revision-overview plot still contains two traces named
`v2 (iterative)` and `v3 (lower bound)`.

The overview builds `later = ALL_VERSIONS[1:]` instead of using the selected
`versions` value. This is a visible filter/UI inconsistency; the supplied
dashboard smoke test checks only that filtering does not raise an exception.

Evidence: `README.md` lines 332-340, `dashboard/app.py` lines 191-229, and the
filter probe in `reproduce_audit.py`.

### 4. The memory table does not contain all advertised memory columns

The README describes a table of "all memory columns." The rendered summary
table contains:

`prepare current`, `prepare peak`, `query current (output)`, `query peak`, and
`total peak`.

It omits `total_current_B` and `output_getsizeof_B`, even though both are
defined as memory columns and are present in the raw-data tab. This is a
documentation/dashboard mismatch rather than a raw-data loss.

Evidence: `README.md` lines 341-342, `dashboard/data.py` lines 14-17, and
`dashboard/app.py` lines 283-297.

### 5. Separately measured totals can be lower than preparation alone

Independent recomputation found:

- **160 of 675 raw timing rows** with `total_s < prepare_s`; and
- **32 of 135 median groups** with median total below median preparation.

The largest median contradiction was v3 hash search in scenario 6:
preparation `0.000118331933 s`, total `0.000109685075 s`, so total was **7.3%
below** an operation it includes.

The author explicitly documents this anomaly and warns against interpreting
separately timed differences of that size. I therefore classify it as a
reproduced measurement shortcoming, not a hidden correctness bug. It still
means the preparation, query, and total columns are not additively reliable.

Evidence: `README.md` lines 355-372 and the raw-timing check in
`reproduce_audit.py`.

## Suspected weaknesses and limitations

These observations are plausible risks or design trade-offs, not reproduced
functional bugs.

1. **Linear preparation performs an avoidable O(n) copy.** `linear_prepare`
   converts the input to a tuple, costing about 800,040 traced bytes at
   `n=100,000`. The course contract requires leaving the caller's input
   unchanged, which scanning by reference already satisfies. The stronger
   requirement that prepared state ignore later caller mutations is
   self-imposed. It makes linear search look slower and larger in total-time
   and preparation comparisons than a conventional linear-search
   implementation.

2. **Order rotation is incomplete.** There are nine method/version pairs but
   only five repeats, shifted by one position per repeat. Each pair therefore
   occupies only five of nine possible order positions. A multiple of nine or
   a balanced randomized schedule would better separate version effects from
   thermal, frequency, and order effects.

3. **The benchmark measures warmed repeated-batch throughput.** Calibration
   and each repeat invoke the same operation many times on the same IDs,
   prepared state, and queries. That is documented and improves timer
   resolution, but CPU cache and branch-predictor reuse mean the absolute
   query numbers should not be read as cold, first-call latency.

4. **Dashboard tests assert survival, not filter semantics.** The supplied
   tests change each filter and assert only that no exception appears. They do
   not assert which traces, rows, or versions remain, allowing the reproduced
   version-filter inconsistency to pass.

## Recommended fixes and optimizations

The following changes are ordered by audit priority. They are recommendations;
the audited source was not modified.

### Priority 1: reproducibility and visible dashboard defects

1. **Record an immutable final target.** Replace the README placeholder with
   the full 40-character SHA of the final runnable commit and, preferably, an
   annotated tag. The recorded commit must contain the algorithms, tests,
   raw results, dashboard, dependencies, and instructions together.

2. **Make the dashboard cache depend on its input files.** Pass a fingerprint
   of the four result files (path plus modification time, size, or content
   digest) into the cached loader. Another acceptable fix is to clear the
   cache after a benchmark or document that the dashboard process must be
   restarted. A file fingerprint is safer because it updates automatically
   and still avoids reloading data on ordinary filter changes.

3. **Honor or relabel the version filter.** The revision-overview chart should
   derive its traces from the selected versions. If the overview is
   intentionally global, move it outside the filtered views and label it
   explicitly; do not claim that the version filter applies to all views.
   Add tests that assert trace names and counts after selecting v1, v2, v3,
   multiple versions, and no versions.

4. **Make the memory table match its documentation.** Add `total_current_B`
   and `output_getsizeof_B` to the visible summary table, or change the README
   from "all memory columns" to the exact chosen subset. Keep the raw-data tab
   unchanged because it already preserves every column.

### Priority 2: measurement reliability

5. **Do not interpret independently timed components as additive.** The
   dashboard should visibly warn when total is below preparation, or present
   preparation, query, and total as three independent estimates. For a
   stronger decomposition, measure the component boundaries and combined
   boundary within the same invocation/repeat, while acknowledging the extra
   timer-call overhead.

6. **Use a balanced measurement order.** Nine method/version pairs should each
   occupy every order position equally. Use at least nine repeats with a Latin
   square or deterministic balanced rotation, or use several independently
   seeded randomized orders and store each order. Report confidence intervals
   or distributions in addition to a five-repeat median.

7. **Separate warm-throughput and cold-start claims.** The current benchmark
   repeatedly runs the same IDs, state, and query batch, so it is a steady,
   cache-warmed throughput test. Retain it, but label it that way and add a
   separate one-call or fresh-process measurement if first-call latency is a
   claim of interest.

8. **Strengthen benchmark correctness checks.** The timed loops keep only the
   final returned value. The contract suite catches the current methods, but
   the harness itself would miss a method that returned wrong answers on an
   earlier repeated call and a correct final answer. A low-overhead untimed
   check before and after each timed block, including prepared-state equality,
   would make the harness more defensive.

### Priority 3: algorithm and project efficiency

9. **Remove the linear prepared-state copy unless the stronger state snapshot
   contract is required.** Directly retaining the input reference makes
   linear preparation O(1) time and space while still leaving the input
   unchanged. If independence from later caller mutation is intentionally part
   of the API, keep the tuple copy but describe this as extra snapshot cost,
   not inherent linear-search auxiliary space.

10. **Reduce iterative binary-search Python overhead.** A future version can
    inline the per-query loop into `binary_query` rather than calling a helper
    once per query, cache the sequence length once per batch, and compare the
    balanced loop with the lower-bound loop across present, absent, and mixed
    cases. Preserve v1-v3 so the new version remains auditable.

11. **Choose methods by workload rather than declaring one universal winner.**
    The saved evidence already shows hash membership is best for 100 queries,
    while linear can win for a single query because it avoids indexing work.
    If many batches reuse the same IDs, expose prepared states clearly so the
    binary sorted copy or hash set is built once and reused; benchmark that
    reuse scenario separately from one-shot `contains_all`.

12. **Trim dependency management.** `requirements.txt` lists the complete
    transitive environment. Keep a lock file for exact reproduction, but also
    provide a short direct-dependency file (`pytest`, `pandas`, `plotly`, and
    `streamlit`) so reviewers can understand and install the actual project
    requirements more easily.

## Conclusion

The search implementations passed both the supplied suite and independent
edge-case checks. Raw result schemas, units, scenario consistency, memory
labels, and dashboard arithmetic are unusually well documented and internally
consistent. The strongest actionable findings are the missing immutable audit
target and the two reproducible dashboard state/filter defects. Performance
claims should retain the author's own noise warning, especially because some
separately measured totals are lower than preparation alone.
