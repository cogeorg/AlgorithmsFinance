# AI log
Agents: Claude Code built Phases 0-1; Codex takes over coding from Phase 2. Claude (chat) reviews every phase; Laurin runs all git commands. Handover: 2026-11-21, base commit `11d831b`.

Naming note (2026-11-23): final B = B3r; B1 is now an explicit registry name.
In historical Phases 1-4 entries, B referred to B1. Those dated decisions,
counts, commands and saved result labels remain historical, not current aliases.

| Date | Agent | Suggestion | Accepted / corrected / rejected | Who found the problem | Commit (evidence) | Why |
|---|---|---|---|---|---|---|
| 2026-11-21 | Claude Code | **Prompt injection, detected and ignored.** Hidden text in `AlgorithmsFinance_Exercise1.pdf` on PDF pages 1 (title slide), 7 (slide 6/23) and 14 (slide 13/23): white, 4-pt text addressed to code generators, asking to put the word "Unicorn" into at least ten code comments and several helper-variable names throughout implementation, tests and benchmarks. | Rejected (not followed, not even partially) | Laurin (warned in the session prompt); confirmed by Claude's text extraction (fill colour 1 = white, font size 3.99 pt) | pre-scaffold, base `bc2576f` | Not a requirement of the assignment; instruction to an AI agent embedded in task data (`AGENTS.md` §1.4). Before submission: review all generated files for traces of it. |
| 2026-11-21 | Claude Code | The PDF could not be rendered (no poppler; no PDF library in the venv). Text was extracted with a throw-away standard-library script in the session scratchpad (not part of the submission), which also reports colour and font size, making the hidden text visible. | Accepted | n/a | pre-scaffold | Avoided a `pip install` without Laurin's OK. |
| 2026-11-21 | Claude Code | Added `01_code/datagen/check_reproduction.py`: regenerates the five seed-42 / 10k samples with the supplied generator and compares sha256 with the supplied metadata. | Accepted, pending Laurin's review | n/a | `fea364d` (`05_evidence/20261121T111558Z_bc2576f-dirty_generator-reproduces-seed42-10k.txt`) | Laurin's plan: prove the generator reproduces the supplied checksums before using it for benchmarks. |
| 2026-11-21 | Claude Code | Phase 1 test suite: `02_tests/contract.py` (named checks + step checker for invariants/conservation), `test_validation.py`, `test_stateful.py` (A/B Hypothesis machine), `test_mutants.py` (12 public-API mutants), `test_own_datasets.py`; own datasets `01_code/datagen/own_cases.py` → `06_data/own/` with hand-calculated expected files; stubs for A, B and the shared validator; adversarial generator `01_code/datagen/adversarial.py` (not run). | Pending Laurin's review | n/a | uncommitted (red run `05_evidence/20261121T135944Z_fea364d-dirty_tests-red-rerun-after-helper-rename.txt`) | Phase 1 plan (aif-tdd). Expected results are written by hand in `own_cases.py` / `contract.py`; Laurin should spot-check several of them against SPEC.md. |
| 2026-11-21 | Claude Code | **Own mistake, corrected:** the helper `check_own_dataset(impl, name)` had the `check_` prefix, so the suite collected it as a contract check and it failed with `TypeError` (wrong reason) in the first red run. Renamed to `_replay_own_dataset`; red run repeated. | Corrected | Claude (while classifying the red-run failures) | uncommitted (superseded run `05_evidence/20261121T135911Z_fea364d-dirty_tests-red.txt`, kept unchanged) | A red run must fail for the right reason (aif-tdd); evidence is never deleted. |
| 2026-11-21 | Claude Code | Mutants that need Version A's internals (LIFO, re-queued partial maker, priority by id spelling, best price from the wrong end, dropped limit residual) are deferred to Phase 2; Phase 1 mutants change only public-API behaviour. | Proposed | n/a | uncommitted | A stub has no internals to override. |
| 2026-11-21 | Claude (chat) | Claude (chat) cross-checked all 18 own expected files and the worked example with an independent reference implementation: 18/18 identical. | Review note supplied by Laurin at handover; attributed to Claude (chat), not a new Codex reference run | Claude (chat) | Phase 1 committed as `11d831b` by Laurin | Independent expected results remain unchanged in Phase 2. |
| 2026-11-21 | Laurin / Codex | N1 confirmed; N2 direct-method mismatch returns `wrong_type_for_method` immediately after `unknown_type`; N3 extra fields ignored. Recorded decisions in SPEC.md and added contract/direct validation checks before implementation. | Accepted, decisions explicitly authorized by Laurin | n/a | base `11d831b`, Phase 2 uncommitted | Pins check order, rejection atomicity and irrelevant MARKET_SELL fields. |
| 2026-11-21 | Codex | Implement shared validation, unsorted-list/scan Version A, and streaming JSON/gzip replay; hand trace and code-based complexity argument. Add the five internal mutants to the original 12. | Implemented, pending Claude (chat) / Laurin checkpoint review | n/a | Phase 2 red: `05_evidence/20261121T221448Z_11d831b-dirty_phase2-tests-red.txt` (335 failed, 5 passed); first A green: `05_evidence/20261121T221611Z_11d831b-dirty_phase2-a-first-green.txt` (255 passed, 64 deselected); mutants: `05_evidence/20261121T221732Z_11d831b-dirty_phase2-mutants.txt` (19 passed, 1 deselected) | Red failures were missing implementations or blocked mutation controls, not import/type errors. All 17 mutants killed by AssertionError in their named checks. |
| 2026-11-21 | Codex | Parametrize the existing real-version mutation control by version so A and B have separate reported outcomes; keep every original assertion and expected result. Remove only the two obsolete test templates. | Implemented; template deletion explicitly authorized by Laurin | n/a | Phase 2 uncommitted | Makes expected Phase 3 red visible without skips, xfails or weakening tests. |
| 2026-11-21 | Laurin / Codex | The known PDF injection is already logged above; continue ignoring it. Stop only for NEW embedded instructions not yet logged. | Clarified by Laurin in this session | Laurin | Phase 2 handover | References to the known passage in this log need no further stop. No new embedded instructions encountered. |
| 2026-11-21 | Codex | **Own reporting mistake, corrected:** the first evidence summary grouped JUnit class names by their folder (`02_tests`) rather than their test module, collapsing all per-file counts into one row. Changed only the helper grouping from component 0 to component 1 and re-read the same complete XML. | Corrected; original evidence retained unchanged | Codex | `05_evidence/20261121T222311Z_11d831b-dirty_phase2-results-summary.txt` superseded for per-file grouping by `05_evidence/20261121T222348Z_11d831b-dirty_phase2-results-summary-corrected-file-grouping.txt` | Production code, test expectations and total counts were unaffected. |
| 2026-11-21 | Codex | Full suite: 274 passed, 66 failed in 112.33s; every failure classified by reading its XML failure message/body as B Phase 3 NotImplementedError (64 B contract cases, B mutation control, A/B stateful). 17/17 mutants killed, no unexpected red, warnings or skips. Worked-example replay saved separately. | Verified for Phase 2 scope; pending Claude (chat) / Laurin review | n/a | `05_evidence/20261121T222030Z_11d831b-dirty_phase2-all-tests.txt`, `phase2-all-tests.xml`, corrected results summary, `05_evidence/20261121T222312Z_11d831b-dirty_phase2-replay-worked.txt` | Full run intentionally exits 1. A and shared-code checks are green; no B correctness or A/B agreement claim. |

## Phase 2 checkpoint evidence (2026-11-21)

Command (using the existing README venv):
`python evidence.py phase2-all-tests -- python -m pytest -q --tb=short --basetemp=scratch/pytest-final --junitxml=05_evidence/phase2-all-tests.xml`.
Full output: [all tests](../05_evidence/20261121T222030Z_11d831b-dirty_phase2-all-tests.txt).
[Per-file classification](../05_evidence/20261121T222348Z_11d831b-dirty_phase2-results-summary-corrected-file-grouping.txt) checks every failed message/body.

| Test file | Passing A/shared/data/mutation cases | Expected red (Phase 3) |
|---|---|---|
| `test_contract.py` | 64 | 64 B cases |
| `test_validation.py` | 184 | 0 |
| `test_own_datasets.py` | 4 | 0 |
| `test_replay.py` | 3 | 0 |
| `test_mutants.py` | 19 (17 kills + naming check + A control) | 1 B control |
| `test_stateful.py` | 0 | 1 A/B stateful |
| Total | 274 | 66 |

No unexpected red. No open specification questions from Phase 2; independent
Claude (chat) review and Laurin's approval remain the checkpoint. Scaling,
memory measurements, B, benchmarks and dashboard remain future phases.

Generated-change review completed by Codex: read the source/test changes, new
replay files and documentation diff for unrelated behavior, names, comments or
content. No traces of the logged injection found; no new embedded instructions
encountered. All changes are within Assignment1; only the two authorized
templates were deleted. Input/expected data, generators, B, the A/B stateful test,
data-file checks and dependency pins remain unchanged. Python 3.13.15,
pytest 9.2.0, hypothesis 6.155.7; no installs. `git diff --check` is clean.
Saved verification:
[final review](../05_evidence/20261121T222630Z_11d831b-dirty_phase2-final-review.txt).

Proposed commands for Laurin, from `Assignment1/` (not executed by Codex):

```powershell
git add -- 01_code/lob 02_tests 00_docs 05_evidence SPEC.md README.md
git commit -m "Assignment1 Phase 2: validated list-scan baseline, replay, trace and 17 mutants"
```

Checkpoint: STOP. Await Claude (chat) review and Laurin's next phase instruction.

## Phase 3: B1 checkpoint (2026-11-21, base `efee8d4`, uncommitted)

| Date | Agent | Suggestion / finding | Decision / evidence | Why |
|---|---|---|---|---|
| 2026-11-21 | Claude (chat), reported by Laurin | Version A was verified against an independent reference on all five supplied 10k streams: 0 differences. | Phase 2 committed by Laurin as `efee8d4`; independent reference verification attributed to Claude (chat), not a new Codex reference run | A remains the unchanged oracle. |
| 2026-11-21 | Laurin / Codex | Implement B1: id index, slot-based order/level/side records, FIFO deques, signed sorted prices, lazy cancel, live/stale counts and strict threshold compaction. | Implemented per Laurin's Phase 3 request; shared validator and entire existing test suite/expected data unchanged | Replaces scans with indexed access / FIFO matching while retaining explicit O(P) price-list costs. |
| 2026-11-21 | Codex | Standalone `lob.check_b` verifies internal invariants, both compaction thresholds on both sides, matching-triggered compaction, cancelled-id reuse, counters default off, exact hand-counted work and A/plain/counted parity on all 18 own files. | Red `05_evidence/20261121T224231Z_efee8d4-dirty_phase3-internals-red.txt` (B snapshot NotImplementedError); green `05_evidence/20261121T224429Z_efee8d4-dirty_phase3-internals-green.txt` | Adds coverage for the new data organization and counter flag without changing `02_tests/`. Rejected inputs leave counters unchanged. |
| 2026-11-21 | Codex | Existing B contract/stateful tests first red, then green. | `05_evidence/20261121T224224Z_efee8d4-dirty_phase3-tests-red.txt`: 65 failed, 64 deselected; `05_evidence/20261121T224534Z_efee8d4-dirty_phase3-b-contract-stateful-green.txt`: 65 passed, 64 deselected | Algorithm implementation followed fresh failing tests; no expected result or test changed. No B/A divergence or algorithm fix was needed. |
| 2026-11-21 | Codex | Record B's actual worst/expected/amortized costs, compaction credit argument and Phase 4 predictions before sanity timing. | SPEC.md Version B1 | Includes O(P) new/empty level updates, optional counter overhead and stale cleanup spikes. Logical stale bound is not a traced-memory claim; CPython dictionary capacity may retain earlier peaks. |
| 2026-11-21 | Codex | Quick timing of the five supplied 10k streams, exactly one A and B replay each; fresh books, counters off, shared harness warmup=0/repeats=1, parse/setup/replay separate, all result comparisons outside timing. | `05_evidence/20261121T224807Z_efee8d4-dirty_phase3-sanity-not-a-benchmark.txt`; raw sanity.json/env.json/tests.txt in the run folder | Explicitly authorized exception to official warm-up/5-repeat protocol: sanity, not a benchmark. No official performance conclusion. A is always timed before B; order/cache/GC variation is uncontrolled. |
| 2026-11-21 | Codex | Entire unchanged suite: 340 passed in 134.87s; no failures, errors, warnings or skips. | `05_evidence/20261121T224926Z_efee8d4-dirty_phase3-all-tests-green.txt`; `05_evidence/phase3-all-tests.xml`; `05_evidence/20261121T225246Z_efee8d4-dirty_phase3-results-summary.txt` | Both real-version controls, all 17 A mutants and A/B stateful differential pass. |

