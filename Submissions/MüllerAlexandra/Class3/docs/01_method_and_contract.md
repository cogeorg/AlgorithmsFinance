# Method and contract

This document records the interpretation fixed before implementation.

1. A window with `N` periods contains the last `N + 1` observations.
2. Calibration uses log returns and their sample standard deviation.
3. Elapsed years are actual UTC elapsed seconds divided by `365.25 * 24 * 3600`.
   Missing exchange hours are therefore not silently treated as observed hours.
4. The strike and initial stock price both equal the first close in the selected
   window.
5. An exercise-boundary entry is the highest node price at that date for which
   intrinsic value is positive and immediate exercise is at least as valuable as
   continuation. `NaN` records that no node meets this condition.
6. At maturity, every in-the-money node is an exercise node.
7. The first historical exercise observation is the earliest selected close at
   or below a finite boundary entry. Its payoff is `K - P_t`.
8. The production pricer must use rolling arrays. Tests compare it with a small
   full-tree oracle that uses a different data layout.
9. A measured workload includes CSV loading, calibration, pricing, and historical
   crossing detection. Seconds come from an untraced trial. Peak bytes come from
   a separate `tracemalloc` trial, following the lecturer's separation of timing
   and memory measurement. Compact outputs from both trials must agree exactly.

The 365.25-day convention is an explicit implementation choice because the lab
states that `T` is elapsed time in years but does not prescribe a day-count
convention.
