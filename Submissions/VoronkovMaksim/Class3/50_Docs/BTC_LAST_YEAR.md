# Required Bitcoin one-year experiment

The last 8,761 supplied Bitcoin observations span 2025-10-31 23:00 through 2026-10-31 23:00 UTC. They contain 8,760 strictly hourly periods with no missing hours. Input validation checks positive finite prices and strictly increasing timestamps. The source SHA-256 is `78bef06514dd17b0dcb7a65625e40a63fe114a7d2809facd27888c13a4168f1e`.

The selected window alone provides 8,760 log returns. Following the slides, the sample standard deviation is 0.00460739514050, u = 1.00461802551, d = 0.99540320262, R = 1.000004563095 and q = 0.499343344003; 0 < d < R < u. Actual elapsed time is 365 days / 365.25 days per year, and R = exp(0.04*T/N). The existing calibration module's first-calendar-year selector excludes its anniversary, so this script applies the same slide formulas directly to all 8,761 required observations instead of calling that selector.

With S0 = K = 109608.01 USDT/BTC, the existing pricing function returned 16714.93527055 USDT per BTC. The untraced call took 10.42793 seconds. A separate call recorded 458,832 peak Python-traced bytes using tracemalloc, not total process memory. The boundary calculation returned the same finite, nonnegative price. Timings depend on the machine.

The first observed exercise crossing was 2026-06-02 14:00 UTC at step 5127: BTC 68019.30, boundary 68193.46617 and intrinsic payoff 41588.71 USDT per BTC. Each observed hourly close maps directly to its corresponding tree step. The analysis is in sample: the whole window calibrated the model, so it is not a prediction.

Saved files: `40_Results/bitcoin_last_year_summary.json` and `bitcoin_last_year_boundary.csv`. Reproduce from the lab folder with `python -B 20_Code/btc_last_year.py 00_Instructor/Class3/data/hourly/BTCUSDT.csv`. Existing output files must be preserved or moved first because the script refuses to overwrite them. The memory-traced call runs much slower than the untraced call. The existing test suite was not rerun in this increment as requested.
