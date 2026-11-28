# Class 3 report: American puts on market data

## Outcome

The exact rolling binomial recurrence was implemented with one value vector, validated against an independent recursive oracle, and executed through a compiled C backend after the pure-Python worker pilot established the runtime need. Bitcoin boundaries and observed exercise decisions are retained; the 40-asset runs return values only.

## Required run table

| Scenario | N | Assets | Workers | Median seconds | Peak RSS bytes | Peak RSS MiB |
|---|---:|---:|---:|---:|---:|---:|
| Bitcoin, one year | 8,760 | 1 | 1 | 0.077180792 | 59,539,456 | 56.781 |
| Bitcoin, full history | 43,822 | 1 | 1 | 1.851040000 | 58,671,104 | 55.953 |
| All assets, one year | 8,760 | 40 | 8 | 0.592842459 | 301,072,384 | 287.125 |
| All assets, full history | 43,822 | 40 | 8 | 14.370036291 | 295,960,576 | 282.250 |

## Bitcoin results

### One year

- Put value: `16713.714208766745`
- Boundary dates present: `8,625` of `8,761`
- First observed exercise: `2026-06-02T14:00:00+00:00`
- Observed price: `68019.30000000`
- Boundary price: `68193.466170886546`
- Payoff: `41588.71000000`

### Full history

- Put value: `20716.754071288182`
- Boundary dates present: `43,608` of `43,823`
- First observed exercise: `2022-06-18T06:00:00+00:00`
- Observed price: `19439.26000000`
- Boundary price: `19823.099264757235`
- Payoff: `42121.23000000`

## Optimization and CPU scaling

Both pilots used identical prepared jobs and required exact ordered values at every worker count. Compilation and worker warm-up were outside timing.

| Workload | Workers | Python seconds | Compiled seconds | Speedup |
|---|---:|---:|---:|---:|
| All 40, one year | 1 | 128.518708 | 3.021854 | 42.53x |
| All 40, one year | 2 | 68.241337 | 1.545391 | 44.16x |
| All 40, one year | 4 | 44.936245 | 0.819462 | 54.84x |
| All 40, one year | 8 | 40.770566 | 0.618899 | 65.88x |
| Four assets, full history | 1 | 351.471670 | 7.489112 | 46.93x |
| Four assets, full history | 2 | 215.789575 | 3.840296 | 56.19x |
| Four assets, full history | 4 | 137.489410 | 2.028192 | 67.79x |

Across the four full-history pilot assets, Python and compiled values had maximum absolute difference `5.6843418860808015e-14` and maximum relative difference `9.8002961288069495e-16`.

8 workers were selected because they had the lowest measured all-assets one-year wall time. Separate processes bypass the Python GIL; macOS schedules them across CPUs without a claim of fixed core affinity.

## Raw timing repeats

- Bitcoin, one year: `0.077180792, 0.076718083, 0.079233000, 0.076384500, 0.078193250` seconds
- Bitcoin, full history: `1.851040000, 1.932311917, 1.927171417, 1.830461500, 1.836721458` seconds
- All assets, one year: `0.560702542, 0.602979125, 0.605164333, 0.561879334, 0.592842459` seconds
- All assets, full history: `13.586133459, 13.760511000, 14.863014458, 14.370036291, 17.500468459` seconds

## All 40 put values

