# Class 3 lab: PriceAmericanPut on market data (BonackerMaurice)

An American put is priced with backward induction on a binomial tree with one
period per hour, using the hourly closes in `Class3/data/hourly/`. It runs in
O(N) memory, and the early-exercise boundary is built in the same pass. The
pure-Python reference is compared with a NumPy version and with a naive full
tree, and the 40 assets are priced in parallel.

**Commit to audit:** `184680a5ca605675de0457f05b41d85dbc9bdd3a` (`184680a`, the
code; the tests came first, in `f637204`).
**Results run:** `02_results/20261127-120909_184680a/`, made from that commit
with a clean `01_code/` (`git.dirty: false` in `environment.json`).

## Run it

From `Submissions/BonackerMaurice/Class3/01_code/` (Python 3.13.15, Windows 11):

```bash
python -m pip install -r requirements.txt     # numpy 2.5.3, psutil 7.2.2, pytest 9.1.1
python -m pytest                              # expected: 203 passed
python -m lab.run_lab                         # everything, about 17 min -> ../02_results/<run_id>/
python -m lab.run_lab --only btc              # tasks 2-4 only (about 1 min)
python -m lab.run_lab --only curve            # memory/time against N (about 8 min, needs about 12 GB free RAM)
python -m lab.run_lab --only assets           # task 5 (about 8 min)
python -m lab.run_lab --quick                 # small grid for development (gitignored)
```

The data are read from `Class3/data/hourly/`, relative to the repository root,
and are never modified. The runner uses `if __name__ == "__main__":` and
`ProcessPoolExecutor`, so it works on Windows (the spawn start method). It does
not use the `resource` module.

## Layout

```
Class3/
  README.md            this file
  00_docs/             DEVLOG.md (tests failed first), REVISIONS.md, AI_USAGE.md
  01_code/
    american_put/      common.py (q, float-range guard), reference.py, vectorised.py, fulltree.py
    market/data.py     loading, windows, calibration, would-have-exercised check
    lab/               measure.py (timing, memory, environment), run_lab.py (all runs)
    tests/             test_pricer.py, test_market.py (203 tests)
  02_results/<run_id>/ environment.json, runs.csv/.md, memory_curve.csv, btc.csv,
                       btc_1y_boundary.csv, btc_5y_boundary.csv, assets.csv
```

## Model and contract

The algorithm (slides 23–26) uses two arrays of length N+1 and works backwards
one date at a time:

```
q = (R-d)/(u-d);  S[0] = S0*d^N;  S[j] = S[j-1]*u/d;  V[j] = max(K-S[j], 0)
for t = N-1..0:  for j = 0..t:  S[j] = S[j]/d;  c = (q*V[j+1] + (1-q)*V[j])/R;  V[j] = max(K-S[j], 0, c)
return V[0]
```

- **Contract:**
  - The input is the last N+1 rows of a file, P0..PN.
  - The put is written at P0, expires at PN, and is at the money: S0 = K = P0.
  - It can be exercised at every hour 0..N.
- **Periods:** one tree period per **row**, so N = rows − 1. Missing hours are
  missing rows, and the rows are counted. Every file has 43,823 rows (one
  missing hour in five years). A gap makes one return span two clock hours. It
  still counts as one period, as the lab specifies.
- **Calibration:**
  - r_t = ln(P_t/P_{t−1}).
  - s is the sample standard deviation of the r_t (`statistics.stdev`, divides
    by N−1).
  - u = e^s and d = 1/u.
  - R = e^(0.04·T/N).
- **T (a choice):** T is the actual time between the timestamps of P0 and PN,
  in years of **365.25 days**. For the one-year BTC window this gives
  T = 0.99932.
- **Windows:**
  - one year = the last 8,761 rows (N = 8,760)
  - five years = every row whose timestamp is at most 5 × 365.25 days before
    the last one, which is the whole file (N = 43,822)