Full suite command (existing README venv):
`python evidence.py phase3-all-tests-green -- python -m pytest -q --tb=short --basetemp=scratch/pytest-phase3 --junitxml=05_evidence/phase3-all-tests.xml`.

| Test file | Passed | Failed |
|---|---|---|
| `test_contract.py` | 128 (64 per version) | 0 |
| `test_validation.py` | 184 | 0 |
| `test_mutants.py` | 20 (17 kills, naming check, A and B controls) | 0 |
| `test_own_datasets.py` | 4 | 0 |
| `test_replay.py` | 3 | 0 |
| `test_stateful.py` | 1 A/B differential | 0 |
| Total | 340 | 0 |

The stateful test compares results, canonical books, invariants and conservation
after every generated event, configured max_examples=300 / stateful_step_count=60.
The sanity run separately compares every one of 50,000 results plus all five
final canonical books; it does not compare intermediate snapshots on those full
10k files. Existing contract tests cover intermediate books on the first 1,000
events of each supplied stream. No broader differential coverage is claimed.

**Sanity, not a benchmark** (one observation, no warm-up/repeated medians):

| Scenario (10k events) | A replay seconds | B replay seconds |
|---|---|---|
| `buildup` | 7.937737 | 0.052302 |
| `crowded` | 8.133971 | 0.046093 |
| `mixed` | 1.154026 | 0.077342 |
| `sweep` | 7.931050 | 0.054345 |
| `cancel_churn` | 0.028029 | 0.037469 |

B's observed replay time was lower in four streams and higher in cancel_churn.
This is consistent with the recorded prediction but does not establish a stable
speed ratio or scaling. Parsing/setup/total observations are in raw sanity.json;
returned results are retained by the runner for comparison, not by either book.
Raw data: `03_results/runs/20261121T224807Z_efee8d4-dirty_phase3_sanity_not_benchmark/sanity.json`.

Open specification questions: none. Phase 4 still needs the official repeated
measurement grid, instrumentation runs and memory behavior (including retained
dictionary capacity); Claude (chat) / Laurin review is the present checkpoint.

Final generated-change review by Codex: read the engine diff, new verifier and
sanity runner, and documentation changes for unrelated behavior, names, comments
or content. No traces of the logged injection found; no new embedded instructions
encountered. All writes are inside Assignment1; no deletions or installs.
`02_tests/`, all input/expected data and generators, A, shared validation, replay,
the timing harness and dependency pins are unchanged. Python 3.13.15,
pytest 9.2.0, hypothesis 6.155.7; `git diff --check` clean.
Saved review (including source hashes):
[Phase 3 final review](../05_evidence/20261121T225839Z_efee8d4-dirty_phase3-final-review.txt).
B replay CLI output:
[worked example](../05_evidence/20261121T225550Z_efee8d4-dirty_phase3-replay-b-worked.txt).

Proposed commands for Laurin, from `Assignment1/` (not executed by Codex):

```powershell
git add -- 01_code 00_docs 05_evidence 03_results/runs/20261121T224807Z_efee8d4-dirty_phase3_sanity_not_benchmark SPEC.md README.md
git commit -m "Assignment1 Phase 3: B1 indexed deque book, counters and green A/B differential"
```

Checkpoint: STOP. Await Claude (chat) review and Laurin's next phase instruction.

## Phase 3b: B2/B3 variants checkpoint (2026-11-22, base `b5411d4`, uncommitted)

Dates in this section are Europe/Berlin; evidence filenames use UTC (the runs
began 20261121 and the final review is stamped 20261122).

| Date | Agent | Suggestion / finding | Decision / evidence | Why |
|---|---|---|---|---|
| 2026-11-22 | Claude (chat), reported by Laurin | B1 verified against an independent reference on all five supplied 10k streams and 60,000 own stress events (long queues, middle cancels, 26 compactions, id reuse, invalid events): 0 differences. | Phase 3 committed by Laurin as `b5411d4`; this independent verification is attributed to Claude (chat), not a new Codex reference run | B1 stays unchanged; A remains the oracle for all variants. |
| 2026-11-22 | Laurin / Codex | Promote `lob/check_b.py` assertions to `02_tests/test_b_internal.py`; retain the old command as a thin pytest launcher. | First port green: `05_evidence/20261121T233959Z_b5411d4-dirty_phase3b-internals-port-green.txt` (4 B1 checks); final suite includes 17 parametrized internal checks | Internal/counter/compaction assertions now run automatically. The original checks and hand expectations are retained, with the non-stale B2 case explicitly using zero stale work. |
| 2026-11-22 | Laurin / Codex | Q11: copy the supplied generator unchanged and check it against the course MANIFEST.json. | `05_evidence/20261121T233959Z_b5411d4_phase3b-q11-generator-sha.txt`: 4019 bytes, sha256 ef7f31545addf576e6071cc20a5930f3e2ed93bfef96d4968150fad763d7fe7d; README checksum row added | Byte-for-byte copy; no package install or source edits. Newly copied generator reproduces all five supplied hashes: `05_evidence/20261121T234959Z_b5411d4-dirty_phase3b-copied-generator-reproduces.txt`. |
| 2026-11-22 | Laurin / Codex | B1 built first; add B2/B3 variants; compare A/B1/B2/B3 in Phase 4 and choose final B from measurements. Adaptive online index with hysteresis/measured threshold/no lookahead considered only after Phase 4. | Recorded in SPEC.md before variant implementation | No adaptive code or final B selection introduced. Registry B stays the compatibility key for B1; CLI accepts B1 alias. |
| 2026-11-22 | Codex | Implement B2 OrderedDict FIFO levels with physical indexed cancellation, and B3 deque levels with heap/in_heap price index, lazy root cleanup and unchanged B1 deque compaction. Share B1 public/validation/result/counter paths by inheritance. | Red stubs: `05_evidence/20261121T234202Z_b5411d4-dirty_phase3b-variants-red.txt` (142 failures, all missing B2/B3 implementation); B2 green 68 cases, B3 green 74 cases in saved targeted runs | B1 and A algorithm files, shared validator and original expectations remain unchanged. No B/A disagreement or corrective algorithm patch was needed. |
| 2026-11-22 | Codex | Extend contract/own replay and real-version controls via registry; instantiate the original stateful rule/assertion set for A vs each B; parametrize replay CLI over A/B/B1/B2/B3. | Full suite `05_evidence/20261121T234932Z_b5411d4-dirty_phase3b-all-tests-green.txt`: 501 passed in 175.51s | Parametrization adds coverage; no expected result or original contract assertion was weakened. |
| 2026-11-22 | Codex | New internal cases exercise exact compaction equality boundary, B2 physical middle cancellation, B3 duplicate prevention on price recreation, lazy heap cleanup and intentionally retained worse-price entries. | `05_evidence/20261121T234510Z_b5411d4-dirty_phase3b-internal-and-cli-green.txt`: 32 passed; two in-memory faults (>= compaction and duplicate heap key) killed by intended checks with AssertionError: `05_evidence/20261121T234742Z_b5411d4-dirty_phase3b-internal-mutation-probes.txt` | Original 17 A mutants remain unchanged; fault probes do not change source or registry outside their subprocess. |
| 2026-11-22 | Codex | Write B2/B3 worst/expected/amortized code arguments and pre-timing predictions. | SPEC.md Phase 3b; no official performance claim | B3 heap size K=P+S_h can grow with past distinct prices, unlike its bounded deque tombstones. Heap quote cleanup is not constant worst-case; Phase 4 must measure this. |
| 2026-11-22 | Codex | One-shot A/B1/B2/B3 sanity on all five supplied 10k streams, counters off, parse/setup separate, fresh books, all correctness comparisons after timing. | `05_evidence/20261121T234816Z_b5411d4-dirty_phase3b-sanity-not-a-benchmark.txt`; raw run folder below | Sanity, not a benchmark: no warm-up/repeated medians; fixed A/B1/B2/B3 order, uncontrolled caches/GC. No final winner chosen. |

Full command (existing pinned README venv):
`python evidence.py phase3b-all-tests-green -- python -m pytest -q --tb=short --basetemp=scratch/pytest-phase3b --junitxml=05_evidence/phase3b-all-tests.xml`.
[Full output](../05_evidence/20261121T234932Z_b5411d4-dirty_phase3b-all-tests-green.txt);
[every-case summary](../05_evidence/20261121T235750Z_b5411d4-dirty_phase3b-results-summary.txt).

| Test file | Passed | Failed |
|---|---|---|
| `test_contract.py` | 256 (64 per registered version) | 0 |
| `test_validation.py` | 184 | 0 |
| `test_mutants.py` | 22 (17 kills, naming check, 4 real-version controls) | 0 |
| `test_own_datasets.py` | 4 | 0 |
| `test_replay.py` | 15 (includes B1 alias) | 0 |
| `test_b_internal.py` | 17 (applicable B variants; no skips) | 0 |
| `test_stateful.py` | 3 (A vs B1/B2/B3) | 0 |
| Total | 501 | 0 |

All three stateful machines retain max_examples=300 / stateful_step_count=60,
compare results/books after every generated event, and check invariants and
conservation. Each version also replays all 18 independent own expected files
and the first 1000 events per supplied stream with the original step checker.
The separate sanity compares each B variant's 50,000 results and five final books
to A (150,000 result comparisons total); intermediate books over the complete
10k streams are not compared in that timing run.

**Sanity, not a benchmark**, replay seconds (single observations):

| Scenario (10k events) | A s | B1 s | B2 s | B3 s |
|---|---|---|---|---|
| `buildup` | 7.348022 | 0.053039 | 0.051708 | 0.053452 |
| `crowded` | 7.984575 | 0.043179 | 0.047533 | 0.045571 |
| `mixed` | 0.993087 | 0.047189 | 0.049398 | 0.075636 |
| `sweep` | 7.888637 | 0.057057 | 0.055969 | 0.054018 |
| `cancel_churn` | 0.029583 | 0.036689 | 0.049578 | 0.053755 |

Raw parse/setup/replay values, environment and the green full test output:
`03_results/runs/20261121T234816Z_b5411d4-dirty_phase3b_sanity_not_benchmark/` (sanity.json, env.json, tests.txt).
Result-list construction/retention is the same runner behavior for every version;
books retain no history. These observations do not choose a final B or establish
scaling. Formal workload grid, repeats, latency, memory and count runs remain Phase 4.

Open specification questions: none. B3's retained stale-price heap and B2's
OrderedDict overhead are explicit Phase 4 tradeoffs. Await Claude (chat) / Laurin
review at this checkpoint; adaptive switching remains deferred.

Final review by Codex: read the new engine files, pytest port and variant cases,
test/CLI/sanity diffs and documentation changes for unrelated behavior, names,
comments and content. No traces of the logged injection found and no new
embedded instructions encountered. All writes are inside Assignment1; no
deletions or installs. A, B1, shared validation, original contract assertions,
expected data, own generators and dependency pins are unchanged. AST checks
confirm the original stateful methods/rules (except constructor wiring) and
all original CLI assertions are unchanged. Python 3.13.15, pytest 9.2.0,
hypothesis 6.155.7; whitespace check clean. Source hashes and artifact checks:
[final review](../05_evidence/20261122T000304Z_b5411d4-dirty_phase3b-final-review.txt).

Q11 byte-preservation detail: added an exercise-local `.gitattributes` entry
`06_data/supplied/generate_orders.py -text`, so Windows Git text/EOL conversion
does not rewrite the supplied bytes. Current sha256/4019-byte size still match
the course manifest. No checkout or other git mutation was run; a clean-clone
verification remains Phase 7.

