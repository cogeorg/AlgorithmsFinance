# Class 3 — American put pricing on hourly market data

## Objective and model

The lab prices American puts on the supplied Bitcoin and other crypto price histories and investigates how the calculation scales. A binomial tree compares immediate exercise with the discounted value of continuing at each date. The option is at the money at inception: `S0 = K =` the first close in the selected window. There are no dividends or trading frictions. The observed exercise comparison is **in sample**: the same window is used for calibration and evaluation.

For N observed returns, the sample standard deviation `s` of `ln(P[t]/P[t-1])` sets `u = exp(s)` and `d = 1/u`. With elapsed calendar time T measured in years using 365.25 days, `R = exp(0.04*T/N)` and `q = (R-d)/(u-d)`. The implementation verifies `0 < d < R < u`. Risk-neutral q prices the option; it is not a forecast probability.

The one-year crypto window uses the last 8,761 closes and 8,760 returns; the full file has 43,823 closes and 43,822 returns. One hourly observation is missing in the full history. We do not fill it: consecutive available closes are treated as consecutive model steps, while elapsed time determines T. The two-hour gap is an approximation to the slides' equally spaced hourly tree, and an exercise crossing in that unobserved hour cannot be ruled out. Prices are USDT per asset unit.

## Correctness and Bitcoin exercise

Version A implements the slide's two-array backward induction in Python. Version B uses NumPy operations for each row. The two-period example produced **7.99319728** in both versions, matching the slide value of 7.9932. For last-year Bitcoin, the versions returned **16,714.93527055 USDT per BTC**, with observed absolute difference zero. The vectorized boundary also matched the small tree and all 8,761 saved one-year boundary entries within 0.0001; its full-history price and first crossing matched the earlier Version A result. Seven focused tests passed in the recorded correctness run; no claim is made that testing proves correctness.

| BTC window | Starting price and strike | Put value | First observed exercise crossing | Boundary | Intrinsic payoff |
|---|---:|---:|---|---:|---:|
| One year: 2025-10-31 23:00 to 2026-10-31 23:00 UTC | 109,608.01 | 16,714.94 | 2026-06-02 14:00 UTC, BTC 68,019.30 | 68,193.47 | 41,588.71 |
| Full history: 2021-11-01 00:00 to 2026-10-31 23:00 UTC | 61,560.49 | 20,719.79 | 2022-06-18 06:00 UTC, BTC 19,439.26 | 19,823.10 | 42,121.23 |

Values are USDT per BTC. The complete boundary is saved for every step, with blank entries where no positive-payoff exercise node is optimal. A crossing is the first observed close at or below that step's boundary, not necessarily the first continuous-time crossing.

## Required experiments and memory

All 40 instructor-supplied assets completed for both horizons. The table shows the later Version B RSS-monitoring runs; each completed and reproduced the previously saved prices.

| Workload | Periods per asset | Assets | Workers | Runtime | Peak aggregate RSS |
|---|---:|---:|---:|---:|---:|
| BTC, one year | 8,760 | 1 | 1 | 0.312 s | 42.26 MiB |
| BTC, full history | 43,822 | 1 | 1 | 10.472 s | 43.92 MiB |
| 40 assets, one year | 8,760 | 40 | 8 | 4.044 s | 408.03 MiB |
| 40 assets, five years | 43,822 | 40 | 8 | 72.223 s | 440.91 MiB |

BTC runtimes cover pricing only; batch runtimes include loading, calibration, worker startup, pricing and collection. Peak RSS is the largest sampled sum across the workload process and descendants, including startup and loading. Sampling approximately every 50 ms may miss short peaks; summing RSS may count shared pages more than once and excludes the monitoring process. It is not the same measure as Python-traced allocations. Earlier Version A one-year tracing recorded 458,832 bytes; full-history tracing was terminated without a peak after excessive overhead.

## Optimization and worker scaling

Both pricing versions use O(N²) time and O(N) working memory. Vectorization reduces Python interpreter overhead but does not change those complexity classes. On last-year Bitcoin, a historical single Version A run took 10.428 s; three Version B runs after warm-up had a median of 1.092 s, an indicative **9.55×** ratio. These are not matched repeated measurements. On full-history Bitcoin, historical Version A pricing took 260.771 s versus 10.472 s for a later RSS-monitored Version B call; their timing boundaries and conditions differ.

For one-year pricing of 40 crypto assets, three complete timed batches per worker count gave medians of 16.678, 8.167, 5.350, 4.078, 3.498, 3.459 and 3.659 seconds for 1, 2, 4, 6, 8, 12 and 16 workers respectively. The fastest observed median was **12 workers, 4.82× speedup**, but it was only 0.038 s faster than eight workers. Sixteen workers was slower than 12. Eight workers were chosen for the five-year batch as a practical near-fastest configuration. Fixed ordering, system load, process startup and NumPy threading limit generalization.

## Deliverables and limitations

The [standalone interactive dashboard](../40_Results/class3_dashboard.html) uses only saved results and opens offline. The [consolidated CSV](../40_Results/required_results.csv), [BTC one-year boundary](../40_Results/bitcoin_last_year_boundary.csv), [full-history boundary](../40_Results/bitcoin_full_boundary.csv), [crypto-only one-year asset results](../40_Results/one_year_crypto.csv), [five-year asset results](../40_Results/five_year_assets/results.csv) and [worker-scaling results](../40_Results/cpu_scaling_one_year/summary.csv) provide the evidence. See the [README](../README.md) for setup, dependencies and reproduction commands.

The lab's stated requirements are met by the saved BTC values and boundaries, in-sample exercise decisions, 40-asset pricing at both horizons, and per-run period count, asset count, runtime and sampled RSS. Performance is machine-specific; RSS sampling and the missing-hour approximation limit interpretation. No market option prices were used for validation. AI assistance was used in implementation, testing, analysis and documentation; the author is responsible for reviewing the results.
