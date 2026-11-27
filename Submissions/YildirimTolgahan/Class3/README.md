# Class 3 lab: `PriceAmericanPut` on market data

Tolgahan Yildirim. Everything is in this folder; the course folders are untouched.

| File | Content |
|---|---|
| `american_put.py` | Four implementations of the slide algorithm, calibration, exercise search |
| `lab.py` | Runs tasks 1 to 6 and writes `results/` |
| `test_american_put.py` | 36 tests that try to break the fast implementation |
| `results/table.md`, `results/runs.csv` | Task 6 table |
| `results/boundary_btc_1y.csv`, `results/boundary_btc_5y.csv` | Early-exercise boundary for every date (tasks 2 and 4) |
| `results/puts_all_1y.csv`, `results/puts_all_5y.csv` | All 40 assets (task 5) |

## Run

Python 3.13 with NumPy (`python -m pip install numpy`), from this folder:

```powershell
python lab.py                        # all runs, 10 to 20 minutes (the pure-Python comparison is slow)
python lab.py --quick                # lab runs only, about 2 minutes
python test_american_put.py          # about 2 minutes
python test_american_put.py --slow   # adds the five-year check on all 40 assets, about 15 minutes
```

## Results

Task 1. The two-period tree gives 7.9932.

Tasks 2 to 4, Bitcoin:

| | One year | Full file |
|---|---:|---:|
| Window (UTC) | 31 Oct 2025 23:00 to 31 Oct 2026 23:00 | 1 Nov 2021 00:00 to 31 Oct 2026 23:00 |
| N | 8,760 | 43,822 |
| Hourly volatility s | 0.004607 | 0.005396 |
| Strike K = first close | 109,608.01 | 61,560.49 |
| Put value | 16,713.71 (15.2% of K) | 20,716.75 (33.7% of K) |
| Dates with an exercise node | 8,625 of 8,761 | 43,608 of 43,823 |
| First close at or below the boundary | t = 5,127, 2 Jun 2026 14:00 | t = 5,502, 18 Jun 2022 06:00 |
| Payoff K - P_t on that date | 41,588.71 | 42,121.23 |
| Payoff if held to expiry instead | 32,025.99 | 0.00 |

The file has 43,823 rows: the hour 24 Mar 2023 13:00 is missing in all 40
files. The full window therefore has N = 43,822 periods and spans 43,823 hours,
and T uses the 43,823.

Task 5. All 40 assets are priced in one process. The holder would never have
exercised on NEAR, TRX, UNI and ZEC (one year) and on BNB, PAXG, TRX and XRP
(five years). Put values range from 7.9% of the strike (TRX) to 49.1% (ENJ)
over one year, and from 12.7% (PAXG) to 70.0% (SNX) over five years.

Task 6:

| Task | Method | N | Assets | Nodes updated | Seconds | of which pricing | Peak memory, pricing (MiB) | Peak memory, process (MiB) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2, 3 | band | 8,760 | 1 | 9,255,637 | 0.18 | 0.12 | 0.3 | 31.9 |
| 4 | band | 43,822 | 1 | 136,235,876 | 0.81 | 0.62 | 1.3 | 41.8 |
| 5 | band | 8,760 | 40 | 372,236,897 | 9.67 | 7.51 | 0.3 | 33.4 |
| 5 | band | 43,822 | 40 | 5,484,819,365 | 46.05 | 41.87 | 1.3 | 48.6 |
| - | slides, pure Python | 8,760 | 1 | 38,373,180 | 22.00 | 21.96 | 1.0 | 32.4 |
| - | slides, NumPy rows | 8,760 | 1 | 38,373,180 | 0.68 | 0.65 | 0.7 | 34.4 |
| - | NumPy rows, whole tree stored | 8,760 | 1 | 38,373,180 | 0.99 | 0.96 | 586.3 | 360.6 |
| - | slides, NumPy rows | 43,822 | 1 | 960,205,753 | 19.24 | 19.17 | 3.5 | 44.8 |

Windows 11, CPython 3.13.12, NumPy 2.5.5, 8 logical cores, one process, one
thread. Each run is one fresh interpreter. Seconds cover loading, calibration,
pricing and the exercise search, without interpreter start-up. "Peak memory,
pricing" is the largest `tracemalloc` peak of one pricing call; "process" is
the peak working set of the whole interpreter, of which about 30 MiB is Python
and NumPy themselves.

Three things in the table need a comment.

- **Where memory binds.** Storing every node to read the boundary off
  afterwards costs 586 MiB for one asset and one year. For five years it is
  14.3 GiB as a square array or 7.2 GiB as a triangle, per asset: not run. The
  boundary needs one integer per date, so the band stays at 1.3 MiB however
  many assets follow.
