# Class 3 progress

## 1. Small pricing algorithm (27 November 2026)

Authorization: after the assignment explanation, the user said "Okay lets go".
The described batch was the small pricing function and correctness checks.
The user then required all lab work to remain inside this Class3 directory.
Filesystem write permission was granted for this turn. No commit is approved.

Changes: added the rolling-array pricing function, independent small-tree
checks, a worked-example README and local working/AI-use records. The function
validates finite parameters, period counts and no-arbitrage inequalities.
The existing empty `american_put.py/` directory is preserved.

Checks and outcomes: the example returned 7.9931972789 per unit, which rounds
to the slides' 7.9932. All six unittest methods passed, including 189 exact
recursive small-tree comparisons, expiry-only cases, zero strike and invalid
parameters. Commands used Python's `-B` flag to avoid bytecode artifacts.
Only this Class3 directory was changed; no parent/course/peer files, existing
merge conflicts, staging entries or commits were modified.

Outstanding: market-data loading/calibration, exercise boundaries and path
comparison, long-tree numerical checks, one-/five-year Bitcoin and 40-asset
runs, and timing/peak-memory results. No market-data run has been performed.

Next proposed stage: explain and implement data loading and calibration for
the one-year Bitcoin window before attempting a large pricing run.

## 2. Bitcoin data loading and calibration (27 November 2026)

Authorization: the user said "Lets go ahead into the next step" after the
proposal to load a year of Bitcoin prices and calculate model parameters.
Filesystem write access was granted for this Class3 directory for the turn.
No commit, upload or large pricing run was approved or performed.

Changes: added `market_data.py` with a validated CSV loader, sample-log-return
calibration and a report CLI, plus nine data/calibration test methods. Updated
local instructions, learning notes and AI-use records. Saved the selected
Bitcoin parameters in `results/calibration_btc_1y.json` with raw data and script
hashes. The CLI restricts outputs to this directory and refuses replacement
of an existing report. Course prices are unchanged.

Results: selected 8,761 prices from 2025-10-31 23:00 UTC through 2026-10-31
23:00 UTC, giving 8,760 returns and no gaps. Initial price and strike are
109,608.01 USDT per BTC. Sample hourly log-return std is 0.00460739514049591;
up=1.004618025505313, down=0.9954032026222204,
R=1.0000045662204708 and q=0.49934368317518857. The no-arbitrage inequalities
hold. The selected window spans exactly one Actual/365 Fixed year.

Verification: all 15 test methods passed, retaining the original 189 exact
small-tree comparisons. New checks cover last-N+1 selection, provenance,
hand-computed sample variance, elapsed-time handling of gaps, malformed data,
invalid period counts and invalid calibration factors. A separate raw-CSV
calculation confirmed the saved standard deviation, model/window consistency,
and data/script hashes. No timing or peak-memory benchmark is claimed.

Decision: the slides leave the day-count basis unspecified. Actual/365 Fixed
is recorded explicitly. Missing whole hours are disclosed without filling;
observed returns remain tree steps, with actual elapsed T in the rate formula.

Outstanding/next stage: add and test the exercise boundary, check long-tree
numerical range, then price the one-year Bitcoin put and compare its observed
path with the boundary. Full-file and 40-asset experiments and the required
runtime/memory table remain later stages. All changes stayed inside Class3.

## 3. One-year Bitcoin pricing and exercise boundary (27 November 2026)

Authorization: the user said "Okay lets go ahead" after the proposal to add
the boundary, calculate the one-year Bitcoin put and compare the observed
prices. The announced batch includes runtime and peak-memory evidence.
Filesystem write access was granted only for this Class3 directory.

Changes: preserved the first pricing file byte for byte as
`price_american_put_original.py` (SHA-256
`ce546f06475744713ce857c28e56d06ea162c79dd6f15f790acfca57b007bec7`).
Extended the current file with an optional boundary and a pre-allocation
numerical-range guard; added `exercise.py`, `test_exercise.py` and
`run_bitcoin.py`. Updated only local documentation. Original expected test
answers are unchanged.