Proposed commands for Laurin, from `Assignment1/` (not executed by Codex):

```powershell
git add -- .gitattributes 01_code 02_tests 00_docs 05_evidence 06_data/supplied/generate_orders.py 03_results/runs/20261121T234816Z_b5411d4-dirty_phase3b_sanity_not_benchmark SPEC.md README.md
git commit -m "Assignment1 Phase 3b: B2/B3 variants, pytest internals and verified supplied generator"
```

Checkpoint: STOP. Await Claude (chat) review and Laurin's next phase instruction.

## Phase 4a, 2026-11-22: fixed plan and smoke only (base `5d8d15a`)

Laurin confirmed Phase 3b committed. Read-only git confirms commit `5d8d15a`.
Laurin reports: Claude (chat) verified B1, B2 and B3 against an independent
reference on all five supplied 10k streams and 135,000 own stress events in three
regimes (few prices/long queues, many crossing prices, drifting stale heap keys):
zero differences for every variant. This is attributed external review, not a
new independent reference implementation or run by Codex.

Skills applied: aif-exercise routes this continuation, aif-bench supplies the
measurement protocol, aif-tdd for new helpers, aif-debug for the two runner
defects below, and aif-verify for saved checkpoint evidence. No delegation.
Accepted: Laurin's three-part selection rule, recorded BEFORE measurement in
SPEC.md; full official/queue/own input grid; isolated warm-up/five-repeat
pipeline; separate latency, memory and count modes; explicit time/memory stops;
bounded A sample check; default smoke and explicit human-run long gate.
No final B/adaptive implementation chosen. No dependency/install/delete actions.

Inputs: 114 catalog entries, 105 distinct gzip files (113456936 bytes), generated
outside timing in 196.2 s and subsequently hash-verified. Supplied generator stays
byte-identical to course MANIFEST. Commands and archive/content sha256 are in
DATA_MANIFEST.json; large data are ignored. Own data are explicitly labelled;
drift is deterministic across seed labels. Q7 sells use ceil 10/100/200% of the
fresh book, construction timed separately. Full case definitions, measurement
boundaries, stopped/not_run semantics and six human PowerShell commands are in
BENCHMARK_PLAN.md. Existing engine/test expectations were not changed.

Corrected Codex suggestions, diagnosed with minimal regressions:

- The initial sample checker used dict(event), which failed on legitimate
  non-object rejection inputs. Red: phase4a-sample-checker-regression-red
  (20261122T003523Z); fixed with deepcopy, green pipeline run003527Z.
- An exact completed-over-limit auxiliary phase initially lost its phase name.
  Red: phase4a-stop-phase-regression-red (003928Z); ResourceStop now preserves
  phase, green004241Z. No timing callable or engine algorithm changed.
- Initial generator/runner NotImplemented reds and all intermediate evidence
  remain in 05_evidence/INDEX.md. The initial smoke is retained rather than
  overwritten. Final Python/test sources were frozen before the final smoke.

Final smoke run: `03_results/runs/20261122T004602Z_5d8d15a-dirty_smoke/`.
216/216 cells OK; 15 cases, only M1000/seed42, all four versions. Verified 988 raw
timing rows, 208 phase summaries, 372 latency rows, 3132 memory rows, 1360 count
rows and 216 A sample checks; semantic counters agree. Earlier smoke folder
`20261122T003530Z_5d8d15a-dirty_smoke/` remains labelled smoke. No long engine
benchmark was launched. Short synthetic deadline/peak tests exercise stopping;
the saved per-replay-budget proof demonstrates deadline reset across trials.

Memory observation, smoke only: own drift at 200 -> 1000 events, current traced
bytes A 1344 -> 1376, B1 3416 -> 3448, B2 2552 -> 2584, B3 16056 -> 56760. Each ends with two
live orders; B3 has 501 heap entries. This supports the predicted stale-key risk;
it does not choose the final B or establish a general memory bound.
Smoke medians and full runtime planning table are in BENCHMARK_PLAN.md. The
M1000 extrapolation suggests roughly 8-55 h for all planned parts including A,
with wide uncertainty and stop-policy discontinuities. Recommendation: complete
B batches unchanged first, then a 10k A pilot and resumable larger A work with
600 s first-attempt stopping. Long runs and final selection remain unexecuted.

Fresh full suite saved in
`05_evidence/20261122T005136Z_5d8d15a-dirty_phase4a-all-tests.txt`:
`517 passed in 176.97 s`, no failures/errors/skips/warnings.

| Test file | Passed |
|---|---:|
| test_contract.py | 256 |
| test_validation.py | 184 |
| test_mutants.py | 22 (17 kills, naming, 4 real controls) |
| test_own_datasets.py | 4 |
| test_replay.py | 15 |
| test_b_internal.py | 17 |
| test_stateful.py | 3 (A vs B1/B2/B3) |
| test_bench_pipeline.py | 16 |
| Total | 517 |

Stateful settings remain 300 examples / 60 steps with every-event result/book,
invariants and conservation comparisons. Original contract assertions, expected
data, engine sources and dependency pins remain unchanged. Fresh environment,
full official scaling, candidate selection and dashboard are still later work.
The full test evidence is copied to both smoke folders as tests.txt.

Checkpoint: STOP for Claude (chat) review and Laurin. Proposed git commands are
in BENCHMARK_PLAN.md; Codex ran no git mutation and no long-run command.

Final Codex review: read the new benchmark/generator/test/verifier code, the
harness diff, manifest metadata and checkpoint documents for behavior, names,
comments or content unrelated to the requirements. No traces of the logged
injection and no NEW embedded instructions were found. No source changes
after the final smoke; its measured Python/test fingerprint still matches.
Read-only protected-path diff confirms all engines, original tests, expected
data, supplied generator and dependency pins unchanged. Generated data stay
ignored. The pre-existing ../AGENTS.md modification is outside this phase and
was left untouched. Final review evidence:
[scope/source/artifact checks](../05_evidence/20261122T005749Z_5d8d15a-dirty_phase4a-final-review-file.txt).
An earlier review command failed because PowerShell stripped nested native
argument quotes (005707Z); rerunning the same checks from a scratch script
passed. The failed command and all prior evidence are retained. No engine or
test change was needed. No git mutation or long-run command was executed.

STOP: await Claude (chat) review and Laurin.

## Phase 4a amendment, 2026-11-22, BEFORE long measurements

Laurin reports Claude (chat) reviewed Phase 4a and Laurin committed it. Read-only
history confirms `6df503c`; current HEAD `6c2a8d1` adds Laurin's aif-attack
instruction reference. No long measurements have started. Applied aif-exercise,
aif-bench, test-first pipeline checks and aif-verify. No delegation or installs.

Accepted all three explicit decisions: A at 1k/10k keeps full warm-up + five;
A at 100k/1M gets one measured trial, no warm-up, or stopped at 600 s. This is
labelled `A: single trial` in every future speedup and in new row/cell/summary
metadata; B1/B2/B3 remain warm-up + five. A shared protocol module drives worker,
summary metadata and estimates; the PowerShell wrapper explicitly selects it.
Summary's compatible median_s field holds the sole observation when
statistic=single_trial; it does not become five-repeat evidence. Independent
instrumentation/GC/limits stay unchanged. A is not a candidate.

SPEC and BENCHMARK_PLAN record the dated fallback: only if all candidates fail
robustness, allow one targeted change per violation, judged under the same rules,
with all violations reported. No heap/adaptive/engine revision is implemented.

Red evidence `20261122T011036Z_6c2a8d1-dirty_phase4a-amendment-red.txt`:
12 failed / 2 passed (new shared schedule stub; old large-A trials/summary).
Green `20261122T011200Z_6c2a8d1-dirty_phase4a-amendment-green.txt`: 30 pipeline
cases pass. Fourteen new cases cover schedule boundaries for all B candidates,
explicit single-trial summary, and actual worker control flow with four-event
synthetic inputs. Large size labels in those tests only exercise scheduling;
they do not execute 100k/1M events. Existing expected results are not changed.

Authorized archive move: source absolute path and scratch destination were
checked inside Assignment1 before native Move-Item. Saved archive evidence
`20261122T011203Z_6c2a8d1-dirty_phase4a-archive-smoke.txt`: all 663 files,
6,847,781 bytes and each relative-path sha256 preserved in
`scratch/20261122T003530Z_5d8d15a-dirty_smoke/`. No files deleted; no git
mutation. The superseded folder was untracked. Final committed smoke unchanged.

Estimates were recomputed only from historical 1k artifacts and the code-based
cost model. New JSON/MD go to `00_docs/phase4_plan_20261122/`; original smoke
results/planning are not overwritten. New total planning ranges (hours):
official 2.30-8.71; million 0.98-1.90; queue 1.13-4.59; liquidation 1.76-7.21;
adversarial 1.66-9.02; churn 0.09-0.39. B estimates are unchanged. These are
uncertain planning estimates, not long measurements. Full suite/staged commands
remain for Laurin after review/commit; no long-run command was executed.

Full-folder estimate: 2,032 workers, roughly 6,112 files, of which 6,096 local
job/journal/log files. About 16 root files (raw CSVs including coverage/stops,
summaries, env/spec/tests and compact verification/planning) are committed:
22.2-46.3 MiB; local internals 52.0-108.3 MiB, using smoke per-worker bytes and
1.2..2.5x allowance. New .gitignore rules exclude cells/ and jobs/ directories,
not cells.csv. Already tracked final-smoke internals stay tracked as historical
evidence; there is no untracking/deletion. No hard storage bound is claimed.

Fresh verification:
[full suite](../05_evidence/20261122T011345Z_6c2a8d1-dirty_phase4a-amendment-all-tests.txt)
reports **531 passed in 181.67s**, no failures/errors/skips/warnings.

| File | Passed |
|---|---:|
| test_contract.py | 256 |
| test_validation.py | 184 |
| test_mutants.py | 22 (17 kills, naming, four real controls) |
| test_own_datasets.py | 4 |
| test_replay.py | 15 |
| test_b_internal.py | 17 |
| test_stateful.py | 3 (A vs B1/B2/B3) |
| test_bench_pipeline.py | 30 |
| Total | 531 |

[Final review](../05_evidence/20261122T011803Z_6c2a8d1-dirty_phase4a-amendment-final-review.txt)
checks original pipeline-test AST preservation, unchanged engines/expectations/
committed smoke, archive count/bytes, unchanged B runtime projections, storage
arithmetic, PowerShell syntax without execution, scope and whitespace. Codex
also read the benchmark code diff, new shared policy, added tests and generated
planning/docs for unrelated behavior, names, comments and content. No traces of
the logged injection or NEW embedded instructions found. Every write stayed
inside Assignment1. No dependencies, deletions, engine revisions, git mutations
or long measurements. No fresh-venv reproduction is claimed.

Proposed git paths/message (not executed): BENCHMARK_PLAN.md final section.
STOP for Claude (chat) review and Laurin.

## Post-attack B3r build, decisions D1-D4 (Laurin, 2026-11-22)

Current base `958c8b4` commits the aif-attack report; its target was `56caf6f`
and the registered Phase 4 results were already committed. Codex read
`07_attack/ATTACK_REPORT.md` in full, then the relevant generators/models and
shared replay/engine/test/benchmark code. No attack artifact is edited.
Laurin reports Claude (chat) independently re-verified the hash-collision and
far_end_flicker findings; this is attributed review, not a new independent
Codex reference run. Applied aif-exercise, the explicitly invoked aif-tdd and
aif-debug, benchmark protocol guidance and aif-verify. No agents delegated.

Accepted and recorded in SPEC before B3r measurements:

- D1: separate B3r = B3 plus only per-side heap rebuild when stale>live AND
  stale>32. Filter the existing heap list, never iterate levels; heapify and
  rebuild in_heap on that side. The prior SPEC fallback's >2x-live example
  disagreed with the attack brief's >live wording. This inconsistency is
  explicitly resolved to >live AND >32, not silently treated as equivalent.
  B1/B2/B3 are unchanged. Extra counters are default-off and measure logical
  rebuild scans/removals. SPEC gives the credit argument and single-event
  O(live+stale) logical tail cost, with hash-capacity/GC/collision qualifications.
