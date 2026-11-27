# One-year crypto multiprocessing benchmark

Forty supplied crypto datasets were processed sequentially and using 2 and 4 Windows processes, with one sequential asset warm-up and one complete timed batch per configuration. Each timed batch includes loading, calibration, worker startup where applicable, pricing and collection. Each uses the last 8,761 available closes and the prior experiment's calibration formulas. The existing calendar-year calibration function selects a different window, so the worker applies the same previous one-year formulas directly; it reuses the existing data reader and NumPy pricer.

| Workers | Completed | Wall time | Assets/sec | Speedup versus sequential |
|---:|---:|---:|---:|---:|
| 1 | 40 | 17.011 s | 2.351 | 1.00x |
| 2 | 40 | 8.285 s | 4.828 | 2.05x |
| 4 | 40 | 5.847 s | 6.841 | 2.91x |

Prices matched the sequential batch within 0.0001 and parameters and period counts matched exactly for all 40 assets. Input hashes were unchanged. Four workers were fastest; improvement from two to four workers was smaller than the first increase, consistent with overhead and diminishing returns. The measured 2.05x speedup with two workers is a single-run observation, not proof of superlinear scaling. Only one batch per configuration was timed, so system load, scheduling, caches and NumPy's internal threading can influence these results.

The machine was an Intel Core Ultra 9 285H with 16 available logical CPUs, Windows 11, Python 3.14.6 and NumPy 2.5.5. Raw per-asset results, hashes, thread environment and summary are in `40_Results/parallel_one_year/`. To reproduce, use `python -B 20_Code/parallel_benchmark.py` from the lab folder with NumPy installed; preserve or move the existing result directory first, since the script will not overwrite it.
