# Class 3: completed assignment

All six lab tasks are implemented and verified locally. The two Bitcoin runs
include full dated exercise boundaries and first observed crossings. The
40-asset runs return all put prices for both horizons in one program invocation.
No commit, push or external submission has been performed.

## Performance table

| Assets | Horizon | Output | N per asset | Seconds | Peak traced MiB |
| --- | --- | --- | --- | --- | --- |
| Bitcoin | One year | Price and boundary | 8,760 | 0.190413 | 0.695871 |
| Bitcoin | Full file | Price and boundary | 43,822 | 3.846328 | 3.435957 |
| All 40 | One year | Prices only | 8,760 | 5.862296 | 0.489229 |
| All 40 | Full file | Prices only | 43,822 | 121.114070 | 2.428617 |

The machine-readable table is [results/final_summary.csv](results/final_summary.csv).
Its manifest identifies the four exact source results and the table builder.
Each row is one timed call plus a separate memory call. The 40-asset rows are
measured around the whole sequential batch; their metrics are not sums of
individual calls or peaks. Source, data and output hashes are retained.

## Bitcoin prices and exercise

| Result | One year | Full file |
| --- | --- | --- |
| Initial price and strike, USDT/BTC | 109,608.01 | 61,560.49 |
| Initial put value, USDT/BTC | 16,713.71420876 | 20,716.75407125 |
| First observed crossing, UTC | 2 June 2026, 14:00 | 18 June 2022, 06:00 |
| Gross exercise payoff, USDT/BTC | 41,588.71 | 42,121.23 |

Full dated Bitcoin boundaries are in `results/audit_v1/`. These are the
corrected results; the audit fixed a falsely exercisable ATM expiry node.
The rounded put values and first crossing dates survived that correction.

## All 40 asset prices

- [One-year prices and parameters](results/all_assets_v1/1y/prices.csv)
- [Full-file prices and parameters](results/all_assets_v1/full/prices.csv)

Every supplied USDT asset appears exactly once per horizon, including BTCUSDT
and tokenized gold PAXGUSDT. Values are USDT per native unit of that asset;
one PAXG token represents one fine troy ounce. No portfolio weighting or
summation of unlike native-unit option values is implied. The S&P 500 fetch
is not needed for the 40 supplied asset files.

## Model and interpretation

Each window has N+1 closes and N returns. Strike equals the first close.
The model uses sample log-return volatility (denominator N-1), reciprocal
CRR moves, a continuously compounded 4% annual rate and Actual/365 Fixed
elapsed years. Missing observations are disclosed without filling. The full
file has one missing hour and 43,822 observed periods; actual elapsed years
are slightly over five under this day-count convention.

Exercise boundaries exclude worthless ties, use the highest exercise tree
node at expiry and preserve exact central nodes in reciprocal trees. The
disclosed payoff-noise tolerance is strike-relative. The observed path is
compared with discrete thresholds without interpolation. Calibration uses
all prices in each selected window, so exercise dates are retrospective.
Gross payoff excludes the premium and is not a trading-profit calculation.

## Runtime and memory scope

The audited NumPy recurrence uses quadratic work in periods and linear working
storage. Batch work is the sum of the 40 tree workloads. Assets are processed
sequentially, retaining the 40 prices; working arrays are released between
assets. Price-only batch workspace therefore scales with the largest tree
plus the price list, rather than with 40 full trees. Bitcoin rows also build
and retain a boundary, so the output workloads differ.

Inputs and calibration are prepared before timing and tracing. Peak traced
allocation includes the new pricing buffers and returned prices/boundary,
but excludes pre-existing histories, interpreter storage and untraced native
allocations. It is not total process RSS. The preloaded histories still use
machine memory. NumPy buffers were confirmed to be traced on this runtime.
No memory limit was reached, and no out-of-memory capacity is inferred.
Single samples do not quantify timing variability or establish speed guarantees.

## Validation

- All 42 test methods pass, including exact rational trees, scale/rounding
  regressions, batch correctness and tampered-evidence rejection.
- All 80 batch prices were recomputed independently using relative-price
  backward induction that imports no production pricer or tree helper.
- All contracts satisfy the independently calculated European put lower bound.
- Bitcoin batch prices exactly match the audited single-asset results.
- Both measured calls agree exactly within each batch. Raw data, calibration,
  coverage of both 40-asset horizons, tables and file hashes are verified.
- Historical measurements and their source snapshots are preserved.

The largest absolute independent-price discrepancy divided by strike is 6.176e-16.
Detailed evidence: `audit/batch_verification.json`, `audit/batch_numerics.json`,
`audit/tests_final.txt`, and the earlier [audit report](audit/AUDIT.md).

Run commands and reproduction instructions are in [README.md](README.md).
All deliverables are inside this Class3 submission directory.
