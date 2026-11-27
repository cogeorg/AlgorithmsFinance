# AI usage

**Tool:** Claude Code (Anthropic), desktop app.

**Date:** 2026-11-20. The initial build used high reasoning effort.
Refinements medium reasoning.

In both cases Opus 5.5

## What the AI produced

The first version of every file in this folder was generated from the lab
slides, following the instructions in `AGENTS.md`:

- the project structure and `AGENTS.md`
- the tests (written before the implementations, see `DEVLOG.md`) and
  `tests/mutation_check.py`
- the implementations: LinearSearch v1/v2, BinarySearch v1/v2 and the hash set
- the synthetic-data generator
- the timing and memory measurement code and the run orchestrator
- the Streamlit dashboard, written by a separate AI agent from the results
  format spec
- an independent AI review of the build, acting as a Phase 2 auditor; the
  findings and how they were handled are below
- a simplified dashboard layout, after Maurice found the first version (nine
  tabs) too hard to read: four tabs (Overview, Runtime, Spot check, Details for
  auditors). No content was removed; the less central parts moved into Details.
  Only `dashboard/app.py` and its smoke test changed, not the measured code

## My decisions

- **Instructions (mine):** I specified what to build, where it goes
  (`Submissions/BonackerMaurice/`), what `AGENTS.md` must contain (slides 54–64),
  and that nothing goes to the course repository before my review (work was
  pushed only to my fork, then submitted by pull request after review).
- **Accepted:** the three methods and both revisions (linear: no copy;
  binary: recursive → iterative). I checked them against my handwritten trace. All methods returned the expected result.
- **Accepted, extended:** I wanted a generator that can produce longer lists,
  so the methods can be compared on different input sizes.
- **Corrected:** the dashboard. Claude showed too much information for a
  reviewer, so I reduced it to what is needed to test and assess the
  application. Lesson for next time: limit the scope in the prompt.
- **Own understanding:** I had the three methods (linear, binary, hash search)
  explained step by step and traced them by hand myself, including the
  simplified hash-table model (slot = value % 8).

## Review findings and how they were handled

An AI reviewer audited the build (algorithms, tests, generator, benchmarks) as a
Phase 2 auditor would. The algorithms were correct on everything it tried. The
findings were about how far the claims can be trusted:

| # | Severity | Finding | Handling |
|---|---|---|---|
| 1 | High | A q=1 "present" timing rested on one random hit position (0.06·n at n=1k, 0.76·n at 10k), so the fitted linear slope came out about 1.5. With duplicates, first hits sat at about 0.4·n, not 0.5·n | **Fixed:** hits are placed at stratified *first-occurrence* positions, `mean_first_hit_frac` (≈ 0.50) is saved per dataset, and tests were added |
| 2 | Medium | Nothing tested the measurement protocol: 4 protocol mutants (prepare timed as free, query including prepare, preflight off, input built inside tracing) survived | **Fixed:** call-counting probe tests per segment, a fresh-state test, preflight tests and a memory test |
| 3 | Medium | Nothing enforced "implemented by hand": a secretly linear binary search, `in` in linear search, and a list-based "hash" all survived | **Fixed:** an AST ban on `in`/bisect/index/count, comparison-counting bounds, prepared-state checks, and 2 new mutants (10/10 killed) |
| 4 | Medium | binary v2 returned `numpy.bool_` for NumPy int input | **Fixed:** validation accepts Python `int` only; NumPy users pass `.tolist()`. Test added |
| 5 | Medium | Query timings are warm-cache; total ≠ prepare + query | **Documented** in the `query`/`total` definitions |
| 6 | Medium | Provenance could claim a clean tree without git; run_id hid dirty runs; code could change mid-run | **Fixed:** `dirty: None` when unknown, a `_dirty` run_id suffix, a source SHA-256 checked at start and end, and a `status` field |
| 7 | Low | `prepare`/`total` include freeing the result | **Documented** |
| 8 | Low | The overhead was measured with a bare call, not the real wrappers | **Fixed:** `noop_call_s` (partial) and `noop_lambda_call_s` (lambda) |
| 9 | Low | Calibration could fall below the target duration | **Fixed:** 25% margin; the duration is derivable from the raw CSV |
| 10 | Low | Memory includes harness bytes | **Documented,** and the no-op baseline is saved as `memory_baseline` |
| 11 | Low | A failing test would leak the Windows user name into public result files | **Fixed:** home and user paths are redacted in `tests.txt`/`tests.xml`. Test added |
| 12 | Low | Dense small IDs are a best case for hashing and comparisons | **Documented** (README limitations) |
| 13 | Low | q=1 "mixed" is really all-present | **Fixed:** removed from the grid |
| 14 | Low | Cross-version determinism was overstated | **Fixed** the wording, and added golden-checksum and shuffle tests |
| 15 | Low | Smaller items | **Fixed:** expected slopes for binary corrected, psutil version recorded, memory phase checks checksums, preflight checks exact `bool`. **Not changed:** a cold-cache timing variant and a large-ID sensitivity run (out of scope) |
