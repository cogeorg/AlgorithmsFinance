# Class 3 Lab 2 — Laurin Bühler
FIN71055 American put pricing. Blocks 1–2 complete; stopped for review before independent audit/hand-off.

Two tested versions: A transparent pure Python, B NumPy layer induction with an O(N) CRR stock/payoff lattice. Both compute the boundary during backward induction without a stored tree. See [SPEC.md](SPEC.md), [REPORT](00_docs/REPORT.md), [TRACE](00_docs/TRACE.md) and [requirements map](00_docs/REQUIREMENTS_MAP.md).

## Results
Both runs are labelled **quick (dirty tree)**. Directory names stay unchanged so saved evidence paths remain valid.

| Run | Label | Coverage |
|---|---|---|
| [Initial vectorization](03_results/runs/20261127T120831Z_279b029-dirty_fast_blocks12/summary.csv) | quick (dirty tree) | Interrupted; completed BTC cells retained |
| [Revised lattice](03_results/runs/20261127T121436Z_279b029-dirty_fast_blocks12/summary.csv) | quick (dirty tree) | Complete required grid |

<!-- COMMITTED_SOURCE_STATUS_BEGIN -->
Post-commit source verification: **pending Laurin's commit**. A working-tree check is not commit verification. The command below will compare both source_sha256.json files with actual committed Git blobs through SOURCE_MAP.json, save evidence, and replace this paragraph with the verified commit. No benchmarks will be rerun.
<!-- COMMITTED_SOURCE_STATUS_END -->

| Workload | Version | N | Assets | Median seconds | Whole-run peak bytes | Pricing peak bytes |
|---|---|---:|---:|---:|---:|---:|
| BTC1y | A | 8760 | 1 | 30.012675 | not measured | not measured |
| BTC1y | B | 8760 | 1 | 0.718781 | 7001865 | 852242 |
| BTC5y | B | 43822 | 1 | 7.199832 | 8685193 | 4217726 |
| ALL1y | B | 8760 | 40 | 26.580497 | 7048338 | 852368 |
| ALL5y | B | 43822 | 40 | 284.649042 | 8731641 | 4218020 |

BTC1y A/B median ratio: **41.75×** on these inputs and this machine. A timing is reused from the earlier same-machine run after A/data/common/pipeline hash checks. Both run folders and reuse provenance are retained.

- BTC1y: value **16714.9352705396 USDT**; first exercise **2026-06-02T14:00:00Z**, payoff **41588.71 USDT**.
- BTC5y: value **20719.7894300243 USDT**; first exercise **2022-06-18T06:00:00Z**, payoff **42121.23 USDT**.

| Version | N | Status | Median seconds |
|---|---:|---|---:|
| A | 1000 | ok | 0.416015 |
| A | 2000 | ok | 1.690320 |
| A | 4000 | ok | 6.303940 |
| A | 8000 | stopped | — |
| B | 1000 | ok | 0.033366 |
| B | 2000 | ok | 0.072495 |
| B | 4000 | ok | 0.179322 |
| B | 8000 | ok | 0.459377 |

Log-log least-squares slopes over completed growth cells: A=1.961, B=1.266. These are finite-range scaling observations, not complexity proofs. A visits quadratic nodes in Python; B has the same node count but layer overhead can dominate the 1k–8k range. Stopped cells are excluded from slopes and ratios; their 60 s limit covers the complete child process, not one repeat.

## Measurement scope
One untimed warm-up, five timing repeats, median and all raw repeats. Whole-run seconds include file loading, calibration, pricing, boundary extraction and observed first-exercise search. Imports/process startup and CSV serialization excluded; warm caches expected. Forty assets run sequentially in one process per batch, with compact scalar summaries retained.

Tracemalloc runs separately from timing. Primary peak covers the whole run. Secondary covers an isolated pricing call, including returned boundary, with calibrated inputs pre-existing; for a batch the table shows the maximum of separately measured calls. These are traced bytes, not RSS. A is timing-only for the ratio. Phase instrumentation is a separate run, with parse and calibration reported together.

All 40 supplied files contain 43,823 observed closes (N=43,822) and one missing hour. Last year selects the last 8,761 rows (N=8,760), not a calendar filter. Read-only originals: ../../../Class3/data/hourly. [Local hashes](06_data/supplied/MANIFEST.json) establish snapshot consistency only, not upstream authentication. No S&P 500 download.

