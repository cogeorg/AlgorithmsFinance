# Assignment 1 submission review — LiuHaina

**State: implementation, evidence and clean-copy reproduction checked; final commit/submission pending.**

The working directory is `Submissions/LiuHaina/Assignment1/` in the clone whose origin is `https://github.com/cogeorg/AlgorithmsFinance.git`. Other students' directories and tracked course files are unchanged.

| Requirement | Evidence | State |
|---|---|---|
| Sequential integer-unit order book, own live `FillMarketSell`, cancellation and inspection | `lob/`, worked example and independent tests | Checked |
| Preserved baseline and justified revision | `version_a.py`, `version_b.py`, complexity notes, `REVISION.md` | Checked; measured source hashes unchanged |
| Tests before implementation, independent expectations and per-event comparison | Red-phase logs, `TEST_PLAN.txt`, 63 tests, 50,000 supplied-event comparison | Checked |
| Five workload families, three sizes, three seeds, five repeats | 450 primary attempt records, 360 complete / 90 stopped | Checked; censored runs retained |
| Fixed-book 10% / 100% / 200% sales and 4 / 1,000 available prices | 180 planned records, 150 completed / 30 blocked by construction timeout | Checked; fresh reset per executed sale |
| Parsing / replay / construction, throughput and independent latency | Raw tables, phase labels, 2,292,107 event-time samples | Checked |
| Separate memory, insertion growth, cancellation cleanup and operation diagnostics | Tracemalloc rows/snapshots, small line-traced runs | Checked; scope and partial runs labelled |
| Dashboard reads saved measurements | Offline `dashboard.html`, 180 global + 18 sale-filter browser checks | Checked |
| Short report, modeling limits, pseudocode, costs, profiling and AI revision record | `REPORT.md`, methods and version notes, `REVISION.md` | Present; author review remains |
| Reproducible project and clean-environment commands | `README.md`, standard-library runtime, recorded Python/OS, source/input hashes | Clean-copy checks passed |
| Large generated input omitted | `work/` ignored; generation commands/checksums in input manifest | Checked; candidate files contain no generated `.jsonl.gz` event streams |
| Final submitted code commit identifier | Current SHA-256 source map identifies measured uncommitted code | **Pending authorized commit** |
| Submit to the course repository under the personal assignment directory | Correct local structure exists | **Not submitted or pushed** |

Docker and peer audit are not required. No historical exchange account or dataset is needed.

## Clean-copy checks actually performed

`tools/preflight_submission.py` obtained the candidate file list without staging, copied only non-ignored files, and excluded all generated work. In that copy it successfully:

1. Ran all 63 tests and both official worked examples, comparing exact fills, remaining orders and proceeds.
2. Audited saved results without absent generated input files, explicitly marking input-hash recomputation as not checked and preserving the original full validation.
3. Rebuilt the dashboard byte-for-byte identical to the browser-verified HTML and checked its saved evidence.
4. Ran a fresh small benchmark covering ten version/workload cases and fifty completed primary repeats, then validated its results.
5. Confirmed the original Git HEAD, index bytes and staged state remained unchanged.

Logs and machine-readable results are in `evidence/submission_review/`. Generated inputs can be rebuilt from `results/benchmark/input_manifest.json` when input-hash recomputation or fresh measurement is desired. Full measurements were not rerun during this review.

The original preflight candidate was approximately 15.2 MiB; the largest file was the approximately 1.6 MiB offline dashboard. Most of the file count is small per-job settings/stdout/stderr evidence, not large event streams.

## Remaining actions

- LiuHaina reviews `REPORT.md` and the dashboard for authorship, wording and course-specific expectations.
- Once explicitly authorized, create the final submission commit and record its identifier. The existing Git base commit is historical provenance, not the submitted code version.
- Only after authorization, perform the actual course-repository submission. No add, commit or push has been performed in this review.
