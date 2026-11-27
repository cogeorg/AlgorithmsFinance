# Final portability and documentation fix verification

Base: `3e9ebfe152605d80f48c2e9d703b965eda246c78`. The implementation remains uncommitted; Git is human-only.

**Working files: PASS. Exact committed-HEAD archive: FAIL until the human commit contains the fixes.** A plain archive cannot include working-tree edits. Both results below are real runs; the passing overlay is not labelled as an unchanged HEAD archive.

## Fresh verification

| Check | Result |
|---|---|
| Final full suite, run to completion once on frozen final runtime | **1,040 passed in 908.12 s**, no failures/errors/skips; [log](../05_evidence/20261125T220142Z_3e9ebfe-dirty_final-fix-all-tests-final.txt) |
| Dashboard + robustness | **50 passed in 56.31 s**, no failures/errors/skips; [log](../05_evidence/20261125T220130Z_3e9ebfe-dirty_final-fix-dashboard-tests.txt) |
| Final portability + resume regressions | **8 passed in 88.09 s**; [log](../05_evidence/20261125T220056Z_3e9ebfe-dirty_final-fix-portability-final-green.txt) |
| Exact `git archive HEAD:Submissions/BuehlerLaurin/Assignment1` → fresh temp → `.\run_all.ps1 -NoDashboard` | Exit **1**, **1046.00 s**; old M1: 1 failed / 1,032 passed; [log](../05_evidence/20261125T215356Z_3e9ebfe-dirty_final-fix-head-only-cleanroom-rerun.txt) |
| Same archive + explicitly hashed working-file overlays → new temp/env → same command | Exit **0**, **982.16 s**; **1,040 passed**, worked example OK, **108/108 smoke workers OK**, explicit dashboard skip; [log](../05_evidence/20261125T220244Z_3e9ebfe-dirty_final-fix-overlay-final-cleanroom.txt) |
| No-Git AppTest and individual README commands | Nine tabs, no exceptions, expected disk warning; worked example and data/hash verification PASS; [log](../05_evidence/20261125T221359Z_3e9ebfe-dirty_final-fix-extra-acceptance-final-review.txt) |

The original HEAD-only M1/M2 audit findings concern `1b7adca`/`3e9ebfe`. The new implementation fixes them: committed-store assertions stay active in a checkout; disk-store revision, allowlist and warning are asserted without one. Seven new cases cover copied submissions, missing Git, ancestor checkouts and strict official/resume gates. The smoke records `no git checkout (source not commit-verified)`, a source fingerprint and an explicit false verification flag. Official long runs still require tracked committed source and no dirty source, before considering a resume pointer.

### Fresh fixed-copy step wall times

| Step | Seconds | Result |
|---|---:|---|
| create venv | 8.08 | PASS |
| install requirements | 52.75 | PASS |
| full tests | 875.42 | PASS |
| worked example | 0.29 | PASS |
| 1k smoke | 44.90 | PASS |
| dashboard skip | 0.03 | PASS |

The boundary clock includes process/report overhead. Some runs overlapped CPU work; these are acceptance durations, not speed comparisons. Both clean-room environments began absent; their package pins were installed from requirements.

The overlay manifest and runtime hashes are in [final-fix-verification.json](../05_evidence/final-fix-verification.json). Only explanatory docs/status wording changed afterward; runtime hashes match the tested copy. Both the exact archive and overlays stay outside the repository, under `%TEMP%/aif-fix-3e9ebfe-20261125/`. No `.git` directory was created.

## Documentation and protected scope

README now has current nine-tab instructions, the PowerShell execution-policy fallback, a results-only path, completed saved sessions and a current expected 1,040-test count. The Submitted commit placeholder is intentionally retained for Laurin. The current requirement table has no pending/todo/partial statuses; actual human submission obligations remain explicitly human actions. Dated phase history is labelled as history.

REPORT cites the committed independent reference, 300,000-event validator check and Linux profile (validation 27–41 % per event); distinguishes Phase 4/attack ratio sources; uses the at-most-2 rebuild bound and worst observed 1.999; explains traced/auxiliary/process memory; and gives official-100k active-order/price-level peaks from counts.csv. REPORT_FACT_CHECK records subsequent selection edits at 5785e9f and 3e9ebfe. The unused LEARNING scaffold was deleted at Laurin's explicit choice. The duplicate marker quotation/query in FINAL_REVIEW_CLAUDE was replaced with a transparent redaction note, leaving AI_LOG as the sole quotation.

