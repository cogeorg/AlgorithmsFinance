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