Checks: all 23 test methods passed. The eight added methods include 189 exact
rational full-tree policy comparisons and matching original implementation
prices, plus worthless/expiry cases, unsafe floating-point ranges and observed
crossing checks. Each of 8,761 saved threshold/path rows was independently
checked: every threshold is a valid lattice node, all crossing flags agree,
no crossing precedes the reported one and gross payoff is correct. The original
source snapshot's SHA-256 still matches its recorded value.

One-year result: put value is 16,713.71420876 USDT per BTC. The first observed
boundary crossing is t=5,127, 2026-06-02 14:00 UTC: observed price 68,019.30,
boundary 68,193.46617089 and gross payoff 41,588.71 USDT per BTC. This uses
full-window calibration retrospectively and does not report a trading profit.

Measurements complete: untraced pricing took 3.695130624808371 seconds.
The separate tracemalloc call recorded peak allocation of 739,464 bytes
(722.1328125 KiB) and took 138.2408365001902 instrumented seconds. Its full
boundary and option value exactly matched the timing call. Tracing duration
is not the reported pricing runtime. Inputs and first-call results predate
tracing; fresh working arrays and new output are included. This is not RSS.
One timing sample and one memory sample were collected.

Saved results in `results/bitcoin_1y/`: inputs, individual timing and memory
records, all dated boundaries in CSV, a summary CSV and a complete result JSON
with environment, conventions and data/source/output hashes. Independently
verified every recorded hash, the earlier calibration's unchanged parameters,
summary/JSON consistency and agreement of the separate calls.

Conventions: record positive-payoff exercise nodes only, excluding worthless
zero-payoff ties. Apply a disclosed tolerance for boundary classification only;
the price uses the ordinary maximum. At expiry retain the highest positive-
payoff tree node, without interpolating to strike. Store all dated thresholds.

Outstanding: extend to the full Bitcoin file and all 40 assets in later
approved stages. No commit, staging, push, publication or changes outside
Class3 have been performed.

Final housekeeping: text-format checks passed, but the additional assumption
that the earlier empty `american_put.py/` directory still existed failed.
Inspection confirmed it is no longer present; this batch did not delete it
and did not recreate it. Updated current instructions/README accordingly.

## 4. Full-file Bitcoin (27 November 2026)

Authorization: "Okay let us move on to doing the next step" approved the
previously proposed full-file Bitcoin calculation. The announced work includes
range/gap checks, a validated NumPy engine and one-year bridge so full-file
memory tracing is practical, then separate full-file timing/memory calls.
Write permission was granted for this Class3 directory only. No commit is
authorized or performed.

Changes: added `price_american_put_numpy.py`, three focused test methods and
`requirements.txt`. Extended the runner with --engine and --full-file; outputs
remain exclusive and engine-labelled. All four original stage-3 source files
were hash-checked and preserved under `versions/step3/` before editing. The
scalar pricer and prior raw results are unchanged. NumPy 2.5.3 was already
available; no dependency installation occurred.

Validation: all 26 test methods passed. New checks include 189 exact full-tree
policy/scalar comparisons, expiry/zero-strike and invalid/unsafe inputs. The
NumPy one-year bridge exactly reproduced the saved price and exercise result;
all 8,761 boundary CSV rows are byte-identical. An 800,000-byte NumPy buffer
probe yielded 800,496 peak traced bytes, confirming buffer inclusion on this
runtime. These are functional checks, not claims of universal precision.

Full-file data: 43,823 prices, 43,822 steps; 2021-11-01 00:00 UTC through
2026-10-31 23:00 UTC. Missing 2023-03-24 13:00 UTC was not filled; one two-hour
return remains one step. Initial price/strike=61,560.49 USDT per BTC;
s=0.005396058959060922. Actual/365 Fixed T=5.002625570776256. Tree extremes
pass the pre-allocation numerical-range guard and no-arbitrage holds.

Full-file outcome: price=20,716.75407125397 USDT per BTC. First observed
crossing at t=5,502, 2022-06-18 06:00 UTC: price=19,439.26,
boundary=19,823.099264757802 and gross payoff=42,121.23 USDT per BTC.
This is retrospective, not net trading profit. Full-file and one-year
contracts have different initial dates/strikes and calibrated volatility.

