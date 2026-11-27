# AI assistance for Class 3

Codex read the lab requirements in PDF pages 30-32 and the earlier pricing
pseudocode, explained the steps, and inspected the provided course reference
algorithm read-only. This implementation deliberately follows the same
rolling-array structure rather than claiming an independently invented method.

For the first authorized coding stage, Codex wrote `price_american_put.py`,
the rational-arithmetic recursive reference and checks, and the learning and
progress notes. The reference enumerates paths rather than sharing the
implementation's array update logic. Passing small checks does not validate
large-tree numerical stability or complete the market-data assignment.

The user's later instruction to keep all work in this Class3 directory
supersedes updating parent progress/AI documentation for this lab. The empty
`american_put.py/` directory was discovered during inspection and preserved.
Execution outcomes are recorded in `PROGRESS.md`. The student has not yet
independently reviewed this code. Commits and uploads require authorization.

For the next authorized stage, Codex wrote the CSV loader, calibration/report
tool and small-fixture checks. Codex chose and documented Actual/365 Fixed
because the lab leaves the day-count basis unspecified. Data gaps are reported
without filling; elapsed time is used in the interest formula. The supplied
Bitcoin file is read-only input. The generated JSON is a calibration report,
not an option-price, timing or memory result. No price history was generated.

For stage 3, Codex preserved the original pricing file byte for byte, extended
the current version with optional exercise boundaries and a numerical-range
guard, and added historical-path comparison and a one-year measurement runner.
Eight new test methods include 189 comparisons of complete boundary policies
with independent exact rational trees, original-price regression checks,
worthless/expiry cases, unsafe ranges and path crossings. The original 15
test methods and their expected answers are unchanged.

Codex explicitly chose positive-payoff exercise nodes to avoid spurious
worthless exercise ties, uses a documented floating-point tolerance for the
boundary only, and retains the highest positive-payoff node at expiry without
interpolating to the strike. These implementation conventions are disclosed
in the README and run metadata. Timing and tracing use separate calls; results
are retrospective and gross payoff is not labelled net profit.

For stage 4, Codex identified that tracing the scalar full-file recurrence
would be costly, added a NumPy float64 version of the same rolling-row
recurrence and extended the runner to select an engine or the full file.
The stage-3 source files were archived and checked against the original
result's hashes before editing the runner. No earlier measurements were
overwritten or relabelled. NumPy was already installed; no package was fetched.

Codex added three test methods, including 189 exact/scalar policy comparisons,
then executed a one-year NumPy bridge and a full-file NumPy run. The bridge's
price/exercise result is exactly equal and its boundary CSV byte-identical to
the original scalar run. A buffer-allocation probe confirmed that NumPy
buffers are traced on the recorded runtime. Source/data/output hashes, all
43,823 full-file lattice/path rows and the first crossing were checked.

The full file has one missing hour, which was disclosed and not filled. A
five-calendar-year window is slightly over five Actual/365 Fixed years.
Runtime and memory are single measurements of separately labelled engines;
the new engine's timings are not presented as timings of the scalar version.
No 40-asset batch or memory-limit experiment has been performed yet.

## Comprehensive audit of earlier AI work

The user authorized reviewing all completed Class3 work and making necessary
fixes. Codex reread the assignment/model/data/measurement pages, preserved
pre-fix sources and every existing result, reproduced defects with failing
tests and corrected its earlier implementation and reporting.

Errors in the earlier AI work: the absolute tolerance could suppress real
exercise nodes for small prices; rounded reciprocal stock updates created a
false ATM expiry payoff in the full Bitcoin file; a near-tie tolerance could
report early exercise when waiting was better; a multiplication could overflow
before division even though valid nodes were finite; the runner always labelled
input as BTCUSDT; public price windows lacked alignment validation; and an
anticipated numerical-range failure left a partial output directory.

The earlier exact scalar/NumPy bridge was overstated as a basis for confidence
in the whole boundary: both engines shared the same numerical defect. The
audit now checks full policies against independently reconstructed relative
prices, with exact small-tree tests and a European lower bound as further
evidence. It found a real correction to the full-file expiry threshold:
61,560.49 becomes 60,899.69 USDT/BTC under the documented positive-payoff rule.
Earlier rounded put prices and first observed exercise dates were correct.

