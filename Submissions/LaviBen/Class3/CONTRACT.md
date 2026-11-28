# Frozen contract: Bitcoin stage

## Core model

`price_american_put(spot, strike, up, down, gross_rate, steps)` returns the
date-zero American put value as a finite nonnegative `float`.

`price_american_put_with_boundary(...)` returns a `PricingResult` containing:

- `value`: the same date-zero value;
- `boundary`: a tuple of length `steps + 1`; entry `t` is the highest strictly
  positive tree price at which immediate exercise has positive intrinsic value
  and is at least as valuable as continuation, or `None`;
- `node_updates`: the number of rollback nodes evaluated, excluding expiry.

Inputs are not mutated. `bool` is not accepted as an integer or real input.
All numeric inputs must be finite. Require:

- `spot > 0`;
- `strike >= 0`;
- integer `steps >= 0`;
- `0 < down < gross_rate < up`.

Invalid inputs are rejected before allocating the rolling vector. The optimized
algorithm uses one rolling value vector and scalar stock prices: exact
`O(steps^2)` time and `O(steps)` memory. It never stores the full tree.

At expiry the boundary is the highest lattice price with positive put payoff.
Before expiry equality between positive intrinsic and continuation counts as
exercise. A zero-payoff `0 == 0` tie does not count as an exercise boundary.

## Market data

CSV input has exactly the columns `timestamp_utc,close`. Timestamps are UTC,
unique, strictly increasing, and aligned to whole hours. Closes must be finite
and strictly positive. Missing whole hours are reported and never filled.

The one-year window is the last 8,761 observations, giving 8,760 periods. For
prices `P0, ..., PN`:

- `S0 = K = P0`;
- returns are `log(Pt / P(t-1))`;
- `s` is their sample standard deviation;
- `u = exp(s)` and `d = 1/u`;
- `T` is endpoint elapsed time in 365-day years;
- `R = exp(0.04 * T / N)`;
- `q = (R - d) / (u - d)` and must satisfy `0 < q < 1`.

A zero-volatility window is rejected because it cannot satisfy the specified
binomial no-arbitrage contract.

## Observed exercise decision

Compare each observed close with the boundary at the same row. Return the first
index and UTC timestamp where a boundary exists and `close <= boundary`, with
payoff `strike - close`. If none exists, return `never` with payoff zero.

## Measurement

Parsing, validation, and calibration occur outside pricing timing. Timing uses
`time.perf_counter`, a warm-up, five fresh raw repeats, and the median. Required
boundary construction is inside timing; cleanup and serialization are outside.

Peak memory is measured in a separate fresh child process by sampling resident
set size while the result remains alive. The saved result records child peak,
parent-plus-child aggregate peak, sampling interval, units, environment, data
checksum, raw repeats, and Git metadata.

## Multi-asset batch stage

All 40 tracked CSV files are validated and calibrated before pricing starts. A
batch job contains only immutable scalar model parameters; observed histories
are not copied to workers. One asset is one process task. Workers never write
files, and the parent returns results sorted by symbol.

`run_batch_once(jobs, workers)` uses the `spawn` process context, warms every
worker outside timing, includes only required pricing and result construction in
its batch wall time, and returns worker PIDs as parallelism evidence. Worker
count is a positive integer no greater than the number of jobs.

The one-year batch uses the last 8,761 observations of every asset. The full
batch uses every observation, so the supplied files have 43,822 periods. Batch
pricing returns values only; boundaries are retained only for the two Bitcoin
runs. Sequential and multi-process values must agree exactly after sorting.

The readable Python rolling kernel is the independent production reference.
Because the worker pilot established that its exact full-history workload is
too slow for rigorous repeated 40-asset measurements, canonical pricing may use
the same recurrence in a compiled C kernel. That kernel must use one contiguous
`double[steps+1]` value vector, return boundary indices rather than a tree, pass
the complete Python contract suite, and agree with the Python reference within
`1e-9` relative error. Compilation and warm-up stay outside timing.

## Dashboard

`dashboard.py` builds `results/dashboard.html` exclusively from saved JSON and
CSV evidence. It performs no pricing, calibration, timing, or network access.
The single-file dashboard embeds its CSS, JavaScript, and data; uses no CDN; and
must be byte-stable on rebuild.

It exposes all four run statuses, N, asset/worker counts, units, every raw timing
repeat, median time, aggregate peak RSS and its definition, all 40 values,
Bitcoin exercise summaries and boundary charts, worker pilots, data integrity,
source/environment/compiler metadata, and links to the exact boundary/value
CSVs. Expected scenarios remain visible as `missing` or `stopped` instead of
being silently omitted.