- **Early-exercise boundary:** boundary_t is the highest tree price at date t
  where exercising is optimal, meaning K − S > 0 and K − S ≥ c. At t = N, c is
  0. It is `None` if no node qualifies. It is recorded **inside the single
  backward pass** as one number per date, so memory stays O(N).
- **Would the holder have exercised?** The first t with P_t ≤ boundary_t gives
  the date (UTC) and the payoff K − P_t. If there is no such t, the answer is
  "never". s is estimated from the option's own window P0..PN, so the
  exercise check has look-ahead bias: at P0 the holder could not have known
  the volatility, and therefore the boundary, that the check uses.

## Results (run `20261127-120909_184680a`)

### BTCUSDT (tasks 2–4)

| Window | N | s (hourly) | s·N | Put value | % of K | Would exercise? |
|---|---|---|---|---|---|---|
| 1 year, from 2025-10-31 23:00 UTC | 8,760 | 0.004607 | 40.4 | **16,714.94** | 15.25 | **yes:** 2026-06-02 14:00 UTC at 68,019.30, payoff **41,588.71** |
| full file (5 years), from 2021-11-01 00:00 UTC | 43,822 | 0.005396 | 236.5 | **20,719.79** | 33.66 | **yes:** 2022-06-18 06:00 UTC at 19,439.26, payoff **42,121.23** |

K = 109,608.01 for one year and 61,560.49 for five years. The full boundaries,
with one row per hour (t, timestamp, close, boundary), are in
`btc_1y_boundary.csv` and `btc_5y_boundary.csv`. In the one-year window the
reference and vectorised versions give the identical value and boundary
(`reference_equals_vectorised = True` in `btc.csv`).

### Memory and time against N: the main result

The inputs are BTC data (the last N+1 hours). For N > 43,822, beyond the data
length, the curve reuses the five-year BTC per-hour u, d and R, and only N
grows. Every cell runs in a fresh process. All versions agree at every N:
identical value and identical SHA-256 of the boundary (`memory_curve.csv`).

| N | reference: s | reference: peak | vectorised: s | vectorised: traced peak | fulltree: s | fulltree: traced peak |
|---|---|---|---|---|---|---|
| 1,000 | 0.075 | 0.1 MiB | 0.009 | 0.1 MiB | 0.015 | 4.0 MiB |
| 2,000 | 0.280 | 0.2 MiB | 0.020 | 0.1 MiB | 0.041 | 15.6 MiB |
| 5,000 | 2.08 | 0.4 MiB | 0.082 | 0.3 MiB | 0.167 | 96.3 MiB |
| 10,000 | 7.23 | 0.9 MiB¹ | 0.278 | 0.6 MiB | 0.647 | 383 MiB |
| 20,000 | 30.0 | 2.0 MiB¹ | 1.15 | 1.2 MiB | 2.67 | 1.49 GiB |
| 43,822 (full file) | 152 | 4.4 MiB¹ | 8.59 | 2.7 MiB | 15.9 | **7.16 GiB** |
| 55,000² | not run³ |  | 14.7 | 3.4 MiB | 23.7 | **11.28 GiB** |
| 70,000² | not run³ |  | 26.3 | 4.3 MiB | n/a | **out of memory:** needs 18.3 GiB, 20.9 GiB free |

¹ psutil process peak (peak working set minus the working set before the call).
The reference is traced only up to N = 5,000, because tracemalloc slows pure
Python about 18× (166 s instead of 9 s at N = 8,760).
² Synthetic N, using the BTC five-year u, d and R.
³ Pure Python beyond the data length would take over 4 minutes per point.

**Reading the curve:**

- **Memory:**
  - The O(N) versions grow linearly, from 0.1 to 4 MiB. That is the two
    arrays, 2·8·(N+1) bytes, plus per-date temporaries.
  - The full tree grows as N²: 8·(N+1)(N+2)/2 bytes. At N = 43,822 that is
    7.68 GB (= 7.15 GiB, the "≈ 7.7 GB" of the task). The measured traced peak
    is 7.16 GiB.
  - Between N = 20,000 and 43,822 the full tree grows 4.8× (the ratio of N²
    is 4.8). The O(N) versions grow 2.2× (the ratio of N is 2.2).
