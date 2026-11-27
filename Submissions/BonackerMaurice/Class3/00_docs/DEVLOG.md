# Development log (Class 3)

## 2026-11-27: tests before the implementation

1. Wrote `01_code/tests/test_pricer.py` and `01_code/tests/test_market.py` first.
   They cover:
   - the slide tree (S0 = K = 100, u = 1.2, d = 0.8, R = 1.05, N = 2): value 7.9932,
     q = 0.625, the intermediate S, c and V of slides 24–26, the boundary
     [None, 80, 96], and the European value 6.2925
   - 40 random small trees against an independent brute-force recursion
   - vectorised and full tree equal to the reference bit for bit
   - no-arbitrage bounds, N = 0, the d < R < u check, and the float-range guard
   - loading, windows, calibration with missing hours, and the exercise check
2. Created stub modules whose functions raise `NotImplementedError`, so that the
   tests import cleanly and fail on behaviour. Result before any implementation:

   ```text
   python -m pytest -q
   203 failed in 2.51s
   ```

3. Implemented `american_put/common.py`, `reference.py`, `vectorised.py` and
   `fulltree.py`. The pricer tests then passed (191 passed). Next came
   `market/data.py`, and then all 203 passed.
4. Hand check of the slide tree: q = (1.05 − 0.8)/(1.2 − 0.8) = 0.625.
   - At t = 2: S = (64, 96, 144) and V = (36, 4, 0).
   - At t = 1, node 80: c = (0.625·4 + 0.375·36)/1.05 = 15.238 < 20, so the
     holder exercises and V = 20.
   - At t = 1, node 120: c = (0.375·4)/1.05 = 1.4286 > 0, so V = 1.4286.
   - At t = 0: c = (0.625·1.4286 + 0.375·20)/1.05 = 7.9932.

   All three pricers return this value.

## 2026-11-27: measurement findings

- The pure-Python reference runs about 18× slower under `tracemalloc`: 166 s
  instead of 9 s at N = 8,760, because every float object is traced. Seconds
  are therefore always measured without tracing. Traced memory is a second,
  identical call, and for the reference it is measured only up to N = 5,000.
  Above that, the psutil process peak is used.
- First quick run: free RAM was 3.2 GB (another program was using about 10 GB).
  When the full run started, Maurice reported about 20 GB free, which psutil
  confirmed (19.2 GB). At 20 GB the full tree fits at N = 43,822 (7.7 GB), so
  the curve continues past the data length (N = 55,000 and 70,000, using the
  BTC five-year u, d and R) to show where it no longer fits. Free RAM is
  recorded in `environment.json` at the start, before every full-tree attempt,
  and at the end.
