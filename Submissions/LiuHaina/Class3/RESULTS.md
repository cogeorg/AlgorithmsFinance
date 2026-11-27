# Class 3 lab results

| Run | Assets | Actual N (min–max) | Pricing seconds | Peak RSS (MiB) | Workers |
|---|---:|---:|---:|---:|---:|
| btc_year | 1 | 8760–8760 | 0.1007 | 129.23 | 1 |
| btc_full | 1 | 43822–43822 | 1.9598 | 128.06 | 1 |
| all_year | 40 | 8760–8760 | 1.0043 | 149.80 | 4 |
| all_full | 40 | 43822–43822 | 19.9989 | 148.70 | 4 |

Seconds cover pricing plus boundary-crossing scans; JIT, loading/calibration and writing files are excluded. Separate JIT and loading/calibration timings are in each measurement JSON; serialization time was not measured. Peak RSS includes imports, JIT and loaded data, measured before output serialization in a fresh child process; it is not just tree storage. Runs execute sequentially; asset computations within each 40-asset run use four threads.

| BTC window | Put value (USDT) | First boundary crossing (UTC) | Payoff (USDT) |
|---|---:|---|---:|
| year | 16713.7142 | 2026-06-02T14:00:00Z | 41588.7100 |
| full | 20716.7541 | 2022-06-18T06:00:00Z | 42121.2300 |

All 40 prices, calibration inputs, window dates, actual step counts, missing-hour counts and crossing outcomes appear in `results/all_year_prices.csv` and `results/all_full_prices.csv`. Every date’s boundary is saved in the corresponding compressed CSV.

One-year windows use the final 8,761 observations (8,760 steps). Full windows use every supplied row; missing exchange hours remain missing. T uses actual elapsed UTC time divided by 365 days, so five calendar years including a leap day can exceed 5.0 ACT/365 years.

Memory scaling: the largest full tree would require approximately 7.15 GiB for one float64 value at every node, before stock prices, boundaries or Python overhead. Rolling values plus boundaries require only 0.669 MiB per active asset. No memory limit was hit in these four runs; this implementation removes the quadratic storage requirement, while retaining quadratic running time. This is an analytical full-tree estimate, not a measured out-of-memory experiment.
