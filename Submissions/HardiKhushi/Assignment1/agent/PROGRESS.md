# Assignment 1 progress

## 1. Read-only review and organization (26 November 2026)

User approved inspection, then organization, then end-to-end completion while
retaining per-commit approval. Existing Assignment1 was empty; Git was clean at
ae01998ab1e03c20d5063fd96519d216854ede73 on audit/liuhaina.
All supplied substantive files matched their original manifest. Missing .DS_Store
is irrelevant macOS metadata and is not invented or added.
PDF text was read using macOS PDFKit because Poppler and Python PDF packages
were unavailable; no dependencies were installed.
Preserved source instructions/data, created an isolated Assignment1 layout,
working agreement, AI instruction/decision records and requirements checklist.
Earlier search algorithms, results and peer-audit evidence remain untouched.
No engine implementation has been written yet. No commit is authorized yet.

## 2. Tests before code

Stage 1 committed with explicit approval as 8270fac; post-commit status clean.
Wrote independent contract tests and deterministic workload checks before any
engine Python file existed. Executed the full suite: failures from missing
orderbook modules are preserved in results/evidence/tests_before.txt; exact
test hashes and return code in tests_before.json. Expected values cover the
worked sale, crossing limits, FIFO, residuals, cancellation, atomic validation,
long queues, generated sale oracles and per-event conservation/differential checks.
Generator checks execute independently of missing engines. No test result has
been weakened to accommodate an implementation.

## 3. Baseline implementation

Tests-first checkpoint committed with explicit approval as 35125e8; clean status
verified. Implemented Version A using a list of individual active orders and
explicit best-price/arrival scans, shared atomic validation/result formatting,
standard-library JSON/gzip reader and replay CLI. The revision did not exist
when the baseline suite ran. All 22 baseline-stage tests completed successfully
(21 passed; the revision comparison was explicitly skipped). Exact test file
hashes still match the red-run record. Log: results/evidence/tests_baseline.txt.

## 4. Revised price-queue implementation

Baseline committed with approval as 52a6c5e; post-commit status clean.
Preserved Version A; added Version B with sorted occupied prices, OrderedDict
FIFO queues and a live identifier index. Cancellation deletes immediately;
there are no stale orders or retained event/trade histories. Price-list updates
remain O(P), rather than claiming logarithmic insertion. OrderedDict avoids
repeated scans over deleted prefixes of a plain dict used as a FIFO queue.
All 43 tests passed, including unchanged original contract test hashes, 4,500
generated events compared after every event, quantity/maker conservation and
new storage/churn regression tests. Log: results/evidence/tests_revised.txt.

## 5. Measurement and evidence

Revision committed with approval as 3276644; post-commit status clean.
Added and passed four measurement-definition tests (47 total). The protocol
smoke run passed before the full experiment. Executed all 90 primary version/
scenario/seed/size configurations, plus construction/application, separate
tracemalloc and latency/counter/depth diagnostics, fixed fresh-book 10/100/200%
sales at 4/1000 available prices, and million-event streaming cancellation churn.
The same four-second wall deadline applied to both engines. Saved 2,478 raw/
diagnostic records, 257 timing summary groups and 642,536 per-event latency
samples. There were 48 stopped timed trials across phases; these remain labelled.
All original test hashes and 12 actual measured-source hashes match. Independent
verification recomputed medians/throughput, all saved percentiles, matrix coverage,
input checksums and memory invariants. All 47 tests passed again. Baseline/revised
completed medians paired in 33 cases: revision faster in 24 and slower in all
nine tiny-active-book churn cases. Million-event streaming parse and both engines
completed warmup plus five repetitions. Generated large inputs remain ignored.

Second verification exported each of the four approved commits: organization
had no engine; tests-only reproduced 37 expected missing-module errors out of
40 tests; baseline passed 21 with one skip; revision passed 43. Evidence is in
results/evidence/checkpoints/ and checkpoint_verification.json. The exporter
initially used a subfolder cwd for a repository-relative archive path; corrected
the helper, reran successfully, and did not change engines or measured results.

## 6. Saved-results dashboard, report and delivery checks

Measurement checkpoint committed with approval as 383b0aa. Its clean local Git
export verified all 52 files against Git blob IDs, passed all 47 tests and both
worked-example replays, revalidated the saved results and exercised CLI help.
That second-verification record is clean_export_383b0aa.json/.txt.

Built the offline dashboard solely from saved measurements, with replay,
throughput, construction/application/parsing, allocation growth/cleanup, per-event
latency distributions/percentiles, fresh-book liquidation/reset scaling, correctness
records, raw repeats, stopped trials and JSON download. It preserves all nine
churn regressions and labels incomplete baseline observations. Wrote the report,
clean-environment README, actual requirements/evidence map, contribution and
commit records; linked Assignment1 from the parent README. The earlier lab's
code/results, audit, course folders and other students remain unchanged.

Chrome passed 90 main filter states at each of 1440- and 500-pixel widths, 463
checks per viewport including raw-data median cards, finite charts, nonoverlapping
x-axis labels, no document overflow, six liquidation selections, three phases,
plain JSON Blob download contents and no JavaScript errors. Top and lower page
screenshots were visually inspected. Sandbox launches aborted before page load;
the authorized external local Chrome launch succeeded. Corrected a requested
460-pixel screenshot versus Chrome's actual 500-pixel minimum, improved narrow
controls, replaced a blank scrolling capture fixture, and spaced chart labels.
Only QA/presentation code changed; measured engines/tests/results did not.

Original test hashes, 12 measured-source hashes, all raw medians/percentiles,
source-data checksums and embedded dashboard data verify. A clean staged delivery
export and post-commit verification are the final checks, using
agent/verify_submission.py; benchmark runs are not repeated for those checks.
The user explicitly approved the final local commit and post-commit verification.
Before approval, clean staged tree 1e27381155a98a3a0bec897be739bfc46aab9193
verified all 64 project files, passed 47 tests and both worked examples, rechecked
saved results/CLI help, and rebuilt dashboard/findings byte-for-byte identically.
The delivery commit identifier is in Git history and the completion message.
No push or external publication is authorized.

## 7. Assignment 1 publication preparation

The user requested pushing Assignment1 as the submission. Prepared a clean
publication branch from current origin/main, preserving the six Assignment1
snapshots and excluding the earlier local peer-audit changes. Added public/local
checkpoint mapping and made Git export verifiers use that mapping and the public
course base. No measured engine, tests, benchmark source or raw values changed.
The parent README links to Assignment1. New publication commits require approval.

The user approved the publication commit batch and push. All six original
Assignment1 tree snapshots were recreated byte-for-byte on the course base;
PUBLICATION.json records actual public commit IDs. Their test-first ordering is
preserved. Final checks cover the mapped checkpoints and clean submission tree.
