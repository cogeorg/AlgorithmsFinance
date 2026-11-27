# Phase 2 audit: Liu Haina

## Target and non-modification statement

- Repository: `https://github.com/cogeorg/AlgorithmsFinance`
- Reviewed commit: `5e81bdc2321208ea66a0267c5014f9e3c86d288f`
- Reviewed path: `Submissions/LiuHaina`
- Audit environment: Windows 11, Python 3.12.10
- Audit date: 20 November 2026

The target was checked out as a detached worktree. No peer source, test, data,
result, dashboard, or documentation file was edited. Generated dashboard output
and all audit evidence were written under `Submissions/MüllerAlexandra`.

## Executive summary

No membership-algorithm correctness bug was found within the specified integer
list interface. The supplied suite passed for both versions, and independent
edge probes and all 108 saved-case calls agreed with an independently computed
set-membership oracle.

Two reproducible cross-platform defects were found:

1. `validate_data.py` rejects correctly regenerated fixed-seed data when the
   current Python version differs from the version stored in the JSON metadata.
2. `dashboard.py` reports semantically unchanged source files as stale when Git
   converts LF line endings to CRLF on Windows.

The saved timing/memory files were otherwise internally consistent, and the
headline performance winner counts agree with independent calculations.

## Confirmed bug 1: validator confuses environment metadata with generated data

### Target

- `validate_data.py:21`
- `generate_data.py:68-84`, especially the recorded `python_version` at line 73

### Smallest useful reproducer

From this audit directory in a checkout containing the reviewed target:

```powershell
python reproduce_validator_python_version.py --target ..\..\LiuHaina
```

The original documented failure on Python 3.12 is:

```powershell
cd ..\..\LiuHaina
python -B validate_data.py
```

No Docker command applies because the reviewed project does not use Docker.

### Expected and actual behavior

Expected: fixed seed 42 regenerates the saved arrays, queries, expected answers,
and generator settings, allowing the documented validator to continue through
its 108 algorithm checks.

Actual on Python 3.12.10:

```text
AssertionError: Regeneration differs
saved_python_version=3.13.0
current_python_version=3.12.10
whole_equal=False
equal_without_python_version=True
```

The generated experiment data is identical after removing only the environment
metadata field `generator.python_version`.

### Why it is wrong and impact

Line 21 compares the entire saved JSON object to a newly built object. The
generator embeds the current interpreter version, so an environment change is
treated as a data-generation failure. This breaks the documented validator and
the seven-command reproducibility workflow on otherwise compatible Python
versions before any saved-case algorithm validation runs.

### Suggested correction

Compare arrays, cases, skipped cases, seeds, and generator policy fields while
excluding environment metadata, or compare `python_version` separately and
report it as an informational environment difference. Do not weaken the actual
array/query/hash assertions.

Evidence: `logs/validator_failure.txt`.

## Confirmed bug 2: dashboard source-integrity warning is line-ending-sensitive

### Target

- `dashboard.py:58-64`
- `results/metadata.json` field `source_sha256`

### Smallest useful reproducer

```powershell
python reproduce_dashboard_line_endings.py --target ..\..\LiuHaina
```

The reproducer copies the target into a temporary directory, performs only a
normal LF-to-CRLF text conversion in that copy, calls the submitted dashboard
payload builder, and deletes the temporary copy automatically.

### Expected and actual behavior

Expected: a platform line-ending conversion that leaves Python semantics
unchanged should not report measured source as modified.

Actual:

```text
dashboard_source_mismatches=[all nine measured source files]
all_lf_normalized_hashes_match=True
```

The real Windows checkout produced the same nine-file mismatch list when the
submitted dashboard builder ran successfully. Raw hashes matched 0 of 9;
canonical-LF hashes matched 9 of 9.

The generated dashboard was opened in a browser and rendered its charts and
filters successfully. Its visible yellow warning listed all nine files as
different. Browser evidence is saved as
`evidence/dashboard_source_warning.png`.

### Why it is wrong and impact

