# Class 3: American put pricing

All six assignment tasks are implemented and verified locally. All work stays
in this directory. Read [REPORT.md](REPORT.md) for the completed assignment and
[audit/AUDIT.md](audit/AUDIT.md) for reproduced defects and their corrections.

## Current results

Use [results/final_summary.csv](results/final_summary.csv) for the four required
performance rows, with output type, period counts and asset counts labelled.
All 80 put prices are in `results/all_assets_v1/1y/prices.csv` and
`results/all_assets_v1/full/prices.csv`. The Bitcoin results below are from
the corrected `results/audit_v1/` runs.
Earlier results are preserved as historical evidence and must not be presented
as measurements of the corrected implementation.

| Result | Bitcoin: last 8,760 returns | Bitcoin: full file |
| --- | --- | --- |
| Prices / periods | 8,761 / 8,760 | 43,823 / 43,822 |
| Initial price and strike, USDT/BTC | 109,608.01 | 61,560.49 |
| Put value, USDT/BTC | 16,713.71420876 | 20,716.75407125 |
| First observed exercise crossing, UTC | 2 June 2026, 14:00 | 18 June 2022, 06:00 |
| Gross payoff, USDT/BTC | 41,588.71 | 42,121.23 |
| Untraced pricing seconds, one call | 0.190413208 | 3.846327875 |
| Separate peak traced allocation, bytes | 729,674 | 3,602,862 |

Both values and first crossing dates agree with independent calculations.
The full-file expiry boundary was corrected from 61,560.48999997 to
60,899.69404033 USDT/BTC: accumulated rounding had made a worthless at-the-money
node look exercisable. The price differences are below 0.00000001 USDT/BTC;
rounded prices and first crossing dates are unchanged. New runtime/memory
measurements belong to the corrected code, not the old implementation.

The two horizons start at different dates/strikes and use different estimated
volatility. The price difference does not isolate the effect of expiry length.
This uses full-window calibration retrospectively; gross payoff excludes the
initial premium and is not net trading profit. Prices are quoted in USDT.

## Step 1: understand the pricing recurrence

An American put lets its holder sell one unit of an asset at a fixed strike
at any allowed date. At expiry it pays `max(strike - asset_price, 0)`. At each
earlier node, compare that exercise value with the risk-neutral expected
successor value, discounted by the per-period gross interest factor. Keep the
larger number and work backward to date zero.

For the slides' two-period example, `spot=strike=100`, `up=1.2`, `down=0.8`,
`R=1.05`. The up probability is `(R-down)/(up-down)=0.625`. Expiry prices are
64, 96, 144 and payoffs are 36, 4, 0. At the preceding prices 80 and 120,
keep values 20 and 1.42857143. The initial put value is `1175/147`, or
**7.9932** rounded. The example's R=1.05 is a per-period teaching assumption,
not the lab's annual interest rate.

`price_american_put_original.py` preserves the first slide-style implementation.
The current scalar and NumPy implementations reconstruct log-price rows to
avoid intermediate product overflow and cumulative stock-price drift. In a
calibrated reciprocal tree, `down == 1/up` is enforced in log-price construction
and central nodes are exactly the initial price. This is an explicit numerical
interpretation of the intended CRR identity, rather than treating the tiny
rounding discrepancy in `up * down` as a financial feature.

Both engines use O(N squared) work and O(N) pricing storage. Increasing indices
in the scalar value array preserve both successor values until they are read.
The NumPy engine computes continuation values into scratch arrays before
replacing the current row. It does not store the full tree.

## Step 2: select data and calibrate

`market_data.py` validates the CSV and selects the last N+1 prices. At least
two returns are required for the sample standard deviation. Prices must be
positive and finite; timestamps must be ordered whole-hour UTC values. Public
`PriceWindow` objects also validate their price/date alignment.

For log returns `r[t]=log(P[t]/P[t-1])`, use their sample standard deviation s
with denominator N-1. Set `spot=strike=P[0]`, `up=exp(s)`, `down=1/up`,
`R=exp(0.04*T/N)` and `q=(R-down)/(up-down)`. The historical mean is reported,
but does not replace the risk-neutral probability in pricing.

The day-count convention is explicitly Actual/365 Fixed:
`T=elapsed UTC seconds / (365*24*3600)`. It is a modelling choice because the
slides do not specify a basis. The final-year Bitcoin sample spans
2025-10-31 23:00 to 2026-10-31 23:00 UTC with no gaps and s=0.00460739514049591.
The full file spans 2021-11-01 00:00 to 2026-10-31 23:00 UTC, with
s=0.005396058959060922. Its missing 2023-03-24 13:00 UTC observation is not
filled. One two-hour return remains one observed tree step, and R uses actual
elapsed T. Such a sample is not perfectly hourly. Its T=5.002625570776256 under
Actual/365 Fixed includes the leap day; the requested full file is not trimmed.

## Step 3: record a boundary and compare the observed path

`return_boundary=True` returns `(value, boundary)` with N+1 thresholds. At each
date record the highest tree price with a positive exercise payoff that is
optimal, or `None`. Excluding worthless exercise ties is an explicit financial
convention, since the slides do not resolve zero-payoff ties. At expiry retain
the highest positive-payoff tree node, not an interpolated strike.