- **Where the full tree runs out:**
  - **Free RAM:** whether the tree fits depends on free RAM, not only on
    total RAM. Free RAM is measured right before each attempt and saved in
    `environment.json` → `ram_checks_before_fulltree`. Before the N = 70,000
    attempt it was 20.9 GiB.
  - **The 80% limit:** the runner refuses a tree that needs more than 80% of
    free RAM, because attempting it would push Windows into the page file
    rather than raise a clean `MemoryError`.
  - **On this machine:** with 20.9 GiB free, the limit is reached at about
    N ≈ 67,000. Free RAM itself is exceeded at N ≈ 75,000.
  - **With less free RAM:** at 3.2 GiB free (earlier in the day, while another
    program was using about 10 GB), the tree would already fail above
    N ≈ 29,000.
- **Time:**
  - All three versions are O(N²) in time, because they do (N+1)(N+2)/2 node
    updates. From N = 20,000 to 43,822 (N² ratio 4.8), the reference grows
    5.1×. The NumPy versions grow faster: 7.4× for vectorised, 6.0× for the
    full tree. The likely reason is cache size. At N = 20,000 each working
    array (about 160 KB) fits in the L2 cache, at 43,822 (about 350 KB) it no
    longer does. This was not measured directly.
  - The vectorised version is about **18× faster** than the reference at
    N = 43,822 (8.6 s against 152 s) and 25× at N = 8,760 (0.24 s against
    5.96 s, `btc-1y`).
  - **Run-to-run variation:** every point is a single measurement on a hybrid
    CPU, and Windows can place a single-threaded run on a performance core or
    an efficiency core. A pre-commit run of the same code gave 6.3 s for the
    vectorised version at N = 43,822 (24×), while the reference gave 153 s in
    both runs.
  - The full tree is 1.6–2.3× slower than the vectorised version, because it
    allocates a new array for every date and has a second pass for the
    boundary.

### All 40 assets in parallel (task 5)

These runs use the vectorised pricer in a `ProcessPoolExecutor`, with one task
per asset. Wall-clock time is measured in the parent process and includes
starting the pool.

| Window | N | Workers | Wall-clock s | Speed-up | Peak per worker | Peak total (sampled) |
|---|---|---|---|---|---|---|
| 1 year | 8,760 | 1 | 21.3 | 1.0× | 45 MiB | 95 MiB |
| 1 year | 8,760 | 4 | 7.1 | 3.0× | 45 MiB | 229 MiB |
| 1 year | 8,760 | 8 | 4.4 | 4.8× | 45 MiB | 405 MiB |
| 5 years | 43,822 | 1 | 288.1 | 1.0× | 54 MiB | 103 MiB |
| 5 years | 43,822 | 4 | 108.9 | 2.6× | 54 MiB | 256 MiB |
| 5 years | 43,822 | 8 | 63.7 | 4.5× | 53 MiB | 454 MiB |

**What the columns mean:**

- **Peak per worker:** the psutil peak working set of one worker process. That
  is the Python interpreter plus NumPy, about 45 MiB, plus the asset's data and
  arrays.
- **Peak total:** the summed RSS of the parent and all workers, sampled every
  0.1 s.
- **Pricing memory:** the traced pricing memory per asset is only 0.5 MiB (one
  year) or 2.7 MiB (five years). Memory in parallel therefore grows with the
  number of **workers**, not with N.

**Why the speed-up is not 8×:** this laptop's CPU (Intel family 6, model 189)
has 8 cores without hyper-threading, some of them efficiency cores. For the
five-year run, the per-asset compute seconds add up to 286 s with 1 worker and
488 s with 8. Each task runs slower when all cores are busy (efficiency cores,
shared cache and memory bandwidth, clock limits).

### Put values and exercise decisions for every asset

