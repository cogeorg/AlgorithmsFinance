# AI usage log (Class 3 lab)

The code, tests, measurement scripts, figure and the first draft of the README were
produced in one working session with an AI coding assistant (Claude, Anthropic, in
Claude Code). The assistant first read the Class 3 slides and the course repository and
proposed a step-by-step plan; I asked it to carry out all steps. This log records the
suggestions, the checks behind them and the decisions I am responsible for.

## 1. Accepted suggestions

| Suggestion | Why accepted |
|---|---|
| Implement `PriceAmericanPut` line by line as on slides 23-26 (two arrays, increasing `j`) and keep a separate function that also records the boundary | The plain version can be compared with the slides directly; the boundary needs only one extra array of N + 1 entries |
| Exact rational tests (`Fraction`): slide tree = 1175/147 = 7.9932, European 6.2925, one-period replication 150/21 = 7.14 | Removes floating-point doubt from the worked examples |
| Two independent oracles for small N: a recursive one that walks all 2^N paths and a full-tree one that stores every node and reads off the boundary | Agreement with the rolling-array code is then evidence, not self-consistency |
| A NumPy engine that vectorises the loop over `j` but performs the same operations per node in the same order | The tests show bit-identical values and boundaries, so the fast engine can be used for the 40-asset runs without changing any result |
| Each measured run in a fresh process; time and traced memory in separate runs; max RSS recorded in every run | Same protocol as `Class3/class3_evidence.py`; tracemalloc slows pure Python about 19-fold (measured 18.7 × and 19.5 ×), so it must not be in the timed run |
| Full-tree memory experiment with extrapolation to the lab sizes | Shows concretely when memory would bind (the lab's heading) and why the two-array design avoids it |

## 2. Findings during the session

* All 40 files miss the same hour, 24 March 2023 13:00 UTC, so the full file has
  43,823 closes (N = 43,822) and the five-year T is 43,823 hours, not 43,822.
* The hourly volatility makes s·N at most 541 (SNX, five years), below ln(10^308) ≈ 709, so
  computing S0·d^N by repeated multiplication (slide line 4) does not underflow on this data.
* Under tracemalloc the pure-Python engine runs about 19 times slower (58.8 s instead of 3.1 s for Bitcoin over one year). The traced run of
  python / 40 assets / five years (about 17 hours) was therefore not made; see the README.
* Floating-point artefact, found while checking the five-year Bitcoin boundary: the middle
  expiry node (exactly S0 = K in theory) comes out as K − 2.6·10⁻⁸ after 43,822
  multiplications and divisions, so the boundary at t = N is ≈ K instead of S0·d². It does
  not change the value (< 10⁻⁸) or any exercise date. It is documented in the README rather
  than fixed, because the measured runs had already used this code; a payoff tolerance
  would remove it.

## 3. Decisions (mine to confirm)

1. Year length for T: 365 days = 8,760 hours (the slides call N = 8,760 one year).
2. Exercise is optimal at a node when the payoff is strictly positive and at least the
   continuation value; ties count as exercise.
3. Task 3 compares the observed close P_t with the boundary of the tree calibrated at date 0.
4. The 40 assets are the 40 files in `Class3/data/hourly/`; the S&P 500 (downloaded
   separately, about three years of New York trading hours) is not part of the runs.
5. Both engines are reported; the pure-Python run is the reference implementation.
