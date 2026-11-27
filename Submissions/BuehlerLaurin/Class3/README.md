# Class 3 Lab 2 — Laurin Bühler
FIN71055 American put pricing. **Step 0b only:** scaffold/specification prepared; no pricing implementation or task-specific tests. The generated test infrastructure is intentionally unfilled. No test-pass, speed or submission-readiness claim.

Read [SPEC.md](SPEC.md) for slide quotations, approved applicability, all eleven decisions and predictions; [requirements map](00_docs/REQUIREMENTS_MAP.md) for outstanding tasks. Quotations use Laurin's supplied transcription, not independent PDF extraction.

## Environment
Existing venv: %USERPROFILE%/.venvs/aif-class3, Python 3.13. Laurin reports pytest 9.2.0, hypothesis 6.170.17, numpy 2.5.5; package availability will be checked in the implementation phase. Nothing installed. No dashboard or extra dependency selected. requirements.txt remains the scaffold placeholder pending dependency selection.

## Data and checks
Read-only originals: ../../../Class3/data/hourly/*.csv. S&P 500 excluded. Inventory found 40 files, each with 43,823 rows, N=43,822, UTC endpoints 2021-11-01T00:00:00Z and 2026-10-31T23:00:00Z, one missing hour. Last-year workload selects 8,761 rows, N=8,760.

Local hashes and counts: [MANIFEST.json](06_data/supplied/MANIFEST.json), [DATA_INVENTORY.json](06_data/supplied/DATA_INVENTORY.json). These are our own snapshot, not supplied upstream checksums. The manifest references originals; data is not copied.

Run from this exercise folder, PowerShell:
```powershell
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py step0-manifest -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B verify_manifest.py 06_data/supplied --metadata
```
This records checksum consistency against the local snapshot, not authenticity. The inventory command and all 40 SHA-256 values are saved in step0-data-inventory evidence. A first invocation failed due to PowerShell quoting; that log is preserved alongside the corrected successful run.

## Measurement definitions and predictions
Primary whole-row timing/memory: load + calibrate + price + boundary + first exercise. Memory is a separate tracemalloc run; secondary peak covers pricing and boundary output only. No RSS. One process, assets sequential. Report actual N and errors, not a fabricated shared N.

Predicted pricing time Θ(N²), workspace Θ(N); M sequential equal-size assets Θ(MN²). B will be chosen after profiling A; NumPy is only a candidate. No measurements yet.

## Numerical caution
Stable stock construction is required. exp(-657) is nonzero in binary64 (~4.66e-286); exp(-876) underflows. The accepted risk and mandatory high-s/large-N regression are documented in SPEC. Stable formulas must also address unrepresentable wings.

## Artifacts and evidence
00_docs/: REPORT, TRACE (reserved for hand trace), REQUIREMENTS_MAP, AI_LOG, REVISION.
01_code/ and 02_tests/: scaffold infrastructure only.
03_results/runs/: no pricing/benchmark results yet.
05_evidence/: data inventory, manifest verification and Step 0 document checks.
No dashboard selected.

## Current evidence boundary
Tests/differential/mutants: not run, later phases.
Pricing/benchmarks/peak memory: not run, later phases.
Fresh-environment reproduction: not run.
Commit to audit: Laurin fills this after committing.
Stop at Step 0b; await go.
