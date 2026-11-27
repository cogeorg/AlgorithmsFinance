# Class 3: American put pricing

Work in progress, taught and implemented one stage at a time. All code and
generated outputs for this lab stay in this directory. Python 3.10 or newer;
the first stage uses only the standard library.

## Step 1: price a small tree

An American put lets its holder sell one unit of the underlying asset at a
fixed strike at any exercise date. Immediate exercise is worth
`max(strike - asset_price, 0)` per unit.

`price_american_put.py` implements the Class 3 rolling-array algorithm. Its
inputs are initial asset price, strike, up factor, down factor, gross interest
factor per period, and number of periods, in that order.

For the slides' example:

| Input | Value |
| --- | --- |
| Initial asset price and strike | 100 |
| Up and down factors | 1.2 and 0.8 |
| Interest factor per period | 1.05 |
| Number of periods | 2 |
| Risk-neutral up probability `(1.05 - 0.8) / (1.2 - 0.8)` | 0.625 |

The interest factor 1.05 belongs to this teaching example. Market-data runs
will instead derive a per-period factor from the lab's 4% annual rate.

1. At expiry, the possible asset prices are `64, 96, 144`.
2. Their put payoffs are `36, 4, 0`.
3. One period earlier, at price 80, exercising gives 20 and holding gives
   about 15.2381. Keep 20.
4. At price 120, exercising gives 0 and holding gives about 1.4286. Keep 1.4286.
5. At the root, exercising gives 0 and holding gives about 7.9931972789.
   The option is therefore worth **7.9932 per unit**, rounded to four decimals.

The general rule is to compare exercise now with the risk-neutral expected
value of holding, discounted by the interest factor. The up probability is
determined by the no-arbitrage model, not estimated as the historical fraction
of rising hours.

The inner loop must visit indices in increasing order: it still needs both
successor values from the following date before overwriting the current entry.
Only one row is stored, so working memory is O(N), while visiting every node
takes O(N squared) time. The forthcoming exercise boundary also needs only
one stored threshold per date.

From the repository root, run the example and the independent checks:

```bash
python3 -B Submissions/HardiKhushi/Class3/price_american_put.py
python3 -B -m unittest discover -s Submissions/HardiKhushi/Class3 -p 'test_*.py' -v
```

The checks include the known exact answer `1175/147`, expiry-only payoffs,
zero strike, invalid model inputs and 189 small trees compared with a separate
recursive reference using exact rational arithmetic.

## Step 2: load Bitcoin prices and calibrate the tree

`market_data.py` reads the course CSV without changing it. It checks column
names, positive finite prices and strictly increasing hourly UTC timestamps.
It selects the last N+1 prices, not the last N prices. No missing hours are
filled; the report records gaps if any are present.

For every adjacent pair, calculate the log return `r[t] = log(P[t]/P[t-1])`.
The sample standard deviation `s` uses denominator N-1, not N, and remains
in hourly units for a gap-free hourly window. Then:

- `spot = strike = first selected close`: the put starts at the money.
- `up = exp(s)` and `down = 1/up`: one typical log-price move each way.
- `T = elapsed UTC seconds / (365 * 24 * 3600)`: Actual/365 Fixed convention.
- `gross_rate = exp(0.04 * T/N)`: a 4% continuously compounded annual rate.
- `q = (gross_rate - down)/(up - down)`: the risk-neutral up probability.

The slides do not specify a day-count basis, so Actual/365 Fixed is an explicit
choice. Use actual elapsed time rather than assuming every file has N hours.
For gapped files, returns span observed intervals and R uses their average
duration, following the slides' one-observation-per-step model. Such a window
is not a set of equally spaced hourly observations, and gaps must be disclosed.
Zero volatility or factors violating `0 < down < gross_rate < up` are rejected
rather than silently modified.

Run calibration only (no option pricing):

```bash
python3 -B Submissions/HardiKhushi/Class3/market_data.py
```

