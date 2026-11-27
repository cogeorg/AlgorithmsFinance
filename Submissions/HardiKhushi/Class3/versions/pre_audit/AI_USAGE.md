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
