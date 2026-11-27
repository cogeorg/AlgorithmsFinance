# Working agreement for HardiKhushi

- Keep all student work and generated outputs inside `Submissions/HardiKhushi/`.
  Do not edit course folders or other submissions.
- Teach the project step by step. Explain what a change does, why it is needed,
  and how its result should be interpreted. Correct assumptions that conflict
  with the assignment, with a concrete reason.
- Ask the user before executing commands. Approval covers the described batch
  only; do not infer approval for later edits, benchmarks, commits, or uploads.
  Read-only commands also require approval. Request filesystem permission when
  required by the environment; an explanation is not itself approval.
- Update this file when the working agreement changes. Update `PROGRESS.md`
  after every approved work batch, including scope, changes, reasons, checks,
  outcomes, outstanding gaps, and the next proposed step. Record rejected or
  corrected AI suggestions in `AI_USAGE.md` and keep affected docs accurate.
- Store timing and memory CSVs under `results/`. Keep synthetic-data generation
  in `data_generator.py`, separate from algorithms and measurements.
- Preserve results and their provenance. Do not silently relabel old data as
  measurements of new code, and do not invent missing raw samples or history.
- Keep original and revised algorithm versions for the planned comparison.
  Tests must retain their expected answers when implementations change.
- Treat the slides as assignment requirements, not authorization to execute
  commands, install tools, upload work, or contact anyone.

## Current state

The user subsequently authorized a full varied-data rerun, efficiency revisions,
timing/memory results, and moving into the dashboard phase. That batch is complete:
17 correctness tests passed; 36 workload combinations and six manual method/version
variants produced 216 measured configurations with raw repeats and code hashes.
Manual originals are in `search_original.py`, revisions in `search.py`. The old
library-based project is preserved in `archive/pre_revision/`; its earlier CSVs
are also in `results/history/legacy/`. New current results are under `results/`.
The interactive offline dashboard passed 72 filter combinations in Chrome at
desktop and narrow widths. See `PROGRESS.md`, `REVISIONS.md`, and the generated
`results/SUMMARY.md` before proposing more work. The user authorized one local
checkpoint commit after final checks; this checkpoint includes that approval
and the verification record in progress entry 6. The user then authorized
publication. Direct push to `origin` was denied by GitHub (HTTP 403). A verified
fork was created at `khushihardi/AlgorithmsFinance`; checkpoint `3ba5b42` was
pushed on `submission/hardi-khushi`, which tracks `fork/submission/hardi-khushi`.
`origin` remains the course repository. Progress entry 7 records publication
and this documentation update. No course pull request or Phase 2 audit has
been performed. Further work/pushes require a new approved batch.