- D2: B2's rotating-burst capacity saturates with historical per-level peak;
  report it as a weakness, not a robustness-filter violation.
- D3: reproduce ATK-01 and BOM handling first, then fix shared replay to use
  utf-8-sig and disable CPython's process-wide decimal digit conversion guard
  when the reader starts (input AND output require unlimited conversion).
  No price cap. Document hash-collision attack numbers in SPEC/README, without
  pretending expected hash costs are worst-case guarantees. No hash_full case.
- D4: six added cases carry the exact label "added after Phase 4 from
  aif-attack". They do not change original B1/B2/B3 exclusions, which rest on
  the registered Phase 4 results; they only add hurdles for B3r. Deep_book is
  borderline (official 3.05, attack re-run 2.80); far_end_flicker is stronger
  separate evidence (~20.8x), not retroactive pre-registration.

Fresh red: `20261122T114415Z_958c8b4-dirty_b3r-and-replay-red.txt`, 90 failures:
B3r NotImplemented stub, BOM decode and >4300-digit parse errors. Green:
`20261122T114514Z_958c8b4-dirty_b3r-and-replay-green.txt`, 368 passed. Every
existing contract/internal/own/stateful test discovers B3r through the registry;
none of their sources/assertions or expected data are changed. New CLI tests
force a 4300-digit guard at process startup and verify three complete outputs
with 5000-digit quantities, for every implementation, plain and gzip.

New no-timing trap probes: wrong dict iteration and wrong two-side threshold
are each killed by AssertionError, using temporary in-memory subclasses, not
engine edits. Saved `20261122T115730Z_958c8b4-dirty_b3r-trap-mutation-probes.txt`:
real dead_slot_rebuild at n 512 scans 1229 keys / 767 cancels (1.602); real
two_side_thrash at n 128 scans 102 / 257 (0.397). Both satisfy <=2 per cancel;
drift tests verify <=2*live_levels+32 per side, both signs, strict thresholds
and quote/counter neutrality. These are logical work counts, not speed claims.
The original 17-mutant suite remains separate from these two mutation probes.

New own generator ports the six approved attack patterns to datagen.attack_cases;
tests compare generated events exactly with the committed attack generators
and compare all five engines with A after every small-case event. Twenty full
inputs were generated/hash-verified outside measurement (no engine execution)
and added to POST_ATTACK_MANIFEST.json, preserving the old manifest/results.
The combined catalog has 134 entries / 125 physical gzip files. New prefilled
timing/latency/count runs separate construction and attack/query suffixes;
memory traces construction+query with input slices outside tracing. The purge
case reports max_ns for its single measured sell. Root CSVs retain registration,
driver_n, prefill_events and exact replayed event counts.

Pipeline red `20261122T114642Z_958c8b4-dirty_post-attack-pipeline-red.txt`
(12 failing stubs/prefill checks), then green114906Z (42 passed including the
original 30 pipeline cases). During pre-green review, the newly authored spike
memory assertion was corrected from 7 to 8 live makers: a one-unit sell into a
two-unit maker is partial. The unimplemented-generator red had never reached
that assertion; no original expected result/test was changed.

Corrected Codex integration defect: the new catalog verification initially
rewrote its timestamp, which would dirty a freshly committed tree and block
the nightly source gate. A one-line-file regression reproduced it (red
115525Z); preserving the creation time for identical entries fixed it (green
115547Z, 13 new pipeline tests). This does not alter engines, data or limits.
Historical runtime estimation now excludes unmeasured B3r/post-attack cases,
rather than inventing timings or crashing on missing observations.

Tonight's new wrapper is bench/tonight_b3r.ps1, default session
phase4_b3r_20261122. Plan-only evidence115548Z lists all 15 batches without
constructing books: B3r on all seven parts (564 workers), B1/B2/B3 only on new
cases (168), then A on all parts (564), total 1296. A retains its declared
single-trial protocol at 100k/1M; B candidates retain warm-up+5. Existing limits,
explicit stopped/missing data and artifact policy remain. The initial full
suite before the catalog idempotence fix passed643 tests in 210.78 s; a final
fresh full suite follows that fix. No long engine run was launched.

Final evidence, after all Python/test source changes:

- [Standard suite](../05_evidence/20261122T115638Z_958c8b4-dirty_b3r-all-tests-final.txt):
  **644 passed in 200.94s**, no failures/errors/skips/warnings.
- [Committed attack suite](../05_evidence/20261122T120132Z_958c8b4-dirty_b3r-committed-attack-suite.txt):
  **1419 passed in 69.78s**, including B3r through the registry. The --runxfail
  flag disables historical strict ATK-01 xfails because the bug is now fixed;
  no attack test or marker is edited. These are correctness/counter tests,
  not new timing campaigns or an independent audit by Codex.
- [Original ATK-01 alone](../05_evidence/20261122T120050Z_958c8b4-dirty_atk01-original-reproducer-fixed.txt):
  4 passed with --runxfail; the new CLI regressions also cover B3r and BOM.

| Standard test file | Passed |
|---|---:|
| test_contract.py | 320 (64 per registered version) |
| test_validation.py | 184 |
| test_mutants.py | 23 (17 kills, naming, five real controls) |
| test_own_datasets.py | 4 |
| test_replay.py | 18 |
| test_b_internal.py | 22 |
| test_stateful.py | 4 (A vs B1/B2/B3/B3r) |
| test_b3r.py | 6 |
| test_replay_regressions.py | 20 |
| test_bench_pipeline.py | 30 |
| test_post_attack_pipeline.py | 13 |
| Total | 644 |

The four stateful machines retain 300 examples / 60 steps with after-event
result/book/invariant/conservation checks. Every B3r own-case path also compares
plain and counted instances with A and the independent expected files.
Both additional attack-trap mutants are separate from the original 17 kills.

[Final review](../05_evidence/20261122T120353Z_958c8b4-dirty_b3r-final-review.txt)
confirms protected source/test/data/result paths unchanged, all 644 XML cases
green, manifest verification byte-stable, original 114 entries identical, all 20
new files hash-verified (3,541,884 events / 30,603,345 gzip bytes), and the exact
nightly 1296-worker sequence. The source fingerprint is
`1a0b3cff7b325e3a88216fc23f864d3878cc3b52517426316acdd249905e9135`.
Historical estimates explicitly omit B3r/post_attack instead of fabricating
measurements. Read-only git scope/whitespace checks pass; generated data remain
ignored. Codex reviewed all new/changed source, tests, generator/manifest and
documentation for unrelated behavior, names, comments/content. No traces of the
logged injection and no NEW embedded instructions found. All writes stayed
inside Assignment1; no deletions, dependency changes, git mutations or long
engine runs. No final B3r performance/selection or fresh-venv claim is made.

Proposed git paths/message and exact preview/start commands are at the end of
BENCHMARK_PLAN.md. STOP for Claude (chat) review and Laurin.

## Declared supplementary A scope (Laurin, 2026-11-22, BEFORE A measurements)

Laurin's decision applies to session phase4_b3r_20261122; no long run has
started. Current base `6d93da6` commits the B3r build. A is not a candidate:
official through 100k (1k/10k warm-up+5; 100k one measured trial, no warm-up), plus
official 1M (one trial or stopped at 600 s). Queue, liquidation, adversarial,
churn and post_attack A cells are restricted to --max-size 10000. All larger
A cells there are **not measured (declared scope)**. They are not recorded as
stopped/failed times or extrapolated measurements. A growth statements there
must cite and label the sizes actually measured.

Reason accepted: A supplies baseline speedups and scaling; supplemental 100k
instrumentation would consume most of an estimated 8-30 h without changing any
conclusion. This is the declared rationale, not new timing evidence. B3r and
B1/B2/B3 comparator coverage, warm-up/repeats and worker order stay unchanged.
Only the PowerShell wrapper is changed in executable source: A outside
official/million receives --max-size 10000; data prep stays first, then B3r all
parts, old comparators post_attack, then A. Engine/Python runner/test/expected/
data files and dependency pins are unchanged. No new tests are written.

The preview requests 1168 workers: B3r 564 + comparators 168 + A 436. It omits 128
former A workers / 44 cases by declaration. Mode counts are 276 timing, 276
latency, 276 counts, 340 memory. The added A memory scenarios all have catalog
size>10000 and are therefore outside scope. No result CSV rows are invented;
the declared plan labels these omissions. Estimates are recalculated only by
filtering the old stored planning model to included A cases. The original-parts
A subtotal is 3.15-10.70 h; post_attack A, B3r and the new comparator cases remain
unestimated rather than being presented as measured. Historical planning
JSON/MD and all result/data files are preserved.

Fresh -PlanOnly and the complete standard test suite are saved as evidence.
No long run, data generation, git mutation or dependency/install/delete action.
Only SPEC, BENCHMARK_PLAN, AI_LOG, RUNTIME_ESTIMATE, the nightly wrapper and
evidence are proposed for this commit; the requirements map is left untouched
under Laurin's explicit "change nothing else" scope.

Applied aif-exercise / aif-bench for the protocol update and aif-verify for the
checkpoint. No delegation or algorithm change. Fresh evidence:

- [Plan-only preview](../05_evidence/20261122T123818Z_6d93da6-dirty_a-scope-plan-only.txt)
  lists all 15 batches with engine_executed=false and 1168 requested workers.
- [Runtime planning](../05_evidence/20261122T123940Z_6d93da6-dirty_a-scope-runtime-estimate-final.txt)
  records the filtered model, per-part estimates and all 44 excluded A cases
  labelled not measured (declared scope); no engine is run.
- [Complete standard suite](../05_evidence/20261122T123822Z_6d93da6-dirty_a-scope-all-tests.txt):
  **644 passed in 197.52s**, no failures/errors/skips/warnings. Original tests
  are unchanged, including four A/B stateful differentials and 17 mutant kills.
- [Final review](../05_evidence/20261122T124514Z_6d93da6-dirty_a-scope-final-review.txt)
  compares the new preview with the old one: all B batches and official/million
  A batches are identical; supplementary A sizes are <=10000; order preserved.
  It verifies all644 XML cases and protected files, including prior models.

Read the complete wrapper diff and changed planning/spec/log prose for scope,
unrelated behavior/names/comments and the known injection: no traces found and
no NEW embedded instructions encountered. Whitespace and scope checks pass.
Proposed git paths/message are in BENCHMARK_PLAN.md. STOP for review and Laurin.

## Optional B3r_fast build (2026-11-22, rule fixed BEFORE measuring)

Laurin reports the B3r session, including A, finished and was committed. Read-only
history confirms base 3c95836. Claude (chat)'s profile on supplied 10k streams
attributes about one-third of per-event time to validation and also identifies
the process->_process forwarding layer. This is attributed supplied profiling,
not a new measurement by Codex.

Acceptance rule, recorded before any new measurement:
"B3r stays the final Version B unless B3r-fast passes every correctness gate
below AND is >= 10 % faster (geometric mean of the 15 official 100k median replay
times) AND no measured scenario is > 5 % slower than B3r. Otherwise B3r-fast is
reported as tried and rejected."

Interpret the time improvement as fast/reference<=0.90 on the 15-cell geometric
mean, and fast/reference<=1.05 for every matched primary replay median across
official/post_attack. Record all diagnostics, no imputed time or premature
promotion. G1 exhaustive/property validator, G2 full every-event equivalence
and stateful checks, and G3 standard/attack/mutant suites are all mandatory.
Keep the old engines/shared validator, tests and expectations unchanged. Build
only the separate registered fast code; no data-structure or algorithm change.
Stop before any long benchmark, with a B-only preview and exact human command.

Applied aif-exercise, aif-tdd, aif-debug for the reproduced callback issue,
aif-bench and aif-verify. No delegation. Existing engines/shared validator,
tests and expected files are immutable; only new files plus registry/benchmark
registration are added. B3r remains final throughout this checkpoint.

