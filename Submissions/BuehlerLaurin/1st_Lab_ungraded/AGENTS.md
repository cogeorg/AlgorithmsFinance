# AGENTS.md — Algorithms in Finance coding lab (Laurin Bühler)

Rules for any AI coding agent (Codex, Claude Code, ...) working on this submission.
The owner is a student. The goal is a correct, reproducible submission AND understanding it.

## 1. Git: the human owns all remote and history operations (MOST IMPORTANT)
- NEVER run: git push, git pull, git fetch, git clone, git commit, git merge, git rebase,
  git reset, git checkout/switch, git stash, git branch -d/-D, git tag, git remote,
  gh pr create, or anything else that changes git history, branches or remotes.
- Allowed (read-only): git status, git diff, git log, git show, git rev-parse HEAD.
- When a step is finished, propose a commit message and the exact `git add` paths.
  Laurin runs the commands himself.
- If a task seems to need a forbidden git operation, stop and ask.

## 2. Scope: only our own submission folder
- Work only inside `Submissions/BuehlerLaurin/` of the course repository.
- Never create, edit, move or delete files outside it (course folders like `Class1-2/`,
  other students' folders, repo-root files). Reading them is fine.
- Never delete files without asking first. Never touch `.git/`.

## 3. Environment and dependencies
- Windows 11 and PowerShell. Give commands in PowerShell syntax.
- Python 3.11+ in a virtual environment OUTSIDE OneDrive (e.g. `%USERPROFILE%\.venvs\aif-lab`).
- Standard library first. Allowed: pytest, streamlit, pandas, psutil (optional).
  Ask before adding anything else, and before any `pip install`.
- Pin exact versions in `requirements.txt` (`pip freeze` subset, `==` versions).
- No network access except `pip install` after approval. No secrets in the repo.

## 4. Engineering rules (from the lab specification)
- Tests and synthetic data come first. Run the tests before implementing and show that they fail.
- Never weaken a test or an expected result to make a bug pass. If a test seems wrong,
  explain why and ask.
- All methods must pass the same test suite (parametrize over methods and versions).
- Never mutate the caller's input array. Keep output order equal to query order.
- Keep data generation, algorithms and measurement code in separate modules.
- Preserve the original AND the revised version side by side. Never overwrite the original.
- Search procedures (linear, binary) are hand-written. `sorted()` and `set()` are allowed
  for preparation. `bisect` and `in` on a list are NOT allowed inside the searches.

## 5. Measurement rules
- Timing: `time.perf_counter()`. Untimed warm-up, then 5 repeats, report the median and keep all raw repeats.
- Very short calls: time k calls together, divide by k, record k.
- Fresh preparation state (sorted copy or hash set) for every repeat. Preparation is never free.
- Report preparation, query batch and total separately. Always state the unit (seconds)
  and whether a value is per query or per batch.
- Memory: `tracemalloc` in separate runs from timing. State whether input, prepared
  structure and output are included.
- Exclude data generation, tests, printing, AI calls and dashboard rendering from timing.
- Save raw results with seed, generator settings, n, q, hit rate, duplicate policy,
  Python version, machine details and code version (git commit hash + dirty flag).

## 6. Documentation and AI log
- Every module gets a docstring with the specification: input, output, edge cases, complexity.
- Keep `docs/AI_LOG.md` up to date. List which AI suggestions were accepted, corrected or
  rejected, and why. This is required by the lab.
- Keep `docs/REVISION.md` up to date: what changed between the original and revised versions, why,
  and the measured effect.
- Passing tests are evidence, not proof. Say so where relevant.

## 7. How to work with Laurin
- One step at a time. End each step with: what changed (files), commands run,
  test results (pass/fail counts), open questions, proposed commit message. Then stop.
- Explain the algorithmic reasoning briefly (invariant, complexity, why the result looks the way it does).
  Laurin has to defend this code in class and the exam.
- Prefer small, readable code over clever code. Type hints everywhere.
- If you are unsure about a requirement, quote the relevant line of `LAB_SPEC.md` and ask.
