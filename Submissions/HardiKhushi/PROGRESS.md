# Project progress and decisions

This log records completed work, approvals, reasons, outcomes, and outstanding
requirements. Entries before this file was created are retrospective summaries
from the conversation, not evidence of an earlier test-first development cycle.
Commands below record work or describe a future proposal; listing a command is
not permission for an agent to execute it.

## 1. Initial setup (20 November 2026, retrospective)

- Request: keep the student's README, AI usage disclosure, tests, dashboard, and
  timing/memory results within `Submissions/HardiKhushi/`.
- Starting file: `test_search.py`, with five assertion-based example cases.
- Added search implementations, runnable unittest tests, a benchmark, an offline
  dashboard generator/page, README, AI disclosure, and two measured CSVs.
- Ran `python3 -m unittest discover -s Submissions/HardiKhushi -v`: 7 tests
  passed, including 50 randomized cases applied to all three methods.
- Ran `python3 Submissions/HardiKhushi/benchmark.py`: 9 summary rows per CSV,
  using n = 1,000/5,000/10,000, q = 200, seed 42, and five repeats.
- Checked matching result rows, measurement ranges, two SVG charts, table rows,
  and CSV links. No course or other-student files were modified.
- Limitation discovered later: the slides had not yet been consulted, so these
  artifacts must not be described as a complete assignment submission.

## 2. Guided assignment review (20 November 2026, retrospective)

- The user requested explanations and approval before every command. Approval
  was given to read the PDF and later to read `test_search.py`; those read-only
  inspections were completed. No implementation changes were made in that stage.
- Source: `AlgorithmsFinance_Slides3-1.pdf`, provided from Downloads. PDF page
  55 is numbered slide 54; it introduces the two-phase lab. Detailed Phase 1
  instructions are on numbered slides 56-64.
- Standard PDF extraction tools were unavailable. Read-only Python inspection
  decompressed PDF streams to extract the relevant text; nothing was installed
  and the PDF was not modified.
- Explained the common search contract, input preservation, the existing test
  helper, edge cases, and repeatable randomized reference checks.
- Corrected an earlier AI choice: built-in list membership and `bisect_left`
  do not satisfy the manual-search requirement. Replacement is still pending.
- A temporary deliberately wrong search implementation was proposed to check
  test sensitivity. At this stage it had not been run or separately approved;
  the later approved demonstration is recorded in entry 4.

## 3. Approved organization and generator step (20 November 2026)

### Approval and scope

The user requested ongoing documentation, an agent file, a results location,
and a separate random-array generator. The user approved the described batch:
inspect current files/instructions; create working rules and this log; relocate
CSVs and update paths/docs; add/connect a generator; run correctness and saved-
result checks without rerunning benchmarks. Filesystem write access was granted
for this submission folder for the turn. No additional approval is implied.

### Changes and reasons

- Added `AGENTS.md` for persistent working rules; use this log for the evolving
  history rather than filling the instructions file with every event.
- Moved CSVs into `results/`. Before/after hashes match; their contents, schemas,
  and recorded timestamps are unchanged. `results/README.md` records provenance.
- Added `data_generator.py`. It returns IDs, queries, expected answers, and
  settings without running search, timing, or file writes. Its optional CLI
  prints a JSON preview.
- Added unique and repeated ID policies, all-present/all-absent/mixed queries,
  a local seeded random generator, explicit actual hit rates, and validation
  for impossible requests such as present queries with an empty ID list.
- A seed reproduces a workload; it does not make timing results repeatable.
  Workload settings and Python version must also be retained.
- Updated `benchmark.py` to call the generator outside measurement regions,
  share its inputs across methods, accept scenario/duplicate options, and save
  future results under `results/` with generator-setting columns.
- Updated dashboard CSV paths and links, the README, and `AI_USAGE.md`.
  The dashboard identifies the existing data as preliminary and explicitly
  describes original workload settings absent from the old CSV schema.
- Added six generator tests. They check reproducibility, global RNG isolation,
  known answers and hit counts, duplicate policies, empty/invalid cases, and
  exact compatibility with the original benchmark's default inputs.
