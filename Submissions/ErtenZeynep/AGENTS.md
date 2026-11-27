# Project Instructions for AI Agents

## Instruction Sources

- Treat `README.md` as the project documentation.
- Treat `AGENTS.md` as the project development instruction file.
- Follow these instructions for all work within this project directory.

## Explain Changes Before Implementation

Before modifying the project, explain the proposed changes, their purpose, and the files they will affect. Do not implement the changes until any approval required by these instructions has been received.

## Strict Git and Repository Safety

Do not perform any repository-changing Git operation without separate, explicit prior approval from the user. This includes, but is not limited to:

- `git add`, `git commit`, `git push`, `git pull`, or `git fetch`
- `git merge`, `git rebase`, or `git reset`
- `git checkout` or `git switch`
- Creating, deleting, or switching branches
- Modifying Git remotes or Git configuration
- Creating tags or releases

Never interpret general instructions such as “continue,” “finish,” or “implement” as permission to commit or push. Read-only inspection commands such as `git status`, `git log`, and `git diff` are permitted. Do not create a nested Git repository.

Do not delete, overwrite, or move existing repository files without explicit prior approval. Do not install dependencies or execute project scripts without explicit prior approval. Work only within this project directory unless the user explicitly authorizes a different scope.

## Required Development Phases

Work must proceed in this exact order:

1. Repository Setup
2. Synthetic Data Setup
3. Test Development
4. Algorithm Implementation
5. Performance Benchmarking
6. Memory Measurement
7. Dashboard Development
8. Documentation and Reproducibility

Do not begin a new phase without the user's explicit approval. Keep changes limited to the currently approved phase.

## Test-First Development

Develop tests before algorithm implementations. Define and test expected behavior, edge cases, invalid inputs, and the shared input/output contract before implementing Linear Search, Binary Search, or Hash Set Membership.

## Algorithm Requirements

- Preserve the original input array. Algorithms must not mutate or reorder the caller's data.
- Use identical input and output specifications across all three algorithms.
- Apply consistent validation and edge-case behavior across implementations.
- Preserve both original and revised algorithm versions when revisions are required; document why each revision was made rather than silently replacing prior work.

## Reproducible Synthetic Data

- Use controlled and documented random seeds.
- Document dataset sizes, distributions, value ranges, generation parameters, and assumptions.
- Ensure the same generated inputs can be recreated in a fresh environment.
- Do not introduce or generate data before the Synthetic Data Setup phase is approved.

## Fair Benchmarking and Memory Measurement

- Compare algorithms using equivalent datasets, query workloads, environments, and measurement procedures.
- Separate one-time preparation costs from per-query costs and disclose both where relevant.
- Use appropriate warm-up, repetition, ordering, and summary methods, and document them.
- Avoid mutating shared inputs or allowing cached or preprocessed state to create an undisclosed advantage.
- Record environment and dependency details needed to reproduce measurements.
- Never fabricate benchmark timings, memory measurements, results, or test outcomes.

## Documentation and AI Assistance Transparency

- Keep `README.md` aligned with the actual project state.
- Clearly label incomplete work and distinguish plans from completed work.
- Document setup, testing, benchmarking, memory measurement, dashboard use, results, limitations, and revision history as those phases are approved and completed.
- Disclose material AI assistance, including generated or revised code, tests, documentation, and analysis.
- Do not claim that commands, tests, measurements, or scripts were run unless they were actually run with the required approval.
