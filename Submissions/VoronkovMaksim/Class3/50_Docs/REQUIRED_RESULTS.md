# Required results — Version B

| Workload | Implementation | Periods per asset | Assets | Workers | Runtime (s) | Peak aggregate RSS (MiB) | Status |
|---|---|---:|---:|---:|---:|---:|---|
| BTC one year | NumPy B | 8760 | 1 | 1 | 0.312 | 42.26 | completed |
| BTC full history | NumPy B | 43822 | 1 | 1 | 10.472 | 43.92 | completed |
| 40 assets one year | NumPy B | 8760 | 40 | 8 | 4.044 | 408.03 | completed |
| 40 assets five years | NumPy B | 43822 | 40 | 8 | 72.223 | 440.91 | completed |

These measurements are separate Version B reruns for RSS evidence. BTC runtimes time pricing only; batch runtimes include loading, calibration, process startup, pricing and collection. RSS is the maximum sampled sum of the child workload process and all descendants, including startup and data loading, sampled approximately every 50 ms. It excludes the monitoring process, can miss short peaks and can count shared pages more than once. Single-process and multi-process sums are not comparable as unique physical memory.

Historical Version A one-year peak traced allocation was 458,832 bytes; full-history tracing was terminated without a peak. Python-traced allocations and process RSS measure different things and must not be compared as equivalent. Full-history inputs have one missing hourly observation, retained as a two-hour gap between consecutive available closes.
