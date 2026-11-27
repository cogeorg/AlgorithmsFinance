# Class 3 lab: PriceAmericanPut on market data

Jiaxin Huang. An American put on a recombining binomial tree (Cox, Ross and Rubinstein
1979), priced by backward induction (dynamic programming) on hourly closes from
`Class3/data/hourly/`, for Bitcoin and for all 40 assets, over one and five years.
Results and discussion: [`REPORT.md`](REPORT.md).

The work follows the five steps from Class 1, one commit each: (1) set up, (2) data and
calibration, (3) tests first, (4) implementation, (5) measurements and documentation.
See `git log -- Submissions/HuangJiaxin/Class3`.

## Run (from the repository root)

Measured with Python 3.14.7 on macOS (Apple Silicon); `requirements.txt` pins the
versions used. A virtual environment outside the repository keeps things clean:
`python3 -m venv ~/venv-aif && source ~/venv-aif/bin/activate`.

```bash
python3 -m pip install -r Submissions/HuangJiaxin/Class3/requirements.txt
python3 -m pytest -q Submissions/HuangJiaxin/Class3            # expected: 166 passed
python3 Submissions/HuangJiaxin/Class3/run_lab.py --quick       # small check, seconds
python3 Submissions/HuangJiaxin/Class3/run_lab.py               # all tasks, about 13 minutes on my MacBook Air
python3 Submissions/HuangJiaxin/Class3/plot_btc.py              # figures from saved results
python3 Submissions/HuangJiaxin/Class3/profile_put.py           # cProfile, one Bitcoin year
streamlit run Submissions/HuangJiaxin/Class3/dashboard.py       # dashboard from saved results
```

`run_lab.py` overwrites `results/`. The figures are drawn from the saved CSV files only.

## Files

| File | Content |
|---|---|
| `data.py` | Reads `Class3/data/hourly/<SYMBOL>.csv`; window of the last N + 1 closes; calibration |
| `put.py` | `price_plain` (slide pseudocode, two arrays), `price_numpy` (two arrays, vectorized per date), `price_full_tree` (every node stored, for the memory comparison), `first_exercise` |
| `test_put.py` | 166 tests, including an exact independent reference (fractions, recursion) and my hand trace |
| `TRACE.md` | My hand trace of a three-period tree (value 23.2, boundary none, 50, 25, 50) |
| `PREDICTIONS.md` | My predictions, committed before the full measurements |
| `run_lab.py` | Runs the six lab tasks and the extras; writes `results/` |
| `plot_btc.py` | Extra 5: Bitcoin price path with the early-exercise boundary |
| `profile_put.py` | cProfile of the plain and numpy versions (shares of time only) |
| `dashboard.py` | Streamlit dashboard (extra): overview, runtime, memory, Bitcoin boundary, all 40 assets, predictions vs results, correctness; reads `results/` only |
| `evidence/` | Test output before (step 3, on stubs, 159 failed) and after (step 4, 163 passed) the implementation; `final_tests.txt`: 166 passed after adding my hand trace as a test |
| `results/` | Raw measurements (CSV), figures, profiles, `environment.json`, `run_log.txt` |
| `REPORT.md` | Short report: method, correctness, results table, predictions vs results, limitations, use of AI |

## Data and calibration (`data.py`)

* Input: `Class3/data/hourly/<SYMBOL>.csv` (40 assets, 1 Nov 2021 to 31 Oct 2026, UTC).
  Every file has 43,823 rows: the hour 2023-03-24 13:00 UTC is missing. Rows are
  counted, never assumed.
* Window: the last N + 1 closes. "One year" is N = 8,760 periods (the last year has no
  gap, so it spans exactly 8,760 hours); "five years" is the whole file, N = 43,822
  periods over 43,823 hours.
* One tree period = one row step. T (for the interest rate) comes from the timestamps,
  in 365.25-day years. For the five-year window the tree therefore has one period fewer
  than the hours it spans; the effect on R is negligible.
* s = sample standard deviation of the hourly log returns (divides by N − 1);
  u = e^s, d = 1/u, R = e^(0.04 T / N), q = (R − d)/(u − d); `calibrate` checks d < R < u.
* Contract: American put, S0 = K = P_0 (at the money), exercisable at hours 0..N.

## Definitions used in the results

* **Exercise rule** (all versions and the reference): exercise at node (t, j) if the
  payoff K − S is positive and at least the continuation value.
* **Early-exercise boundary** b_t: the highest tree price at date t where exercising is
  optimal; empty if there is none. At expiry, b_N is the highest tree price below K.
* **First exercise** (task 3): the first t ≥ 1 with P_t ≤ b_t and K − P_t > 0; the
  payoff is K − P_t in USDT per unit. t = 0 is excluded because K = P_0 pays nothing.
* **Early-exercise premium** (extra 1): American value − European value on the same tree.
* **seconds**: `time.perf_counter`, pricing only (reading the CSV files is timed
  separately and noted); single-asset numpy runs: one warm-up and three repeats, every
  repeat saved; plain Python and the 40-asset runs: timed once.
* **peak_traced_bytes**: `tracemalloc` in a separate run: allocations made during the
  call (numpy buffers and Python objects), not the input already in memory, the
  interpreter or the native stack.
* Units: prices in USDT (Tether, tracks the US dollar) per unit of the asset.

## Where the results come from

* Timing and memory (`run_lab.py`): my MacBook Air, Python 3.14.7, numpy 2.5.5, code
  `2f6683c`, 27 November 2026 (`results/environment.json`, `results/run_log.txt`).
* Figures (`plot_btc.py`) and profiles (`profile_put.py`) were produced from the saved
  results in the Linux environment on the same laptop (Python 3.10, numpy 2.2.6). The
  figures only read CSV files; the profiles are used for shares of time only.
* Datasets are not copied: they are the course files in `Class3/data/hourly/`.
