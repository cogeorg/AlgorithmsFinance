CLASS 3 SUBMISSION - GARV SHARMA
===============================

Required destination: Submissions/SharmaGarv/Class3/

HAND-IN FILES
lab.py                 Complete pricing implementation and validation.
verify_results.py      Independent checker for regenerated detailed outputs.
asset_results.csv      All 82 asset/window values and exercise outcomes.
performance.csv        Four experiments: N, assets, seconds and sampled peak RSS.
report.txt             Human-readable results and model/measurement conventions.
requirements.txt       Exact dependency versions.
README.txt             These instructions.
.gitignore             Excludes generated results and Python caches.

Prepared for Garv Sharma. This folder contains the Class 3 hand-in files.

SETUP (Python 3.12)
From the repository root:
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r Submissions/SharmaGarv/Class3/requirements.txt

CHECK THE ALGORITHM
  .venv\Scripts\python.exe Submissions/SharmaGarv/Class3/lab.py --validate

REPRODUCE IN THE COURSE REPOSITORY
The course data are in Class3/data/hourly/ relative to the course repository root:
  .venv\Scripts\python.exe Submissions/SharmaGarv/Class3/lab.py --data Class3/data/hourly --run-all
  .venv\Scripts\python.exe Submissions/SharmaGarv/Class3/verify_results.py --data Class3/data/hourly

REPRODUCE IN THIS LOCAL WORKSPACE
Here the workspace itself is the Class3 directory, so the data are in data/hourly/:
  .venv\Scripts\python.exe Submissions/SharmaGarv/Class3/lab.py --data data/hourly --run-all
  .venv\Scripts\python.exe Submissions/SharmaGarv/Class3/verify_results.py --data data/hourly

Regeneration writes fresh tables, metadata, report and per-hour boundaries to
Submissions/SharmaGarv/Class3/results/ (excluded from Git). The two hand-in CSVs
beside the code are the verified snapshot of the completed experiments. To hand
in a future rerun, replace these snapshots with its generated CSVs and report.

LOCAL ARCHIVE (outside the hand-in folder; excluded from Git)
.lab-artifacts/SharmaGarv/Class3/results/ contains the existing full boundary
files, metadata, verification evidence and original generated tables/report.
The original detailed step-by-step guide is preserved next to that results folder.
To recheck this archived run from this workspace:
  .venv\Scripts\python.exe Submissions/SharmaGarv/Class3/verify_results.py --data data/hourly --results .lab-artifacts/SharmaGarv/Class3/results

RESULT CONVENTIONS
Values and payoffs are per underlying unit, in USDT (approximately USD).
All timestamps are UTC. Payoff excludes the option premium.
Memory is total process RSS sampled every 10ms, not exact auxiliary-space usage.
Missing hours are not filled; full history uses actual available row counts.
See report.txt for numerical conventions and the six-task results summary.
