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

## Assignment status and remaining work

- [x] Keep all work in the student's submission folder.
- [x] Document AI assistance, corrections, and command-approval rules.
- [x] Cover required search edge cases with a common test suite.
- [x] Separate synthetic data generation and record its settings for future runs.
- [x] Demonstrate that tests fail on a deliberately wrong procedure (entry 4).
  The initial tests-before-implementation sequence was not recorded and must
  not be claimed retroactively.
- [ ] Implement manual linear and binary search; trace small examples together.
- [ ] Preserve original/revised algorithm versions and justify a revision.
- [ ] Expand experiments to n = 1,000/10,000/100,000 and q = 1/100, with all
  three query scenarios and a documented duplicate policy. Current defaults
  still describe the small preliminary experiment, not the final matrix.
- [ ] Separate preparation, complete query-batch time, and combined elapsed
  time; keep fresh preparation state per repeat and raw repeat values. Batch
  very short operations and divide by the number of executions as needed.
- [ ] Record code version alongside environment and generator settings; preserve
  old results before new measurements.
- [ ] Retain current and peak traced memory with clear inclusion boundaries.
  Existing output retains peak only; process RSS is optional.
- [ ] Extend the dashboard to preparation/query/total time, original/revised
  curves, workload settings, raw repeats, environment, and memory tables.
- [ ] Verify exact commands from a fresh checkout and record a commit for audit.
- [ ] Upload only after explicit approval. Docker remains optional.
- [ ] Phase 2: audit another student's fixed commit and separate reproduced
  bugs from suspected weaknesses using reproducible evidence.

## Next proposed step (not authorized by this log)

Walk through a manual linear search on a small example. Before changing code,
obtain approval to preserve the current implementation as a clearly labelled
library-based baseline, implement manual linear search, run the unchanged tests,
and update the documentation. A library-based baseline is historical evidence;
it does not replace the required original/revised manual algorithm comparison.
Binary search remains a separate learning step. Ask before further commands
or edits, and do not regenerate measurements for this step.
