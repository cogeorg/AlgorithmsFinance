# Algorithm, correctness, complexity, and results

## Calibration

For the last `N + 1` closes, the code computes each log return, their sample
standard deviation `s`, then uses the required formulas

```text
u = exp(s)
d = 1 / u
R = exp(0.04 * T / N)
q = (R - d) / (u - d)
```

`T` is the actual elapsed UTC time between the first and last selected rows in
Julian years of 365.25 days. This matters because the data documentation states
that missing trading hours are omitted.

## Pricing pseudocode

```text
PRICE-AMERICAN-PUT(S0, K, u, d, R, N)
    q <- (R - d) / (u - d)
    stock[j] <- S0 * d^N * (u/d)^j for j = 0..N
    value[j] <- max(K - stock[j], 0)
    boundary[N] <- highest stock[j] with positive intrinsic value, or none

    for t <- N-1 down to 0
        for j <- 0..t
            stock[j] <- stock[j] / d
            continuation[j] <- (q*value[j+1] + (1-q)*value[j]) / R
            intrinsic[j] <- max(K - stock[j], 0)
            exercise[j] <- intrinsic[j] > 0 and intrinsic[j] >= continuation[j]
            value[j] <- max(intrinsic[j], continuation[j])
        boundary[t] <- highest stock[j] with exercise[j], or none

    return value[0], boundary
```

NumPy performs each row operation in compiled loops, but the algorithm and work
are unchanged from the lecture's rolling-array backward induction.

## Invariants and correctness argument

At the start of the iteration for date `t`, for every `j = 0..t`:

1. `stock[j] = S0 * u^j * d^(t-j)` after division by `d`.
2. Before overwriting, `value[j]` and `value[j+1]` are the two successor option
   values at date `t+1`.
3. Discounting their risk-neutral expectation therefore gives the continuation
   value at node `(t,j)`.
4. Taking the maximum of intrinsic and continuation value gives the American
   option's Snell-envelope value at that node.
5. The maximum stock price among the nodes choosing positive exercise is exactly
   the requested highest exercise-optimal tree price at that date.

The maturity initialization is correct because no continuation is possible at
date `N`. Backward induction preserves the invariants to date zero, so the
returned `value[0]` is the American put value and every boundary entry has the
stated meaning. The tests also compare the rolling implementation with a small,
independently laid-out full-tree oracle and verify the two-period value 7.9932.

## Complexity

There are `1 + 2 + ... + N = Theta(N^2)` node updates. The two numerical arrays
and returned boundary each have `N + 1` entries, so auxiliary workspace is
`Theta(N)` and output space is `Theta(N)`. Calibration and historical crossing
are `Theta(N)` time. Processing `A` assets sequentially is `Theta(A*N^2)` time
but does not multiply peak workspace by `A`, because full boundaries are not
retained for the batch after their compact result is extracted.

## Measurement protocol

- Machine run: Windows, Python 3.12.10, NumPy 2.5.5.
- A workload includes CSV loading, calibration, pricing, and crossing detection.
- Seconds are from one untraced execution using `perf_counter`.
- Peak bytes are from a separate execution using `tracemalloc`.
- Both executions must produce exactly equal compact results.
- The 40 assets are processed sequentially in sorted filename order.
- This is traced allocation peak, not whole-process resident-set size.

| Run | N | Assets | Seconds | Peak traced MiB |
|---|---:|---:|---:|---:|
| BTC one year | 8,760 | 1 | 0.326341 | 3.764416 |
| All 40 one year | 8,760 | 40 | 15.384043 | 3.781358 |
| All 40 full history | 43,822 | 40 | 421.225151 | 7.127047 |

Increasing `N` by approximately five multiplies the 40-asset time by about
27.38, close to the quadratic prediction of 25 with additional data and system
overheads. Peak traced memory rises by less than a factor of two and does not
scale with the number of assets, which is consistent with sequential processing
and linear rolling-array storage.