The dashboard hashes working-tree bytes directly. Git commonly checks out text
as CRLF on Windows even when the committed content and program semantics are
unchanged. The dashboard consequently gives reviewers a false stale-source
warning and weakens the usefulness of its provenance check.

### Suggested correction

Enforce LF for measured files with `.gitattributes`, hash canonicalized LF text,
or record and compare Git blob IDs. If byte-for-byte hashes are intentionally
required, the dashboard should label a line-ending-only difference separately
from a substantive source change.

Evidence: `logs/dashboard_hash_failure.txt` and
`evidence/dashboard_source_warning.png`.

## Documented shortcomings and suspected weaknesses

These are kept separate from demonstrated software failures:

1. The AI-assistance sections state that student acceptance, correction, or
   rejection of AI suggestions “remain to be recorded.” The lab explicitly
   requires those decisions, so the submitted disclosure is incomplete even
   though it is unusually detailed about AI scope.
2. `REPRODUCIBILITY.md` explicitly describes an isolated local copy, not a fresh
   remote clone. The detached audit checkout shows that tests and dashboard
   building work, but the submitted seven-command log itself does not prove a
   fresh-clone run.
3. `dashboard_validation.txt` reports 54 browser combinations and responsive
   checks, but the browser automation used for those checks is not included.
   The HTML is manually inspectable and the builder validates raw medians, but
   the exact browser-validation claim is not independently automated from the
   submitted files.
4. Performance uses one seed/array per size, negative-only absent values, and
   one traced-memory observation per configuration. These limitations are
   already disclosed in `REPORT.md`; they restrict generalization but do not
   invalidate the saved measurements.

## Cases and claims checked

- supplied 13-test suite against original and revised versions;
- empty arrays and empty query batches;
- duplicates;
- first and last matches;
- absent queries below, between, and above stored values;
- repeated calls and earlier-output stability;
- input-array and query mutation;
- exact Boolean output types;
- all 18 saved cases across two versions and three methods (108 calls);
- preparation inclusion in binary/hash total timing;
- identical saved inputs across methods and versions;
- seconds-per-complete-batch units;
- five raw repeats and independently recomputed medians;
- memory inclusion/exclusion labels and current/peak ordering;
- dashboard/raw run-ID and median agreement;
- report claims that hash wins 9/9 q=100 cases and linear wins 5/6 q=1 cases.

Detailed output: `logs/supplied_tests.txt` and
`logs/edge_and_measurement_checks.txt`.

## Discussion questions

### Which revision preserved correctness and improved measured performance?

Liu Haina's revised version adds early handling for empty queries and empty
arrays. The unchanged supplied suite passed for both versions. For q=0, it
avoids unused binary sorting and hash-set construction, producing the clear
recorded preparation/time/memory reduction. The saved nonempty ratios do not
support a general speedup claim, and the report correctly says so.

In Alexandra Müller's Phase 1 work, replacing recursive binary search with an
iterative version also preserved the shared tests and reduced the observed
query-batch median in 14 of 15 configurations, but did not improve every total.

### Which peer test exposed a bug or unsupported performance claim?

The submitted algorithm tests did not expose an algorithm failure. Running the
documented `validate_data.py` on Python 3.12 exposed the environment-metadata
comparison bug. Running the dashboard builder on a Windows checkout exposed the
line-ending-sensitive stale-source warning. Independent calculations did not
find an unsupported headline performance winner claim.

### Could another student reproduce the result from submitted files?

The algorithms, supplied tests, saved raw measurements, summary calculations,
and dashboard builder are largely reproducible from the repository. The two
included audit scripts make the discovered failures reproducible without
editing peer code. However, the validator is not portable across the recorded
Python-version boundary, and dashboard source provenance produces false
warnings after normal cross-platform line-ending conversion.

## Investigation limits

This audit used Windows 11 and Python 3.12.10. It did not rerun the full timing
benchmark because new timings would describe a different machine; instead it
audited the harness, recomputed every saved median, and checked the report's
winner counts. It did not use native-memory/RSS tooling, fuzz arbitrary Python
objects outside the integer-list specification, or reproduce the unavailable
browser-automation suite.
