# Assignment 1 entry point

Run these commands from `Submissions/SinghJoga/Assignment1/` in PowerShell.
The student quick-start is at the top of `README.md`; the original supplied
assignment specification follows it unchanged.

## Setup

Python 3.14.7 was used. Create a local environment if needed, then install the
exact pinned packages:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Replay a saved or supplied JSONL stream

Replay the supplied worked example through either implementation:

```powershell
.\.venv\Scripts\python.exe -m orderbook.replay data\worked_example.jsonl --version baseline
.\.venv\Scripts\python.exe -m orderbook.replay data\worked_example.jsonl --version revised
```

The command accepts `.jsonl` and `.jsonl.gz` inputs and prints event results,
the last accepted sequence, and the final canonical book.

## Benchmark

The all-mode smoke command exercises every experiment and measurement mode;
it is infrastructure validation, not performance evidence:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --smoke --run-id smoke_final_04
```

The documented full-matrix command uses the older 300-second timeout policy.
It is shown for reproducibility only; do not rerun it over existing evidence.
The latest continuation used the phase-level policies documented in
`docs/benchmark_protocol.md` and the saved stop manifest.

```powershell
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --resume full_20261125 --primary-time-limit-seconds 300 --latency-time-limit-seconds 300 --memory-time-limit-seconds 300 --state-peaks-time-limit-seconds 300 --counter-time-limit-seconds 60 --profile-time-limit-seconds 60 --memory-limit-mib 4096
```

The latest continuation command, with the actual per-phase budgets, was:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --resume full_20261125 --primary-time-limit-seconds 60 --latency-time-limit-seconds 30 --memory-time-limit-seconds 60 --state-peaks-time-limit-seconds 30 --counter-time-limit-seconds 30 --profile-time-limit-seconds 30 --memory-limit-mib 4096
```

That execution is already represented in the saved evidence; this command is
for reference, not a request to rerun it.

To inspect compatibility without starting workers, add `--plan-resume`.
Read `docs/benchmark_protocol.md` before running any matrix.

## Dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

The dashboard reads `results\coverage.csv` and saved result records only. It
does not execute benchmarks or import either order-book engine.