To save a new report, add
`--output Submissions/HardiKhushi/Class3/results/calibration_btc_1y.json`.
The tool refuses to overwrite an existing report or write outside this Class3
folder. Reports include the raw data hash, script hash, selected dates and
parameters. `--periods N` selects a different number of returns; `--full-file`
selects every available row.

The saved Bitcoin calibration selected 31 October 2025 23:00 UTC through
31 October 2026 23:00 UTC, with 8,761 prices, 8,760 periods and no missing hours.

| Parameter | Saved value |
| --- | --- |
| Initial price and strike | 109,608.01 USDT per BTC |
| Hourly log-return sample standard deviation | 0.00460739514 (about 0.4607%) |
| Up factor | 1.00461802551 |
| Down factor | 0.99540320262 |
| Hourly gross interest factor | 1.00000456622 |
| Risk-neutral up probability | 0.49934368318 |

These satisfy `down < gross_rate < up`. Both the data selection and sample
standard deviation were checked independently of the calibration function.
At the end of step 2, the suite had 15 passing test methods, including the
original 189 small pricing-tree comparisons. The pricing results below were
produced later, in step 3.

## Step 3: exercise boundary and the one-year Bitcoin put

The original price-only implementation is preserved byte for byte as
`price_american_put_original.py`. The current `price_american_put.py` still
returns a number by default. Passing `return_boundary=True` instead returns
`(price, boundary)`, with N+1 thresholds for dates 0 through N.

While updating each row, record the highest asset price where exercising has
a positive payoff and is at least as valuable as holding. A row with no such
node has boundary `None`. Exclude worthless zero-payoff ties, including at
expiry, so an out-of-the-money option does not produce an exercise signal.
At expiry the boundary is the highest in-the-money tree node, rather than an
interpolated strike. This convention follows the requested tree-node threshold.

Boundary classification uses tolerance `32 * float epsilon * max(strike, 1)`:
payoff must exceed tolerance and exercise plus tolerance must cover holding.
This handles numerical indifference without changing the calculated option
value, which always uses the actual maximum. The pricer also checks the range
of extreme tree prices before allocating arrays, rejecting trees that would
overflow or enter the subnormal range. These checks are not a proof of complete
floating-point accuracy for arbitrary inputs.

`exercise.py` compares the observed prices with their corresponding thresholds
and returns the first crossing (including expiry), or `None` for "never".
It uses the exact condition `observed_price <= boundary` without interpolation.
The payoff is `strike - observed_price` per BTC; it is not profit after paying
the initial option premium. Calibration uses the entire window, so this is a
retrospective application of the assignment rule, not a trading backtest.

Run the one-year pricing and measurement pipeline:

```bash
python3 -B Submissions/HardiKhushi/Class3/run_bitcoin.py --output Submissions/HardiKhushi/Class3/results/bitcoin_1y_python
```

The original stage-3 outputs are saved in `results/bitcoin_1y/`; the current
command above uses a new `results/bitcoin_1y_python/` directory. Existing output directories are never
replaced; to rerun, pass `--output` with a new directory inside this Class3
folder. `boundary.csv` contains every dated threshold and observed price.
`summary.csv` is the requested one-row performance/result table. JSON files
preserve calibration, timing, memory, environment and source/data/output hashes.

The runtime is one untraced `perf_counter` call, including tree construction
and the complete boundary. It excludes data loading, calibration, comparing
the observed path and writing results. A second call measures fresh peak
`tracemalloc` allocations with the inputs already loaded; working arrays and
new outputs are included. The first call's retained result is outside tracing.
Traced bytes are not process RSS or all native allocations. The second call's
value and full boundary must exactly equal the first call's output. One sample
per measurement provides no estimate of timing variability.

The completed one-year run produced:

| Result | Value |
| --- | --- |
| Periods / assets | 8,760 / 1 |
| Put value at the first date | 16,713.71420876 USDT per BTC |
| First observed boundary crossing | 2 June 2026, 14:00 UTC (t=5,127) |
| Observed price / model boundary then | 68,019.30 / 68,193.46617089 USDT per BTC |
| Gross exercise payoff | 41,588.71 USDT per BTC |
| Untraced pricing runtime | 3.695130625 seconds |
| Peak traced allocation in separate call | 739,464 bytes (722.1328125 KiB) |

