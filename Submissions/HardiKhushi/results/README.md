# Saved results and provenance

## Current manual-version experiment

The root CSVs contain 36 workload combinations and 216 method/version
configurations, with five repeats. Exact run settings, Python/machine details,
protocol, git state, and source hashes are in `environment.json`.

| File | Definition |
| --- | --- |
| `timing.csv` | One row per configuration, with median/min/max preparation, query-batch, and total milliseconds per complete execution. |
| `memory.csv` | One row per configuration, with median/min/max current and peak traced bytes for separate full calls. |
| `timing_raw.csv` | One row per phase/repeat, with elapsed batch milliseconds, execution count, and milliseconds divided by executions. |
| `memory_raw.csv` | One row per tracing repeat, with current/peak bytes while prepared state and output remain alive. |
| `environment.json` | Settings, protocol, machine/Python details, and hashes of measured source files. |
| `SUMMARY.md` | Generated measured findings, including regressions and limitations. |
| `qa/` | Browser checks identified by run ID; validation artifacts rather than performance measurements. |

Join raw and summary rows by `run_id` and `case_id`; timing repeats also have
a `phase`. Summaries record method, version, n, query count, seed/effective seed,
generator version, actual hit rate/count, duplicate policies, and code version.
Timing is per complete batch, not per query unless q=1. Query-only repeats
prepare fresh state outside each timed batch and reuse it within that batch.
Preparation and total phases rebuild state on each execution. Independent phase
medians need not sum to the total. Short timings use saved batching divisors.

Inputs exist before tracing and are excluded from newly traced memory. New
prepared structures and output are included and kept alive at the reading.
Tracing is not process RSS and misses some native allocations. Dashboard KiB
means 1,024 bytes. All variants share identical inputs for each workload.

`original` means the first manual implementation in `search_original.py`;
`revised` means the manual revision in `search.py`. Older built-in searches
are a historical snapshot and are not a manual version in this experiment.
See `../REVISIONS.md` for the actual development sequence.

One seed, one machine, and sequential version runs limit interpretation. Ratios
are descriptive, not confidence intervals or universal improvements. Source
hashes identify uncommitted code more precisely than the parent git commit.
From the repository root, run `python3 Submissions/HardiKhushi/verify_results.py`
to verify sample counts, raw divisions/statistics, source/archive hashes, and
dashboard links. Dashboard/summary generation never runs measurements.

## Historical preliminary run

`history/legacy/timing.csv` and `history/legacy/memory.csv` are preliminary
measurements from the initial implementation created on
20 November 2026. They are not the final assignment experiment.

- Source: the original `benchmark.py`, before generator extraction.
- Algorithms: Python list membership for linear search, `sorted` plus
  `bisect_left` for binary search, and standard-library set membership.
  The first two still need manually implemented search procedures.
- Workload: n = 1,000, 5,000, 10,000; q = 200; seed = 42, with each size
  using `random.Random(seed + n)`; unique shuffled IDs; 50% present queries;
  repeated queries permitted.
- Five repeats after a correctness check/warm-up. Nine summary rows per CSV.
- Timing includes preparation and query processing together, in milliseconds.
  Memory is separate peak traced allocation in bytes, including preparation and
  output but excluding already-created inputs. It is not process RSS.
- Python version, machine details, and measurement time are in the CSVs.
- No source commit identifier or raw repeat values were saved for the original
  run. The missing raw values cannot be recovered from the summaries.

During the approved organization step, the files were moved into this directory
without changing their contents. No benchmarks were rerun. SHA-256 at relocation:

| File | SHA-256 |
| --- | --- |
| `timing.csv` | `d1f4c4772142ff8e64eb4a82a511237ce4a961f32b34bce6c9b60cb6a77a39fd` |
| `memory.csv` | `6ab05a21c9f930aed8b7db3a9df70b1b2154a509c1f97f81c3b7a40d87220906` |

The extracted generator's default inputs reproduce the original benchmark's
arrays and queries; this is checked by a regression test. That does not make
these old results measurements of the updated benchmark code. New scenarios
and duplicate policies have not been measured here.

The expanded benchmark copied these files byte-for-byte to `history/legacy/`
before replacing the root CSVs. They are also preserved in the full snapshot
at `../archive/pre_revision/`. Old files retain their old schema; missing raw
repeats were not invented. Future approved benchmark runs copy existing root
results into `history/<previous-run-id>/` before writing a new run. Browser QA
is run-specific and must be repeated for new data or dashboard behavior changes.
