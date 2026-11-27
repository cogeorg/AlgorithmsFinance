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

The approved organization/data-generation batch is complete and documented in
`PROGRESS.md`. All 13 tests passed, the dashboard was rebuilt from saved CSVs,
and original measurement contents were preserved. No benchmarks were rerun.
The search procedures still use built-ins and need manual implementations.
Existing CSVs are preliminary results from the initial implementation; they
have not been regenerated for the extracted generator. Consult the progress
log before proposing the next batch, and ask for approval before commands.