All 23 test methods pass. In addition to the original checks, 189 independent
exact trees verify the full boundary policies and unchanged option values.
The complete saved boundary was checked against its lattice nodes and observed
prices. Source/data/output hashes and agreement of the two measured calls
were verified. No memory limit was reached in this run.

## Step 4: full-file Bitcoin and a NumPy rolling-row engine

`price_american_put_numpy.py` computes the same recurrence for a whole row at
once using float64 NumPy arrays. It retains a fixed number of row-sized
scratch buffers, so time remains O(N squared) and working memory O(N). It
uses the same positive-payoff, tie-tolerance and expiry-boundary conventions.
The scalar engine is unchanged. The original stage-3 runner and its three
dependencies are preserved with verified hashes under `versions/step3/`.

NumPy is required for this engine and its tests. The recorded runtime already
had NumPy 2.5.3 installed; no installation was performed. `requirements.txt`
records the dependency. No external services or data downloads are needed.

The new one-year bridge run in `results/bitcoin_1y_numpy/` has exactly the same
option value, first exercise and all 8,761 boundary CSV rows as the original
scalar run. All 26 test methods pass, including 189 additional exact-policy
and scalar comparisons for the NumPy engine. A tracing probe confirmed NumPy
data buffers are included in tracemalloc on this runtime.

Commands for these saved runs (choose a new output directory to repeat):

```bash
python3 -B Submissions/HardiKhushi/Class3/run_bitcoin.py --engine numpy --output Submissions/HardiKhushi/Class3/results/bitcoin_1y_numpy
python3 -B Submissions/HardiKhushi/Class3/run_bitcoin.py --engine numpy --full-file --output Submissions/HardiKhushi/Class3/results/bitcoin_full_numpy
```

The full file spans 1 November 2021 00:00 UTC to 31 October 2026 23:00 UTC.
It contains 43,823 prices, hence **43,822 periods**. The absent timestamp is
24 March 2023 13:00 UTC; it is not filled. Volatility therefore includes one
two-hour observed return as a single step, as disclosed by the gap policy.
Calendar coverage is approximately five years; Actual/365 Fixed gives
T=5.002625570776256 because of the leap day and the precise end timestamp.

| Full-file result | Value |
| --- | --- |
| Initial price and strike | 61,560.49 USDT per BTC |
| Sample log-return standard deviation | 0.005396058959060922 |
| Put value | 20,716.75407125 USDT per BTC |
| First observed boundary crossing | 18 June 2022, 06:00 UTC (t=5,502) |
| Observed price / boundary then | 19,439.26 / 19,823.09926476 USDT per BTC |
| Gross exercise payoff | 42,121.23 USDT per BTC |
| Untraced pricing runtime | 2.176927125 seconds |
| Separate peak traced allocation | 3,251,102 bytes (3.1004924774 MiB) |

Use `results/bitcoin_comparison.csv` to compare the three labelled runs.
The NumPy one-year and full-file calls took 0.117672125 and 2.176927125 seconds;
their allocation peaks were 658,410 and 3,251,102 bytes. The full-file case used
about 4.94 times the traced memory for about five times as many periods, which
is consistent with row-sized working storage. Both are single measurements;
the measured time ratio need not equal the asymptotic node-count ratio.

The full-file and one-year contracts start at different dates and strikes,
and use different calibrated volatility. Their price difference therefore
does not isolate the effect of expiry length. No memory limit was reached.
Saved outputs, source/data hashes, all full-file lattice thresholds and the
absence of an earlier crossing were independently checked. The bridge and
comparison-file identities are recorded in `results/bitcoin_numpy_comparison.json`.

## Remaining stages

- Price all 40 assets in one run for each horizon.
- Extend the periods/assets/runtime/peak-memory table to those larger runs.

The 40-asset numerical range/performance checks remain outstanding.
The runnable pricing file is `price_american_put.py`.
