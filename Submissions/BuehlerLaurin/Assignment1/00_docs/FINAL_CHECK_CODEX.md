# Final technical acceptance — Assignment1

Date: 25 November 2026 (Europe/Berlin). Reviewer: Codex. **Verdict: NOT ACCEPTED under the requested criteria.** Three must-fix findings are reproduced below. No fixes were applied.

Reviewed commit: `1b7adca07896ef2406d316e34eeb304e12c52917`.
Local comparison ref `upstream/main`: `e04b40c799b0d08bdc7b49bbba0354eef351607f` (20 November 2026). No remote refresh was performed.

## Scope and isolation

The committed Assignment1 tree was exported with `git archive --format=zip HEAD:Submissions/BuehlerLaurin/Assignment1`, then extracted to a fresh directory outside the repository. Its initial contents had no environment, scratch tree or Git metadata. The archive contains **1,084 files / 46,978,327 bytes**; SHA-256 `256620d792bfcbd531df884d9b649d0cba68688b9de49f329f9cd7e147318f5c`. A second independent extraction was used for the `-Full` entry-point check.

All execution, installations, generated inputs, test caches, logs and reviewer helper scripts stayed under `%TEMP%/aif-final-1b7adca-20261125/`. The sole repository write is this report. Git commands were read-only, including the explicitly requested archive; this audit made no Git state or remote changes. The initial working tree was clean. During execution, concurrent external edits appeared in `00_docs/FINAL_SELECTION.md`, plus untracked `00_docs/FINAL_REVIEW_CLAUDE.md` and `05_evidence/chat_reference/`. They were left untouched and are outside this committed-tree acceptance; see `status-concurrent.txt` and `concurrent-selection.diff`. All **1,084** original files in each of the two clean copies remain byte-identical to the archive after the checks (`final-copy-integrity.json`).

Python **3.13.15**, Windows PowerShell, pinned requirements from the archive. The host's default `python` was a disabled Store alias; the installed Python 3.13 directory was prepended to the temporary process PATH. No submission script was edited. AppTest used an empty PATH, making Git unavailable.

## Ranked findings

### Must-fix M1 — standard suite cannot pass in a clean archive

Target: `02_tests/test_dashboard.py:76–83`, especially line 78; `04_dashboard/saved_results.py:27–32,71–75`.

In a directory without a checkout, `head()` correctly returns `None` and the dashboard uses `DiskStore`, whose `revision` is `None`. The test unconditionally evaluates `len(store.revision) == 40` and raises `TypeError: object of type 'NoneType' has no len()`.

Independent README command:

```powershell
python -m pytest -q --basetemp=scratch/pytest-manual
```

Actual: **1 failed, 1,032 passed in 688.49 s**, process exit **1**, wall **690.18 s**. Expected: **1,033 passed**. The initial from-zero run reproduced the same single failure, and a single-test reproduction exited 1 in **8.21 s**:

```powershell
python -m pytest -q 02_tests/test_dashboard.py::test_loader_restricts_paths_and_uses_a_fixed_commit --basetemp=scratch/pytest-repro
```

Impact: `run_all.ps1` stops at its test gate before replay, smoke or dashboard. The no-Git dashboard itself renders successfully; the failure is the suite's checkout-only assumption. Suggested direction, not applied: retain committed-store assertions where a checkout exists and verify disk-store semantics in the archive case.

Evidence: `run-all.log`, `manual-pytest.log`, `manual-failing-test-repro.log`, `readme-run-all-default.log`, `readme-full.log`, `Assignment1/scratch/run_all-tests.xml` in the temporary evidence directory.

### Must-fix M2 — smoke requires an enclosing Git checkout

Targets: `submission_tools.py` smoke runner; `01_code/bench/run_all.py:48–51,153–164`.

```powershell
python -m submission_tools smoke
```

Actual: exit **1** in **2.97 s**. Its 12 small catalog entries / 11 physical inputs generate and verify, then `get_run()` calls `source_dirty()` unconditionally. `git status --porcelain=v1 --untracked-files=all -- .` exits **128** because the copied workspace is outside a checkout. The helper prints a traceback and `FAIL`; **zero benchmark workers run**. Expected: successful 1k smoke (the existing successful-run claim is 108/108 workers).

