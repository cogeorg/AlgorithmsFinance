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
earlier implementation choice was rejected as the final submission approach;
replacing the procedures remains a future approved step. The initial benchmark
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