Each put is at the money and written at P0. The value is shown as a percentage
of K = P0. Of the 40 assets, the holder would have exercised 36 in the one-year
window and 36 in the five-year window. The full data, including s, u, R, the
exercise price and the timing, are in `assets.csv`.

| Asset | 1y put (% of K) | 1y exercise (UTC) | 5y put (% of K) | 5y exercise (UTC) | 5y s·N |
|---|---|---|---|---|---|
| AAVEUSDT | 30.20 | 2026-05-28 03:00, payoff 147.5 | 62.93 | 2026-05-18 03:00, payoff 228.5 | 465 |
| ADAUSDT | 27.58 | 2026-05-27 22:00, payoff 0.3724 | 57.45 | 2022-12-19 17:00, payoff 1.715 | 414 |
| ALGOUSDT | 29.31 | 2026-07-29 17:00, payoff 0.1004 | 61.92 | 2022-12-16 22:00, payoff 1.663 | 456 |
| ATOMUSDT | 26.19 | 2026-07-24 10:00, payoff 1.564 | 58.08 | 2024-07-05 00:00, payoff 31.69 | 420 |
| AVAXUSDT | 26.05 | 2026-06-04 10:00, payoff 10.62 | 62.32 | 2025-11-21 09:00, payoff 51.05 | 459 |
| AXSUSDT | 39.36 | 2026-10-25 05:00, payoff 0.473 | 65.33 | 2022-09-18 21:00, payoff 124.7 | 490 |
| BCHUSDT | 25.94 | 2026-06-05 06:00, payoff 311.1 | 53.89 | 2022-11-09 21:00, payoff 510.5 | 384 |
| BNBUSDT | 15.86 | 2026-02-11 08:00, payoff 493 | 39.64 | never | 277 |
| BTCUSDT | 15.25 | 2026-06-02 14:00, payoff 4.159e+04 | 33.66 | 2022-06-18 06:00, payoff 4.212e+04 | 236 |
| CHZUSDT | 31.43 | 2026-07-31 05:00, payoff 0.01821 | 63.12 | 2024-08-04 16:00, payoff 0.3712 | 467 |
| COMPUSDT | 30.11 | 2026-10-14 18:00, payoff 12.47 | 63.72 | 2022-06-14 01:00, payoff 312.7 | 473 |
| CRVUSDT | 32.27 | 2026-10-25 07:00, payoff 0.1333 | 69.61 | 2024-04-13 20:00, payoff 4.043 | 537 |
| DASHUSDT | 47.27 | 2026-10-31 17:00, payoff 4.65 | 64.00 | 2024-06-18 01:00, payoff 170.4 | 476 |
| DOGEUSDT | 24.41 | 2026-06-05 06:00, payoff 0.1027 | 59.97 | 2026-06-04 08:00, payoff 0.192 | 437 |
| DOTUSDT | 29.37 | 2026-06-03 03:00, payoff 1.819 | 56.81 | 2022-10-21 08:00, payoff 37.59 | 409 |
| EGLDUSDT | 30.93 | 2026-06-04 01:00, payoff 5.92 | 60.39 | 2023-06-10 02:00, payoff 242.7 | 441 |
| ENJUSDT | 49.07 | 2026-10-25 06:00, payoff 0.017 | 69.45 | 2023-10-10 08:00, payoff 2.376 | 535 |
| ETCUSDT | 24.26 | 2026-06-05 02:00, payoff 8.82 | 55.83 | 2025-10-10 21:00, payoff 41.85 | 400 |
| ETHUSDT | 21.09 | 2026-06-02 14:00, payoff 1907 | 44.71 | 2022-06-18 19:00, payoff 3402 | 313 |
| FILUSDT | 37.50 | 2026-10-22 14:00, payoff 0.543 | 63.31 | 2022-06-12 00:00, payoff 57.31 | 469 |
| GRTUSDT | 29.61 | 2026-06-04 01:00, payoff 0.03935 | 64.98 | 2022-06-15 08:00, payoff 0.9319 | 486 |
| HBARUSDT | 25.73 | 2026-05-28 03:00, payoff 0.1181 | 61.68 | 2022-11-09 21:00, payoff 0.3741 | 453 |
| ICPUSDT | 38.85 | 2026-10-31 04:00, payoff 0.45 | 65.66 | 2022-11-09 09:00, payoff 41.46 | 493 |
| LINKUSDT | 24.90 | 2026-06-05 06:00, payoff 9.748 | 57.91 | 2026-02-05 23:00, payoff 22.4 | 419 |
| LTCUSDT | 22.20 | 2026-06-04 01:00, payoff 50.06 | 52.11 | 2026-01-31 17:00, payoff 135.3 | 370 |
| MANAUSDT | 29.51 | 2026-05-28 03:00, payoff 0.1446 | 63.57 | 2022-12-30 07:00, payoff 2.568 | 472 |
| NEARUSDT | 37.58 | never | 68.02 | 2025-12-01 01:00, payoff 8.584 | 519 |
| NEOUSDT | 25.46 | 2026-06-05 18:00, payoff 2.843 | 58.99 | 2025-03-09 22:00, payoff 37.13 | 428 |
| PAXGUSDT | 9.07 | 2026-10-31 12:00, payoff 103.6 | 12.75 | never | 105 |
| SANDUSDT | 33.60 | 2026-06-02 15:00, payoff 0.1402 | 65.97 | 2025-04-07 03:00, payoff 1.464 | 496 |
| SNXUSDT | 33.10 | 2026-03-27 18:00, payoff 0.724 | 69.97 | 2025-02-03 01:00, payoff 9.135 | 541 |
| SOLUSDT | 23.35 | 2026-04-02 01:00, payoff 107.9 | 61.14 | 2022-11-09 01:00, payoff 185.3 | 448 |
| THETAUSDT | 32.92 | 2026-06-05 02:00, payoff 0.3286 | 64.35 | 2023-06-08 03:00, payoff 6.562 | 479 |
| TRXUSDT | 7.89 | never | 34.70 | never | 243 |
| UNIUSDT | 34.98 | never | 63.02 | 2025-12-15 16:00, payoff 20.12 | 466 |
| VETUSDT | 27.61 | 2026-05-27 22:00, payoff 0.009499 | 59.07 | 2022-12-19 03:00, payoff 0.1177 | 429 |
| XLMUSDT | 28.87 | 2026-10-08 15:00, payoff 0.1158 | 55.18 | 2026-08-06 13:00, payoff 0.2141 | 395 |
| XRPUSDT | 22.94 | 2026-06-04 01:00, payoff 1.348 | 53.33 | never | 380 |
| XTZUSDT | 27.87 | 2026-06-10 04:00, payoff 0.3475 | 57.47 | 2022-12-17 20:00, payoff 5.497 | 415 |
| ZECUSDT | 46.59 | never | 68.82 | 2024-07-05 02:00, payoff 154.6 | 528 |