This is a second, separately reproduced blocker: correcting M1 alone would not make the requested clean-room entry point complete. Suggested direction, not applied: give smoke an explicit no-checkout provenance path while retaining strict commit checks for official measurements.

Evidence: `manual-smoke.log`, `manual-results.json`. No Git repository was created to work around the failure.

### Must-fix M3 — requested branch-scope condition is false

Executed the requested `git diff --stat upstream/main...HEAD`, plus `--name-only` and an outside-scope `--shortstat` check.

```text
All paths:      1181 files changed, 231818 insertions(+), 254 deletions(-)
Outside scope:   56 files changed,   8471 insertions(+)
```

The 56 paths are in **three other student folders**, grouped **42 / 1 / 13**; no course-root change was found. Therefore it is not possible to confirm that only `Submissions/BuehlerLaurin/` differs on this branch. Read-only history inspection shows pre-existing commits by other contributors; this finding describes the requested comparison, not authorship by Laurin or this audit. The locally stored upstream ref may lag the service; no fetch was authorized or performed. Human review of the comparison base/branch contents is needed.

Evidence: complete `branch-stat.txt`, `branch-paths.txt`, `branch-summary.json` in the temporary directory. Other students' names are kept out of this report to avoid adding them to the submission's hygiene scan.

### Should-fix S1 — personal absolute paths are published in evidence

The case-insensitive committed-tree scan found **573 personal-path lines in 162 files**; the broader absolute-path expression found **574 lines in the same 162 files**. Most are historical provenance: **565 lines under `05_evidence/`, 6 under `03_results/`, 2 in `00_docs/AI_LOG.md`**. They disclose the owner's home directory, checkout location and interpreter location. No executable-source path dependency was found by this scan.

Examples by location, with the actual personal prefix omitted here: `00_docs/AI_LOG.md:868,1105`; `03_results/runs/20261121T224807Z_efee8d4-dirty_phase3_sanity_not_benchmark/tests.txt:2–3`; dated command logs and JUnit XML in `05_evidence/`. Review the public disclosure and any redaction/provenance policy before submission. Historical evidence was not rewritten.

Evidence: `hygiene-personal_path.json`, `hygiene-absolute_path.json` (full matching lines).

### Should-fix S2 — unfinished submission documentation

- `00_docs/LEARNING.md:1–9` is an unfilled scaffold, including its exercise/date heading and every study-note prompt.
- `00_docs/REQUIREMENTS_MAP.md:102–110,116` retains partial/pending final checks, two unresolved required rows and the pending optional peer-audit row. In particular, its clean-environment success statement at R65 does not describe this archive acceptance result.
- `README.md:71,419` still has the submitted-commit and audit-commit placeholders. These are clearly marked human submission steps, but remain unfinished for final delivery.

There are 17 broad template-pattern hits across 7 files. The remaining hits are legitimate CLI metavariables or reusable helper documentation, not unfinished engine stubs. No source TODO/FIXME defect was found. Suggested direction, not applied: finish or explicitly mark out-of-scope scaffolds, reconcile the final requirement statuses, and have the human record the intended submitted revision.

### Should-fix S3 — historical worker diagnostics match current ignore rules

The archive includes **648 files / 4,829,768 bytes** under the old smoke run's `cells/` and `jobs/` directories. Assignment1 `.gitignore:17–18` explicitly excludes these local per-worker journals/logs; ignore rules do not remove already tracked files. They are not large input datasets, but they remain committed packaging leftovers. Review whether to retain them as explicitly documented evidence or exclude them from the deliverable. No file was removed.

Evidence: `hygiene-tracked-local-diagnostics.json` contains every matched path and size.

### Nice-to-have N1 — make the chosen packaging boundary explicit

The working checkout contains **16,075 ignored artifact files / 1,291,028,068 bytes**, including a local environment, scratch outputs, generated data and caches. None is present in the committed archive. This is not a committed-submission defect; use the committed-tree boundary when preparing the deliverable. No local artifact was removed.

## Initial clean-room run: every script step

