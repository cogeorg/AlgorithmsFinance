# Class 3: American Put on Market Data

This submission completes the Class 3 lab with strict positive-price validation,
an independent Python reference, an equivalent compiled `O(N)`-memory kernel,
Bitcoin exercise boundaries, and process-parallel pricing of all 40 tracked
assets.

Start with [the evidence dashboard](results/dashboard.html) for the complete
interactive overview, or [REPORT.md](REPORT.md) for the required table, all
values, raw timing repeats, memory definitions, optimization evidence,
assumptions, and exercise decisions. [CONTRACT.md](CONTRACT.md) freezes the public behavior;
[AUDIT.md](AUDIT.md) records the supplied-code and data review.

## Final required results

| Scenario | N | Assets | Workers | Median seconds | Peak RSS MiB |
|---|---:|---:|---:|---:|---:|
| Bitcoin, one year | 8,760 | 1 | 1 | 0.077180792 | 56.781 |
| Bitcoin, full history | 43,822 | 1 | 1 | 1.851040000 | 55.953 |
| All assets, one year | 8,760 | 40 | 8 | 0.592842459 | 287.125 |
| All assets, full history | 43,822 | 40 | 8 | 14.370036291 | 282.250 |

Bitcoin values are `16,713.714208766745` for one year and
`20,716.754071288182` for full history. The first observed boundary crossings
are 2 June 2026 14:00 UTC and 18 June 2022 06:00 UTC respectively.

## Design

- `american_put.py`: readable one-vector Python reference.
- `american_put_kernel.c` and `compiled_backend.py`: identical recurrence using
  one contiguous double vector; compiled library is reproducibly built in the
  system temporary directory and never committed.
- `market_data.py`: strict UTC CSV parsing, positive finite prices, gap reporting,
  window selection, and calibration.
- `batch.py`: deterministic `spawn` process pool; one independent asset per task.
- `run_bitcoin.py`: Bitcoin value, complete boundary, exercise decision, five
  timing repeats, and separate peak-RSS run.
- `run_all_assets.py`: 40-asset values, five batch repeats, and separate process-
  tree memory measurement.
- `pilot_workers.py`: exact 1/2/4/8-worker comparison and worker selection.
- `build_report.py`: saved-results-only deterministic report and tables.
- `dashboard.py`: deterministic standalone HTML built only from saved JSON/CSV
  evidence, with explicit completed, missing, and stopped states.

The compiled backend improved the measured eight-worker one-year pilot from
`40.770566 s` to `0.618899 s` (`65.88x`) while reducing persistent pricing
workspace to one `double[N+1]` vector. The Python version remains the independent
production reference used in equivalence tests.

## Reproduce

Requirements: Python 3.9 or later, a C11 compiler available as `cc`, and
`psutil` from `requirements.txt`.

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 run_bitcoin.py --window one_year
python3 run_bitcoin.py --window full
python3 pilot_workers.py
python3 run_all_assets.py --window one_year --workers 8
python3 run_all_assets.py --window full --workers 8
python3 dashboard.py
python3 dashboard.py --check
python3 build_report.py
python3 build_report.py --check
```

Canonical JSON, complete Bitcoin boundaries, raw pilot records, combined values,
summary table, test baselines, and checksums are under `results/`. No S&P 500
file is required for the stated 40-asset runs, and no generated shared library
is stored in the repository.