| Symbol | One-year value | Full-history value |
|---|---:|---:|
| AAVEUSDT | 68.983985160662 | 199.406084472175 |
| ADAUSDT | 0.167964751471 | 1.132846405898 |
| ALGOUSDT | 0.051989932547 | 1.145334150464 |
| ATOMUSDT | 0.775724317430 | 21.794383981849 |
| AVAXUSDT | 4.737658358479 | 39.910070968421 |
| AXSUSDT | 0.557318971739 | 89.404026326300 |
| BCHUSDT | 138.814494188930 | 322.868109738990 |
| BNBUSDT | 172.702067150210 | 209.327086817205 |
| BTCUSDT | 16713.714208766745 | 20716.754071288182 |
| CHZUSDT | 0.009700750365 | 0.268549381855 |
| COMPUSDT | 10.545203378677 | 220.055194883550 |
| CRVUSDT | 0.154846140447 | 3.076483278019 |
| DASHUSDT | 25.002712871815 | 123.831979081744 |
| DOGEUSDT | 0.045512387286 | 0.168386570811 |
| DOTUSDT | 0.846311533171 | 24.635689247357 |
| EGLDUSDT | 2.821019377991 | 166.713106844472 |
| ENJUSDT | 0.020519388859 | 1.800711699484 |
| ETCUSDT | 3.846929987321 | 30.465397225212 |
| ETHUSDT | 811.436540660004 | 1929.861726946268 |
| FILUSDT | 0.568113209636 | 40.171823550329 |
| GRTUSDT | 0.018168226418 | 0.664248143610 |
| HBARUSDT | 0.051707289510 | 0.257237446296 |
| ICPUSDT | 1.142838520129 | 29.874109874290 |
| LINKUSDT | 4.292346122658 | 17.556272712032 |
| LTCUSDT | 21.176355626677 | 100.816087027641 |
| MANAUSDT | 0.066947596892 | 1.814044698888 |
| NEARUSDT | 0.788801925019 | 6.991045892597 |
| NEOUSDT | 1.263304329020 | 26.565918552022 |
| PAXGUSDT | 362.666993653956 | 227.124157074618 |
| SANDUSDT | 0.067893966852 | 1.116562467621 |
| SNXUSDT | 0.331002386568 | 7.145619746191 |
| SOLUSDT | 43.713828999515 | 127.176729054770 |
| THETAUSDT | 0.160289661982 | 4.702668677449 |
| TRXUSDT | 0.023365200152 | 0.035164125558 |
| UNIUSDT | 2.009197703633 | 15.855578173619 |
| VETUSDT | 0.004304196496 | 0.079156756154 |
| XLMUSDT | 0.088042725642 | 0.206365414412 |
| XRPUSDT | 0.575599839662 | 0.602596670346 |
| XTZUSDT | 0.161803282835 | 3.636010454957 |
| ZECUSDT | 188.465772363122 | 117.606048922692 |

## Correctness and data integrity

- The two-period example equals `1175/147 = 7.9931972789` and displays as `7.9932`; its boundary is `(None, 80, 96)`.
- The Python and compiled kernels agree on the exhaustive small-tree suite and the complete Bitcoin one-year boundary.
- All 40 CSV files contain finite, strictly positive prices and ordered UTC timestamps.
- The one-year windows contain 8,761 observations and no missing hours.
- Full files contain 43,823 observations (`N=43,822`) and one common missing hour, 2023-03-24 13:00 UTC; it is reported and not filled.
- Bitcoin source SHA-256: `2262b9e97986e964107c9d59085d4403ef90ea63ffa58ba73df3740587b59df6`.

## Measurement protocol

Inputs were parsed, validated, checksummed, and calibrated outside timing. Each scenario has five fresh raw repeats and reports their median. Worker processes were warmed outside timing. Required output construction is inside timing; serialization and cleanup are outside. Peak memory comes from a separate fresh run sampling RSS with `psutil`; Bitcoin includes parent plus child, and batch runs include parent plus the coordinator process tree. Outputs remain alive at the final sample.

## Assumptions and limitations

- A year is 8,760 hours, matching the assignment's one-year definition.
- The missing full-history exchange hour is not interpolated; adjacent available observations remain adjacent tree periods, while endpoint timestamps determine T.
- USDT is treated as the supplied US-dollar proxy; PAXG is the supplied gold proxy.
- The S&P 500 file is optional, date-dependent, and not part of the required 40 tracked assets.
- Canonical measurements identify the committed implementation by Git commit and by SHA-256 source hashes.

## Dashboard

`results/dashboard.html` is a standalone, saved-results-only dashboard. It exposes all raw repeats, statuses, units, memory definitions, all 40 values, Bitcoin boundary charts, CPU-scaling pilots, environment details, and source checksums. It has no network dependency and does not run pricing or measurement code. `python3 dashboard.py --check` verifies byte-stable regeneration.

## Reproduction

```bash
python3 -m unittest discover -s tests -v
python3 run_bitcoin.py --window one_year
python3 run_bitcoin.py --window full
python3 pilot_workers.py
python3 run_all_assets.py --window one_year --workers 8
python3 run_all_assets.py --window full --workers 8
python3 dashboard.py
python3 dashboard.py --check
python3 build_report.py
python3 build_report.py --check
```