## Saved artifacts
Committed artifacts include summary.csv (success/error counts), timing.csv and raw repeats, memory.csv/scopes, phase_instrumentation.csv, growth.csv/logs, env.json, source_sha256.json, SOURCE_MAP.json, tests.txt, asset summaries and BTC boundary/path CSVs. ALL1y_B_boundaries/ and ALL5y_B_boundaries/ stay local and are git-ignored: 80 files, 123,993,881 bytes. Their per-file SHA-256 hashes, byte sizes and exact boundary-only regeneration command are in [BOUNDARIES_MANIFEST.json](03_results/runs/20261127T121436Z_279b029-dirty_fast_blocks12/BOUNDARIES_MANIFEST.json). No local boundary files were deleted. Full artifact verification in a fresh clone requires regenerating those CSVs first; regeneration does not rerun timing or memory measurements.

Missing boundaries are empty CSV fields; Python uses None and JSON null. Final comparison exceptions are explicitly recorded in BTC1y_A_B_FINAL_COMPARISON.json. GROWTH_PROTOCOL.txt identifies the direct-interpreter final grid; the initial launcher grid is retained separately and excluded from final tables.

## Run commands (PowerShell, from this folder)
Use the existing venv. No installs were performed; requirements.txt pins the verified environment.

```powershell
$env:TEMP=Join-Path (Get-Location) 'scratch'
$env:TMP=$env:TEMP
$env:HYPOTHESIS_STORAGE_DIRECTORY=Join-Path (Get-Location) '.hypothesis'
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py tests -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B -m pytest -q --basetemp=scratch/pytest-manual
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py data -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B verify_manifest.py 06_data/supplied --metadata
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py diagnostic -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B run.py bench.diagnostic
$env:EVIDENCE_TIMEOUT_S='14400'
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py benchmark -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -u -B run.py bench.run_lab
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py artifacts -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B 00_docs/verify_results.py
```
Before running tests, keep TEMP/TMP and Hypothesis storage inside this exercise as recorded in the evidence commands. Full benchmark regeneration is expensive. The reported run's exact command uses --reuse-a with provenance recorded inside its run folder. The verifier's independent baseline comparison intentionally references the preserved initial run.

## Precommit staging and size
The exact human-only file-by-file staging commands are in [STAGE_BLOCK2.ps1](00_docs/STAGE_BLOCK2.ps1). No result folder is added wholesale; the script lists individual files, excludes ALL1y/ALL5y boundaries, and explicitly stages all measured source targets under the scoped byte-preservation attributes. It has been syntax-checked, not executed by Codex.

Measured retained size: **4.5M** from `du -sh` excluding ALL1y/ALL5y boundary folders and local scratch/test caches (precommit-du evidence). The excluded CSVs remain on disk.

## After Laurin commits (no benchmark rerun)
Run from this exercise folder:

```powershell
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py committed-source-hashes -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B 00_docs/verify_committed_sources.py
```

This checks all 50 recorded source entries from both runs. Historical B/runner/SPEC versions map to committed snapshots; other entries map to committed current files. Scoped .gitattributes rules preserve exact measured bytes. The verifier reads HEAD using read-only git show, writes 03_results/COMMITTED_SOURCE_VERIFICATION.json and updates the status above only on success. The resulting README/evidence changes can be included in a human follow-up documentation commit. Both run labels remain quick (dirty tree).

## Evidence and limits
Saved red before A/data; A green before B; B/pipeline red before implementation; shared green contracts, exact Fraction oracle through N=12, six mutants and 200 Hypothesis comparisons; full BTC1y A/B differential and revised artifact verification. See [evidence index](05_evidence/INDEX.md).

- Fresh final tests: `python -B -m pytest -q --basetemp=scratch/pytest-final-block2` → **36 passed** (tests-final-block2 evidence).
- Artifact check: **82 asset outputs, 2,155,944 boundary rows**, all saved first-exercise results verified; final BTC1y A/B value delta **0**, boundary exceptions **0**.
- Data: **40 hashes match** our local snapshot. Implementation/test hashes match the measured code; the run preserves `SPEC_at_measurement.md` for the documentation-only phase update.
- Benchmark command used: `python -u -B run.py bench.run_lab --reuse-a 03_results/runs/20261127T120831Z_279b029-dirty_fast_blocks12`; final direct-process growth command: `python -B 00_docs/growth_direct.py`. Both saved through `evidence.py`.
- Fresh-environment check and independent Claude audit/attack: **pending**. No submission-readiness claim.

Slide quotations are Laurin's transcription; PDF not independently extracted. Stable stock construction and affine continuation are documented deviations in evaluation, preserving the recurrence and exact exercise rule. Claude's e^-657 underflow illustration was corrected by Codex (normal/subnormal transition near e^-708; zero near e^-745).

These are human-commit-plus-dirty-source-hash measurements, not clean-commit or fresh-environment reproducibility claims. The interrupted initial B grid remains explicitly labelled and incomplete cells are excluded. Independent Claude audit/attack and fresh-environment hand-off verification remain pending. No git writes, installs or network calls.
