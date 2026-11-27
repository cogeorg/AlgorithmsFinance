# Class 3: American put on market data

This submission implements the Class 3 lab from pages 28-31 of the supplied
lecture deck. The lab's task list continues onto PDF page 32 because the PDF page
numbers and slide footer numbers differ by one.

## Contents

1. `src/american_put_lab/`: calibration, rolling-array pricing, boundary and
   historical-exercise analysis, measurement, and reporting.
2. `tests/`: independent small full-tree oracle and contract/edge-case tests.
3. `scripts/00_run_tests.py`: reproducible test command.
4. `scripts/01_run_lab.py`: BTC, 40-asset one-year, and 40-asset full-history
   experiments.
5. `results/01_run_summary.csv`: required `N`, asset count, seconds, and peak
   memory table.
6. `results/02_asset_results.csv`: option value and first historical exercise
   result for every asset/run.
7. `results/03_btc_one_year_boundary.csv`: the required BTC boundary at all
   8,761 dates (blank means that no exercise node exists).
8. `docs/`: contract, corrections, complexity, results, and AI-assistance record.

Course data remain in `Class3/data/hourly/` and are not copied or changed.

## Reproduce

From this submission directory, using Python 3.10 or later:

```powershell
python -m pip install -r requirements.txt
python scripts/00_run_tests.py
python scripts/01_run_lab.py --scope btc
python scripts/01_run_lab.py --scope all
```

`--scope all` performs separate timing and traced-memory trials and therefore
takes longer than the seconds reported in the table. On the recorded machine it
took roughly 18 minutes wall-clock; the measured untraced full-history workload
itself took about seven minutes.

## Required result table

| Run | N | Assets | Seconds | Peak traced MiB |
|---|---:|---:|---:|---:|
| BTC, one year | 8,760 | 1 | 0.326341 | 3.764416 |
| All supplied assets, one year | 8,760 | 40 | 15.384043 | 3.781358 |
| All supplied assets, full history | 43,822 | 40 | 421.225151 | 7.127047 |

The BTC one-year option value is `16714.9352705429`. The first historical close
at or below the computed boundary is `2026-06-02T14:00:00+00:00`, at a close of
`68019.30`; with strike `109608.01`, its payoff is `41588.71`.

See `docs/03_algorithm_and_results.md` before interpreting the timings or memory
figures.