Engine and validation logic, expected data, generators, requirements pins, all stored benchmark files, dashboard implementation, final selection and committed chat-reference evidence remain unchanged. Only `source_dirty` and `get_run` changed in the runner; its worker invocation, timing and aggregation function ASTs are unchanged. Entry-script logic is unchanged (expected-count comments only). All existing dashboard tests except the explicitly requested M1 function are AST-identical. See [source/doc review](../05_evidence/final-fix-review.json) and [report calculations](../05_evidence/final-fix-doc-check.json).

## Remaining acceptance boundaries

- Commit the reviewed files manually, then repeat the exact unchanged-HEAD archive check. Its current failure is expected because HEAD still contains the old test; it is not presented as evidence that committed fixes passed.
- Current local `upstream/main` = `43ff26c35cb9a27439b86ed5054e188639609903`: **0 outside-owner paths** in `git diff upstream/main...HEAD`. This supersedes the old audit's 56-path finding against e04b40c. This fix ran no fetch or Git mutation.
- The existing personal paths in historical/reference evidence and 648 tracked worker diagnostics remain published; no personal-path redaction or untracking was requested for execution. No likely secrets or submitted files over 20 MB were found by the repeated heuristic scan. Large regenerated data exists only in temporary/ignored directories. Bash syntax passes; native macOS/Linux execution is not certified.
- Initial test-fixture/archive-setup mistakes and the two intentionally interrupted pre-final runs remain in evidence, and are not counted as passing final checks. See AI_LOG for the correction record.

## Proposed human Git commands (not executed)

Run from `Submissions/BuehlerLaurin/Assignment1`.

The following exact command untracks only the 648 historical smoke `cells/` and `jobs/` files while leaving the local files intact. It is a proposal, not an action taken by this fix:

```powershell
git rm -r --cached -- 03_results/runs/20261122T004602Z_5d8d15a-dirty_smoke/cells 03_results/runs/20261122T004602Z_5d8d15a-dirty_smoke/jobs
git add -- README.md SPEC.md run_all.ps1 run_all.sh 01_code/bench/run_all.py 02_tests/test_dashboard.py 02_tests/test_checkout_portability.py 00_docs/REPORT.md 00_docs/REPORT_FACT_CHECK.md 00_docs/REQUIREMENTS_MAP.md 00_docs/AI_LOG.md 00_docs/FINAL_REVIEW_CLAUDE.md 00_docs/FINAL_FIX_VERIFICATION.md 05_evidence/INDEX.md '05_evidence/*final-fix*'
git add -u -- 00_docs/LEARNING.md
git commit -m "Assignment1: fix no-checkout acceptance and reconcile final documentation"
```

The untracking proposal is optional and separate from the verified code changes; stored measurement contents have not been changed by this audit. **STOP.**


## 2026-11-25 — Final pure-HEAD acceptance (`7e56958`)

**PASS** at commit `7e56958f606d5b8b18c056778ee4e95191e3bf3a`. This committed-only run supersedes the earlier pre-commit HEAD limitation above. Exported `git archive HEAD:Submissions/BuehlerLaurin/Assignment1` into a new external directory: no initial `.venv`, `scratch` or `.git`, **no overlays**; Python 3.13.15.

| Step | Result / exit code | Wall time |
|---|---|---:|
| Create .venv | PASS / exit 0 | 6.30 s |
| Install pinned requirements | PASS / exit 0 | 56.86 s |
| Full standard suite | 1,040 passed, 0 failed, 0 skipped / exit 0 | 721.58 s |
| Worked-example replay and check | OK / exit 0 | 0.32 s |
| 1k smoke | 108/108 workers OK / exit 0 | 44.73 s |
| NoDashboard completion | PASS / exit 0 | 0.04 s |
| No-Git dashboard AppTest (after run-all) | 9/9 tabs rendered, exit 0 | 5.56 s |

Run-all exit **0**; total **830.43 s**. AppTest used an empty PATH, confirmed no Git/checkout, no errors/exceptions and the disk-source warning. All **470 archived files** remained byte-identical. Step wall times include process overhead.

Logs and structured results: `%TEMP%/aif-pure-head-7e56958-20261125/` (`run-all.log`, `step-boundaries.jsonl`, `run-result.json`, `apptest.log`, `final-result.json`, and `05_evidence/20261125T223039Z_nogit_pure-head-7e56958-acceptance.txt`). The only repository write in this acceptance is this appended section; no code changes or Git mutations.