- Two initial documentation patch attempts failed validation on unmatched
  context and applied no changes; corrected patches were then applied.

### Verification

- Ran `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s
  Submissions/HardiKhushi -v`: all 13 tests passed (7 search and 6 generator).
  The compatibility test reproduced the original default arrays and queries at
  all three sizes. No temporary failing implementation was exercised.
- Ran `PYTHONDONTWRITEBYTECODE=1 python3
  Submissions/HardiKhushi/dashboard.py`: rebuilt the page from the relocated
  CSVs, without taking new measurements.
- A read-only Python verification checked both saved SHA-256 hashes, absence
  of the old top-level CSVs, 9 matching rows per CSV, and valid min/median/max
  ranges. All checks passed.
- Parsed the dashboard HTML: two SVG charts, nine data rows, all three local
  result/log links resolved, no unexpanded template tokens, and visible
  preliminary-data and 50% hit-rate labels. These are structural/data checks,
  not a claim of browser screenshot verification.
- Compiled Python source in memory to check syntax; required documentation
  files are present. Bytecode writing was disabled for verification runs.
- Git status reported the submission folder as untracked. Git also emitted
  sandbox warnings about temporary cache creation; no staging, commits, or
  uploads were performed. No course or other-submission files were changed.
- No benchmark execution or dependency installation occurred in this batch.
- Documentation was updated with these actual outcomes after verification.

### Generator walkthrough

For n=6 with unique IDs, the input is a shuffle of 0 through 5. Absent queries
are drawn from 6 through 11, so they cannot accidentally be present. A mixed
batch with q=4 has exactly two hits and two misses. For example, queries
`[3, 8, 0, 10]` would have answers `[True, False, True, False]`; this is an
illustration, not a claim about the exact seed-42 output. Holding these inputs
fixed across methods makes performance comparisons fair. The seed/settings
reproduce the data; the benchmark remains responsible for timing it later.

## 4. Test sensitivity demonstration (20 November 2026)

### Approval and purpose

The user approved temporarily running the existing search tests against a
function that always returns `False`, then documenting the outcome. The goal
was to show that the tests reject a known incorrect procedure before moving
on to manual search implementations. This is a later test-sensitivity check,
not evidence that the initial project followed tests-first development.

### Procedure

- Read the working agreement, tests, and existing logs.
- Ran one Python process with `PYTHONDONTWRITEBYTECODE=1`. Defined
  `wrong_search(ids, queries)` to return `[False for query in queries]`.
- Temporarily pointed `test_search.SEARCH_METHODS` at that function in memory.
  The actual search functions and test file were not edited.
- Ran the seven search test methods, captured their assertion failures, and
  restored the original registry in a `finally` block.
- Ran all 13 search/generator tests with the real implementations restored.
- Compared SHA-256 snapshots of every project file before and after execution.
  The snapshots matched, confirming no file contents changed during the demo.
- Updated only this log and `AI_USAGE.md` afterward. No benchmarks, dependency
  installation, commits, or uploads were performed.

### Observed outcomes and explanation

The deliberately wrong function caused **52 expected assertion failures and
zero execution errors** across seven test methods. Five methods rejected it:

| Test method | Failing subtests |
| --- | --- |
| `test_normal_search` | 1 |
| `test_single_element` | 1 |
| `test_unsorted_ids` | 1 |
| `test_duplicates_and_negative_ids` | 1 |
| `test_randomized_reference` | 48 |

These are subtest failures, not 52 separate test methods. For the normal example,
the expected answer was `[True, False, True]` while the wrong function returned
`[False, False, False]`. Empty IDs and empty queries correctly did not expose
this particular defect: always-False output happens to be right in those cases.
Two of the 50 randomized cases also had no hits and therefore passed.

After restoration, **all 13 real tests passed**. This provides evidence that
the suite catches this specific fault; it does not prove that all possible bugs
will be detected or that the current algorithms satisfy the manual-search rule.
Search code, tests, generator, dashboard, and saved measurements were unchanged.

### Reproducing the central check