Ignore payoff noise below `32 * float epsilon * strike`, without an absolute
currency floor. Compare exercise and continuation strictly at nonzero interest;
only R=1 uses a numerical indifference tolerance. At R<1, positive-payoff early
exercise is never optimal in the no-dividend model. These remain finite-precision
calculations; the noise cutoff is not an exact-arithmetic proof.

`exercise.py` finds the first observed `P[t] <= boundary[t]`, including expiry,
or returns `None` for never. The observed path can lie between lattice nodes;
no boundary interpolation or substitution of the strike at expiry is made.
The terminal intrinsic payoff and a literal discrete-boundary crossing need
not be the same event for every possible off-grid observed price.

## Step 4: measure and verify

`run_bitcoin.py` supports both engines and labels the actual input asset.
Numerical range is checked before any output directory is created. Completed
runs have a final `result.json`; files without it are not completed results.
Existing output directories are never replaced. Each contains inputs, timing,
memory, dated boundary CSV, summary CSV and source/data/output hashes.

Runtime is one untraced pricing call, including its boundary and internal
validation. It excludes input loading, calibration, observed-path comparison
and file writing. Memory is a separate tracemalloc call with inputs already
loaded. It includes newly allocated work arrays and output. It excludes the
first call's retained result, the interpreter, pre-existing inputs and untraced
native allocations. NumPy buffers were confirmed to be traced on this runtime.
These are pricing-allocation peaks, not end-to-end process RSS. One timing
sample and one memory sample provide no variability estimate. No memory limit
was reached, and no memory-limit capacity claim is made.

`verify_results.py` validates every saved complete run against its raw data,
source version, calibration, lattice, crossing, metrics and table. Archived
source hashes are resolved for historical runs. Tamper tests check that it
rejects changed prices, crossing flags and unavailable source versions.
`audit_numerics.py` independently reconstructs relative-price CRR rows and
checks all 52,584 current policy rows, crossing dates and a European lower bound.
All **42 test methods pass**, retaining exact rational expected answers.

## Step 5: both 40-asset batches and final verification

`run_assets.py` prices every supplied USDT asset in one process for each
horizon. It preloads and calibrates inputs, then times one sequential batch
call returning the 40 prices. A separate full batch call measures peak traced
allocation; all 40 prices must exactly agree. No boundaries are requested for
the task-5 batches. The Bitcoin boundary runs remain available separately.

The one-year batch uses N=8,760 for each of 40 assets: 5.862296291 untraced
seconds and 512,994 peak traced bytes (0.489229 MiB). The full-file batch uses
N=43,822: 121.114069916 seconds and 2,546,590 peak traced bytes (2.428617 MiB).
Neither is a sum of isolated per-asset measurements. Sequential processing
reuses work space; loaded inputs are outside tracing and still consume RAM.

`verify_assets.py` checks every raw input, independent calibration, source/file
hash, asset/horizon, metric and table. `check_asset_numerics.py` independently
reprices all 80 contracts using relative CRR rows and checks European lower
bounds. It imports no production pricing or tree helper. All checks pass,
and the two batch Bitcoin prices exactly match the audited boundary runs.

`build_summary.py` builds the four-row delivered performance table from saved
results after verifying them. The output mode column distinguishes Bitcoin
price-and-boundary measurements from the price-only 40-asset measurements.

## Commands and dependencies

Python 3.10+ and NumPy are needed for the full suite and NumPy engine. The
recorded runtime has Python 3.14.7 and NumPy 2.5.3; no package installation was
performed during this work. The dependency is listed in `requirements.txt`.
From the repository root:

```bash
python3 -B Submissions/HardiKhushi/Class3/price_american_put.py
python3 -B -m unittest discover -s Submissions/HardiKhushi/Class3 -p 'test_*.py' -v
python3 -B Submissions/HardiKhushi/Class3/verify_results.py
python3 -B Submissions/HardiKhushi/Class3/audit_numerics.py
python3 -B Submissions/HardiKhushi/Class3/preflight_assets.py
python3 -B Submissions/HardiKhushi/Class3/verify_assets.py
python3 -B Submissions/HardiKhushi/Class3/check_asset_numerics.py
```

To repeat pricing, choose new output directories inside Class3:

```bash
python3 -B Submissions/HardiKhushi/Class3/run_bitcoin.py --engine numpy --output Submissions/HardiKhushi/Class3/results/rerun_1y
python3 -B Submissions/HardiKhushi/Class3/run_bitcoin.py --engine numpy --full-file --output Submissions/HardiKhushi/Class3/results/rerun_full
python3 -B Submissions/HardiKhushi/Class3/run_assets.py --output Submissions/HardiKhushi/Class3/results/all_assets_rerun
```

To verify a new batch run, pass `--directory` with its parent results directory
to both batch-verification scripts. Optional --output reports must use new
filenames inside Class3. `build_summary.py --output PATH` regenerates a table
of the delivered saved runs into a new CSV and manifest without overwriting
evidence. All source data remain unchanged. No required implementation or
measurement task remains. Student review and approval before committing are
still pending; no commit or publication was performed.
