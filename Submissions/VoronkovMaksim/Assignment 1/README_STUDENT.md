# Assignment 1 — student submission guide

This project compares two sequential Bitcoin limit order books. Version A scans a list of resting orders; Version B uses order-ID and exact-price indexes, FIFO queues and price heaps. Both use only the Python standard library. The professor's original `README.md` contains the assignment specification.

## Quick Start / Reproduce Results

Open **PowerShell in the assignment folder** (the folder containing `20_Code` and this README). Use Python **3.11 or newer**; the recorded measurements used Python 3.14.6 on Windows 11. Run these steps in order.

### Quick verification (recommended)

1. **Set up the environment.** Creating a virtual environment is optional, but recommended. If `.venv` already exists, these commands leave it in place; if it has no Python interpreter, inspect it or choose another environment rather than overwriting it. The commands below call its Python directly, so PowerShell activation is unnecessary.

   ```powershell
   python --version
   if (-not (Test-Path -LiteralPath '.\.venv')) { python -m venv .venv }
   if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) { throw 'Existing .venv has no Python interpreter; inspect it before continuing.' }
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   To skip the virtual environment, run `python -m pip install -r requirements.txt` and use `python` in place of `.\.venv\Scripts\python.exe` in the commands below. Plotly generates the final offline dashboard; Matplotlib generates the earlier static diagnostic dashboard. The algorithms and tests need neither package. The finished HTML itself needs only a browser.

2. **Run the correctness tests** against both versions:

   ```powershell
   .\.venv\Scripts\python.exe -B -m unittest discover -s 30_Tests -p 'test_*.py' -v
   ```

   The latest recorded run passed 27 tests, including checks that instructor-provided files match `MANIFEST.json`.

3. **Replay the worked example** with each implementation:

   ```powershell
   .\.venv\Scripts\python.exe -B 20_Code\replay_orders.py --version A --input 10_Data\worked_example.jsonl
   .\.venv\Scripts\python.exe -B 20_Code\replay_orders.py --version B --input 10_Data\worked_example.jsonl
   ```

   Each line is an event result followed by the final book. The six-BTC sale fills `b1`, `b2`, `b3`, `b4` in that order for $359,400 gross; four BTC remain on `b4` and the ask is unchanged. To save a copy, add `--output replay_b.jsonl` to a command; the output file must not already exist. The CLI also accepts `.jsonl.gz`. Rejected events are reported, with exit code 1; file or decoding errors return 2.

4. **Regenerate the dashboard from the saved measurements:**

   ```powershell
   .\.venv\Scripts\python.exe -B 20_Code\final_dashboard.py
   ```

   This rebuilds `40_Results\bitcoin_order_book_dashboard.html` without running a benchmark. It reads the specific saved result folders named in `20_Code\final_dashboard.py`; it does **not** automatically select a newly generated benchmark folder. Earlier controlled trials are labeled with their earlier source versions. The script replaces the generated HTML, not the raw results.

5. **View the results:** open `40_Results\bitcoin_order_book_dashboard.html` directly in a browser and read `50_Docs\FINAL_REPORT.md`. No server or internet access is needed to view the HTML.

### Full experimental reproduction (optional)

Run the quick verification first. The commands below create **new timestamped result folders** and do not replace earlier results. Timings and memory figures vary with the machine and system load; reproduce the method rather than expecting identical times. Version A's large workloads can be very slow. Each benchmark phase or 100,000-event attempt has a 120-second limit; stopped runs are recorded, not treated as completed.

The project includes generated 1,000- and 100,000-event streams in `10_Data\full_benchmark_inputs`. If any are missing, the following optional PowerShell loop generates **only missing files** using the unchanged professor's generator, with seed 42, 43 or 44 and 1,000 available levels. It will not overwrite a stream; if its metadata file already exists without the stream, it stops for inspection.

```powershell
foreach ($scenario in @('buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn')) {
    foreach ($seed in @(42, 43, 44)) {
        foreach ($events in @(1000, 100000)) {
            $file = "10_Data\full_benchmark_inputs\${scenario}_${events}_seed${seed}.jsonl.gz"
            if (-not (Test-Path -LiteralPath $file)) {
                if (Test-Path -LiteralPath "$file.metadata.json") { throw "Metadata exists without its stream: $file" }
                .\.venv\Scripts\python.exe -B 20_Code\generate_orders.py --scenario $scenario --events $events --levels 1000 --seed $seed --out $file
                if ($LASTEXITCODE -ne 0) { throw "Generation failed: $file" }
            }
        }
    }
}
```

Run the small comparison first, then the larger experiments only if desired:

```powershell
.\.venv\Scripts\python.exe -B 20_Code\benchmark_1000_current.py
.\.venv\Scripts\python.exe -B 20_Code\targeted_benchmark.py
.\.venv\Scripts\python.exe -B 20_Code\scaling_experiment.py
```

The 1,000-event script uses the generated streams. The 10,000-event script uses the supplied seed-42 streams and generates missing seed-43/44 streams. The scaling script uses the 100,000-event streams **and the existing** `40_Results\full_comparison_20261123_171219` and `40_Results\targeted_comparison_20261123_175037` folders: it checks input fingerprints and source hashes against them. Regeneration on a different Python or compression environment may produce different compressed-file hashes; in that case use the supplied matching files or investigate the mismatch rather than bypassing the checks.

To display a new run, the dashboard generator's saved-result folder references would need to be updated deliberately and its expected CSV schema and source hashes checked. Simply rerunning a benchmark followed by the dashboard command continues to show the original saved run. The dashboard also relies on the earlier diagnostic and controlled-trial folders and the saved 100,000-event scaling folder.

## Files and limitations

- Final report: `50_Docs\FINAL_REPORT.md`; implementation notes: `50_Docs\VERSION_A.md` and `50_Docs\VERSION_B.md`.
- Current 1,000-event results: `40_Results\current_1000_20261124_151858`; 10,000-event results: `40_Results\targeted_comparison_20261123_175037`; 100,000-event single attempts: `40_Results\scaling_100000_20261124_114134`.
- Four Version A 10,000-event memory runs stopped, and full 100,000-event correctness comparison was not completed for the current code. The million-event experiment was not performed because Version A's observed scaling made it infeasible within the available time and resources; it is not mathematically impossible.
- Each result folder records input fingerprints, code hashes, environment details and stopped runs. Earlier code versions are labeled separately. The final Git commit identifier and course-repository submission check remain for the actual submission step.

### Construction scaling experiment

To reproduce the separate construction and price-concentration experiment, run from the project root:

```powershell
.\.venv\Scripts\python.exe -B 20_Code\construction_scaling.py
```

It generates deterministic passive BUY inputs outside timing, verifies both versions, and measures four order counts at concentrated and dispersed prices. It uses one warm-up, five repeats, and a 30-second limit per attempt. A new timestamped result folder is created; the saved run is `40_Results\construction_scaling_20261124_162635`. The dashboard reads that named saved run and does not automatically switch to a new folder. Version A's larger constructions may be slow.