The following command is documentation, not approval to run another batch.
From the repository root, it runs the same test substitution and restores it;
the original demonstration additionally hashed all files and ran the full suite.
Its failure summary is intentional.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import io
import sys
import unittest

sys.path.insert(0, 'Submissions/HardiKhushi')
import test_search

def wrong_search(ids, queries):
    return [False for query in queries]

original = test_search.SEARCH_METHODS
try:
    test_search.SEARCH_METHODS = {'always_false': wrong_search}
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_search.SearchTests)
    result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
finally:
    test_search.SEARCH_METHODS = original

assert not result.wasSuccessful() and not result.errors
print(result.testsRun, 'test methods;', len(result.failures), 'expected failures')
PY
```

## 5. Expanded experiment, efficiency revisions, and dashboard (20 November 2026)

### Authorization and scope

The user requested running all three methods on different data types, making
efficiency changes, saving timing/memory results, and moving into the dashboard
phase. This directly authorized the described implementation/measurement batch.
Write access was granted for this submission folder. Later commands, commits,
uploads, and Phase 2 work still require separate approval.

### Preserved history and actual development sequence

- Copied and hash-verified all 14 previous files to `archive/pre_revision/`;
  the manifest preserves source, tests, documentation, dashboard, and old CSVs.
- Wrote a first manual version in `search_original.py`, then ran the seven
  pre-existing search tests against it in memory: all passed before revision.
- Revised the manual methods in `search.py`. Linear search now stops at a hit;
  all methods avoid unnecessary defensive copies. Binary search is iterative;
  set answers use a list comprehension. Reasons/costs are in `REVISIONS.md`.
- Both manual versions are retained. The archived library-based version is
  historical evidence, not the manual original in the measured comparison.
- Added tests for binary boundaries/gaps, all-equal IDs/repeated queries, all
  generator scenarios/policies on two seeds, and repeated use of prepared state.
  Existing expected results were not weakened. The 17-method test suite passed
  against all six registered manual method/version variants.

### Executed experiment and saved evidence

- Executed `PYTHONDONTWRITEBYTECODE=1 python3
  Submissions/HardiKhushi/benchmark.py` once for the full default matrix.
- Run ID: `20261120T145013469725Z`; measured 14:50:13-14:50:43 UTC
  (15:50:13-15:50:43 Europe/Berlin), 20 November 2026.
- Source version: `c2b486377bb6f569785d1167e9a3bb05f80b5920706ac19837d7c0e71d00ef01`.
  Individual source hashes and uncommitted git state are in `environment.json`.
- Matrix: n=1,000/10,000/100,000; q=1/100; all-present/all-absent/mixed;
  unique/repeated IDs; seed 42. This is 36 workload combinations. Each is
  shared across original/revised linear, binary, and set methods (216 cases).
- All measured calls returned expected answers; inputs were unchanged.
- Five repeats per phase, with warm-up/calibration and adaptive short-call
  batching. Timing excludes generation, validation, tracing, printing, and UI.
  Preparation and total rebuild state per execution. Query-only repeats prepare
  outside timing, then reuse state within the repeat. Total is independently
  measured, so phase medians need not add to the total median.
- Saved `results/timing.csv` and `results/memory.csv`, plus 3,240 raw timing
  rows and 1,080 raw memory rows. Current and peak traced memory include
  preparation/output and exclude already-existing inputs. This is not RSS.
- Previous CSVs were copied unchanged to `results/history/legacy/` before
  replacement. Missing raw repeats from that old run were not reconstructed.

### Measured findings

Revised total medians were lower in 34/36 linear cases, 36/36 binary cases,
and 36/36 set cases. Median original/revised time ratios across workloads were
1.718x, 1.053x, and 1.282x respectively. Revised median peak allocation was
lower in all 36 workloads per method. Two linear timing regressions remain in
the data; a revision is not assumed to win universally.

For 100,000 unique IDs and 100 mixed queries, revised measurements were:

| Method | Median total ms | Median peak KiB |
| --- | --- | --- |
| Linear | 36.53125 | 0.84 |
| Binary | 7.98204 | 1171.71 |
| Set | 0.67702 | 6144.21 |

These show a time/memory trade-off on one machine/seed. Version runs are
sequential; scheduling, cache warmth, and allocator state can affect ratios.
No confidence intervals or general fastest-method claims are made. Full
findings are generated in `results/SUMMARY.md` from the CSVs, not handwritten.

### Dashboard and verification

- Built an offline interactive dashboard from saved data: query scenario,
  query count, duplicate policy, preparation/query/total phase, and linear/log
  vertical scale. Original curves are dashed, revised curves solid. The table
  shows all timing phases and current/peak memory, with raw-data downloads and
  environment details. Filtering never invokes a benchmark.
- Added `dashboard_template.html`; `dashboard.py` validates matching case IDs,
  run/code identity, and embeds saved data. It also generates `SUMMARY.md`.
- Added/executed `verify_results.py`: all 216 cases and all raw repeats present;
  every batching division, median/min/max, workload combination, run/source
  identity, historical archive hash, and dashboard link passed checks.
- Exercised all 72 filter combinations in actual headless Chrome at 1,440px
  and 500px widths. Checked row/series/point counts, table numbers against
  saved values, finite chart coordinates, fresh filter state, and no horizontal
  page overflow. Both widths passed; screenshots were inspected visually.
- Chrome enforced a minimum 500px viewport, so a requested 390px capture was
  replaced by a verified 500px capture; narrower widths are not claimed tested.
  Early CLI launches aborted; reusing the existing temporary profile succeeded.
- Browser outcomes are saved as `results/qa/<run-id>.json`. Temporary profiles,
  test DOM, and screenshots stay in ignored `.preview/` inside this project.
- A shell here-document encountered a sandbox temp-file restriction while
  creating the verifier; a file patch completed the write instead. Several
  documentation patch attempts were rejected on context mismatch without
  applying changes; corrected patches succeeded. No measurements were rerun
  in response to documentation or browser-tool issues.
- Updated README, working instructions, AI disclosure, result provenance, and
  this log. No third-party dependencies, course edits, commits, or uploads.

## 6. Local checkpoint commit (20 November 2026)

### Approval and final checks

The user approved the proposed final checks, documentation update, and a local
commit limited to `Submissions/HardiKhushi/`, with the message
`Add search revisions, benchmark results, and interactive dashboard`.
No push was authorized. Write access was granted for this folder and `.git`.

- Checked repository status and the existing index: only this submission was
  untracked and no unrelated changes were already staged.
- Reran all 17 tests: passed. Reran `verify_results.py`: all 216 configurations,
  3,240 timing samples, 1,080 memory samples, summary calculations, source/archive
  hashes, and dashboard links passed.
- Reviewed source and staged paths; no files outside this folder were staged.
  Confirmed `.preview/` is ignored, so browser profiles, screenshots, and clean
  export verification files are excluded from the commit.
- Initial `git diff --cached --check` flagged standard CSV CRLF endings and
  original whitespace in the immutable archive. Added local `.gitattributes`:
  preserve exact bytes across checkout platforms, recognize CSV CRLF, and
  exempt archived original whitespace. The check then passed, with no changes
  to measured source, results, or historical snapshot bytes.
- Exported the staged tree to a fresh ignored directory using `checkout-index`;
  verified all 42 staged submission files against their Git index blobs.
- In that clean export, all 17 tests and saved-results verification passed.
  Dashboard/report regeneration was byte-identical to the saved outputs.
  Benchmark `--help` and a small generator preview also worked.
- This was clean staged-content verification, not a remote clone or a new
  machine. No full benchmark rerun or new browser session was necessary.
- Updated README, working instructions, AI disclosure, and this log with the
  actual approval/check outcomes before creating the checkpoint commit.

This entry travels inside the authorized commit. Its own hash is intentionally
not embedded in its contents: retrieve it with `git log` or `git rev-parse HEAD`
after creation. A commit records a local snapshot; pushing would be a separate
explicitly approved action. The assistant's final response reports the actual
commit result and post-commit status.

## 7. Authorized GitHub push and fork publication (20 November 2026)

- User request: "Push it then", authorizing publication of checkpoint `3ba5b42`.
  The preceding checkpoint committed 42 files entirely within this folder;
  repository status was clean before publication.
- Confirmed current branch `main`, upstream `origin/main`, and remote
  `https://github.com/cogeorg/AlgorithmsFinance.git`. Network/write permissions
  were granted for this publishing batch.