Command: `.\run_all.ps1 -NoDashboard` from the fresh archive. Wall **757.12 s**. Result: **FAIL at full test suite**.

| Step | Result | Duration |
|---|---|---:|
| Create `.venv` from zero | PASS | 7.68 s |
| Install pinned requirements | PASS; pytest 9.2.0, hypothesis 6.155.7, pandas 3.1.1, Streamlit 1.67.0 | 64.15 s |
| Full standard tests | FAIL; 1 failed, 1,032 passed; pytest reports 682.18 s | 684.53 s including process/report overhead |
| Worked replay + expected-output comparison | Not reached; later independent commands PASS | Not reached |
| 1k smoke | Not reached; later independent command FAIL (M2) | Not reached |
| Dashboard/NoDashboard completion branch | Not reached after failure; separate AppTest PASS | Not reached |

Setup/test step durations use external script-boundary timestamps. The first review wrapper returned zero because its caller did not propagate the child script's exit; that is a reviewer-harness limitation, not evidence of a successful run. Its `FAIL` output and pytest failure are retained. The subsequent direct `powershell.exe -File run_all.ps1` invocation returned **1** in **789.96 s**, independently confirming the entry-point failure with the real process exit code.

## README “Start here”: individual commands versus expectations

Commands ran from the main clean copy with its local environment active (absolute interpreter paths in raw logs are the equivalent activated `python`). A failed command did not prevent later independent checks.

| Command | Expected | Actual / comparison | Wall |
|---|---|---|---:|
| `python -m venv .venv` | Local environment | PASS, exit 0; initial from-zero creation also recorded above | 4.06 s |
| `.\.venv\Scripts\Activate.ps1` | Environment activation | PASS; `python --version` = 3.13.15 | 1.00 s |
| `python -m pip install -r requirements.txt` | Pins installed/already satisfied; hypothesis 6.155.7 | PASS, exit 0; requested pins satisfied | 1.66 s |
| `python -m pytest -q --basetemp=scratch/pytest-manual` | 1,033 passed | FAIL, exit 1; 1,032 passed / 1 failed (M1) | 690.18 s |
| `python -m run lob.replay 06_data/supplied/worked_example.jsonl --version B` | Six JSON results; final B = B3r | PASS, exit 0; exactly six JSON lines, checked against fixture below | 0.17 s |
| `python -m streamlit run 04_dashboard/app.py` | Saved-results dashboard, default 8501 | PASS with Git unavailable; independent retry healthy at `http://127.0.0.1:8501` | 1.79 s startup |
| `python -m submission_tools data` | Regenerate catalog; verify content; print archive hashes | PASS, exit 0; 134/134 exact archive hashes and content hashes | 243.14 s |
| `python -m submission_tools data --verify-only` | All recorded hashes verified | PASS, exit 0; 134 entries / 125 files; no gzip mismatch on this host | 8.52 s |
| Replay piped to `Set-Content -Encoding UTF8 scratch/worked_actual.jsonl` | Save worked results | PASS, exit 0 | 0.77 s |
| `python -m submission_tools check-worked scratch/worked_actual.jsonl` | OK | PASS, exit 0; CLI rows, fills, final book and proceeds match `worked_expected.json` | 0.20 s |
| `.\run_all.ps1` | Tests, worked OK, smoke OK, then dashboard | FAIL, exit 1, same single test; later steps not reached | 789.96 s |
| `.\run_all.ps1 -NoDashboard` | Same checks, explicit dashboard skip | FAIL at tests from zero; later steps not reached | 757.12 s |
| `.\run_all.ps1 -Full` | Prerequisites, then confirmation before long runs | FAIL, exit 1; 1 failed / 1,032 passed in 749.81 s; no long confirmation/measurements reached | 814.90 s |

`bash run_all.sh`, `bash run_all.sh --no-dashboard` and `bash run_all.sh --full` were each invoked under available **Windows Git Bash**: exit 1 in 0.38 / 0.18 / 0.18 s, with `FAIL: .venv has no Unix Python`. This is the expected platform mismatch with a Windows environment, not a demonstrated macOS/Linux defect. `bash -n run_all.sh` passed. No real macOS/Linux environment was available; those platform alternatives (`python3` venv creation, Unix activation/redirection and successful Bash execution) are **not runtime-certified**.