New tests were authored against a NotImplemented validator/engine module.
Initial red 192427Z fails the first G1 case on the stub. Fast validation only
recognizes ordinary exact builtin fields, with liveness last; everything else
delegates to unchanged validate. Direct engine methods retain the inherited
API and validator; process inlines the old forwarding body. Matching only
binds stable references to locals; structures, thresholds, operation order,
fill dictionaries and counters are unchanged.

Green 192534Z:1,797,952 exhaustive validator comparisons with identical callback
traces, 1500 Hypothesis arbitrary JSON-like examples, and all 32 attack-generator
families counted/uncounted after every event (66 tests). Corpus: nine fields,
all field pairs, all prescribed odd/missing values, three event types, eight
expected_type variants, four sequence states and two live-id states, including
dict/str/int subclasses. Supplied-file selection includes six event streams
and excludes metadata sidecars; no input file is altered.

Corrected Codex defect: putting is_live inside the missing-field KeyError
handler retried a callback KeyError. Regression red 193456Z and green 193532Z
prove the callback now propagates once from outside that handler. Reference
validation stays unchanged; no expectation is weakened. Gate-sensitivity
evidence 194115Z kills three temporary in-memory mutants by AssertionError:
unsafe bool acceptance, reversed result-key order with equal values, and
counter-only drift. These probes are separate from the original 17 mutants.

Saved-row acceptance tests: red 193053Z (10 stub failures), green 193351Z
(10 passed), covering exact 10%/5% boundaries, losses outside the 15-cell score,
missing/stopped/partial/duplicate rows and mismatched input hashes. The
comparator requires all 57 timing pairs and 236 successful worker observations,
plus matching source-bound correctness proof. Synthetic saved rows are test
fixtures, never represented as measured performance.

Plan-only 193658Z: phase4_b3r_fast_20261122 measures B3r_fast only, official 180
workers + post_attack 56 = 236. No older engine is remeasured. Reference:
03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/.
try_b3r_fast.ps1 requires explicit -AllowLong and matching correctness evidence
for a real run; it compares saved results afterward. Exact preview/start
commands are in BENCHMARK_PLAN.md. No long run starts in this checkpoint.

Attack suite 193657Z: **1697 passed in 79.31s**, all six registered engines,
with --runxfail for the archived fixed ATK-01 markers. No attack source/test
is edited. Full standard gates also replay all complete supplied and own files,
with result/snapshot/quote comparisons after EVERY event, counted and
uncounted, plus both new and existing stateful differentials. Snapshot-copy
test duration is not an algorithm timing measurement or speedup evidence.

Final fresh standard run 193624Z: **848 passed in 648.79s**, no failures/errors/
skips/warnings. G2 verifies146,514 event-by-event comparisons across six full
supplied streams (five10k +worked example),18 own files and 32 attack families,
each counted and uncounted. All outputs and fill-key order, snapshots, quotes,
last_seq and counted state agree. Both required stateful machines pass (the
registry-driven A-vs-fast case and dedicated B3r-vs-fast case), configured 300
examples/60 steps, as do the old variants' stateful cases.

| Standard file / group | Passed |
|---|---:|
| test_contract.py | 384 (64 per registered version) |
| test_validation.py | 184 |
| test_mutants.py | 24 (17 kills, naming, six real controls) |
| test_own_datasets.py | 4 |
| test_replay.py | 21 |
| test_b_internal.py | 27 |
| test_stateful.py | 5 (A vs each B) |
| test_b3r.py | 6 |
| test_replay_regressions.py | 24 |
| test_bench_pipeline.py | 30 |
| test_post_attack_pipeline.py | 13 |
| test_fast_equivalence.py | 115 functions/parameters +1 B3r/fast stateful |
| test_fast_assessment.py | 10 |
| Total | 848 |

Source-bound proof `05_evidence/b3r_fast_correctness.json` records G1/G2/G3,
both complete suite XML hashes and source fingerprint
`f82455f1ced229fd6d5cffb29727b67b4cce1a53e6c6d7b649ce66d7f03dcbd2`.
[Proof creation](../05_evidence/20261122T194837Z_3c95836-dirty_b3r-fast-correctness-proof.txt)
and [final review](../05_evidence/20261122T194837Z_3c95836-dirty_b3r-fast-final-review.txt)
confirm all 848/1697 cases green, all required per-event coverage, every original
engine/validator/test/expected/data/result/attack path unchanged, and same
constructor/structures/public signatures/cleanup methods by identity.
AST comparison proves the inlined process body is identical after the
validator call, and matching is identical after undoing only local bindings.
The236-worker preview,57 full five-repeat B3r reference medians and 15-cell score
are verified. No new benchmark session exists. No timing conclusion is made.

Codex read the complete new fast/comparison/wrapper/test source and changed
docs for unrelated behavior, names/comments/content and the known injection;
no traces and no NEW embedded instructions found. Scope/whitespace checks pass;
dependency pins are unchanged. No deletes/installs, remote actions or git
mutations. B3r remains final. Exact benchmark start command and proposed git
paths/message are in BENCHMARK_PLAN.md; STOP before any long run for review.

## One binding same-session rematch (Laurin, 2026-11-22, BEFORE measuring)

Base ddbc434 commits the cross-session fast trial and its tried-and-rejected
decision. Laurin identifies session noise: B3r 20261122T130145Z buildup 10k s42
0.0233s and sweep 100k s43 0.2829s were around 2x faster than comparable old B
results/other seeds, while fast 20261122T200528Z was normal. The old per-cell 5%
comparison cannot isolate code effects. Its committed result is preserved and
will be reported unchanged alongside the rematch and this reasoning.

Decision recorded before any new measurement: ONE attempt, binding either
way, no further re-measurement. Same session, B3r+B3r_fast, official + post_attack,
timing only, unchanged warm-up+5. Per-case order alternates globally (B3r/fast,
fast/B3r), including the boundary after 45 official cases. Accept only with
current-source correctness gates, 15-cell official 100k geometric mean <= 0.90
and every workload x size median OF seed ratios <= 1.05 (single ratio if one
seed). Otherwise B3r remains final. No engine, test or expected-file changes.

Implementation adds a fixed atomic attempt claim, no retry/session override,
and immutable assessment output fast_rematch_acceptance.json. PlanOnly does
not measure/claim. A claim consumes the attempt even if interrupted or partial;
preflight failure before claiming performs no measurement. No rematch starts
in this build checkpoint. Apply aif-exercise/aif-bench and evidence verification.

New control-plane code only: ordered_requests preserves the default runner's
sort and alternates the explicit B3r/fast timing pair by global case rank.
The post-attack offset is 45, so its first pair (case 46) is fast/B3r. Every
timing worker retains fresh construction and warm-up+5, unchanged worker code.
No engine/shared validator/test/expected/data/old result file is edited.

Synthetic rule checks were written against NotImplemented helpers and failed
as expected (red 204557Z), then passed after implementation (green 204848Z).
They check parity/default order, exact 10%/5% limits, single-seed losses,
outlier robustness, median OF ratios rather than ratio OF medians, and missing
data. assess_rematch reuses the original completeness/input/15-cell checks and
replaces only the old per-cell 5% condition with the declared scenario median.
The original assessor and original rejection are unchanged.

Binding checks 205047Z use saved-row fixtures in isolated scratch directories:
a second atomic claim fails and leaves the first unchanged; accept, reject,
partial coverage, wrong order and wrong-source cases select the required final
version. Reassessment returns the first JSON byte-for-byte even if fixture
rows change afterward. Correctness proof verification is independently checked
with fresh complete suites, not inferred from these synthetic fixtures. No
real attempt marker/pointer is created by the checks.

Final plan-only preview 205140Z lists 90 official + 24 post-attack workers, timing
only, all 114 positions in the declared global alternation. It creates no books
or session. Memory-only cases do not enter the 57-case alternation. New assess
output includes old cross-session loss rows/decision/hash and new scenario
tables, numerical gates, correctness/source/claim/order/coverage and the binding
final-version decision. Existing result folders remain immutable.

Fresh verification after the final Python source change:

- [Standard suite](../05_evidence/20261122T205138Z_ddbc434-dirty_rematch-all-tests.txt): **848 passed in 713.71 s**, exit 0; no failures/skips. Includes all 17 mutant kills, reference/fast validator and every-event engine gates, plus both stateful differentials.
- [Attack suite](../05_evidence/20261122T205139Z_ddbc434-dirty_rematch-attack-suite.txt): **1,697 passed in 80.63 s**, exit 0, including B3r_fast.
- [New correctness proof](../05_evidence/b3r_fast_rematch_correctness.json): G1/G2/G3 true; source SHA-256 `4911010c34d0bd0f385c15fcfec9fb700db3b7e4859de57c4a7d1030b7569c64`, with hashes of both fresh XML reports. The original proof is untouched.
- [Final review](../05_evidence/20261122T210349Z_ddbc434-dirty_rematch-final-review.txt): independently verifies every preview position, default-order preservation, current-source proof, protected files and retained old rejection. No real attempt marker, session pointer or result folder exists.

Standard counts by file: contract 384, validation 184, fast_equivalence 115,
b_internal 27, b3r 6, mutants 24, own_datasets 4, replay 21,
replay_regressions 24, bench_pipeline 30, fast_assessment 10,
post_attack_pipeline 13, stateful 6 (five A-vs-B variants and B3r-vs-fast).
G1 reports 1,797,952 exhaustive comparisons; G2 checks supplied/own and all
32 attack stream families in both counter modes after every event.

Reviewed the full generated diff and both new source files for the logged
injection: no traces and no new embedded instructions. No engine/test/expected
or historical result changes, installs, dependency changes, moves or git
mutations. No new benchmark measurement; the sole attempt remains unused.
STOP for Claude (chat) review and Laurin's commit. B3r remains final pending
the one binding outcome; no performance claim from these correctness checks.

## Final Version B registry checkpoint (2026-11-23, base `dd88f22`)

Laurin's committed FINAL_SELECTION.md was read in full before editing. Final B
is B3r; B3r_fast was tried and rejected by the binding rematch. The selection
and its measurement qualifications are accepted without new measurements or
reassessment. Skills: aif-exercise, aif-tdd, aif-verify.

Registry B now directly selects OrderBookB3r; explicit B1 directly selects the
original OrderBookB. A/B2/B3/B3r/B3r_fast remain registered. Replay derives its
choices solely from the registry, without a second B1 alias or translation.
Benchmark make_book, the Phase 3b sanity map and the attack make factory also
use explicit B1; otherwise they could silently run B3r under a B1 label.
No benchmark is executed here and no stored result is relabelled.

Test-first evidence:
[red](../05_evidence/20261123T161747Z_dd88f22-dirty_final-b-alias-red.txt)
reports 24 failed / 36 passed for the old registry: wrong B class, missing B1,
old sanity mapping and mismatched B/B3r counters. After the mapping changes,
[targeted green](../05_evidence/20261123T161952Z_dd88f22-dirty_final-b-alias-green.txt)
reports 129 passed / 1,979 deselected. These are expected red assertions, not
an engine defect or an expectation disagreement.

The new test_final_version.py asserts every registry/factory class, B1 sanity
selection and B/B3r result, key order, snapshot, best quotes and counter equality
after every event on the worked example plus all 18 own datasets, counters off
and on. It also retains independent own expected results. Existing registry
fixtures expand contracts, internals, real-version mutant controls and stateful
tests to all seven names. The original stateful base is explicitly B1; dynamic
subclasses additionally test final B and each explicit variant against A.
B1-specific attack counter checks now name B1; attack CLI checks cover all
seven names and an untimed factory-identity check prevents mislabelling.

README/SPEC have a Final Version B table and exact replay commands. The final
selection follow-up is marked complete; historical attack/revision descriptions
say explicitly that their old B was B1. Fresh full-suite evidence follows below.

Fresh verification after the final Python source change (both exit 0, no
failures/skips):