- `git push origin main` failed with HTTP 403: GitHub account `khushihardi`
  has no direct write access to the course repository. No force push or remote
  permission changes were attempted.
- No GitHub CLI was installed. A public API lookup found no accessible fork.
  Python's HTTP client encountered a local certificate-chain error; system
  curl performed subsequent requests with standard certificate verification.
- Used Git's existing credential helper privately for GitHub API authentication.
  No credential was printed, stored in project files, or passed in command-line
  arguments. GitHub returned account `khushihardi` and accepted creation of
  `khushihardi/AlgorithmsFinance` as a fork of `cogeorg/AlgorithmsFinance`.
- Added remote `fork` without changing `origin`. Created local branch
  `submission/hardi-khushi` from `3ba5b42` and executed
  `git push -u fork submission/hardi-khushi`: succeeded.
- The published checkpoint is at
  <https://github.com/khushihardi/AlgorithmsFinance/tree/submission/hardi-khushi/Submissions/HardiKhushi>.
  Its branch tracks `fork/submission/hardi-khushi`; local `main` retains the
  original checkpoint. A course pull request remains a separate next step.
- Updated AGENTS, README, AI usage, and this progress log to record the
  publishing result and the fork workflow. A documentation-only follow-up
  commit accompanies the checkpoint on the same publication branch. The final
  response reports its actual push outcome after remote verification.