The first dashboard launch auto-selected 8502 while 8501 was occupied; a later independent exact-command retry used 8501 and returned HTTP 200 / `ok`. A separate instance on 18501 was also healthy. Only reviewer-started server processes were terminated. The optional 6–10-hour benchmark reproduction was never reached or confirmed. Some final entry-point suites overlapped other temporary-copy checks; their wall times are observations, not comparative benchmark measurements.

An independent standard-library pass recomputed hashes and line counts for all **125 physical generated files / 13,204,884 events** and matched the committed catalog, including every archive hash. Own-generator line-ending-only notices were explicit; no committed generator or manifest was changed. This verifies data reproduction, not benchmark speed claims.

## No-Git dashboard AppTest

`AppTest.from_file(..., default_timeout=180).run()` completed in **7.01 s** with an empty PATH and `saved_results.head() is None`. All tabs contain rendered content, with **zero exceptions and zero error elements**:

| Tab | Dataframes | Markdown blocks |
|---|---:|---:|
| Final selection | 1 | 2 |
| Overview | 1 | 2 |
| Scaling | 7 | 0 |
| Original vs revised & variants | 7 | 3 |
| Throughput & latency | 5 | 0 |
| Memory | 3 | 1 |
| Correctness | 3 | 3 |
| Bottleneck explained | 4 | 2 |
| Method & data | 7 | 3 |

The top warning states that files are read from disk and values are not commit-verified. Observed metrics: B3r official 100k geomean **0.4247 s**, A replay limits **13**, non-churn 10k speedup range **21–186x**. The existing algorithmic-spike qualification remains visible. This acceptance checks rendering and these displayed headlines; it is not a new exhaustive audit of every numerical dashboard cell.

Evidence: `dashboard-apptest.json`, `dashboard-apptest.log`, `manual-streamlit-auto-result.json`, `live-server-results.json`.

## Hygiene: full committed submission

All 1,084 files were searched case-insensitively; gzip fixtures were decompressed and searched too. No submitted PDF required extraction.

| Check | Result |
|---|---|
| Logged injected term | Exactly one match, at `00_docs/AI_LOG.md:10`, in its permitted quotation; no other match |
| Other students' names | No matches; checked all 15 other submission-folder names and their separated name components |
| Likely secrets | No matches for common service-token/private-key markers or quoted credential assignments; heuristic scan, not a guarantee about arbitrary secret formats/history |
| Personal/absolute paths | Finding S1: 573 personal / 574 broader absolute-path lines in 162 files |
| Tracked `.venv`, scratch, Python/Hypothesis/pytest caches, bytecode, Git metadata, `06_data/generated/` | None |
| Per-worker journals/logs ignored by current rules | S3: 648 tracked files / 4,829,768 bytes under historical smoke `cells/` and `jobs/` |
| Million-event dataset filenames | None in committed archive; references/settings in manifests are expected |
| Small data | Five supplied 10k gzip samples and the labelled small own/worked fixtures are intentional |
| Files over 20 MB | None (also none over 20 MiB); largest is `03_results/runs/20261122T012525Z_5eaeb03_phase4/memory.csv`, 6,557,190 bytes |
| Templates / unfinished status fields | Finding S2; full locations in `hygiene-template.json` |

The working checkout's ignored artifacts were inventoried separately and were not copied as initial inputs. The scan does not inspect Git object history. It establishes absence of the logged term outside its quotation, not an independent proof of every historical AI-generated behavior.

## Evidence retention and final state

All detailed evidence and reviewer scripts remain outside the repository in `%TEMP%/aif-final-1b7adca-20261125/`: archive, command logs/results, AppTest results, hygiene match inventories, branch stat/path lists, independent data checks and copy-integrity checks. Key failures and totals are embedded in this report so the verdict does not depend on a persistent temporary directory.

No engine, test, expected output, dependency pin, saved result, manifest, AI log or README was fixed. The only repository change made by this audit is `00_docs/FINAL_CHECK_CODEX.md`. Git remains human-only. **STOP.**
