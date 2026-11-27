# Class 3 — American put on hourly market data

Author: LiuHaina. Python implementation for the lab on physical pages 30–32
(printed slide numbers 29–31) of `AlgorithmsFinance_Slides3.pdf`.

Start with [RESULTS.md](RESULTS.md) for the four runs' timings, memory usage,
BTC option values and first exercise-boundary crossings. Detailed prices for
all 40 assets are in `results/all_year_prices.csv` and
`results/all_full_prices.csv`.

## Requirements and deliverables

| Slide task | Implementation / saved evidence |
|---|---|
| 1. Implement PriceAmericanPut; obtain 7.9932 | `american_put.py`; `test_lab.py` exact rational reference |
| 2. BTC last 8,760 steps; value and boundary at every date | `results/btc_year_prices.csv`; `btc_year_BTCUSDT_boundary.csv.gz` |
| 3. First observed price at/below boundary, date and payoff, or never | `exercise_*` columns in each prices CSV |
| 4. BTC full file, approximately five years | `results/btc_full_*` |
| 5. All 40 assets in one run, one year and full file | `results/all_year_prices.csv`; `all_full_prices.csv` and all boundaries |
| 6. Actual N, asset count, seconds and peak memory | `results/runs.csv`; each `*_measurement.json`; `RESULTS.md` |

## Reproduce

Run these commands from this directory, using Python 3.13 (tested on macOS ARM64):

```sh
python3 -m venv work/venv
work/venv/bin/python -m pip install -r requirements.txt
work/venv/bin/python -B fetch_data.py
work/venv/bin/python -B -m unittest -v test_lab
work/venv/bin/python -B run_lab.py
work/venv/bin/python -B summarize_results.py
```

`fetch_data.py` uses system `curl`, with normal certificate verification, and
verifies each file's Git blob SHA-1. The committed manifest also records SHA-256.
Raw data and the local virtual environment stay in ignored `work/`.
The source is teacher repository `cogeorg/AlgorithmsFinance`, commit
`0325907cb0a6cc3cd1f292fca095b52d9343ac97`, directory `Class3/data/hourly`.
No data file is interpolated or changed. The 40 symbols include PAXGUSDT;
S&P 500 is mentioned as a separate optional data fetch, and is not one of the
40 assets specified by the task. The source download location for every CSV
is preserved in `data_manifest.json`.

Individual experiments can be reproduced with, for example:

```sh
work/venv/bin/python -B run_lab.py --scope btc --horizon year
work/venv/bin/python -B run_lab.py --scope all --horizon full --workers 4
```

Numba compiles the Python numerical loop to native machine code; the algorithm
and all implementation source are Python. No full two-dimensional tree is
allocated. The default driver starts a fresh process for each of the four runs.
Compilation is warmed separately. See each measurement's timing and memory
definitions before comparing machines or implementations.

## Model and algorithm

For the chosen window of N+1 closes, set S0=K=P0. Calculate hourly log returns
and their **sample** standard deviation s (ddof=1). Set u=exp(s), d=exp(-s),
T=(last UTC time−first UTC time)/(365 days), R=exp(0.04*T/N), and
q=(R−d)/(u−d). Reject parameters violating 0<d<R<u.

The one-year task uses the final 8,761 observations, exactly as the slide's
last-N+1 window rule specifies. The full task uses every supplied observation.
Missing hours are omitted by the source: actual N and missing-hour count are
reported separately, and T still uses elapsed clock time. This follows the
teacher's dataset convention; irregular observation gaps are compressed into
steps, rather than claiming a fully regular hourly sample or inventing prices.

At expiry, V=max(K−S,0). At an earlier node:

```
V(t,j) = max(K − S(t,j), [q*V(t+1,j+1)+(1−q)*V(t+1,j)] / R)
```

Only one value row and the N+1 boundary vector are retained: O(N) storage,
O(N²) computation. Index j is updated in increasing order so neither child
has been overwritten. Log stock prices and `expm1` avoid overflow in high
up branches and cancellation near the strike. Stock prices are exponentiated
only for a chosen boundary; overflowing high-price tree nodes need not exist
as floating-point stock prices.

The boundary at each date is the highest tree price with **positive payoff**
where exercise value is at least continuation value. Positive-payoff ties
exercise. Zero-payoff ties continue/lapse, so high out-of-the-money nodes do
not create an economically meaningless boundary. Blank boundary means no
exercise node under that policy. At expiry this convention includes only
strictly in-the-money nodes.

The observed-price diagnostic scans t=0,...,N and returns the first Pt at or
below that date's discrete boundary, or `never`. It reports the actual Pt and
K−Pt. This is the slide's discrete-boundary crossing rule, not a continuous
boundary interpolation, a trading backtest, or a realized return on capital.
`terminal_payoff` is also shown separately: a terminal observed price between
the highest in-the-money tree node and K can yield a terminal payoff without
triggering the discrete crossing rule.

## Verification and limitations

The tests compare with a separate exact-fraction full-tree recursion, verify
the two-period American and European values and boundaries, compare compiled
and Python execution, test a large-volatility tree, validate calibration,
check unchanged input arrays, reject invalid parameters, and test crossing
and no-crossing outcomes. `results/unit_tests.log` records the tests.

`summarize_results.py` reads every saved boundary row for all 82 priced
contracts, recomputes first crossings/payoffs, checks asset coverage, valid
prices/probabilities and step counts, and requires identical BTC results in
the individual and 40-asset runs. See `results/validation.json`.

The heading “scale up until memory binds” motivates comparing full-tree and
rolling storage. These requested runs completed without memory exhaustion.
The full-tree estimate is explicitly theoretical; no failed memory-allocation
experiment is claimed. Peak process RSS is broader than numerical workspace
and includes the Python/Numba environment. Timings depend on hardware, worker
count, compilation policy and other system activity.

This is the calibrated binomial model requested in the lab, with constant
volatility and rate; it does not model trading fees, funding, liquidity,
dividends, or time-varying volatility.