- No source, tests, CSV values, environment metadata, archives, or dashboard
  behavior changed, so no new measurements or test reruns were needed.

## Assignment status and remaining work

- [x] Keep all work in the student's submission folder.
- [x] Document AI assistance, corrections, and command-approval rules.
- [x] Cover required search edge cases with a common test suite.
- [x] Separate synthetic data generation and record its settings for future runs.
- [x] Demonstrate that tests fail on a deliberately wrong procedure (entry 4).
  The initial tests-before-implementation sequence was not recorded and must
  not be claimed retroactively.
- [x] Implement manual linear and binary search; explanations in `REVISIONS.md`.
- [x] Preserve original/revised manual versions and justify revisions.
- [x] Expand experiments to n = 1,000/10,000/100,000 and q = 1/100, with all
  three query scenarios and both documented duplicate policies.
- [x] Separate preparation, complete query-batch time, and combined elapsed
  time; keep fresh preparation state per repeat and raw repeat values. Batch
  very short operations and divide by the number of executions as needed.
- [x] Record source version alongside environment and generator settings; preserve
  old results before new measurements.
- [x] Retain current and peak traced memory with clear inclusion boundaries.
  Process RSS is optional and was not measured.
- [x] Extend the dashboard to preparation/query/total time, original/revised
  curves, workload settings, raw repeats, environment, and memory tables.
- [x] Verify tests, saved results, dashboard rebuild, and CLI entry points from
  a clean staged export; authorize a local checkpoint commit (entry 6).
- [ ] Rerun the full experiment from a fresh clone before final submission if
  requested, and identify the final commit to be audited.
- [x] Publish the checkpoint to the student's fork after explicit approval.
- [ ] Open a pull request for integration into the course repository if requested.
  Docker remains optional.
- [ ] Phase 2: audit another student's fixed commit and separate reproduced
  bugs from suspected weaknesses using reproducible evidence.

## Next proposed step (not authorized by this log)

The dashboard phase now has a working implementation and saved evidence. Review
the dashboard with the student: begin with mixed/100 queries/unique IDs/total,
then switch to one query, absent queries, preparation, and memory comparisons.
Explain why the preferred method changes when preparation or memory matters.
Offer a small manual algorithm trace if desired. Course integration needs a
pull request from the published fork branch; none has been opened. That step,
a final fresh-clone benchmark check, further commits, and subsequent pushes
need a new approved batch. Phase 2 audit has not begun.
