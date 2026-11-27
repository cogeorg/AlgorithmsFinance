# American put: NumPy Version B

Version A remains in `20_Code/price_american_put.py`. Version B is `20_Code/price_american_put_numpy.py`; it reuses A's validation and uses NumPy slices to calculate each complete backward-induction row, eliminating the inner Python loop. It still processes all tree nodes, uses O(N²) time and O(N) working memory, and does not build the full tree. Only the price is implemented here; the existing boundary implementation is unchanged.

On Python 3.14.6 and NumPy 2.5.5, both versions produced 7.993197278911565 for the two-period slide example and 16714.9352705545 USDT/BTC for the 8,760-period Bitcoin case: absolute difference 0, within the 0.0001 tolerance.

After one Version B warm-up, three untraced price-only runs took 1.899373, 1.092285 and 0.852214 seconds, median 1.092285 seconds. The earlier Version A measurement was a historical single run of 10.427927 seconds, yielding 9.55x when divided by the B median. This is not a matched three-repeat comparison; the variation in B's timings limits the strength of the speedup estimate. Data loading, calibration and tracing were excluded. Raw timings, parameters and code hashes are in `40_Results/numpy_btc_comparison.json`.

Requires NumPy in addition to Python. To reproduce from the lab folder, run `python -B 20_Code/benchmark_numpy.py`; it refuses to overwrite its existing results. Preserve or move the previous result before rerunning.
