# Class 3 — American put pricing lab

This project prices American puts using the class binomial tree. Version A uses Python loops; Version B vectorizes each tree row with NumPy. It includes the required one-year and full-history Bitcoin boundaries and the 40-asset experiments.

- [Final report](50_Docs/FINAL_REPORT.md) · [Required results table](50_Docs/REQUIRED_RESULTS.md)
- [Interactive offline dashboard](40_Results/class3_dashboard.html) · [Results CSV](40_Results/required_results.csv)
- [CPU scaling](40_Results/cpu_scaling_one_year/summary.csv) · [One-year crypto](40_Results/one_year_crypto.csv) · [Five-year crypto](40_Results/five_year_assets/results.csv)

## Quick start — Windows PowerShell

From this project folder, use Python 3.11 or newer. The recorded environment was Python 3.14.6, NumPy 2.5.5, psutil 7.2.2 and Plotly 6.9.0. A virtual environment is recommended; if `.venv` already exists, use it rather than overwriting it.

```powershell
if (-not (Test-Path -LiteralPath '.\.venv')) { python -m venv .venv }
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) { throw 'Existing .venv has no Python interpreter.' }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = (Resolve-Path .\20_Code).Path
.\.venv\Scripts\python.exe -B -m unittest discover -s 30_Tests -p 'test_*.py' -v
```

Version A itself uses only the standard library. NumPy supports Version B, psutil measures RSS, Matplotlib supports the optional CPU figure, and Plotly generates the self-contained dashboard. The finished dashboard opens offline in a browser.

## Instructor data

Scripts expect the 40 instructor CSVs in `00_Instructor/Class3/data/hourly/`. They come from `Class3/data/hourly/` in the course repository. In a checkout where this project is at `Submissions/VoronkovMaksim/Class3`, copy the data for local use:

```powershell
New-Item -ItemType Directory -Force .\00_Instructor\Class3\data\hourly | Out-Null
Copy-Item ..\..\..\Class3\data\hourly\*USDT.csv .\00_Instructor\Class3\data\hourly\
```

Keep the original data unchanged. The full-history files have one missing hourly observation; no data is filled. Consecutive available closes are mapped to consecutive model steps, with actual elapsed time used for T. This approximates an hourly tree through the gap.

## Regenerate the dashboard from saved results

With the 40 source files in place and dependencies installed, no benchmark is needed. Supply an output path that does not exist:

```powershell
.\.venv\Scripts\python.exe -B 20_Code\build_dashboard.py . 40_Results\class3_dashboard_rebuilt.html
```

The generator reads `one_year_crypto.csv`, the five-year results, CPU-scaling summary, BTC boundary and source BTC prices, and the saved RSS and benchmark JSON files. It refuses to overwrite an existing HTML file. Opening the saved dashboard itself does not require Python or internet access.

## Reproduce experiments (optional)

Commands below run from the project folder. Scripts refuse to overwrite their existing output files or directories; preserve the saved evidence elsewhere before repeating a corresponding run. Full-history processing and the historical Version A memory trace can be slow. Timings and memory depend on the machine.

```powershell
# One-year BTC price and boundary, Version A; includes a slow Python allocation trace
.\.venv\Scripts\python.exe -B 20_Code\btc_last_year.py 00_Instructor\Class3\data\hourly\BTCUSDT.csv

# Small-tree and one-year boundary checks, then complete BTC full-history boundary
.\.venv\Scripts\python.exe -B 20_Code\full_boundary.py

# 40-asset one-year and full-history pricing
.\.venv\Scripts\python.exe -B 20_Code\one_year_assets.py 00_Instructor\Class3\data\hourly
.\.venv\Scripts\python.exe -B 20_Code\export_one_year_crypto.py
.\.venv\Scripts\python.exe -B 20_Code\five_year_assets.py

# Four Version B RSS measurements, then consolidate them
.\.venv\Scripts\python.exe -B 20_Code\rss_compliance.py
.\.venv\Scripts\python.exe -B 20_Code\consolidate_compliance.py
```

The full-boundary script uses the saved `bitcoin_full_history.json` calibration and price and compares with the saved one-year boundary. RSS measurement uses the saved BTC and 40-asset pricing results as checks. For a fresh rerun, preserve the corresponding old outputs before executing each command, and restore or regenerate the prerequisite saved files where needed. To reproduce CPU scaling separately, run `python -B 20_Code/cpu_scaling.py` after preserving its existing result folder.

RSS is a sampled sum of the workload process and descendants. It includes startup and input loading, excludes the monitor, can miss short peaks and may count shared pages more than once. Single-BTC runtimes cover pricing only; batch runtimes include loading, calibration, process startup and collection. Historical Python-traced allocations are not RSS. See the [results table](50_Docs/REQUIRED_RESULTS.md).

## Public-submission scope

Submit the crypto-only `40_Results/one_year_crypto.csv` and required results, dashboard, code, tests and documentation. **Exclude the locally downloaded S&P 500 file and S&P-derived material**, including `40_Results/sp500_*`, `40_Results/one_year_assets.csv` and `40_Results/one_year_assets_metadata.json` from the current private workspace, plus `50_Docs/CALIBRATION.md`, `50_Docs/PRICING_BASELINE.md`, `50_Docs/EXERCISE_ANALYSIS.md` and `20_Code/run_sp500_pricing.py`. The generic `exercise_analysis.py` supplies the BTC boundary code and is needed. The instructor's datasets already exist in the course repository; avoid committing duplicate local copies in `00_Instructor`.
