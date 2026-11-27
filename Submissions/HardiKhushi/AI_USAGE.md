# AI usage

OpenAI Codex assisted with organizing this submission inside
`Submissions/HardiKhushi` on 20 November 2026.

The original file supplied was `test_search.py`, containing five search test
cases. Codex adapted these into runnable standard-library tests and added
duplicate/negative-ID and randomized checks. Codex also generated the three
search implementations, benchmark script, dashboard generator, this disclosure,
and the README.

`results/timing.csv` and `results/memory.csv` contain measurements produced by executing
`benchmark.py`; they are not invented or estimated AI results. The dashboard
is generated from those CSV files. See the README for the measurement protocol,
limitations, and commands to reproduce the work.

This disclosure records the assistant's contributions. It does not claim that
the student has independently reviewed or approved the generated code.

## Assignment review and corrections

After the user requested a guided review of the lab slides, Codex identified
that its initial list-membership and `bisect_left` implementations do not meet
the requirement to implement the linear and binary searches manually. This
earlier implementation choice was rejected as the final submission approach.
Replacement was pending at that stage and was completed in the later expanded
experiment described below. The initial benchmark
also lacks separate preparation/query timing, raw repeats, a full workload
matrix, and original/revised version comparisons. Passing tests do not establish
assignment compliance. Tests were not demonstrably run against missing or broken
code before the initial implementations; the history must not be rewritten to
claim that they were.

## Organization and data-generation step

The user approved persistent documentation, a `results/` directory, and a
separate random-data generator. Codex created `AGENTS.md`, `PROGRESS.md`,
`data_generator.py`, generator tests, and results provenance documentation;
updated the benchmark to consume generated workloads; and updated dashboard
paths and the README. Original CSV contents are preserved and are explicitly
identified as preliminary. The dashboard was rebuilt from saved results only;
no new benchmark measurements were requested for this step.

The generator design uses reproducible seeds, known present/absent ranges,
three query scenarios, and documented duplicate policies. The accepted user
direction is to work step by step, ask before commands, explain choices, and
maintain documentation. Approval to carry out these edits is not a claim that
the user has independently reviewed the implementation.

Verification for this step: 13 tests passed, including six generator tests.
Codex rebuilt the dashboard from the relocated CSVs and verified preserved
file hashes, matching measurement rows, local links, and Python syntax. The
dashboard was checked structurally, without browser screenshot verification.
No new benchmark measurements, commits, or uploads were performed.

## Test sensitivity demonstration

After explicit user approval, Codex ran the existing search tests against a
deliberately incorrect function returning one `False` per query. The function
and temporary test-registry substitution existed only in memory. The seven
search test methods produced 52 expected assertion failures across five methods,
with zero execution errors. After restoring the real methods, all 13 search and
generator tests passed. Project-file SHA-256 snapshots matched before and after
the execution; only the progress log and this disclosure were updated afterward.

Codex proposed and executed the demonstration and documented its interpretation
and reproduction instructions in `PROGRESS.md`. It shows sensitivity to this
specific incorrect implementation, not proof of correctness or retroactive
evidence of tests-first development. The search implementations and their
remaining assignment gaps were not changed. No benchmarks were rerun.

## Expanded experiment, revisions, and interactive dashboard

The user explicitly requested rerunning the three methods on different types
of data, making efficiency changes, recording timing/memory, and moving to the
dashboard. Codex treated this as authorization for that implementation and
measurement batch, while retaining approval requirements for later work.

Codex preserved a hash-verified snapshot of all 14 prior files, then wrote a
first manual version in `search_original.py`. It passed the seven pre-existing
search tests before the revised version was written. Codex revised linear
search to stop on a hit, removed unnecessary copies from all methods, replaced
recursive binary search with iteration, and used a comprehension for set
answers. The original manual version is a teaching baseline introduced in this
batch; it is not the earlier built-in implementation or an optimal baseline.
Both manual versions remain available. Existing expected answers were preserved.

Codex expanded correctness checks (17 test methods passed), rebuilt the
benchmark to separate preparation/query/total timing, kept raw repeats, and
measured current/peak traced memory separately. The full run executed 36 input
combinations and 216 method/version configurations. It saved 3,240 raw timing
rows and 1,080 raw memory rows. Every measured variant returned expected answers;
input-preservation checks passed. These results come from executed code.

Codex generated the interactive offline dashboard, measured-findings report,
and results verifier. Timing and memory summaries were recomputed from raw
samples; source and historical snapshot hashes were verified. Browser checks
exercised 72 filter combinations at each of 1,440- and 500-pixel widths, checked
displayed values against data, and found no page overflow. Screenshots at both
widths were inspected. QA outcomes are saved under `results/qa/` by run ID.

Measured revisions had lower total medians in 34/36 linear workloads and 36/36
binary/set workloads. All revised peaks were lower in this experiment. The
two linear timing regressions are retained; no universal improvement is claimed.
The report records one-machine/one-seed and measurement-order limitations.
AI-generated code and explanations still require the student's understanding
and review. No final commit, upload, fresh-checkout validation, or Phase 2 audit
was performed or claimed.

## Local checkpoint preparation and verification

The user approved final checks, documentation updates, and one local commit
containing only `Submissions/HardiKhushi/`, with no push. Codex reran the
17-test suite and saved-results verifier successfully, reviewed staged scope,
and confirmed temporary browser files were ignored.

An initial Git whitespace check flagged standard CSV CRLF endings and preserved
historical whitespace. Codex added folder-local `.gitattributes` to preserve
bytes across platforms, recognize CSV record endings, and leave the immutable
archive unchanged. The staged whitespace check then passed. No measured source
files, CSV contents, or archived files were modified.

Codex exported all staged contents to a clean ignored directory and verified
the 42 submission files byte-for-byte against the Git index. All 17 tests and
saved-result checks passed there. Rebuilding the dashboard/report produced
identical bytes; benchmark help and the generator preview also worked. A full
benchmark was not rerun. This validates a clean staged export, not a remote
clone or another machine. The authorized checkpoint's hash is available from
Git history after creation; it is not embedded in its own committed contents.

## Authorized GitHub publication

The user requested pushing the checkpoint. GitHub rejected direct push to
`cogeorg/AlgorithmsFinance` with HTTP 403 for account `khushihardi`. Codex found
no accessible fork at the standard address, used the existing Git credential
helper privately to authenticate to GitHub's API, and created a verified fork
at `khushihardi/AlgorithmsFinance`. Credentials were not printed or committed.
An initial Python HTTP lookup failed local certificate verification; system
curl completed the lookup and API calls with normal TLS verification enabled.

Codex retained the course `origin`, added remote `fork`, created branch
`submission/hardi-khushi` from checkpoint `3ba5b42`, and pushed it successfully
with tracking to `fork/submission/hardi-khushi`. Codex updated the working
instructions, README, progress log, and this disclosure to record publication.
This documentation-only follow-up is included in the same publication batch.
No algorithms, measured data, or historical provenance were changed. No pull
request was opened and no write to the course repository succeeded.
