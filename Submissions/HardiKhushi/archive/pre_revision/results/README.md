# Saved results and provenance

These are preliminary measurements from the initial implementation created on
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

Before a future approved benchmark run, archive these preliminary files and
update this provenance document. The current benchmark overwrites these CSV
paths. Future output adds generator-setting columns; the original files remain
in their old schema. Do not invent new metadata columns in the old data.