### Numerical trap: S0·d^N underflow

- **The trap:** d^N = e^(−s·N). If ln S0 − s·N falls below ln(smallest normal
  float) ≈ −708, then S[0] = S0·d^N underflows to 0 (or to a subnormal with
  few digits), and S[j] = S[j−1]·u/d then makes **every** node 0. Similarly,
  S0·u^N overflows at +709.8.
- **The data are safe:** the largest s·N in the data is **541** (SNXUSDT, five
  years). The lowest tree price is 10^−234 (CRVUSDT, ENJUSDT and SNXUSDT over five
  years), which is far inside the float range of about 10^±308.
  Every run saves s·N, log10(S0·d^N) and log10(S0·u^N) (`btc.csv`,
  `assets.csv`).
- **The guard:** `american_put/common.py: check_inputs` refuses a tree outside
  the float range with a `ValueError` instead of returning a wrong price
  (`test_underflowing_tree_is_rejected`: s·N = 800). It accepts s·N = 600
  (`test_large_but_representable_tree_is_accepted`).
- **Rounding:** the chained products S[j] = S[j−1]·u/d accumulate a relative
  rounding error of about 2N·ε ≈ 10^−11 at N = 43,822. That is negligible
  next to the price.

### Every run (task 6)

N, number of assets, wall-clock seconds and peak memory for every run, from
`runs.csv`. MB means MiB (2^20 bytes).