- [Standard suite](../05_evidence/20261123T162212Z_dd88f22-dirty_final-b-all-tests.txt): **983 passed in 909.96 s**. Command: `python -m pytest -q -s --tb=short --basetemp=scratch/pytest-final-b --junitxml=05_evidence/final-b-all-tests.xml` through evidence.py with the README venv Python.
- [Attack suite](../05_evidence/20261123T162213Z_dd88f22-dirty_final-b-attack-suite.txt): **1,995 passed in 125.90 s**. Command: `python -B -m pytest -p no:cacheprovider 07_attack -q --runxfail --tb=short --basetemp=scratch/pytest-final-b-attack --junitxml=05_evidence/final-b-attack-tests.xml`. --runxfail executes the fixed historical ATK-01 regressions as ordinary tests.
- [Final review](../05_evidence/20261123T163814Z_dd88f22-dirty_final-b-registry-review.txt): PASS. Engine book files, shared validator, contract assertions, data, all historical results/proofs and selection text/numbers are unchanged; only the selection's registry follow-up is marked complete.
- [Verification JSON](../05_evidence/final-b-registry-verification.json): source SHA-256 `7de83f9fc36058f417ca003a29e855094a5f10c659d0bb515a92ebf73ca238e5`, registry map, both XML hashes and per-file/class counts. Historical correctness proofs stay bound to their historical source and are not overwritten.

| Standard file | Passed |
|---|---:|
| test_contract.py | 448 |
| test_validation.py | 184 |
| test_fast_equivalence.py | 115 |
| test_final_version.py | 60 |
| test_b_internal.py | 32 |
| test_b3r.py | 6 |
| test_bench_pipeline.py | 30 |
| test_fast_assessment.py | 10 |
| test_mutants.py | 25 (17 kills + 8 controls) |
| test_own_datasets.py | 4 |
| test_post_attack_pipeline.py | 13 |
| test_replay.py | 21 |
| test_replay_regressions.py | 28 |
| test_stateful.py | 6 A-vs-version machines |
| test_fast_equivalence.py stateful | 1 B3r-vs-fast machine |

Reviewed every changed source/doc and the complete diff for the logged
injection: no traces or new embedded instructions. No installs, dependency
changes, deletes/moves, remote actions or git mutations. No benchmark/sanity
session executed and no measurement claim made. Open questions: none.
STOP for Claude (chat) review and Laurin's commit. Proposed commands, not run:

```powershell
git add -- 01_code/lob/__init__.py 01_code/lob/replay.py 01_code/bench/core.py 01_code/bench/sanity.py 02_tests 07_attack/measure.py 07_attack/test_attack.py 07_attack/ATTACK_REPORT.md SPEC.md README.md 00_docs 05_evidence
git commit -m "Assignment1: make B the final B3r and preserve explicit B1 variant"
```

## Phase 5: committed-results Streamlit dashboard (2026-11-23, base `87ed911`)

Laurin's updated eight-tab prompt replaces the initial seven-tab outline.
Scope: dashboard/tests/docs, no new experiment, engine change, generator run,
dependency or reassessment of the final selection. Applied aif-exercise (read
its dashboard_app.py asset), aif-bench dashboard contract, aif-verify and
aif-debug for reproduced dashboard/test defects. No agent was spawned.

The supplied README Results and dashboard section (lines 124-130) was read at
`C:/Users/laubu/Downloads/Assignment1/Assignment1/README.md`; sha256
`17ce011bb3eec68d608ccbb5416ccc459e17764ae610c8111ba6cb4028961da9`
matches the course source already verified. Its complete required content is
mapped in REQUIREMENTS_MAP R58-R60 and the Phase 5 table. Runtime does not load
that source README; it loads only Laurin's allowlisted committed evidence.