Measurements: NumPy one-year untraced seconds=0.1176721251104027, peak traced
bytes=658,410. Full-file untraced seconds=2.17692712508142, peak traced
bytes=3,251,102 (3.100492477416992 MiB). The latter memory call took
4.842538208002225 instrumented seconds and exactly reproduced the timed
call's price/boundary. These are one timing and one separate memory call
per case, excluding pre-existing inputs. Memory is traced allocations, not RSS.
No memory limit was reached.

Evidence: `results/bitcoin_1y_numpy/`, `results/bitcoin_full_numpy/`, aggregate
`results/bitcoin_comparison.csv` and bridge/hash record
`results/bitcoin_numpy_comparison.json`. Independently checked all 43,823
full-file boundary/path rows, threshold lattice membership, crossing flags,
first-crossing payoff, summary/JSON agreement and all recorded source/data/
output hashes. Original run and archived-source hashes still match.

Next stage: all 40 supplied assets in one run for each horizon, with range
checks and an expanded performance table. No course/peer files, Git index,
commits or publications were changed.

## 5. Comprehensive audit and corrections (27 November 2026)

Authorization: the user explicitly requested reviewing every completed Class3
step, making necessary changes and being critical of mistakes. Write access
was granted only for this Class3 directory. This includes affected Bitcoin
reruns and relevant checks; the 40-asset pricing batch remains outstanding.

Preservation: snapshotted all 15 root source/document files under
versions/pre_audit and hash-recorded all 22 pre-audit result files. Every old
result file remains byte-identical. The earliest scalar and step-3 source
versions also remain intact. Current corrected runs use new result paths.

Confirmed defects: absolute tolerance broke currency-scale invariance;
rounded reciprocal nodes produced a spurious ATM expiry exercise payoff;
near-tie tolerance could favour suboptimal early exercise at negative rates;
intermediate multiplication could overflow despite safe final nodes; the
runner mislabelled non-Bitcoin inputs; manually constructed price windows
could have mismatched dates/prices; and predictable unsafe-tree failure left
a partial output directory. See audit/AUDIT.md for concrete cases and impact.

Corrections: tree_model.py centralizes the validated contract, stable log-node
prices, exact reciprocal central nodes and a strike-relative cutoff. Both
engines now reconstruct prices rather than accumulating row-update drift.
Strict exercise comparison is used at nonzero rates; zero-rate indifference
remains tolerance-based and R<1 has no positive-payoff early exercise in this
no-dividend model. Window construction validates alignment and inputs. The
runner preflights before output creation and labels the actual input asset.

Verification: 38 test methods pass. The added regression suite reproduced 11
failing subcases before repair. The original rational expected answers remain
unchanged; cross-engine bitwise assertions now use 10-decimal comparisons
appropriate for independently evaluated exp operations. Added verify_results.py
with four real tamper/consistency tests. It checks all five saved runs against
data, archived/current source, calibration, dates/lattice, path crossing and
summary metrics. It verifies 113,929 saved rows across the five runs.

Independent audit_numerics.py checks every one of the 52,584 current policy
rows, initial values, first crossings and European binomial lower bounds.
There are no current policy disagreements. Price discrepancies from its
independent reference are at most 3.64e-11 USDT/BTC. The independently checked
legacy values also agreed well below a cent.

Actual Bitcoin correction: the full-file expiry boundary changes from
61,560.48999997437 to 60,899.69404033294 USDT/BTC. It had falsely included the
intended worthless ATM node. No other policy node choice changes. Neither
first crossing date changes, and price changes are below 5e-9 USDT/BTC.

New measurements under results/audit_v1: one-year value=16,713.71420875807,
seconds=0.19041320797987282, peak traced bytes=729,674; full-file value=
20,716.754071249332, seconds=3.846327875042334, peak traced bytes=3,602,862.
Separate memory calls exactly agree with timed values and boundaries. These
are new-code measurements; old performance numbers are historical, not reused.

