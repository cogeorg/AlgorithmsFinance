# Assignment 1, limit order book: Laurin Bühler

## Start here (two minutes)

Requires Python 3.11 or newer (reference runs on 3.13; core tests and dashboard
also checked on 3.11, 3.12 and 3.14). Git is required for official long
measurements; the results dashboard and 1k smoke also work without a checkout.
From Assignment1:

```powershell
.\run_all.ps1                 # Windows PowerShell
```
```bash
bash run_all.sh                # macOS/Linux
```

If PowerShell blocks the script: `powershell -ExecutionPolicy Bypass -File .\run_all.ps1`.

**Results only (1 minute).** With Python 3.11+ and your environment active:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run 04_dashboard/app.py
```

Read Final selection → Overview → Bottleneck explained. Grade A against
B (= B3r); B1–B3 are measured candidates and B3r_fast is a rejected optimisation.

The run-all command creates `.venv` and installs pinned packages if absent; prints **1,040 passed**
(about 13 minutes here), worked-example **OK**, then **1k smoke OK** (a few
minutes, outputs under `scratch/`). Stops at the first error with **FAIL**;
otherwise opens localhost:8501. Terminal-only: `.\run_all.ps1 -NoDashboard` /
`bash run_all.sh --no-dashboard`. Long runs are excluded by default.

**Final B is B3r**, selected in [FINAL_SELECTION.md](00_docs/FINAL_SELECTION.md).
Report section 6: at 10k, B3r is **21–186x faster** on non-churn workloads;
at 100k the seed-median A/B3r ratios exceed **1,295x / 1,299x / 1,260x** on
buildup/crowded/sweep (A stopped at 600 s), and are **299x** on mixed.
**A wins cancel_churn** (ratios about 0.7–0.8). B3r's 1M replays take about
5–7 s; stopped A cells are bounds. B3r_fast is faster but was rejected by the
binding pre-registered rule. Sources and qualifications: [REPORT §6](00_docs/REPORT.md#6-runtime).

Individual setup: `python -m venv .venv` (macOS/Linux: `python3 -m venv .venv`),
then activate with `.\.venv\Scripts\Activate.ps1` / `source .venv/bin/activate`.

```text
python -m pip install -r requirements.txt
# Expected: pinned packages installed/already satisfied; hypothesis 6.155.7.
python -m pytest -q --basetemp=scratch/pytest-manual
# Expected: 1040 passed.
python -m run lob.replay 06_data/supplied/worked_example.jsonl --version B
# Expected: six JSON result lines; final B = B3r. A: use --version A.
python -m streamlit run 04_dashboard/app.py
# Expected: saved-results dashboard at localhost:8501 (no measurements).
python -m submission_tools data
# Regenerate the large catalog; verify content hashes, print archive SHA-256.
python -m submission_tools data --verify-only
# Expected: all recorded content hashes verified; gzip differences explicitly labelled.
```

To save/compare manually, create `scratch/`, then in PowerShell:
```powershell
python -m run lob.replay 06_data/supplied/worked_example.jsonl --version B | Set-Content -Encoding UTF8 scratch/worked_actual.jsonl
python -m submission_tools check-worked scratch/worked_actual.jsonl  # OK
```
In bash use `> scratch/worked_actual.jsonl` instead of `| Set-Content ...`.

Generator commands/checksums: [DATA_MANIFEST.json](00_docs/DATA_MANIFEST.json)
and [POST_ATTACK_MANIFEST.json](00_docs/POST_ATTACK_MANIFEST.json). Regeneration
uses those commands, writes ignored inputs/local manifests and reports gzip
differences across zlib versions. Committed manifests stay unchanged.

Long reproduction: `.\run_all.ps1 -Full` / `bash run_all.sh --full`.
Prints **about 7 h; allow 6–10 h** here (estimate from saved worker times),
requires `RUN FULL`, then runs the candidate/final-B grid and scoped A baseline.
A: single trials at 100k/1M, supplementary parts through 10k; B: warm-up + five.
Commit source first. Scripts show every command; new sessions preserve old
results. The binding fast decision is not repeated.

Folder map: `01_code/` engines, generators and benchmark runner; `02_tests/`
correctness; `03_results/runs/` committed measurements; `04_dashboard/` saved-file
views; `00_docs/` spec/report/selection/logs; `05_evidence/` verification;
`06_data/supplied/` fixtures, `06_data/generated/` ignored large inputs;
`07_attack/` independent attacks; `scratch/` local checks and smoke output.

Submitted commit: the head of branch `assignment1` in this pull request. Full
acceptance (1,040 tests, 1k smoke, no-git dashboard) ran on Windows and Linux at
`7e56958`/`859e89e`; later commits change README text only.

## Detailed reference

This section describes the current submission. Dated checkpoint counts and
superseded plans are retained in [AI_LOG.md](00_docs/AI_LOG.md), rather than
presented as current instructions here.

## Final Version B

**B = B3r**, `OrderBookB3r`; replay defaults to it. Use `--version A` for the
baseline. Explicit `B1`, `B2`, `B3`, `B3r` and `B3r_fast` remain available.
Historical saved labels `B` meant B1 at those recorded commits. The final
decision and its literal-filter qualification are in
[FINAL_SELECTION.md](00_docs/FINAL_SELECTION.md).

```powershell
python -m run lob.replay 06_data/supplied/worked_example.jsonl --version A
python -m run lob.replay 06_data/supplied/worked_example.jsonl --version B
```

`run.py` adds `01_code/` to the import path; `pytest.ini` adds the test paths.
No package installation step is needed for the engine itself.

## Dashboard: nine tabs

Final selection; Overview; Scaling; Original vs revised & variants;
Throughput & latency; Memory; Correctness; Bottleneck explained; Method & data.
It reads saved files only. In a checkout, it prefers committed blobs; without
Git or a checkout it uses allowlisted disk files and prominently warns that
values are not commit-verified. It never starts a benchmark.

```powershell
python -m pytest -q 02_tests/test_dashboard.py
python -m pytest -q 02_tests/test_checkout_portability.py
```

The first tab shows both primary-session and binding same-session comparisons.
Every plot explains its units and reading convention. Method & data exposes
raw repeats, warm-ups, provenance and stopped/not-run coverage. Audit trail:
[clarity audit](05_evidence/clarity-audit.json),
[selection verification](05_evidence/selection-primary-verification.json),
and [current fix verification](00_docs/FINAL_FIX_VERIFICATION.md).

## Environment

- Windows 11, Python 3.13.15; requirements are pinned in `requirements.txt`.
- Use modules (`python -m pytest`, `python -m pip`, `python -m streamlit`):
  Windows Smart App Control can block standalone tool launchers.
- `hypothesis==6.155.7` is deliberate: newer native modules were blocked on the
  author's machine. The matching engine and generators use the standard library.
- If `python` resolves to a disabled Store alias, activate the Python 3.11+
  environment or put that installed interpreter on PATH before starting.
- Windows path limit: if `pip install` or `test_checkout_portability` fails with
  `No such file or directory`, Windows long paths are off (260 characters).
  Enable them once in an administrator PowerShell, then reopen the shell:
  `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force`.
  Extracting/cloning to a short folder (e.g. `C:\aif`) also helps.
- Streamlit normally opens port 8501; if occupied, use its printed URL or
  `python -m streamlit run 04_dashboard/app.py --server.port=8502`.

## Expected output (worked example)

Replay prints one JSON result per input event. The first five limits return
`resting` with no fills and their full quantities as `unfilled_qty_units`.
The sixth result is:

```json
{"event_id": "event6", "order_id": "s1", "status": "filled", "unfilled_qty_units": 0, "fills": [{"maker_id": "b1", "taker_id": "s1", "price_ticks": 6000000, "qty_units": 100000000}, {"maker_id": "b2", "taker_id": "s1", "price_ticks": 6000000, "qty_units": 100000000}, {"maker_id": "b3", "taker_id": "s1", "price_ticks": 5990000, "qty_units": 300000000}, {"maker_id": "b4", "taker_id": "s1", "price_ticks": 5970000, "qty_units": 100000000}]}
```

Final book (via `snapshot()`, not printed as an extra replay line): b4 retains
400000000 units at 5970000 ticks, arrival_seq 4; a1 retains 200000000 units at
6010000 ticks, arrival_seq 5. Integer gross proceeds = 3594000000000000 tick-units
= 359400.00 USD. Hand trace: `00_docs/TRACE.md`.

Replay also accepts `.jsonl.gz` and every name in the Final Version B table. Events stream in file order; the shared validator rejects
nonincreasing seq without advancing the last accepted seq. Each book starts empty;
neither inputs nor result history are retained by the replay command.

Malformed JSON, invalid UTF-8, UTF-16 and an unexpected additional BOM stop
replay with one stderr line, `<file>:<line>: <problem>`, and a non-zero exit
code. There is no traceback for these input errors. Line numbers include blank
lines; results from earlier valid lines remain on stdout. Valid JSON events
still use the unchanged validator and may produce normal JSON rejections.
One leading UTF-8 BOM, CRLF/bare-CR newlines, gzip and unbounded integers remain
supported. A BOM character inside a JSON string is ordinary data.

## Measurement definitions and saved results

One untimed warm-up and five measured repeats for B variants; medians are
computed only from complete successful cells. Events are generated and parsed
outside engine timing, with a fresh book for every replay. Parsing,
construction, replay and total are separate phases; a fixed-book sale includes
matching, updates and result construction, with its construction reported
separately. Counter, tracemalloc and latency instrumentation use separate runs.

A's declared deviation is single trials without warm-up at 100k/1M and a 10k
ceiling for supplementary scenarios. The replay limit is 600 s and the traced
peak limit 4 GiB. Stopped A cells yield lower bounds, never measured times.
Throughput is replayed events / replay seconds; service-time latency uses
nearest-rank p50/p95/p99 by event type and early/late segment. It excludes
queueing and network delay. Memory includes the live book/current result,
excludes pre-parsed inputs and retained history, and is not process RSS.

| Saved session under `03_results/runs/` | Role |
|---|---|
| `20261122T012525Z_5eaeb03_phase4/` | Original B1/B2/B3 candidate grid |
| `20261122T130145Z_00bb1ad_phase4_b3r_20261122/` | Final B3r, scoped A baseline and post-attack comparators |
| `20261122T200528Z_8a22753_phase4_b3r_fast_20261122/` | First fast comparison; cross-session |
| `20261122T210801Z_e4fd928_phase4_b3r_fast_rematch_20261122/` | Binding same-session fast rematch |

These measurements were completed; no full grid is awaiting a later phase.
They are preserved unchanged by this portability fix. Settings, source/data
hashes and machine/package metadata remain with each run.

## Results and revision summary

At 10k, final B3r is 21–186x faster than A on the four non-churn official
workloads; A wins cancel_churn. At 100k, stopped A cells provide the lower
bounds reported in [REPORT §6](00_docs/REPORT.md#6-runtime). B3r's heap rebuild
replaces B3's history-sized drift heap, with a declared single-event cleanup
spike. The binding rematch rejected B3r_fast despite its 12.7 % aggregate gain,
because one scenario exceeded the fixed 5 % loss bound. B remains B3r.

## Data generation and optional reproduction

```powershell
python -m submission_tools data
python -m submission_tools data --verify-only
```

[DATA_MANIFEST.json](00_docs/DATA_MANIFEST.json) and
[POST_ATTACK_MANIFEST.json](00_docs/POST_ATTACK_MANIFEST.json) record generation
commands and SHA-256. The supplied generator remains byte-for-byte preserved;
own synthetic generators are labelled. Regeneration writes only ignored
inputs/local manifests, verifies decoded content and explicitly labels any
gzip-byte differences across zlib versions. Million-event files stay ignored.
The full catalog has 134 entries / 125 physical files.

The safe short reproduction is `python -m submission_tools smoke`: 1k events,
seed 42, A/B3r, 108 workers in a unique scratch copy. Without a checkout its
provenance is `no git checkout (source not commit-verified)` and a source
fingerprint is retained. Official long runs and official session resumes
still require committed source in a checkout. `--plan-only` lists coverage
without executing engine measurements.

`.\run_all.ps1 -Full` / `bash run_all.sh --full` repeat the saved grid in new
sessions after `RUN FULL` confirmation; allow 6–10 h on the original laptop.
Commit source first. The binding selection is not repeated. The detailed
protocol and declared A scope are in [BENCHMARK_PLAN.md](00_docs/BENCHMARK_PLAN.md).

## Verification and reading order

Current expected collection: **1,040 standard tests** (seven portability cases
added to the 1,033 collected as of `3e9ebfe`). Commands and actual full-suite,
dashboard and fresh-environment results are linked from
[FINAL_FIX_VERIFICATION.md](00_docs/FINAL_FIX_VERIFICATION.md) and
[final-fix-verification.json](05_evidence/final-fix-verification.json).
An exact `git archive HEAD` contains only committed files; before Laurin's
commit, passing tests of hashed working-file overlays are explicitly labelled
pre-commit evidence. They are not described as an unchanged committed archive.
Bash syntax is checked; a successful native macOS/Linux run is not claimed.

Read Start here → [REPORT](00_docs/REPORT.md) → dashboard Final selection /
Overview → [FINAL_SELECTION](00_docs/FINAL_SELECTION.md). Requirements, AI and
revision logs are the audit trail. `00_docs/TRACE.md` contains the hand trace;
`01_code/`, `02_tests/`, `03_results/`, `04_dashboard/`, `05_evidence/` and
`06_data/` hold implementation, tests, saved measurements, dashboard, evidence
and fixtures respectively. The unused learning scaffold was removed at
Laurin's request.