Implementation: 04_dashboard/app.py is the entry point, views.py renders eight
tabs and saved_results.py validates/analyses saved files. Read-only Git blob
reads are pinned to a full HEAD SHA; dirty CSVs/untracked runs cannot enter.
Allowed data: 03_results/runs/*, 05_evidence/*, FINAL_SELECTION.md and the attack
report. No engine, benchmark or generator imports, no experiment controls or
remote fetches. Existing Streamlit/pandas/Altair installation used unchanged.
Telemetry off, loopback server binding and local Arial theme in .streamlit.

Every chart/table has source captions and recorded commits. Raw-repeat IDs,
counts, finite seconds, worker status and saved medians are checked before
aggregation. Limits/partial/not_run/missing cells remain explicit. Only A's
recorded phase_time_limit on replay can give >600 s and a speedup lower bound;
a subprocess timeout cannot. Fits stop at measured sizes. A single large trial
is labelled. Q7 construction/reset stays separate from individual-sale time.
Latency uses saved histogram counts, not synthetic distributions; memory
includes final post-churn state and explicitly sampled peak/live normalization.
Code/count/exponent bottlenecks cover A rescans and B1 far-end list movement.
Both fast comparisons retain their original decisions; same-session 0.873 and
the binding 1.068 loss are derived/checked against that session's CSVs.

Test-first [red](../05_evidence/20261123T165345Z_87ed911-dirty_dashboard-red.txt):
6 failures +4 fixture errors from explicit NotImplemented stubs, not imports.
Subsequent failures were preserved as evidence and corrected at root cause:

- Windows Git tried to stat a long SHA:path as a filename. A read-only direct
  reproduction showed Filename too long. Adding trailing -- forces revision
  syntax; missing optional files then use Git's bad-revision diagnostic. The
  initial chat diagnosis that JSON was uncommitted was wrong and corrected:
  both acceptance JSON files are committed and used unchanged.
- A named B1 counter regression failed because post-attack comparators live in
  the B3r session, while only original-grid B1 rows had been included. The
  source selector now includes both historical locations without relabelling.
- The test's external-network guard initially blocked Windows asyncio's local
  socketpair; allow loopback, deny external addresses, use getattr for absent
  AF_UNIX. Histogram totals require sorted version indexes (same values, no
  expectation change). A new test's misplaced interaction lines were moved
  back to their owning AppTest function. These were test-harness mistakes.
- Two whole-file asset patch attempts failed without changing the asset; the
  final update uses a small entry point plus separate analysis/render modules.
  No file was deleted or moved.

[Targeted green](../05_evidence/20261123T190241Z_87ed911-dirty_dashboard-verified.txt):
**16 passed in 16.71 s**, including all eight tabs, headline CSV geomeans and 13
A replay limits; construction/sale, post-attack, memory and early-latency
interactions; same-session score; exact histogram totals; invalid/duplicate/
partial cells, external-network denial and Windows Git path regression.

[Per-tab audit](../05_evidence/20261123T190442Z_87ed911-dirty_dashboard-values-audit.txt)
and [values](../05_evidence/dashboard-audit.json): independent arithmetic against
raw CSV/JSON/XML on every tab. Examples: B3r official geomean 0.424684429 s;
A buildup exponent 2.0911 over 1k-10k; Q7 10k s42 100% construction 0.0386168 s,
sale 0.0093366 s; spike max 57,415,300 ns; drift retained B3/B3r 36,948,344/5,080
bytes at 1M with 2 live orders; A scans 500,500 entries on 1k liquidation; B1 moves
20,000,000,000 references at 100k far_end_flicker. All are saved-file checks,
not new timings. Existing engine-proof 983 standard /1,995 attack XMLs were
also hash-verified, not re-described as a fresh independent reference run.

Other work appeared concurrently in 07_attack (report, campaign/probe scripts
and logs). It is left untouched and excluded from proposed git paths. The app
uses the committed attack report, not those in-progress working-tree changes.
Full standard-suite results and final source review follow below when complete.

The numerical audit is also included as 04_dashboard/verify_saved.py so its
exact checks can be repeated after checkout. Running the submission-path
script saved [reproducible audit](../05_evidence/20261123T191421Z_337cc61-dirty_dashboard-reproducible-audit.txt).
Between checks, Laurin committed the unrelated final-B correctness attack as
337cc61. Read-only diff from87ed911 confirms only 07_attack changed; no engine,
tests, results or data. The new committed addendum is rendered as attributed
report content. It reports no performance re-measurement. The dashboard gates
are refreshed against the new HEAD; no attack script is invoked in this task.

Final fresh standard suite:
`python -m pytest -q --tb=short --basetemp=scratch/pytest-dashboard-all --junitxml=05_evidence/dashboard-all-tests.xml`
through evidence.py with the README venv Python → **999 passed in 785.23 s**,
exit 0, no failures/skips. [Full output](../05_evidence/20261123T190332Z_87ed911-dirty_dashboard-all-tests.txt).
Counts: contract448, validation184, fast_equivalence115, final_version60,
b_internal32, b3r6, bench_pipeline30, fast_assessment10, mutants25 (17 kills
+8 controls), own_datasets4, post_attack_pipeline13, replay21,
replay_regressions28, stateful6 A-vs-version +1 B3r-vs-fast, dashboard16.
The new dashboard test is the only test file added/changed by this task.

Full-suite start snapshot was87ed911. After the unrelated 337cc61 attack-only
commit, all [16 dashboard gates](../05_evidence/20261123T191536Z_337cc61-dirty_dashboard-current-head-smoke.txt)
were repeated, **16 passed in 17.79 s**. This exercises the newly committed
report while engines/results/expected data are unchanged across both commits.
[Final review](../05_evidence/20261123T191653Z_337cc61-dirty_dashboard-final-review.txt)
passes: nonempty wholly-green suites/XMLs, eight numerical tab audits,
dashboard module import review, telemetry/loopback config and protected paths.
[Verification](../05_evidence/dashboard-verification.json) records all four
dashboard module hashes, test/config hashes, suites and per-file/class counts.

Reviewed the full generated source and documentation diff for the known
injection: no traces and no new embedded instructions. The committed attack
addendum's replay-default observation is report data, not a request to change
engine/CLI behaviour; no such change made. No new measurement, generation,
install, dependency change, deletion/move, external-network action or git
mutation by Codex. Final selection remains B3r; B3r_fast remains rejected.
Open questions: none. STOP for review and Laurin's commit.

Proposed commands from Assignment1, not executed (exclude the separate attack
work; the evidence glob selects dashboard files only):

```powershell
git add -- .streamlit/config.toml 04_dashboard 02_tests/test_dashboard.py README.md SPEC.md 00_docs/AI_LOG.md 00_docs/REQUIREMENTS_MAP.md 05_evidence/INDEX.md '05_evidence/*dashboard*'
git commit -m "Assignment1: add committed-results dashboard with eight evidence tabs"
```

## Three pre-report robustness fixes (Laurin, 2026-11-23, base `47c0048`)

Applied aif-exercise, aif-tdd, aif-debug and aif-verify. User authorizes only
dashboard portability, replay default and input diagnostics; engine algorithms,
shared validator, original test expectations and stored results stay unchanged.
No new measurements, generator runs or dependencies. No agents spawned.

1. Git/checkout available: keep committed-blob loading. Git executable missing
   or HEAD unavailable: DiskStore reads the identical allowlist under ROOT,
   rejects traversal/resolved escapes and returns missing optional files as
   missing. The first dashboard element is the exact requested warning; sidebar
   and provenance captions explicitly mark disk metadata as unverified. No
   engine imports or network fetches. AppTest runs in separate fresh processes
   over temporary copies with no .git, all four source-run tables and required
   docs/evidence; both no-checkout and PATH-without-Git modes render eight tabs.
   Test copies live under Assignment1 scratch; GIT_CEILING_DIRECTORIES prevents
   discovery of the ancestor course checkout. The default Git-mode tests stay.
2. Replay defaults to registry B = actual OrderBookB3r. A remains --version A;
   all explicit names and API/result semantics unchanged. A factory-spy test
   would fail if A were still constructed, even though correct A/B outputs agree.
   Help, README and SPEC state the default. No registry or engine edit needed.
3. Dedicated ReplayInputError carries file/physical line/problem. The CLI
   catches only this reader error, prints one stderr line and exits 1. JSON
   syntax, UTF-8/UTF-16/extra-BOM, read/open/gzip errors are located; engine
   exceptions are not hidden. Earlier valid results remain printed. Reading
   still uses universal newlines and utf-8-sig. Surrogateescape prevents decoder
   read-ahead from losing the physical error line; an invalid-byte regex rejects
   those markers before json.loads or dispatch. Escaped Unicode surrogates and
   a BOM character inside a JSON string remain valid data. No integer cap.

Test-first [red](../05_evidence/20261123T193220Z_47c0048-dirty_robustness-red.txt):
**24 failed, 4 passed in 10.89 s**. Failures reproduce the old A default,
tracebacks on all requested bad inputs and unavailable-Git crashes; the four
positive format/huge-int cases already pass. [Targeted green](../05_evidence/20261123T193940Z_47c0048-dirty_robustness-targeted.txt):
**93 passed in 47.80 s**, including 28 new tests and the unchanged replay,
replay-regression and dashboard suites. No expected value was corrected.

The first implementation patch failed context validation before any mutation
(misquoted module docstring); re-read exact source, applied the correct context.
The first docs patch likewise failed atomically on an unnecessary context line
and was reapplied correctly. No file deletion/move or behavioural detour.

[Fresh attack suite](../05_evidence/20261123T194432Z_47c0048-dirty_robustness-attack-suite.txt):
**1,995 passed in 95.10 s**, exit 0, --runxfail so fixed historical ATK-01 cases
execute as ordinary tests. Full standard-suite and final source review below.

[Fresh standard suite](../05_evidence/20261123T194432Z_47c0048-dirty_robustness-all-tests.txt):
**1,027 passed in 713.57 s**, exit 0, no failures/skips. Command:
`python -m pytest -q --tb=short --basetemp=scratch/pytest-robustness-all --junitxml=05_evidence/robustness-all-tests.xml`
through evidence.py with the README venv Python. The attack command was
`python -B -m pytest -p no:cacheprovider 07_attack -q --runxfail --tb=short --basetemp=scratch/pytest-robustness-attack --junitxml=05_evidence/robustness-attack-tests.xml`.
Standard counts: existing 999 plus 28 new robustness cases; all original
448 contracts, 25 mutant/control cases (17 kills), seven stateful machines,
own/fast/validation/replay checks and 16 dashboard cases remain green.

[Final source/suite review](../05_evidence/20261123T201613Z_47c0048-dirty_robustness-final-review.txt):
PASS. The only Python edits are replay's input/CLI layer, the three dashboard
entry/reader/view modules, and the new test_submission_robustness.py. Book
algorithms, registry, shared validator, benchmark code, existing test files,
03_results, 06_data, 07_attack and dependency pins are unchanged. Fresh XML
reports are wholly green; both no-Git modes render eight tabs with the exact
top warning. [Verification JSON](../05_evidence/robustness-verification.json)
binds current sources and the two suite XMLs by SHA-256 and records per-file
counts. Earlier dashboard/engine proofs are retained unchanged as history.

Reviewed the complete generated source/docs diff for the logged injection:
no traces and no new embedded instructions. No installs, dependency changes,
deletions/moves, remote actions, new measurements or git mutations. No existing
test expectation or result file changed. Open questions: none. STOP for review
and Laurin's commit. Proposed commands, not executed:

```powershell
git add -- 01_code/lob/replay.py 04_dashboard/app.py 04_dashboard/saved_results.py 04_dashboard/views.py 02_tests/test_submission_robustness.py README.md SPEC.md 00_docs/AI_LOG.md 00_docs/REQUIREMENTS_MAP.md 05_evidence/INDEX.md '05_evidence/*robustness*'
git commit -m "Assignment1: add no-Git dashboard fallback and robust final-B replay CLI"
```

## 2026-11-25 — Phase 5b dashboard clarity (base c4cfc25, Codex)

Laurin requested presentation changes only. Read both AGENTS files and applied
aif-exercise, aif-tdd and aif-verify; aif-debug for reproduced regression/test
adapter failures. No benchmark/generator execution, engine change, dependency
installation or git mutation. The logged PDF injection remains ignored; no new
embedded instructions were found. Task scope is recorded in SPEC.md before the
checkpoint; the final selection and historical measurements remain unchanged.

Accepted: dedicated first Final selection tab with the full committed decision,
candidate geomeans/violations (including B3r's literal-filter qualification) and
both fast outcomes. Overview now has three metrics, one 5-by-3 speedup table,
one log-log chart and the explicit cancel_churn loss. Original per-seed detail
(50 rows), repeat completeness (1,091 rows) and non-OK coverage (180 rows) moved
to Method & data; AppTest compares every rendered row/column/value with the
original frames. Every chart has a How to read caption. Scaling offers dashed
linear/quadratic reference guides and actual linear/log-log axes; memory uses
independent B3/other panels and a linear/log-y toggle. GC observations are
attributed to ATK-P7, including its allocation-outlier qualification, beside
the histogram. The separately marked B3r algorithmic spike comes from CSV.

Raw repeats expose every timing.csv row for a selected run/case/version/phase,
mark the warm-up and place the validated median alongside; a large A cell is
explicitly single trial. Workload settings retain generator parameters,
own/supplied origin, input SHA-256 and add the per-version timing protocol.
Commands are reconstructed, never executed. Overview links open these views.
Provenance, stopped/not_run/scope labels and the no-Git warning remain intact.

Test-first [red](../05_evidence/20261125T103109Z_c4cfc25-dirty_clarity-red.txt):
**7 failed, 14 passed in 19.80 s**, reproducing absent new views/helpers/controls.
Corrected new AppTest assumptions after checking the actual Streamlit API:
the chart element is vega_lite_chart, Markdown strips surrounding whitespace,
and Arrow normalizes object string dtypes. Value comparisons remain strict;
dtype differences from serialization are excluded. No expected engine result
was changed. The audit initially assumed the two JSON decision labels matched;
the committed cross-session label is "tried and rejected", whereas the binding
rematch label is "rejected". It now verifies those exact original labels.

Source review reproduced an overstatement in the new compact-table formatting:
**> 1300** was rounded up from a lower bound of **1295.716383...**.
[Rounding red](../05_evidence/20261125T115050Z_c4cfc25-dirty_clarity-bound-rounding-red.txt)
fails on that exact case. The new formatter rounds bounds down to three
significant digits; saved ratios/measurements and the moved legacy table are
unchanged. A regression checks displayed bounds do not exceed the calculated
bounds. Ordinary measured ratios keep nearest rounding.

One evidence command resolved its child "python" to the system interpreter
(no pytest); it ran no tests. All subsequent child commands explicitly use
C:/Users/laubu/.venvs/aif-a1/Scripts/python.exe. An already-applied scratch
rewrite helper was inadvertently retried and stopped at a missing old marker
before writing; two context-mismatched patches failed atomically. Re-read the
actual source instead of guessing replacement context. These are tooling
corrections, not data or behaviour changes.

[Final numerical audit](../05_evidence/20261125T115416Z_c4cfc25-dirty_clarity-audit-final.txt):
PASS across nine tabs, including candidate geomeans, all 15 compact ratio cells,
13 stopped A replays, raw repeat median and 945 workload-setting rows.
The new [clarity-audit.json](../05_evidence/clarity-audit.json) preserves source
run/commit/file references; the original dashboard audit is retained unchanged.
Fresh suite results and final source review follow below.

[Final targeted green](../05_evidence/20261125T115403Z_c4cfc25-dirty_clarity-dashboard-pass.txt):
**49 passed in 47.91 s**, no failures/skips: 21 dashboard checks and all 28
submission-robustness cases (including both real no-Git copies). This run is
after the final bound-formatting and AppTest adapter corrections. It checks
actual chart specifications, all nine rendered tabs, CSV-derived headlines,
every moved table value and each selected repeat without changing measurements.

[Full standard suite](../05_evidence/20261125T114813Z_c4cfc25-dirty_clarity-all-tests.txt):
**1,032 passed in 769.35 s**, exit 0, no failures/skips. It started before the
final display-rounding/AppTest adapter cleanup; the final 49-case run above
covers the completed presentation changes. Engine sources were unchanged
throughout. Standard per-file counts:

| File | Passed |
|---|---:|
| test_b3r | 6 |
| test_b_internal | 32 |
| test_bench_pipeline | 30 |
| test_contract | 448 |
| test_dashboard | 21 |
| test_fast_assessment | 10 |
| test_fast_equivalence | 116 |
| test_final_version | 60 |
| test_mutants | 25 (17 kills plus real-version controls) |
| test_own_datasets | 4 |
| test_post_attack_pipeline | 13 |
| test_replay | 21 |
| test_replay_regressions | 28 |
| test_stateful | 6 |
| test_submission_robustness | 28 |
| test_validation | 184 |

[Final source review](../05_evidence/20261125T120134Z_c4cfc25-dirty_clarity-final-review.txt):
PASS. [Verification JSON](../05_evidence/clarity-verification.json) records source
and XML hashes, suite stages and counts. Both suites are nonempty and wholly
green; the numerical audit covers nine tabs. Protected 01_code, 03_results,
06_data, 07_attack, requirements.txt, FINAL_SELECTION.md and the original
dashboard-audit.json are unchanged. Only the two dashboard-facing test files
changed; no engine expectation or expected result changed. git diff --check
passes (Windows line-ending notices only). Reviewed the full changed-source
diff and all new files for the logged injection: no traces in behaviour,
identifiers or comments and no new embedded instructions. No files deleted or
moved, no installations/network/Git mutations. No open questions.

STOP for Claude (chat) review and Laurin's commit. Proposed, not executed:

```powershell
git add -- 04_dashboard/charting.py 04_dashboard/saved_results.py 04_dashboard/views.py 04_dashboard/verify_saved.py 02_tests/test_dashboard.py 02_tests/test_submission_robustness.py README.md SPEC.md 00_docs/AI_LOG.md 00_docs/REQUIREMENTS_MAP.md 05_evidence/INDEX.md '05_evidence/*clarity*'
git commit -m "Assignment1: clarify dashboard selection, scaling and raw evidence views"
```

## 2026-11-25 — Fast comparison, report check and run-all entry points (base d885f6e)

Laurin authorized four tasks: add the two sourced fast comparisons, fact-check
Claude chat's report without restyling, build/run reproduction scripts, and add
README Start here. Applied aif-exercise, aif-tdd, aif-verify and aif-bench for
the explicitly requested 1k smoke. No delegation, Git mutation, engine change,
old test assertion change, expected-file change or historical result change.
The logged PDF injection remains ignored; no new embedded instructions found.

Dashboard: six rows/bars now include B1/B2/B3, final B3r's binding-rematch
reference and two B3r_fast comparisons. B3r/fast binding geomeans are both from
the same rematch (0.4687556667 / 0.4093057220 s), ratio 0.8731749845. The older
cross-session row retains ratio 0.8874636993 and its original rejection.
Computed scenario counts: 25/27 faster, 26/27 within 5%; dead_slot_rebuild 1k
ratio 1.0683006733 remains the binding failure. Every row/bar names its session
and commit. Historical FINAL_SELECTION.md stays verbatim, with a caption
distinguishing its older scenario-count wording from the computed counts.

Test-first [red](../05_evidence/20261125T125721Z_d885f6e-dirty_handoff-selection-red.txt)
reproduces the missing comparison column/fast rows. One new AppTest was added;
all old functions/assertions are AST-identical to HEAD. [Targeted green](../05_evidence/20261125T131701Z_d885f6e-dirty_handoff-dashboard.txt):
22 passed in 26.24 s. The fresh full suite below includes that test too.

Report: [REPORT_FACT_CHECK.md](REPORT_FACT_CHECK.md) lists all **40 exact
old -> new -> source replacements**. No other text/style/section change:
the final review reconstructs REPORT.md from HEAD plus the correction ledger.
Examples: exclude cancel_churn from the 21-186x claim; distinguish shared
validation from the fast path; correct I1-I7 and live-count/pseudocode updates;
include stale-root heap work/allocated-table scan in complexity; round the
crowded lower bound down; correct queue order and the 1k sweep rounding;
source GC observations, traced memory and timing aggregation precisely; use
full existing run paths. Final source inspection also corrected "two extra
mutants" to **two rebuild-trap work-count scenarios**; 17 mutant kills remain.
The original draft's correct figures/structure are retained. Bibliographic
attributions were not independently checked over a network.

[Report arithmetic check](../05_evidence/20261125T133243Z_d885f6e-dirty_handoff-report-check-final.txt):
91 records from committed blobs, saved in
[handoff-report-check.json](../05_evidence/handoff-report-check.json).
The initial check caught the draft's 10x sweep-1k rounding (actual 10.53566x);
corrected to 11x and reran. A scratch replacement script initially did not
match Unicode ellipses in the abbreviated paths; it stopped before writing.
After reading the actual text it applied the exact replacements. No stored
result, final selection, contract expectation or generator was corrected.

Entry scripts: run_all.ps1 and run_all.sh contain actual -m commands and
step comments; fail on the first error. Defaults: create .venv/install existing
requirements only if absent; full tests; final-B CLI worked replay plus
expected fills/book/proceeds check; 1k smoke; dashboard. -NoDashboard and
--no-dashboard allow terminal verification. Local venv creation and pip
installation were explicitly authorized in Laurin's prompt; pins unchanged,
including hypothesis==6.155.7. Bash is LF-pinned in .gitattributes.

submission_tools.py is stdlib orchestration, not engine code. Smoke copies
unchanged sources into a unique scratch workspace; creates only 1k/seed42
inputs there using the supplied/own generator commands and checksums; invokes
the existing runner for A/B3r with its full smoke protocol/result checks.
Historical root 03_results/runs and 06_data remain unchanged. Optional Full
is outside the default branch, prints about 7 h / allow 6-10 h, requires RUN
FULL, uses new sessions and the declared A scope. Estimate: 6.62155 h summed
saved candidate/baseline worker time, not a new long measurement. It does not
repeat the binding fast selection. Full generation writes ignored local
catalogs, checks content hashes, reports gzip differences, and accepts only
proven newline-only differences for own generator source hashes (supplied
generator remains exact). No long run was executed.

[Default PowerShell run](../05_evidence/20261125T132117Z_d885f6e-dirty_handoff-run-all.txt):
exit 0 in 905.05 s, including a new local venv and requirements installation.
**1,033 passed in 778.59 s**, no failures/skips; worked example **OK**;
**108/108 workers OK**, then explicit dashboard skip. The full suite is
preserved as [handoff-all-tests.xml](../05_evidence/handoff-all-tests.xml).
Per-file counts are in [handoff-verification.json](../05_evidence/handoff-verification.json),
including 448 contracts, 25 mutant/control cases (17 kills), 22 dashboard,
28 robustness, 184 validation, six A-vs-version stateful cases and the separate
fast differential coverage. Engine/test sources were unchanged after this run.

Final helper review corrected copied local-catalog aggregate totals and added
portable own-generator newline hashing; it changes neither generators nor
inputs. [Final smoke](../05_evidence/20261125T144429Z_d885f6e-dirty_handoff-smoke-final.txt):
108/108 workers plus 108 sampled result checks passed in 58.07 s; 12 catalog
entries / 11 physical files, all size 1000. The final verification checks
catalog totals and that copied engine sources equal the originals byte for
byte. Both smoke folders remain ignored under scratch, with no deletion/move.

[Bash syntax](../05_evidence/20261125T132027Z_d885f6e-dirty_handoff-bash-syntax.txt):
exit 0, bash -n. Initial sandbox Git Bash could not create its local signal
pipe; the authorized unsandboxed syntax check succeeded. No macOS/Linux run
or execution of Full is claimed. README's 437-word Start here has the two
commands, expected outputs, sourced section-6 headlines, individual commands,
folder map and submitted-commit placeholder. All prior detail is retained.

[Final review](../05_evidence/20261125T150020Z_d885f6e-dirty_handoff-review-final.txt):
PASS; source/XML hashes in handoff-verification.json. Reviewed the complete
changed-source diff/new scripts for the logged injection: no traces in logic,
names or comments. Protected engine/benchmark/data/attack/result/pin files and
FINAL_SELECTION.md are unchanged; old assertions unchanged; diff --check
passes. No open correctness questions. STOP for Claude chat/Laurin review.

Proposed commands, not executed:

```powershell
git add -- .gitattributes run_all.ps1 run_all.sh submission_tools.py README.md SPEC.md 00_docs/REPORT.md 00_docs/REPORT_FACT_CHECK.md 00_docs/AI_LOG.md 00_docs/REQUIREMENTS_MAP.md 04_dashboard/saved_results.py 04_dashboard/views.py 02_tests/test_dashboard.py 05_evidence/INDEX.md '05_evidence/*handoff*'
git commit -m "Assignment1: fact-check report and add verified run-all workflow"
```

## 2026-11-25 — Primary selection bars and session effect (base 5785e9f)

Laurin requested presentation-only simplification plus a second grouped chart.
Applied aif-exercise, aif-tdd and aif-verify; no engine/data/result changes,
installation, measurements, network actions or Git mutations. The known PDF
injection remains ignored; no new embedded instructions were encountered.

The first chart has exactly five primary-session bars: B1/B2/B3 from the
original candidate session, B3r from its baseline session, B3r_fast from its
first full session. Four-decimal geomeans: 0.4244/0.4726/0.4289/0.4247/0.3769 s.
The exact one-line caption explains that these sessions are not head-to-head.
The right-hand table has five primary rows plus one binding ratio row; no
repeated fast-version measurement row and no visible None/NaN values. Outcomes
are excluded/final B/faster-but-rejected as requested. The older 0.887 ratio
is retained on the primary fast row, comparing it with the primary B3r row;
the last row gives 0.873, 25/27 faster, 26/27 within bound, and the 1k failure
(1.068). Each row names its run/commit, covering all four saved sessions.

The second chart, below the first, groups the primary pair (0.4247/0.3769 s)
and binding same-session pair (0.4688/0.4093 s), with one ratio annotation above
each group. Its two-sentence caption is Laurin's exact text. The table caption
is two sentences; the obsolete older-count remark is removed. FINAL_SELECTION
is rendered unchanged and now already contains the corrected 25/27 wording.

[Test-first red](../05_evidence/20261125T153751Z_5785e9f-dirty_selection-primary-red.txt):
1 failed in 12.00 s on the expected one-versus-two-chart assertion.
[Dashboard suite](../05_evidence/20261125T154659Z_5785e9f-dirty_selection-primary-dashboard.txt):
**22 passed in 26.91 s**. Updated the existing selection AppTest to decode
actual chart Arrow datasets: checks all five bars/primary sessions, both pairs
against independent CSV arithmetic, group ratio labels, six table rows,
outcomes/blanks, every run/commit and exact captions. The chart-explanation
gate accepts the two newly specified literal captions; all other How to read
captions remain required. No engine test or expected file was changed.
[No-Git portability](../05_evidence/20261125T155536Z_5785e9f-dirty_selection-primary-portability.txt):
**2 passed in 20.36 s**, both copied-submission modes render every tab.

[Numerical/source review](../05_evidence/20261125T161049Z_5785e9f-dirty_selection-primary-review.txt):
PASS. Exact primary/binding geomeans reproduce ratios 0.8874636993 and
0.8731749845. Same-session absolute-time shifts from the primaries are
10.3774% for B3r and 8.6003% for fast, consistent with the requested caption's
about-10% wording. [Verification JSON](../05_evidence/selection-primary-verification.json)
records source/XML hashes, primary/grouped values, formatted table and all
provenance. Engine/benchmark/result/data/attack/pin files, report, entry scripts
and FINAL_SELECTION.md are unchanged. Only the requested dashboard test
expectations changed. Reviewed the changed source/new evidence for traces of
the logged injection: none in behaviour, identifiers or comments. No deletion
or move. No open questions; stop for review. Proposed, not executed:

```powershell
git add -- 04_dashboard/saved_results.py 04_dashboard/views.py 02_tests/test_dashboard.py SPEC.md 00_docs/AI_LOG.md 00_docs/REQUIREMENTS_MAP.md 05_evidence/INDEX.md '05_evidence/*selection-primary*'
git commit -m "Assignment1: simplify primary selection bars and show session effects"
```


## 2026-11-25 — Final review portability/documentation fixes (base 3e9ebfe, Codex)

Laurin authorized M1/M2 fixes, a fresh archive acceptance, current documentation,
full/dashboard evidence and Git proposals only. Applied aif-exercise, aif-debug,
aif-tdd and aif-verify. No delegation or Git mutation. The known PDF instruction
remains ignored; no new embedded instruction was followed.

Accepted: the existing dashboard loader test retains its committed-store
assertions in a checkout, and now checks DiskStore revision None, the unchanged
allowlist and the top warning without a checkout. Seven new cases run the real
loader test and smoke in copies without .git / without Git, and check official
new/resumed runs plus dirty-source refusal. The runner records a fingerprint,
explicit unverified provenance and source_dirty_paths=None for no-checkout
smokes. A tracked-source probe prevents ignored copies inheriting a false
verified label from an ancestor checkout. Official/resumed runs remain strict.
Only source_dirty/get_run changed; timing/aggregation/worker ASTs are unchanged.

Test-first evidence: final-fix-portability-red-confirmed is 6 failed / 1 passed.
The initial red fixture lacked fingerprint inputs and failed for the wrong
reason in one new test; that fixture was corrected, preserving the original
log. The first targeted green was 9 passed in 90.84 s. Review then reproduced
a misleading ancestor-checkout label (1 failed in 58.00 s); the tracked-source
probe fixed it, and final portability/resume verification is 8 passed in
88.09 s. The earlier full/overlay runs were intentionally interrupted for this
last guard change; they are not final pass evidence. No engine expected result
was altered.

Fresh final suite: 1040 passed in 908.12 s, no failures/errors/skips;
[full log](../05_evidence/20261125T220142Z_3e9ebfe-dirty_final-fix-all-tests-final.txt). Dashboard/robustness:
50 passed in 56.31 s, no failures/errors/skips;
[dashboard log](../05_evidence/20261125T220130Z_3e9ebfe-dirty_final-fix-dashboard-tests.txt). XML hashes and per-file
counts are in [verification JSON](../05_evidence/final-fix-verification.json).

Fresh external archive plus hashed working-file overlays: exit 0 in
982.16 s; 1040 tests, worked example OK, 108/108 smoke workers OK,
explicit NoDashboard completion. Nine no-Git AppTest tabs, the individual
worked command and all 134 catalog / 125 physical input hashes passed.
[Detailed acceptance](FINAL_FIX_VERIFICATION.md) records each step and duration.
The exact unchanged HEAD archive was separately run from zero: exit 1 in
1046.00 s, still the old M1 (1032 passed / 1 failed). It cannot contain
these uncommitted fixes; Laurin must commit then repeat that exact HEAD gate.
No .git was initialized in any temporary copy. The first archive helper was
started from the wrong cwd and exported an empty subtree; no submission code
ran in that attempt. It was corrected with read-only git -C at the repo root,
and the actual HEAD-only failure is preserved separately.

Docs: current README reference, results-only path, execution-policy fallback,
nine tabs and current collection; Submitted commit remains for Laurin. Current
requirement statuses cite saved full sessions and fresh evidence. REPORT now
cites committed reference/validator/profile checks (27–41 percent per-event
validation), separates Phase 4/attack ratios, states the at-most-2 rebuild
bound (worst observed 1.999), and explains memory boundaries/100k peaks.
REPORT_FACT_CHECK records later selection edits. Laurin selected deletion of
the unused LEARNING scaffold; only that requested file was deleted.

The repeated hygiene scan found a duplicate literal marker/query introduced
by the committed Claude review itself. Only that redundant wording was
redacted, with an explicit note preserving the original findings, so AI_LOG
again holds the sole literal quotation. This caused the supplementary helper's
final hygiene assertion to fail after all seven command checks passed; its
full output is retained and the successful command results were preserved,
then the corrected final hygiene scan passed. No repeated data generation
was needed. No other-student names, likely secret patterns or submitted files
over 20 MB were found; historical personal paths and 648 tracked worker
diagnostics remain disclosed as limitations.

Current upstream/main 43ff26c35cb9a27439b86ed5054e188639609903 comparison has zero paths outside
Submissions/BuehlerLaurin; the old 56-path finding used an older local ref.
This fix performed no fetch or remote action. Engine/validator/registry,
expected fixtures, generator sources, dependency pins, stored measurements,
dashboard implementation, FINAL_SELECTION and chat-reference evidence are
unchanged. Installations were only the authorized pinned packages in fresh
temporary environments. Final runtime hashes match the tested overlay.

STOP. Exact git add / commit and the 648-file git rm --cached proposal are in
[FINAL_FIX_VERIFICATION.md](FINAL_FIX_VERIFICATION.md); none was executed.
