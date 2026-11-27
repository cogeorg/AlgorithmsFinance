# Class 3 results

`calibration_btc_1y.json` records data selection and model parameters only.
It includes the source-data and calibration-script SHA-256 hashes. It does not
contain an option price, exercise boundary, runtime or peak-memory measurement.

`bitcoin_1y/` contains the first completed pricing run:

| File | Content |
| --- | --- |
| `inputs.json` | Window, model and data/calibration-source identity |
| `timing.json` | One untraced pricing call, put value and first crossing |
| `memory.json` | Separate call's traced allocation peak and agreement check |
| `boundary.csv` | All 8,761 observed prices and dated boundary entries |
| `summary.csv` | N, asset count, seconds, peak bytes, price and payoff |
| `result.json` | Complete outcome, protocol, environment and hashes |

For N=8,760 and one asset, the put value is 16,713.71420875558 USDT per BTC.
The first observed crossing is 2026-06-02 14:00 UTC, with gross payoff
41,588.71 USDT per BTC. Pricing took 3.695130624808371 seconds without tracing.
Peak traced allocation in the separate call was 739,464 bytes (722.1328125 KiB).
This measures new pricing allocations rather than total process RSS; inputs
were already loaded. A single timing and a single memory call were collected.

Preserve saved reports. The calibration CLI refuses to overwrite existing
files, and the pricing runner refuses to replace existing result directories.

Stage 4 adds two runs with the NumPy engine, retaining the original scalar
run. Each directory has the same input/timing/memory/boundary/summary/result
structure. `summary.csv` and `result.json` now also label the engine.

| Directory | N | Seconds | Peak traced bytes | Put value (USDT/BTC) |
| --- | --- | --- | --- | --- |
| `bitcoin_1y_numpy/` | 8,760 | 0.1176721251 | 658,410 | 16,713.71420876 |
| `bitcoin_full_numpy/` | 43,822 | 2.1769271251 | 3,251,102 | 20,716.75407125 |

The full-file first crossing is 2022-06-18 06:00 UTC, with gross payoff
42,121.23 USDT/BTC. One missing hour in that file was disclosed, not filled.
The one-year NumPy boundary is byte-identical to the original scalar result.
The different horizons also have different initial strikes and volatility.

`bitcoin_comparison.csv` combines all three runs with explicit engine labels.
`bitcoin_numpy_comparison.json` records bridge checks, result-file identities
and same-engine growth ratios. The four original stage-3 source files are
preserved under `../versions/step3/` and match the original result's source
hashes. Later runner edits do not rewrite historical result metadata.