Codex wrote tree_model.py, revised both engines and the runner, strengthened
window validation, added regression and verifier-tamper tests, and produced
verify_results.py, audit_numerics.py and preflight_assets.py. Both affected
Bitcoin cases were freshly measured under results/audit_v1. Their runtime and
allocation peaks are new measurements of corrected code. All 22 historical
result files remain byte-identical and their source versions remain available.

The original rational expected answers were retained. Cross-implementation
bitwise equality was changed to numerical agreement because math.exp and
NumPy exp can round differently after stable node reconstruction. The changes
are documented, with pre-fix test/source snapshots. The suite has 38 passing
methods, and before-fix logs show real failures in the new regressions.

Audit mistakes were also corrected: an early diagnostic calculated only the
continuation value for a huge-number case even though immediate exercise
dominates; the reported defect is the missing boundary node. The initial
unsafe-range test used 100 still-safe periods and was corrected to 200 before
judging the failure path. Both logs are kept. An extreme-return robustness
case already passed and is not claimed as a discovered defect.

The review retains explicit conventions: positive-payoff boundaries, a
strike-relative payoff noise cutoff, tolerance only for zero-rate numerical
indifference, exact reciprocal CRR central nodes, Actual/365 Fixed and no gap
filling. Calibration uses the selected window in hindsight. The independent
checks and preflight are evidence within these conventions, not proofs or
completed 40-asset benchmarks. No commits or publications occurred; the user
has not yet independently endorsed the corrected submission.

## Final 40-asset stage

The user authorized the next step after the audit. Codex added the two-horizon
batch producer, completeness/calibration/evidence verifier, independent
all-contract numerical reference, performance-table builder and four batch
test methods. The audited core pricing code was left unchanged. Both batches
ran in one process and returned all 40 prices in sorted asset order.

The scope was stated before execution: task-5 batches calculate prices only;
the earlier Bitcoin runs include dated exercise boundaries. Timings and
allocation peaks were measured around a whole batch, with a separate memory
call. Metrics were not assembled by summing standalone calls. Preloaded input
histories remain outside tracing; the reported peaks are not process RSS or
proof of a machine's memory capacity.

Codex independently recomputed all 80 contracts using a relative-price CRR
reference that imports no production pricing, tree, loading or calibration
code, and checked European lower bounds. All passed, and Bitcoin batch prices
exactly match the audited standalone values. All 42 test methods pass. The
saved batch verifier also checks raw data/calibration, source/evidence hashes,
the complete asset sets, both horizons and table/metric consistency.

Codex wrote REPORT.md and the completed four-row performance table, with each
row's output type labelled. All raw history and corrected Bitcoin results
remain preserved. All six assignment tasks are complete locally. No commit,
push, external submission or messages to others were performed; the student
has not yet independently reviewed or endorsed the final work.

## Second complete review

At the user's request, Codex preserved the completed sources/results and
reassessed pricing, input immutability, verification coverage, table mapping
and reporting. New failing tests reproduced positive root/expiry payoffs being
filtered as noise, an expiry-only range restriction, mutable caller lists,
zero-case numerical verification, missing collection/horizon checks in the
table builder, and incorrect non-Bitcoin console units. These were corrected;
original rational expected answers were retained.

Codex added a complete-submission verifier and freshly recalibrated/repriced all
80 contracts with current production code. Every price and all 52,584 Bitcoin
boundary entries match exactly. All 52 test methods pass. The rebuilt table
is byte-identical, and all 52 pre-review result files remain unchanged.

The earlier independent calculation was not rerun again: its reference
computation is unchanged, its actual 80-case coverage and batch identities
are checked, and current production results were freshly recomputed. The saved
timing/allocation measurements retain their original source hashes and snapshots;
they are not presented as newly measured samples of the edge-case revisions.
The review and reproduction details are in audit/second_review/REVIEW.md.
No commits, publication or work outside Class3 occurred.

The user subsequently approved a local Class3 commit. Codex uses an isolated
checkout and dedicated branch to preserve the pre-existing Assignment1 merge
and unrelated staged files. Class3 Git attributes preserve exact evidence bytes;
temporary verification files are ignored. Authorization covers this local
checkpoint and its checks only; no push or external submission is approved.