Preflight only: preflight_assets.py validated all 40 supplied USDT files at
both horizons (80 calibrations and range checks), with no failed range. This
does not price/measure the 40-asset batches. Data gaps and Actual/365 Fixed
remain disclosed assumptions. No memory limit was reached or inferred.

Audit self-corrections: an initial diagnostic used continuation alone in the
huge-number example, overlooking immediate exercise; only the terminal-boundary
defect is claimed. The initial 100-step range fixture was still safe; corrected
it to 200 before diagnosing the partial-directory failure. Both preliminary
logs remain. See AI_USAGE.md and audit/AUDIT.md.

Deliverables: updated README, results/CURRENT.md, audit/AUDIT.md, failed/passed
logs, numerical and evidence-verifier reports, 80-case preflight JSON, corrected
run outputs and comparison manifest. Existing result READMEs are historical
and preserved unchanged. No staging, commits, pushes, external publication,
course/peer changes or edits outside Class3 were performed.

Remaining assignment work: the two 40-asset pricing/measurement batches and
their aggregate table, followed by a final batch verification. Commit only
after explicit user approval.

## 6. All 40 assets and completed assignment (27 November 2026)

Authorization: the user said "Okay lets go on to the next step" after the
completed audit and the proposal to price all 40 supplied assets at both
horizons. Write access was granted for this Class3 directory. No commit or
publication is authorized.

Implementation: added run_assets.py, verify_assets.py, check_asset_numerics.py,
build_summary.py and four batch test methods. The audited pricing kernel is
unchanged. The producer discovers all 40 supplied USDT assets including BTC
and PAXG, loads and calibrates inputs, then runs one sequential 40-price call
per horizon. Task 5 requests prices; no boundaries are generated for the batch.
Bitcoin's dated boundaries remain in the corrected audit_v1 runs.

Measurement protocol: each horizon has one complete untraced batch call and
one separate tracemalloc batch call. All prices are retained in sorted asset
order, with one asset's work buffers alive at a time. Timings and allocation
peaks are measured directly around the complete batch, not summed from
individual measurements. Preloaded histories and first-call prices are
outside tracing and still consume RAM; peak traced bytes are not process RSS.

Results: 40/40 one-year contracts, each N=8,760, completed in
5.862296290928498 untraced seconds with 512,994 peak traced bytes
(0.4892292022705078 MiB). Its memory call took 15.890660374891013 instrumented
seconds. The 40/40 full-file contracts, each N=43,822, took
121.11406991584226 untraced seconds with 2,546,590 peak traced bytes
(2.428617477416992 MiB). Its memory call took 171.77810833393596 instrumented
seconds. All 40 prices exactly agree between timed and traced calls in each
horizon. No memory limit was reached; no capacity is inferred.

Validation: all 42 test methods pass in audit/tests_final.txt. New tests cover
whole-batch values against the scalar engine, sorted asset identity, duplicate
rejection, missing-price rejection and a changed CSV with a recomputed hash.
The final batch verifier checks all 40 assets, both distinct horizons, raw
data/calibration, source/output hashes, output completeness and metrics/tables.
Its evidence is audit/batch_verification.json.

Independence: check_asset_numerics.py imports no production pricer, tree helper,
loader or calibration code. It recomputes all 80 CRR prices from relative-price
rows and separately computes European binomial lower bounds. All 80 pass.
The maximum independent discrepancy divided by strike is
6.176394660718002e-16. Both batch Bitcoin prices exactly match the audited
single-asset values. Evidence is audit/batch_numerics.json.

Deliverables: results/all_assets_v1 has 80 prices with parameters, both batch
measurement records, hashes and a two-horizon completion manifest.
results/final_summary.csv contains four required rows, labelling Bitcoin
price-and-boundary work and 40-asset price-only work separately. The table
builder verifies its input runs and records their identities in
final_summary.manifest.json. REPORT.md is the completed write-up; README,
results/CURRENT.md, local instructions and AI notes now reflect completion.
Historical raw measurements remain intact and matched to their source versions.

All six assignment tasks are complete locally, including the requested code
and table. The student still needs to review the deliverables and authorize
any commit. No staging, commits, pushes, publication or edits outside Class3
were performed.