| run | version | N | assets | workers | wall_s | traced_peak_mb | process_peak_mb | status |
|---|---|---|---|---|---|---|---|---|
| btc-1y | vectorised | 8760 | 1 | 1 | 0.242 | 0.5 | 1.5 | ok |
| btc-1y | reference | 8760 | 1 | 1 | 5.959 |  | 0.7 | ok |
| btc-5y | vectorised | 43822 | 1 | 1 | 8.198 | 2.7 | 4.5 | ok |
| curve | reference | 1000 | 1 | 1 | 0.075 | 0.1 | 0.1 | ok |
| curve | vectorised | 1000 | 1 | 1 | 0.009 | 0.1 | 1.9 | ok |
| curve | fulltree | 1000 | 1 | 1 | 0.015 | 4.0 | 6.2 | ok |
| curve | reference | 2000 | 1 | 1 | 0.280 | 0.2 | 0.2 | ok |
| curve | vectorised | 2000 | 1 | 1 | 0.020 | 0.1 | 2.1 | ok |
| curve | fulltree | 2000 | 1 | 1 | 0.041 | 15.6 | 18.2 | ok |
| curve | reference | 5000 | 1 | 1 | 2.081 | 0.4 | 0.5 | ok |
| curve | vectorised | 5000 | 1 | 1 | 0.082 | 0.3 | 1.6 | ok |
| curve | fulltree | 5000 | 1 | 1 | 0.167 | 96.3 | 98.8 | ok |
| curve | reference | 10000 | 1 | 1 | 7.232 |  | 0.9 | ok |
| curve | vectorised | 10000 | 1 | 1 | 0.278 | 0.6 | 2.3 | ok |
| curve | fulltree | 10000 | 1 | 1 | 0.647 | 383.3 | 386.0 | ok |
| curve | reference | 20000 | 1 | 1 | 30.033 |  | 2.0 | ok |
| curve | vectorised | 20000 | 1 | 1 | 1.153 | 1.2 | 3.2 | ok |
| curve | fulltree | 20000 | 1 | 1 | 2.672 | 1529.5 | 1532.3 | ok |
| curve | reference | 43822 | 1 | 1 | 152.418 |  | 4.4 | ok |
| curve | vectorised | 43822 | 1 | 1 | 8.586 | 2.7 | 4.5 | ok |
| curve | fulltree | 43822 | 1 | 1 | 15.949 | 7333.5 | 7337.4 | ok |
| curve | reference | 55000 | 1 | 1 |  |  |  | not run: pure Python too slow beyond the data length |
| curve | vectorised | 55000 | 1 | 1 | 14.718 | 3.4 | 5.3 | ok |
| curve | fulltree | 55000 | 1 | 1 | 23.656 | 11549.3 | 11553.5 | ok |
| curve | reference | 70000 | 1 | 1 |  |  |  | not run: pure Python too slow beyond the data length |
| curve | vectorised | 70000 | 1 | 1 | 26.284 | 4.3 | 6.9 | ok |
| curve | fulltree | 70000 | 1 | 1 |  |  |  | out of memory: tree needs 18.3 GB, 20.9 GB free (not attempted) |
| assets-1y | vectorised | 8760 | 40 | 1 | 21.277 | 0.5 per asset (max) | 45.0 per worker (max); 94.7 total (sampled) | ok; sum of per-asset seconds 19.4 |
| assets-1y | vectorised | 8760 | 40 | 4 | 7.067 | 0.5 per asset (max) | 45.2 per worker (max); 229.0 total (sampled) | ok; sum of per-asset seconds 24.2 |
| assets-1y | vectorised | 8760 | 40 | 8 | 4.432 | 0.5 per asset (max) | 45.1 per worker (max); 404.8 total (sampled) | ok; sum of per-asset seconds 28.0 |
| assets-5y | vectorised | 43822 | 40 | 1 | 288.062 | 2.7 per asset (max) | 54.4 per worker (max); 103.2 total (sampled) | ok; sum of per-asset seconds 286.1 |
| assets-5y | vectorised | 43822 | 40 | 4 | 108.858 | 2.7 per asset (max) | 53.8 per worker (max); 255.6 total (sampled) | ok; sum of per-asset seconds 421.5 |
| assets-5y | vectorised | 43822 | 40 | 8 | 63.712 | 2.7 per asset (max) | 52.6 per worker (max); 453.9 total (sampled) | ok; sum of per-asset seconds 488.2 |