- **Process peak below the traced peak** in the stored-tree row: the array is
  requested zero-filled, and Windows commits only the pages that are written,
  which is the lower triangle.
- **The 40-asset runs are slower per asset** (about 1.05 s per five-year tree
  instead of 0.62 s). The node count per asset is the same. Reordering the
  assets shows that it depends on position in the run and not on the asset:
  the first three trees take 0.6 s, later ones 1.0 to 1.3 s. I read this as the
  processor lowering its clock under sustained load, but did not measure the
  clock.

## The algorithm

`price_band` returns the same value and boundary as the slide algorithm and
updates only the nodes whose value is not known in closed form.

Write D = V - (K - S) for the value of waiting. The slide recurrence becomes
D[t][j] = max(0, (q D[t+1][j+1] + (1-q) D[t+1][j]) / R - K (1 - 1/R)).
For d <= 1 <= R, which every tree calibrated with d = 1/u satisfies:

1. The exercise nodes of a date are a prefix j <= jstar[t].
2. jstar[t] is jstar[t+1] or jstar[t+1] - 1, so one comparison per date finds
   the whole boundary.
3. Below the boundary V = K - S. In every column whose leaf is out of the
   money V = 0.

The recurrence runs only between the two. At the top, the band also stops where
values underflow. On Bitcoin that is 24% of the nodes of the full tree for one
year and 14% for five; the share keeps falling as N grows. Memory is Θ(N).

Three more decisions:

- **Node prices are computed directly**, as S0 u^(2j-t) by repeated squaring on
  mantissa and exponent, not by N chained multiplications. The slide pseudocode
  first forms S0 d^N. Once s N exceeds about 745 that underflows to zero, every
  price becomes zero, and the algorithm returns the strike. The most volatile
  asset in the data (SNX, five years) reaches s N = 541.
- **The middle leaf is exactly the strike.** With S0 = K and N even, the leaf
  with as many ups as downs equals K. Chained multiplication misses it by
  rounding and can create an exercise node that pays 1e-11.
- **Convention.** Exercise is optimal at a node if K - S > 0 and K - S >= c.
  A tie counts as exercise; a payoff of zero does not.

The tree alternates between two price grids on odd and even dates, so the
boundary in the CSV files zigzags between two neighbouring prices from one hour
to the next. That is a property of the tree, not of the put.

Task 3 follows the slide literally: the first t with P_t at or below the
boundary. At t = N the boundary is the highest leaf below K, so a close between
that leaf and K is "never" by this rule although the put pays at expiry. The
column `payoff_at_expiry` in the result files covers that case.

## Testing

`price_band` is checked against three independent references: the slide
pseudocode in pure Python (`price_slides`), the same recurrence in exact
rational arithmetic (`price_exact`), and a NumPy version that evaluates every
node and scans every row for the boundary (`price_dense`). It also agrees with
the course's own `price_american_put` and `recursive_put_oracle` in
`Class3/class3_evidence.py`. On the lab data, band and dense agree in value and
in the boundary on every date, for all 40 assets, one year and five years.

The tests found these defects, all fixed:

| Defect | Found by |
|---|---|
| R = 1 with the strike exactly on a node: wrong boundary | exhaustive small trees against the exact oracle |
| Immediate exercise returned slightly less than K - S0, from chained rounding of the boundary price | structural property test |
| 1 < d < R < u (allowed by the specification): value 0 for an in-the-money put, because property 3 fails there. Such trees now go to `price_dense` | review |
| Strike below about 1e-300: the underflow cut-off was absolute and removed real value. Prices are now rescaled by a power of two, which is exact | review |
| S0 near the largest float, or subnormal: node prices overflowed or rounded to zero | review |
| q at rounding level: value below K - S0 by 3,398 ulps after 3,481 steps | review |
| Calibration: closes whose quotient leaves the float range gave a wrong s | review |
| The memory column of the first table measured the CSV parser | review |

"Review" is a second pass in which the code was attacked from five directions
(floating point, the derivation, the lab pipeline, an independent
reimplementation on 3,480 real windows, and mutation testing of this test
suite) and every reported defect was reproduced before it was accepted. The
mutation run also showed tests that could not fail; those were tightened.

Known limits:

- When R - 1 is within a few ulps of zero, the exact time value at the
  boundary is below floating-point resolution and the boundary can differ from
  the exact one by a column. The value is unaffected.
- A strike within one ulp of a tree node pays either 1e-15 or nothing,
  depending on how the node price is rounded. No float algorithm can decide
  that; `price_slides`, `price_dense` and `price_band` can disagree there.
- Trees with R < 1 or d > 1 are correct but take the dense Θ(N²) path.

I used Claude Code for the implementation, the tests and the review pass.
