# Assignment 1 — student implementation and results

This project compares a list-based BTC limit order book (Version A) with an indexed version (Version B). The instructor's `README.md` remains the authoritative assignment specification and has been preserved. The report is `50_Docs/FINAL_REPORT.md`; the offline interactive dashboard is `40_Results/bitcoin_order_book_dashboard.html`.

From the assignment root, using Python 3.11 or newer:

```sh
python -B -m unittest discover -s 30_Tests -p 'test_*.py' -v
python -B 20_Code/targeted_benchmark.py
python -B 20_Code/final_dashboard.py
```

The benchmark command repeats the 15 targeted workloads and creates a new timestamped results folder; it may take considerable time. It uses supplied seed-42 10,000-event streams and generates missing seed-43/44 streams with the supplied generator. The dashboard generator reads the saved run `40_Results/targeted_comparison_20261123_175037/`, plus labeled earlier controlled trials; it does not run benchmarks. Open the generated HTML directly in a browser. The HTML embeds Plotly JavaScript and requires no server or network access.

Algorithms and benchmarks use only Python's standard library. Generating the HTML requires Plotly; tested with Plotly 6.9.0. For example, install it with `python -m pip install plotly==6.9.0`. The saved targeted benchmark used Python 3.14.6 on Windows 11, AMD64, Intel64 Family 6 Model 197 Stepping 2; its `environment.json` records all benchmark source hashes and settings. The dashboard shows those hashes and labels historical measurements with their earlier source versions. Existing benchmark outputs retain raw repeats, correctness status, stopped-run records and input fingerprints.

`50_Docs/VERSION_A.md`, `VERSION_B.md`, `PHASE1_TEST_PLAN.md`, `PERFORMANCE_COMPARISON.md` and `TARGETED_COMPARISON.md` describe the design, tests, prior bounded comparison and latest measurements. The latest recorded suite passed 27 tests; the targeted run passed 15 separate comparative correctness checks. Four targeted Version A memory runs stopped, and the larger 100,000-event matrix was not fully completed within the earlier limit. No final commit identifier has been recorded; obtain it at submission time after the user handles Git.

## 100,000-event scaling experiment

Run `python -B 20_Code/scaling_experiment.py` from the assignment root to reproduce the targeted one-attempt scaling experiment. It requires the previously generated 100,000-event input files and earlier result folders; the 120-second limit applies to each attempt. The saved run is `40_Results/scaling_100000_20261124_114134/`, including actual outcomes, progress snapshots, hypothetical estimates, historical Version B references, source hashes, and the exact originally executed script. The script was subsequently corrected to calculate conservative lower bounds from observed processing timestamps; original result rows are retained as `attempts_original.csv`.

The dashboard generator now reads that saved scaling run as well as the 10,000-event comparison. Open `40_Results/bitcoin_order_book_dashboard.html` directly. The instructor's original README remains unchanged; this guide supplies the project-specific commands and current results.