## Measurement definitions

- **Seconds:** `time.perf_counter()` around one complete pricing call
  `pricer(S0, K, u, d, R, N)`, with no tracemalloc running. Calibration and
  loading are excluded. For the asset runs, the time is the wall clock of the
  whole pool in the parent process, plus each task's own pricing seconds in
  `assets.csv`. Each point was measured once, so absolute times can vary by
  about 35% between runs (see "Run-to-run variation" above). Memory and
  results do not vary: values, boundaries and traced peaks were identical in a
  pre-commit run.
- **Traced peak:** the `tracemalloc` peak of a second, identical call in the
  same fresh process. NumPy reports its buffers to tracemalloc. This covers
  the pricing allocations only, not the input data or the interpreter.
- **Process peak:** psutil `peak_wset` (the Windows peak working set) after the
  call, minus the RSS before it. This includes allocator and interpreter
  overhead of about 1–2 MiB.
- **Free RAM:** psutil `virtual_memory().available`. It is recorded at the
  start of the run, before every full-tree attempt, and at the end
  (`environment.json`). This run had 20.4 GiB free at the start, 20.9 GiB
  before the N = 70,000 attempt, and 21.2 GiB at the end. Total RAM is
  31.5 GiB.
- **Machine:**
  - Windows 11 Pro, Python 3.13.15, NumPy 2.5.3, 8 cores, plugged in.
  - OneDrive sync was paused and VS Code was closed. CPU load just before the
    run was 6.5%, and the Claude desktop app stayed open.

## Revision summary

`00_docs/REVISIONS.md` describes the changes from the reference to the
vectorised version:

- the inner j loop is replaced by one NumPy step per date, and the
  continuation is computed from the old V before V is overwritten
- the operation order is unchanged, so the results are identical bit for bit
- the result is about 18× faster at N = 43,822 and 25× faster at N = 8,760

It also explains why the boundary is built inside the pass, and the
measurement fixes found along the way: tracemalloc's overhead on pure Python,
and the RAM-dependent full-tree limit. `00_docs/DEVLOG.md` shows the tests
failing first (203 failed against stubs) and the hand trace of the slide tree.

## Tests (203, all pass)

- **Slide tree:**
  - value 7.9932, q = 0.625, European 6.2925
  - the intermediate S, c and V of slides 24–26
  - the boundary [None, 80, 96]
- **Random trees:** 40 random small trees against an independent brute-force
  recursion that computes prices directly as S0·u^j·d^(t−j).
- **Version agreement:** the vectorised and full-tree versions equal the
  reference **exactly** (value and boundary) on 40 random trees.
- **Edge cases:**
  - no-arbitrage bounds
  - N = 0
  - the d < R < u check
  - the float-range guard
  - Python `float` and `list` return types
- **Market data:**
  - loading the files and taking the last N+1 rows or a five-year window
  - calibration with missing hours (N counts rows, T comes from timestamps)
  - the inputs stay unchanged
  - the first-exercise rule (equality counts, "never", mismatched lengths)
