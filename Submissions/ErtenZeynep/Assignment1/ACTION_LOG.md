# Action Log

This file records actual operations. Planned actions are not presented as completed work.

## 2026-11-22 - Stage 1, Task 1: project foundation

### 1. Read the local PDF workflow instructions

- Purpose: follow the required read-only PDF inspection procedure before the later security review.
- Command: `Get-Content -LiteralPath '<CODEX_HOME>\plugins\cache\openai-primary-runtime\pdf\26.1026.10807\skills\pdf\SKILL.md' -Raw`
- Result: succeeded. The workflow requires complete text extraction plus visual page review. It requires no authoring marker for read-only work.
- Files changed: none.

### 2. Verified the project root and checked for existing targets

- Purpose: avoid overwriting existing work.
- Command: `$root = '<PROJECT_ROOT>'; Write-Output ('WorkingDirectory=' + (Get-Location).Path); Write-Output ('RootExists=' + (Test-Path -LiteralPath $root -PathType Container)); Get-ChildItem -LiteralPath $root -Force | Select-Object Name,Mode,Length,FullName`
- Result: the project root existed and was empty. The shell working directory was the course workspace parent.
- Files changed: none.

### 3. Requested scoped write permission

- Purpose: create only the user-authorized project structure and five initial files.
- Tool: filesystem permission request limited to the `Assignment1` directory.
- Result: write access granted for this work turn.
- Files changed: none.

### 4. Created the approved directory tree

- Purpose: prepare later stages without adding implementation or placeholder modules.
- Command: `$root = '<PROJECT_ROOT>'; $directories = @('orderbook','tests','data','data\supplied','data\generated','benchmarks','results','results\raw','docs'); foreach ($relative in $directories) { $target = Join-Path $root $relative; if (Test-Path -LiteralPath $target) { throw "Refusing to overwrite existing path: $target" }; New-Item -ItemType Directory -Path $target -ErrorAction Stop | Select-Object -ExpandProperty FullName }`
- Result: all nine requested directories were created successfully.
- Directories created: `orderbook`, `tests`, `data`, `data/supplied`, `data/generated`, `benchmarks`, `results`, `results/raw`, and `docs`.

### 5. Checked the Python version

- Purpose: compare the local interpreter with the generator's documented Python 3.11.9 check environment.
- Command: `python --version`
- Result: Python 3.13.17.
- Files changed: none.

### 6. Recorded interpreter and operating-system details

- Purpose: establish initial reproducibility metadata.
- Command: `python -c "import sys, platform; print('executable=' + sys.executable); print('implementation=' + platform.python_implementation()); print('version=' + sys.version.replace(chr(10), ' ')); print('os=' + platform.platform())"`
- Result: CPython 3.13.17, 64-bit, running on Windows 11 (`Windows-11-10.0.26200-SP0`). The interpreter path is `<PYTHON_EXECUTABLE>`.
- Files changed: none.

### 7. Checked required standard-library modules

- Purpose: verify that approved testing, parsing, compression, statistics, and memory tools are available without dependency installation.
- Command: `python -c "import unittest, json, gzip, csv, statistics, tracemalloc; print('stdlib_checks=OK')"`
- Result: `stdlib_checks=OK`.
- Files changed: none.

### 8. Created the five approved initial files

- Purpose: document project scope, decisions, persistent rules, operational history, and artifact exclusions.
- Tool: one `apply_patch` file-edit operation.
- Files created: `README.md`, `ACTION_LOG.md`, `AI_DECISIONS.md`, `.gitignore`, and `AGENTS.md`.
- Result: all five files were created successfully.

### 9. Verified the complete project structure

- Purpose: confirm Task 1 was complete before inspecting the PDF.
- Command: `$root = '<PROJECT_ROOT>'; Write-Output 'FILES'; Get-ChildItem -LiteralPath $root -File -Force | Sort-Object Name | Select-Object Name,Length; Write-Output 'DIRECTORIES'; Get-ChildItem -LiteralPath $root -Directory -Recurse -Force | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($root.Length + 1) }; Write-Output 'TARGET_CHECKS'; @('README.md','ACTION_LOG.md','AI_DECISIONS.md','.gitignore','AGENTS.md') | ForEach-Object { $path = Join-Path $root $_; Write-Output ($_ + '=' + (Test-Path -LiteralPath $path -PathType Leaf)) }`
- Result: all five approved files existed and were nonempty. The intended directories existed: `orderbook`, `tests`, `data/supplied`, `data/generated`, `benchmarks`, `results/raw`, and `docs`. No Python modules, tests, datasets, benchmark programs, or result files were present.
- Files modified: `ACTION_LOG.md` (this verification entry).

No dependency was installed. No external network was accessed. No Git or GitHub operation was performed.

## 2026-11-22 - Stage 1, Task 2: original PDF security and specification review

### 10. Checked the source PDF and attempted system PDF metadata tools

- Purpose: confirm the source existed and begin a read-only fingerprint/metadata review.
- Command: `$pdf = '<SOURCE_PACKAGE_ROOT>\AlgorithmsFinance_Exercise1.pdf'; Write-Output ('Exists=' + (Test-Path -LiteralPath $pdf -PathType Leaf)); Get-Item -LiteralPath $pdf | Select-Object FullName,Length,LastWriteTime; Get-FileHash -LiteralPath $pdf -Algorithm SHA256 | Select-Object Algorithm,Hash,Path; pdfinfo $pdf`
- Result: source existed, size 172,965 bytes, last-write time 2026-11-21 10:35:03. `pdfinfo` was unavailable.
- Files changed: none.

### 11. Checked available local PDF capabilities

- Purpose: find an installed read-only extractor/renderer without installing dependencies.
- Commands/tools:
  - `Get-Command pdftoppm,pdftotext,pdfinfo -ErrorAction SilentlyContinue`
  - Python module discovery for `pypdf`, `pdfplumber`, and `fitz`.
  - Recursive search under the local Codex runtime for `pdftoppm.exe`.
  - Local tool-capability metadata searches for PDF-capable tools.
  - Checks for Edge, Chrome, Ghostscript, ImageMagick, `mutool`, and Node PDF packages.
- Result: Poppler, the Python PDF libraries, Ghostscript, ImageMagick, and Node were unavailable. Local Edge and Chrome executables were present. No dependency was installed.
- Files changed: none.

### 12. Attempted offline browser rendering

- Purpose: satisfy visual page inspection using an already installed local browser.
- Commands: headless Chrome and headless Edge were invoked with a local `file:///` PDF URL, isolated temporary profiles, no extensions, no network URL, and screenshot output under `docs/.pdf_review_temp`.
- Result: Chrome failed because its GPU process was unusable. Edge wrote a screenshot only after its initial existence check; visual inspection showed a blank grey image rather than a rendered PDF page. Browser rendering was rejected as evidence.
- Temporary items created: `.pdf_review_temp`, browser profile files, and `page-01.png`.

### 13. Attempted read-only Microsoft Word conversion

- Purpose: obtain page-separated text using an installed local application without modifying the PDF.
- Commands/tools:
  - A PowerShell COM attempt, which failed because constrained-language mode prohibits COM creation.
  - Temporary helper `docs/.pdf_review_temp/extract_pdf.vbs`, created with `apply_patch`.
  - `cscript.exe //NoLogo ...extract_pdf.vbs ...AlgorithmsFinance_Exercise1.pdf`, first in the sandbox and then with approved elevated sandbox permission.
- Result: the sandboxed script was denied; elevated attempts did not return text and left two helper scripts and two invisible Word processes. No PDF content was saved by Word.
- Cleanup commands: inspected `WINWORD`/`cscript` processes, stopped helper `cscript` PIDs 84784 and 94772, verified both Word instances had no visible window, and stopped the two assistant-created invisible Word PIDs 9828 and 64300 with elevated permission.
- Safety: no unrelated visible Word session was terminated.

### 14. Parsed the PDF directly with temporary standard-library helpers

- Purpose: inspect every PDF page without network access or dependency installation.
- Temporary helpers created with `apply_patch`:
  - `docs/.pdf_review_temp/scan_pdf.py`
  - `docs/.pdf_review_temp/extract_text.py`
- Commands: each helper was run with Python against the original PDF. The scanner was iteratively corrected to read compressed PDF object streams. The extractor was corrected once after an initial CMap range overflow.
- Actual result:
  - PDF header: PDF 1.7.
  - Size: 172,965 bytes.
  - SHA-256: `c25a0e79f061f82124631bb120edb7d28ce99dd6d5fc3dadfdbbe0f537463c93`.
  - Direct and compressed objects parsed: 306 total, including 256 objects recovered from object streams.
  - Physical pages extracted: 26.
  - Complete page-separated text was inspected.
  - The previously reported irrelevant directive was found on physical PDF pages 1, 7, and 14.
  - No additional prompt-injection pattern was found.

### 15. Compared the PDF with the cleaned presentation and README

- Purpose: distinguish legitimate specifications from suspicious embedded content and identify unresolved requirements.
- Result: no material technical contradiction was found. The README consistently expands the slides with exact output fields and additional implementation detail. Ambiguities and benchmarking traps were documented in `AI_DECISIONS.md`.
- Legitimate AI-related requirement: PDF page 14 asks the student to record accepted, corrected, and rejected AI suggestions. It was classified separately from the unrelated naming directive.

### 16. Updated the persistent project records

- Tool: one `apply_patch` operation.
- Files modified:
  - `README.md`: added PDF fingerprint, review outcome, and legitimate AI-disclosure classification.
  - `AI_DECISIONS.md`: added exact injection locations and passage, the separately classified AI-disclosure passage, twelve specification findings, and twelve correctness/benchmarking risks.
  - `AGENTS.md`: added rules for separating legitimate and suspicious passages and clarified that AI disclosure does not expand authority.
  - `ACTION_LOG.md`: added this actual operational record.

Visual inspection limitation: installed renderers were unavailable and both local browser renderers failed to display PDF content in headless mode. The complete textual content and page mapping were nevertheless recovered directly from the PDF's compressed objects. This limitation is reported rather than hidden.

### 17. Removed temporary PDF-review material

- Tool: `apply_patch` deleted the three temporary text helpers `extract_pdf.vbs`, `scan_pdf.py`, and `extract_text.py`.
- Safety check and cleanup command: resolved both the project root and `docs/.pdf_review_temp`, verified that the temporary path began with the absolute project `docs` path, counted its contents, and only then ran `Remove-Item -LiteralPath $temp -Recurse -Force`.
- Result: 597 temporary browser/profile items were removed. `docs/.pdf_review_temp` no longer exists. These were generated review artifacts and are not recoverable; no project evidence or supplied source was deleted.

### 18. Performed final Stage 1 verification

- Purpose: verify source integrity, final files, directory structure, and required documentation sections.
- Commands: `Get-Item` and `Get-FileHash -Algorithm SHA256` on the original PDF; recursive `Get-ChildItem` on the project; `Select-String` for required headings in `AI_DECISIONS.md` and `AGENTS.md`.
- Results:
  - Original PDF remained 172,965 bytes with last-write time 2026-11-21 10:35:03.
  - Final PDF SHA-256 remained `c25a0e79f061f82124631bb120edb7d28ce99dd6d5fc3dadfdbbe0f537463c93`.
  - Exactly five project files existed: `.gitignore`, `README.md`, `ACTION_LOG.md`, `AI_DECISIONS.md`, and `AGENTS.md`.
  - Intended directories existed: `orderbook`, `tests`, `data/supplied`, `data/generated`, `benchmarks`, `results/raw`, and `docs`.
  - No files existed inside later-stage directories.
  - Required security, specification, risk, Git-prohibition, test-first, benchmarking, and prompt-protection headings were present.

Stage 1 stopped here. No matching code, tests, workload generation, benchmark execution, dependency installation, network access, or Git/GitHub operation occurred.

## 2026-11-22 - Stage 1 amendment: numbered repository migration

### 19. Inspected the actual project structure and persistent instructions

- Purpose: base the migration proposal on the filesystem rather than the earlier planned structure and reuse recorded environment information.
- Commands:
  - Recursive `Get-ChildItem -Force` inspection of the `Assignment1` root.
  - `Get-Content -Raw` on `AGENTS.md`.
  - `Select-String` on the README environment and planned-structure sections.
- Result: the project contained exactly five root files and six empty unnumbered directory trees. The recorded environment remained Windows 11 with CPython 3.13.17. No implementation, test, data, benchmark, dashboard, or result file existed.
- Files changed: none. These read-only commands were not logged at the time because the user had prohibited modifications during planning.

### 20. Performed the migration preflight and captured initial hashes

- Purpose: prevent collisions, moves outside the project root, and accidental content loss.
- Command: resolved the absolute project root and each source directory; checked that `01_environment` through `08_documentation` were absent; computed SHA-256 for the five root files; recursively checked for files below the root.
- Result:
  - Sources verified inside the project: `data`, `tests`, `orderbook`, `benchmarks`, `results`, and `docs`.
  - All eight numbered destination names were absent.
  - No non-root files existed.
  - Initial hashes were recorded by the command output before intentional documentation changes.
- Files changed: none.

### 21. Requested scoped write permission

- Purpose: perform only the approved migration and update the five existing root files.
- Tool: filesystem permission request restricted to the absolute `Assignment1` directory.
- Result: permission granted for the current turn.
- Files changed: none.

### 22. Migrated the directory structure

- Purpose: organize the project visually around the approved workflow.
- Command: one PowerShell operation re-resolved every source inside the project root, rejected any pre-existing destination, created `01_environment`, `04_implementation`, and `06_dashboard`, then used literal-path moves for the six existing directory trees.
- Actual mapping:
  - `data` -> `02_data`
  - `tests` -> `03_tests`
  - `orderbook` -> `04_implementation/orderbook`
  - `benchmarks` -> `05_benchmarks`
  - `results` -> `07_results`
  - `docs` -> `08_documentation`
- Result: all eight numbered top-level directories were present after the move.
- Files changed: none; the moved directory trees were empty.

### 23. Inspected path references before documentation updates

- Purpose: locate every obsolete structure, data, result, and ignore path precisely.
- Command: `rg -n` searches in `README.md` and `.gitignore` for the old directory names and paths.
- Result: old structure references and the `data/generated/` ignore rule were located.
- Files changed: none.

### 24. Updated project documentation and control rules

- Tool: one `apply_patch` operation.
- Files modified:
  - `README.md`: replaced the old tree, documented clean `orderbook` imports through command-scoped `PYTHONPATH`, added cross-platform command patterns and stable path-resolution rules, and updated data/result paths.
  - `.gitignore`: changed the generated workload exclusion to `02_data/generated/` while preserving supplied data and required results.
  - `AGENTS.md`: added the numbered layout, import boundary, stable-path rules, and supplied/generated data separation.
  - `AI_DECISIONS.md`: recorded the numbered structure and import strategy as accepted decisions.
  - `ACTION_LOG.md`: added this actual migration record.
- Result: documentation now reflects the filesystem migration.

No dependency was installed. No network was accessed. No Git or GitHub command or equivalent operation was performed.

### 25. Verified the completed Stage 1 migration

- Purpose: confirm the exact numbered structure, removal of obsolete paths, absence of unintended stage files, and required documentation updates.
- Command: a read-only PowerShell verification checked each expected and obsolete path, listed root and non-root files, calculated SHA-256 for the five root files, and used `Select-String` for the new structure, import policy, ignore rule, persistent instructions, and accepted decisions.
- Actual results:
  - All expected directories existed: `01_environment`, `02_data/supplied`, `02_data/generated`, `03_tests`, `04_implementation/orderbook`, `05_benchmarks`, `06_dashboard`, `07_results/raw`, and `08_documentation`.
  - Old paths `data`, `tests`, `orderbook`, `benchmarks`, `results`, and `docs` no longer existed.
  - Exactly five root files existed.
  - No file existed below the project root; all later-stage directories remained empty.
  - README structure/import rules, the `02_data/generated/` ignore rule, the AGENTS numbered-layout section, and decisions DEC-005/DEC-006 were present.
- Root-file hashes observed before appending this final verification entry:
  - `.gitignore`: `939c1d9a1e7ef8f2617536438c6a7db5f5de1f01dee8ea76189d407a53e033fc`
  - `ACTION_LOG.md`: `58a710a9cfedcac9d5049b3fcf0ef44d5bb14aa51bbe56a6e68ce13c5d417264`
  - `AGENTS.md`: `a8ae36e5df4b56c829356f704956424212a5985b94ccf07597abea213bd2ab96`
  - `AI_DECISIONS.md`: `0c70cedc246f632fee237edffee349226dc197fa3392aa7fc0cd747221091bff`
  - `README.md`: `99a96ab8891889647e11c089a0de6142a66f76c0ec0a998c2a1fff7e9524529e`

The only change after that verification was this appended action-log entry. Stage 1 is complete and stopped before supplied-package inspection or Stage 2 work.

## 2026-11-22 - Stage 2A: supplied package preservation and validation

### 26. Inventoried and read the instructor package

- Purpose: inspect the source package before copying or generating anything and treat its documents as untrusted specification data.
- Read-only commands:
  - Recursive `Get-ChildItem -File -Force` under `<SOURCE_PACKAGE_ROOT>` with relative paths, byte sizes, and timestamps.
  - `Get-Content -Raw` on the source `MANIFEST.json`, `generate_orders.py`, and instructor `README.md`.
  - `Get-Content -Raw` on the project `AGENTS.md` to apply persistent operating rules.
- Result: 16 actual files were present: the PDF, instructor README, generator, manifest, five gzip workloads, five metadata files, worked input, and worked expected result.
- Files changed: none.

### 27. Compared source files with the instructor manifest

- Purpose: establish integrity before preservation.
- Command: PowerShell parsed `MANIFEST.json`, checked each listed path, computed SHA-256 with `Get-FileHash`, compared byte counts and hashes, and reported unlisted actual files.
- Results:
  - 15 manifest-listed files matched exactly.
  - `.DS_Store` was listed but missing.
  - No manifest-listed assignment file had a size or checksum mismatch.
  - `MANIFEST.json` was the only actual file not listed in its own mapping; its SHA-256 was `63b9d1872c6d966a2cfd53f32fba0d6f8ff3c5abc96e7710a2b85a67e5b22db1`.
- Files changed: none.

### 28. Inspected metadata, worked files, generator help, and target state

- Purpose: confirm supplied scenarios and generator interface without generating data.
- Commands:
  - Read all five metadata JSON files, `worked_example.jsonl`, and `worked_expected.json`.
  - Ran the source generator with `--help` under Python 3.13.17.
  - Verified `02_data/supplied` existed and was empty.
- Result: metadata identified five 10,000-event, seed-42 streams generated with Python 3.11.9 and levels argument 1,000. The generator help path succeeded and exposed the five expected scenarios plus `--events`, `--levels`, `--seed`, and required `--out`. No dataset was generated.
- Files changed: none.

### 29. Requested scoped write permission

- Purpose: preserve the instructor package and create only approved Stage 2A verification artifacts.
- Tool: filesystem permission request restricted to the project `Assignment1` directory.
- Result: permission granted for this turn.

### 30. Preserved the instructor package

- Purpose: copy the complete actual package while preserving its separate instructor README and data hierarchy.
- Command: verified the target was empty, recursively copied each source-root item into `02_data/supplied`, then compared source and destination sizes and SHA-256 values for every actual file.
- Result: 16 source files and 16 target files. Every copied file matched its source exactly. No supplied file was edited.

### 31. Created reproducible Stage 2A verification artifacts

- Tool: `apply_patch`.
- Files created:
  - `01_environment/environment.json`: observed Python/platform and generator-reference metadata.
  - `02_data/validate_inputs.py`: standard-library structural validator with stable internal paths and explicit CLI path resolution.
- Files modified later in this block: `README.md`, `AI_DECISIONS.md`, and `ACTION_LOG.md`.

### 32. Validated supplied streams and metadata

- Commands:
  - Ran `02_data/validate_inputs.py` against `02_data/supplied`, writing `02_data/supplied_verification.json`.
  - Enhanced the validator with observed limit-side counts and unique-price counts, then reran it and printed a structured summary.
- Results:
  - Six streams validated: five gzip workloads and the plain worked example.
  - Invalid streams: zero.
  - Invalid metadata records: zero.
  - Every workload contained 10,000 events with sequences 1 through 10,000.
  - `buildup`: 10,000 LIMIT events; 988 observed bid prices and 989 ask prices.
  - `cancel_churn`: 5,000 LIMIT and 5,000 CANCEL events; all limits were BUY.
  - `crowded`: 10,000 LIMIT events; exactly four bid and four ask prices.
  - `mixed`: 6,075 LIMIT, 2,438 CANCEL, and 1,487 MARKET_SELL events.
  - `sweep`: 8,000 LIMIT and 2,000 MARKET_SELL events.
  - Worked example: six valid events and sequences 1 through 6.
  - Manifest summary in the verification report: 15 matched, one missing `.DS_Store`, and unlisted `MANIFEST.json`.

No synthetic dataset was generated. No matching engine, test, or benchmark code was written. No dependency was installed. No external network, Git, or GitHub operation occurred.

### 33. Performed final Stage 2A verification

- Purpose: confirm preservation, validation artifacts, and the absence of generated data before stopping.
- Command: counted supplied and generated items; rehashed every source and preserved file; checked the three Stage 2A artifacts; parsed the verification report and counted valid streams and metadata records.
- Results:
  - Preserved supplied files: 16.
  - Source/destination checksum or size mismatches: zero.
  - Items under `02_data/generated`: zero.
  - Valid streams: six.
  - Valid metadata records: five.
  - `01_environment/environment.json`: 507 bytes, SHA-256 `9d09435d3a8d9dd11882519af814814f95e1f84c0898b1f1d7c6aebd3c9c012c`.
  - `02_data/validate_inputs.py`: 12,161 bytes, SHA-256 `edf7e90d0dd34f42a30e434b07aebcaf15e77c1bc78bf6f9ed92984455ab51bf`.
  - `02_data/supplied_verification.json`: 13,789 bytes, SHA-256 `94e889e19379e03d2248cfccc63427c9ab32116d97e1f719084e4b0348045c02`.

Stage 2A completed here. Stage 2B generation remains unexecuted and requires separate approval of its exact matrix and resource limits.

## 2026-11-22 - Permanent proactive risk methodology and Stage 2B planning

### 34. Inspected current risk and operating-rule records

- Purpose: preserve the user's reviewed findings without misclassifying technical risks as malicious instructions.
- Read-only commands: `Select-String` on risk, specification, liquidation, timing, and section headings in `AI_DECISIONS.md` and `AGENTS.md`; `Get-Content -Tail` on `ACTION_LOG.md`.
- Result: confirmed the existing prompt-injection section, proposed unknown-cancellation interpretation, Stage 4 risks, supplied-data findings, and current persistent instructions.

### 35. Requested scoped write permission

- Purpose: update only approved project control records.
- Tool: filesystem permission request restricted to the project `Assignment1` directory.
- Result: permission granted for this turn.

### 36. Added continuous risk-analysis controls and register

- Tool: `apply_patch`.
- Files modified:
  - `AGENTS.md`: added permanent proactive analysis, seven-part risk assessment, stage-end review, evidence-based statuses, and preserved authorization boundaries; clarified actual-active-bid liquidation sizing and engine-only versus total-application timing.
  - `AI_DECISIONS.md`: accepted the continuous methodology and Stage 4 measurement boundaries; kept unknown-cancellation sequence advancement proposed; added a structured 22-entry Risk Register.
  - `ACTION_LOG.md`: added this operational record.
- Result: technical edge cases, experimental risks, security findings, and unresolved interpretations remain separately classified. No risk was marked mitigated or verified without an existing control or recorded evidence.

No dataset was generated. No implementation, test, benchmark, dependency, environment, network, Git, or GitHub action occurred.

### 37. Verified the permanent risk-record update

- Command: checked that `02_data/generated` remained empty and used `Select-String` to verify the proactive-risk section, accepted decisions, proposed unknown-cancellation wording, actual-active-bid rule, timing boundary, Risk Register heading, and final RR-022 entry.
- Result: all required records were present and generated item count remained zero.

## 2026-11-22 - Stage 2B: workload generation and paired concentration transformation

### 38. Performed Stage 2B preflight

- Purpose: prevent overwrite, confirm source integrity, and verify capacity before generation.
- Commands and results:
  - Checked `02_data/generated`: zero items.
  - Hashed the preserved generator: `ef7f31545addf576e6071cc20a5930f3e2ed93bfef96d4968150fad763d7fe7d`, 4,019 bytes.
  - Confirmed `generated_manifest.json` and `generate_workloads.py` did not exist.
  - A restricted PowerShell free-space helper failed without modifying anything; a read-only Python `shutil.disk_usage` check then reported 285,423,149,056 free bytes.
- Files changed: none.

### 39. Requested scoped Stage 2B write permission

- Purpose: create only the approved orchestrator, manifest, workload/metadata outputs, and approved record updates.
- Tool: filesystem permission request restricted to the project `Assignment1` directory.
- Result: permission granted for this turn.

### 40. Created and checked the Stage 2B orchestration helper

- Tool: `apply_patch` created `02_data/generate_workloads.py`.
- Implemented controls: fixed 40-file core matrix, three paired transformations, 43-name uniqueness check, exact event-total check, generator hash check, staging-only finalization, 120-second direct-generation timeout, 30-minute total limit, 512 MiB limit, sequential execution, incremental manifest, structural validation, metadata verification, coverage metrics, deterministic spot check, source-pair comparison, final 45-combination check, and `--verify-only` mode.
- Commands:
  - In-memory `compile(...)` syntax check: `SyntaxCheck=OK`.
  - `python ...\02_data\generate_workloads.py --help`: succeeded and showed only `--execute` and `--verify-only` modes.

### 41. Generated and validated the approved Stage 2B matrix

- Exact top-level command: `python "<PROJECT_ROOT>\02_data\generate_workloads.py" --execute`
- Direct-generation command form recorded per workload in `02_data/generated_manifest.json`: current `sys.executable`, unchanged instructor generator, scenario, events, levels 1,000, seed, and exact staging/final output paths.
- Results:
  - 40 direct generator workloads completed and validated.
  - Three paired price-only transformations completed and validated.
  - All 43 workload and 43 metadata files finalized.
  - Full actual/reproduction commands, stdout, elapsed times, coverage metrics, metadata, file sizes, and SHA-256 values were saved in `generated_manifest.json` rather than duplicated here.
  - No failure occurred.

### 42. Verified paired transformations and reproducibility

- Formula: recover passive depth using the instructor references, calculate `bucket = min(3, (depth * 4) // 1000)`, then apply the instructor BUY/SELL price formulas with the bucket.
- Results for seeds 42, 43, and 44:
  - 100,000 events each.
  - Non-price mismatches: zero.
  - Formula mismatches: zero.
  - Quantity totals equal: true.
  - Monotonic: true.
  - Uncrossed: true.
  - Bid prices: 6,000,000; 5,999,999; 5,999,998; 5,999,997.
  - Ask prices: 6,000,100; 6,000,101; 6,000,102; 6,000,103.
- Deterministic spot check: the regenerated seed-42 paired gzip SHA-256 matched the finalized file; the exact temporary staging file was then removed.
- Staging directory: empty and removed with non-recursive `rmdir` by the helper.

### 43. Ran independent final revalidation

- Exact command: `python "<PROJECT_ROOT>\02_data\generate_workloads.py" --verify-only`.
- Additional read-only checks: rehashed every original package file against its preserved copy; checked staging absence and searched for million-event filenames.
- Results:
  - Generated workloads: 43.
  - Generated metadata files: 43.
  - Core combinations including supplied streams: 45.
  - Paired workloads: 3.
  - Generated directory size: 22,735,805 bytes.
  - Supplied source/destination mismatches: zero.
  - Staging directory present: false.
  - Million-event files: zero.

### 44. Inspected the finalized generated manifest

- Read-only command: parsed `02_data/generated_manifest.json` and summarized record counts, timings, failures, Python, deterministic evidence, paired invariants, file size, and hashes.
- Results:
  - Manifest status: `complete`.
  - Direct records: 40; paired records: 3; failures: zero.
  - Total elapsed: 76.58006449975073 seconds.
  - Direct generator elapsed sum: 26.7980269026011 seconds.
  - Maximum direct call: 1.56999230012298 seconds.
  - Python: CPython 3.13.17.
  - Manifest: 209,205 bytes before this documentation update; SHA-256 `8e3a632738c6b61a57d6389e2154949c427e81397f97245d8dd0c7c4c97fd801`.
  - Orchestrator SHA-256: `5ebfd34a1b08873f6de7db666714024192e80584be722cdfbd0f6da1670417ee`.

No correctness test, matching engine, benchmark, one-million-event workload, dependency installation, network action, Git command, or GitHub operation occurred.

### 45. Performed final filesystem audit and interpreter-cache cleanup

- Read-only audit results: 43 finalized workloads, 43 finalized metadata files, generated directory size 22,735,805 bytes, unchanged complete manifest SHA-256 `8e3a632738c6b61a57d6389e2154949c427e81397f97245d8dd0c7c4c97fd801`, and required README/decision/risk sections present.
- Detected temporary artifact: Python created `02_data/__pycache__/validate_inputs.cpython-313.pyc` while importing the approved validator.
- Safety verification: resolved the cache directory inside the project `02_data` path, enumerated its exact contents, and required the single expected 16,825-byte cache filename before cleanup.
- Cleanup command: removed that exact `.pyc` file and then the now-empty exact `__pycache__` directory with literal paths; no recursive delete was used.
- Result: cache directory no longer exists. No supplied file, generated workload, finalized metadata, manifest, or unrelated file was removed.

Stage 2B completed and stopped here. Stage 3 has not begun.

## 2026-11-22 - Stage 2B documentation and portable-reproduction correction

### 46. Captured the pre-change integrity baseline

- Purpose: prove that the manifest migration did not alter workload meaning, historical commands, or generated files.
- Read-only commands and observed results:
  - `Get-FileHash -LiteralPath '.\02_data\generated_manifest.json' -Algorithm SHA256`: `8e3a632738c6b61a57d6389e2154949c427e81397f97245d8dd0c7c4c97fd801`.
  - Parsed the actual manifest schema and calculated a canonical inventory over workload parameters, source provenance, workload SHA-256 values, metadata SHA-256 values, and supplied coverage: 43 workloads; semantic SHA-256 `c3c374d10e98c2b1b8a6ee226636e98458676248f514f04f8833ed96f3324c41`.
  - Hashed the ordered 40 `actual_command` arrays: `2e0b302b52ec3b43655378b0f415e7990efc69da9b4701699010b1aff857924e`.
  - Hashed the name-plus-content-hash inventory of all generated workload and metadata files: 86 files, 22,735,805 bytes, inventory SHA-256 `e097b248e1918d43d47c8e721e9a9e5ceebd9edf739ba4a67fd01057b86d61b5`.
- Harmless failures: one earlier PowerShell quoting attempt failed before execution, and one read-only Python query assumed a nonexistent `workloads` key and raised `KeyError`. Neither command wrote a file. An initial multi-operation `apply_patch` request was rejected by the patch tool before changing anything; the patch was reapplied in supported form.

### 47. Updated the five approved files

- `AI_DECISIONS.md`: retained one canonical current row for each of RR-001 through RR-023; kept RR-014 `MITIGATED`; changed RR-015 and RR-022 to `OPEN`; added a separate Risk Status History table.
- `README.md`: replaced the original-user-directory-dependent reproduction examples with Windows PowerShell and macOS/Linux commands that first change to the project root and then use relative paths. It now distinguishes immutable historical evidence from portable reproduction commands.
- `02_data/generate_workloads.py`: added schema-v2 output, portable command fields, explicit historical-context labels, canonical semantic hashing, and a one-time `--migrate-manifest-v2` mode guarded by the exact schema-v1 manifest hash.
- `02_data/generated_manifest.json`: migrated from schema 1 to schema 2. Exact `actual_command` arrays and former absolute final-path commands remain historical evidence; portable project-relative command arrays were added.
- `ACTION_LOG.md`: added this factual correction and verification record.

### 48. Ran the approved lightweight checks and manifest migration

- In-memory `compile(...)` syntax check: `PASS`.
- `python .\02_data\generate_workloads.py --help`: succeeded and listed `--execute`, `--verify-only`, and the one-time `--migrate-manifest-v2` maintenance mode.
- `python .\02_data\generate_workloads.py --migrate-manifest-v2`: succeeded only after matching the approved old hash.
- Migration evidence:
  - Previous manifest SHA-256: `8e3a632738c6b61a57d6389e2154949c427e81397f97245d8dd0c7c4c97fd801`.
  - New manifest SHA-256: `5c408a6ac8aec13f0596f20ab974a526fe238a99f2f68ec32195a1a82ee16ca5`.
  - Semantic inventory before and after: `c3c374d10e98c2b1b8a6ee226636e98458676248f514f04f8833ed96f3324c41`.
  - Historical actual-command digest before and after: `2e0b302b52ec3b43655378b0f415e7990efc69da9b4701699010b1aff857924e`.

### 49. Revalidated the migrated record and unchanged generated files

- `python .\02_data\generate_workloads.py --verify-only`: succeeded without regeneration.
- Observed results: 43 workloads, 43 metadata files, 45 core combinations including supplied files, three paired workloads, and 22,735,805 generated bytes.
- Post-migration inventory: the same 86 files and `e097b248e1918d43d47c8e721e9a9e5ceebd9edf739ba4a67fd01057b86d61b5` digest; therefore no generated workload or metadata byte changed.
- Portable-field scan: no original `<USERPROFILE>` path in the README or portable manifest fields. Machine-specific paths remain only in explicitly labelled historical manifest evidence and this action history.
- Risk-table scan: 23 canonical rows, 23 unique IDs, no duplicate current entry; RR-014 `MITIGATED`, RR-015 `OPEN`, RR-022 `OPEN`.
- No interpreter cache remained after the checks.

No workload was regenerated. No correctness test, matching engine, benchmark, dependency installation, environment change, network action, Git command, or GitHub operation occurred. Stage 3 has not begun.

## 2026-11-22 - Final Stage 3 contract review and RED checkpoint

### 50. Performed the final read-only specification comparison

- Read the preserved instructor `README.md`, `worked_example.jsonl`, and `worked_expected.json` and compared their exact field names, statuses, fills, remaining orders, and proceeds with the proposed Stage 3 contract.
- Attempted read-only PDF inspection with `pdfinfo` and `pdftotext`; neither executable was installed. Checked for already-installed `pypdf`, `pdfplumber`, `fitz`, `PyPDF2`, `pymupdf`, `pdfminer`, and `pikepdf`; none was available. No dependency was installed. Used the earlier recorded complete page-level PDF review only as secondary evidence and did not claim a fresh PDF extraction.
- Verified correction: canonical inspection uses the worked fixture's `qty_units` field in one BUY-then-SELL ordered list rather than introducing `remaining_qty_units`.
- Independently recomputed worked proceeds as `3,594,000,000,000,000` tick-units, equal to `359,400.00` dollars under the instructor conversion.

### 51. Verified empty approved paths and requested scoped permission

- A first PowerShell existence-check pipeline had a parser error and changed nothing.
- A read-only Python retry confirmed that all eight approved test files and all six package/stub files were absent and that `03_tests` and `04_implementation/orderbook` were empty.
- Requested and received write permission limited to `03_tests`, `04_implementation/orderbook`, `AI_DECISIONS.md`, and `ACTION_LOG.md`.

### 52. Created the Stage 3 test suite and minimal RED stubs

- Created eight test files: `support.py`, seven behavioral/test modules, and the transition-verifier self-test module under `03_tests`.
- Created six package files: `__init__.py`, `contracts.py`, `validation.py`, `baseline.py`, `optimized.py`, and `replay.py` under `04_implementation/orderbook`.
- An initial multi-file patch used a misspelled parent path for `support.py`; it stopped at that file after creating the six approved package files. The misspelled directory did not exist and was not created. A corrected patch then created the approved test support file.
- Both engine classes expose the approved interface. `process_event`, `AddLimitOrder`, `CancelOrder`, and `FillMarketSell` raise `NotImplementedError`; replay and stateless validation also raise `NotImplementedError`. No matching, cancellation, mutable order storage, or state-dependent validation was implemented.

### 53. Ran pre-RED infrastructure gates

- In-memory `compile(...)` check: all 14 Python source files passed.
- Command-scoped `PYTHONPATH` import check: `BaselineOrderBook`, `OptimizedOrderBook`, validation, and replay imported; both books constructed with empty snapshots.
- Read-only unittest discovery: initially 43 tests, then 45 after approved focused additions.
- Exact fixture-only check: one test passed.
- Transition-verifier self-test command: nine tests passed, including valid transitions and deliberately corrupted price, FIFO, quantity, residual, snapshot, rejection, and sequence cases.
- Added an oracle-integrity gate so every deterministic expected sequence is passed through the transition verifier before either engine is invoked.

### 54. Ran and corrected the complete RED suite

- First complete command: `python -m unittest discover -s '.\03_tests' -p 'test_*.py' -v` under command-scoped `PYTHONPATH`.
- Initial observed result before the focused additions: 43 tests and 84 error entries; the visible traces were intentional stub errors.
- Correction: changed only the test regex to use `re.escape`; no contract or stub behavior changed.
- Added the approved explicit noncrossing-opposite-side case, market-sell live-ID collision case, direct `CancelOrder` parity case, and pre-engine oracle verification.
- The first 45-test error-type audit then found 89 intended `NotImplementedError` entries and one replay-test `re.PatternError` caused by an unescaped Windows path.
- Final standard RED command returned exit code 1 as intended: 45 tests run, `FAILED (errors=90)`.
- Final in-memory classification reran the same discovered suite and observed:
  - Successful test methods: 12.
  - Error entries: 90.
  - Assertion-failure entries: zero.
  - Skipped tests: zero.
  - Error types: 90 `NotImplementedError`; no other error type.
  - Sources: 25 baseline event-processing, 24 optimized event-processing, two replay-processing, and 39 stateless-validation stub errors.

### 55. Recorded decisions and performed the final Stage 3 audit

- Updated `AI_DECISIONS.md` with the approved result/interface contract, validation and sequence decisions, canonical inspection boundary, randomized-test deferral, RED evidence, and current risk statuses.
- Read-only source audit results:
  - Exactly eight approved test files and six approved package files exist.
  - All 14 files compile in memory.
  - Static test-method count is 45.
  - Engine processing methods contain only explicit raises; initial sequence and empty-snapshot inspection are the only stub state behavior.
  - No rejected injected terminology appears in Stage 3 sources.
  - No replay temporary directory remained.
- Python created eight test-cache files and six package-cache files during imports/runs. Their exact names and directories were verified, each exact file was removed, and the two now-empty cache directories were removed non-recursively. Final cache count: zero.
- Final read-only checkpoint audit confirmed 25 unique canonical risk rows, no cache or replay-temporary directory, eight test files, and six package files. Its first instructor-manifest lookup incorrectly assumed a list and raised `AttributeError` without writing anything; a corrected mapping lookup verified unchanged SHA-256 values for both worked files against the instructor manifest (`831015ac...798ec` and `c715f527...54d2c`).

No supplied assignment file, generated workload, benchmark, dashboard, result file, or README was modified. No randomized engine test, dependency installation, network action, Git command, or GitHub operation occurred. Version A and Version B matching implementations have not begun.

## 2026-11-22 - Focused Stage 3 RED corrections

### 56. Applied the two approved test-only corrections

- Modified only `03_tests/test_cancellation_and_sequences.py` and `03_tests/test_differential.py` before verification.
- Repeated cancellation: extended the partial-fill case so the remaining three units are cancelled, the same ID is cancelled again at sequence 4 with `not_found` and zero quantity, the book remains empty, sequence advances, and the following unfilled market sell moves to sequence 5.
- Stateful D10 parity: retained the valid direct `AddLimitOrder` case and added exact fresh-engine parity scenarios for successful active cancellation, market selling against a resting bid, duplicate-live `AddLimitOrder` rejection, and equal-sequence `FillMarketSell` rejection. Each scenario specifies exact results, snapshots, and last accepted sequence; rejection scenarios require unchanged state and sequence.
- No test file, helper, expected assignment fixture, transition-verifier logic, engine stub, or implementation file was added or changed.

### 57. Ran the corrected RED verification gates

- In-memory syntax command compiled all 14 Stage 3 Python files: passed.
- Command-scoped `PYTHONPATH` import check loaded both engines, validation, and replay and constructed two empty stubs: passed.
- Read-only unittest discovery: 45 methods, unchanged because existing methods were strengthened rather than added.
- Transition-verifier command: nine tests passed with zero failures.
- First corrected complete-suite run observed 45 tests and 94 errors. The subsequent classifier identified 92 intended `NotImplementedError` entries plus two `PermissionError` entries because the turn's initial file-specific write grant did not allow the replay tests to create their self-cleaning temporary fixtures under `03_tests`.
- Read-only inspection confirmed no temporary directory was left. Requested and received directory-scoped permission solely for the approved replay test fixtures, then reran with `PYTHONDONTWRITEBYTECODE=1`.
- Final standard RED command: `python -m unittest discover -s '.\03_tests' -p 'test_*.py' -v` under command-scoped `PYTHONPATH`; returned exit code 1 and `FAILED (errors=94)` as intended.
- Final classification:
  - Tests run: 45.
  - Successful test methods: 12.
  - Error entries: 94.
  - Error types: 94 `NotImplementedError`, zero other types.
  - Assertion failures, skips, expected failures, and unexpected successes: zero.
  - Stub sources: one Baseline and one Optimized `AddLimitOrder`, 26 Baseline and 25 Optimized dispatcher, two replay, and 39 stateless-validation errors.

### 58. Performed the post-correction audit

- Confirmed `03_tests` and `04_implementation/orderbook` contain no cache, replay-temporary, or other subdirectory.
- Recompiled the two modified tests in memory: passed.
- Parsed both engine sources: constructors only initialize `last_accepted_seq`; snapshots only return the empty RED value; all event-processing and named operation methods contain only explicit `raise` statements.
- Result: matching, cancellation, state-dependent validation, replay, and stateless validation remain unimplemented by design.

No randomized or mutation test, benchmark, dependency installation, network action, Git command, or GitHub operation occurred. Stage 4 has not begun.

## 2026-11-23 - Stage 4A Version A baseline implementation

### 59. Inspected the approved Stage 4A scope and requested narrow write access

- Read the existing Version A/Version B stubs, shared contracts, validation stub, replay stub, Stage 3 tests, fixtures, root README, action history, and decision/risk record.
- Confirmed the approved boundary: implement Version A, shared stateless validation, replay, one deterministic randomized transition test, and documentation only. Version B, existing Stage 3 tests, benchmarks, datasets, dashboard, and results remained out of scope.
- Requested and received write permission only for the approved implementation/documentation files and the approved new test under `03_tests`.
- One initial combined patch request was rejected before changing any file because it attempted multiple operations on the same target. The supported patch was then applied; no partial content from the rejected patch remained.

### 60. Implemented the transparent baseline and shared stateless validation

- Modified `04_implementation/orderbook/validation.py` to validate event mappings, exact integer fields (with booleans rejected), required fields, nonempty string identifiers, positive price/quantity, known event types, and valid sides. Rejections use the approved stable reason codes and include `event_id` when available.
- Modified `04_implementation/orderbook/baseline.py` to use one list of active orders. It independently performs sequence and duplicate-live-ID checks, maker-price price-time matching, partial-fill updates, exhausted-order cleanup, cancellation, limit residual resting, market residual discard, and detached canonical snapshots.
- Modified `04_implementation/orderbook/replay.py` to replay plain or gzip JSONL sequentially, fail with path and line information for blank/malformed records, and expose `python -m orderbook.replay PATH --engine baseline|optimized`.
- Created `03_tests/test_randomized_transitions.py` with 10 fixed seeds and 40 events per seed. It invokes the independent Stage 3 transition verifier after every accepted or rejected event; it does not implement a reference engine.
- Did not modify `optimized.py`, `contracts.py`, `__init__.py`, or any existing Stage 3 test.

### 61. Ran syntax, import, and CLI gates

- In-memory syntax compilation: 15 Python files passed.
- Command-scoped import check: baseline, optimized stub, validation, and replay imported; both books constructed and returned detached empty snapshots.
- `python -m orderbook.replay --help`: passed and showed required `PATH` plus `--engine {baseline,optimized}`.
- `PYTHONDONTWRITEBYTECODE=1` was used for test/import commands to prevent cache artifacts.

### 62. Ran the exact Version A projection

- The exact portable PowerShell command is retained verbatim in `README.md`; it was executed from the project root with command-scoped `PYTHONPATH`.
- The command discovered the entire suite, required the exact two-engine-only method ID once, injected only `BaselineOrderBook` into `support.ENGINE_CLASSES`, and excluded only `test_differential.TestDifferentialObservations.test_each_engine_matches_oracle_before_cross_engine_comparison`.
- Observed result: `discovered=46 included=45 excluded=1`; `run=45 failures=0 errors=0 skipped=0 successful=True`.
- Reason for the one exclusion: that method requires two observation entries for a cross-engine comparison. All Version A behavior within it is already checked against the independent oracle by the applicable engine tests; no Version A expectation was weakened or rewritten.

### 63. Verified the supplied worked example and replay entry point

- A first read-only verification script imported a nonexistent helper name, `replay_path`, and raised `ImportError`; the following CLI command still passed because the PowerShell command did not stop on the earlier native-process failure. No file was changed. Inspection showed the actual documented helper is `replay_file`.
- Reran the direct check with `replay_file`. Observed: six events; exact final market-sell result matched; exact remaining canonical orders matched; gross proceeds equalled `3,594,000,000,000,000` tick-units.
- The command-line replay of `02_data/supplied/data/worked_example.jsonl` with `--engine baseline` returned successfully.

### 64. Audited the unchanged full suite

- Ran all tests with the ordinary discovered two-engine matrix and captured results without changing tests.
- Initial classifier intercepted ordinary errors but not subtest errors; a second classifier was too narrow because one optimized direct-operation stub has a different method-specific message. These were audit-script classification limitations only.
- Final traceback classification accepted only explicit `NotImplementedError: Optimized ... intentionally absent in RED` messages.
- Observed result: 46 methods run, zero assertion failures, 37 error entries, zero skips; all 37 errors were from untouched `OptimizedOrderBook` stubs and there were zero other errors.

### 65. Recorded the Stage 4A evidence and future policies

- Updated `README.md` with Version A architecture/complexity, the exact baseline projection command and result, portable replay commands, untouched-Version-B RED status, and the proposed stopped-run benchmark policy.
- Updated `AI_DECISIONS.md` with accepted Version A design/validation/randomized-test decisions, the unexecuted mutation plan, proposed benchmark limits, actual GREEN evidence, and remaining risks.
- Proposed benchmark ceiling only; no benchmark was executed: 90 minutes primary replay, 45 minutes separate diagnostic modes, and 15 minutes verification, with first-timeout termination per engine/workload configuration.

No mutation experiment, benchmark, Version B implementation, dependency installation, environment change, network access, Git command, or GitHub operation occurred.

### 66. Performed the final Stage 4A read-only integrity audit

- Compiled all 15 implementation/test Python files in memory: passed.
- README Markdown fence count: 28, an even and balanced count.
- Canonical Risk Register: 25 rows and 25 unique IDs; no duplicate current-status entry.
- Untouched Version B check: `optimized.py` SHA-256 `60617165c7aae2fe11a5252313ddddea4d9485e6f52d873e60bea759473d8fba`; all four processing-operation methods still contain explicit raises.
- Supplied fixture preservation: `worked_example.jsonl` SHA-256 `831015ac71d56ada0898b0bf8f59f125900b4dc32134d6ef37bd3cec304798ec`; `worked_expected.json` SHA-256 `c715f52724df6bbfcedcad0e203ddb5a7752d38c809f4cf12b513ba809554d2c`.
- Generated-manifest preservation: SHA-256 `5c408a6ac8aec13f0596f20ab974a526fe238a99f2f68ec32195a1a82ee16ca5`, unchanged from the Stage 2 migration record.
- Cache artifacts: zero.

## 2026-11-23 - Stage 4B Gate A focused mutation verification

### 67. Established the immutable production baseline and exact detectors

- User evidence: the user confirmed that the verified Version A GREEN checkpoint was manually committed and that Git showed no uncommitted production-source changes. The assistant performed no Git or GitHub operation.
- Hashed every Python production source before mutation work:
  - `__init__.py`: `3d66c22f15c7324adc9c92c4dc90c2556dca30b94d0516a4e338f4cb8a46f71a`
  - `baseline.py`: `a9836eb21682a82491c01935fe46475b88b69f817f9556964e9ade6f82565f8b`
  - `contracts.py`: `c2d55a0b9eb45fd18e2e9035b71b21652ffbc9a3844857a849026ba04bae1e6b`
  - `optimized.py`: `60617165c7aae2fe11a5252313ddddea4d9485e6f52d873e60bea759473d8fba`
  - `replay.py`: `0b74f1a87cb396a591b9b853d947c9720336d393853bed2160aac1dda66461ba`
  - `validation.py`: `d22baa7d2c288e200ba5e1a3772bb34c62c15924b9a5882cf2e857202879f517`
- Discovered test methods from the actual files. Confirmed that the matching module is `test_matching.py`, not the earlier speculative `test_limit_matching.py` name.
- Ran each of the six exact detector IDs against unmodified Version A before mutation. Each ran once and passed with zero failures and zero errors.
- Exact detectors:
  1. `test_matching.TestMatching.test_partial_fill_preserves_fifo_for_follow_up_taker`
  2. `test_matching.TestMatching.test_multilevel_crossing_buy_rests_residual_with_original_sequence`
  3. `test_matching.TestMatching.test_one_unit_exact_price_crossing`
  4. `test_cancellation_and_sequences.TestCancellationAndSequences.test_cancel_middle_and_last_order_then_follow_up_match`
  5. `test_cancellation_and_sequences.TestCancellationAndSequences.test_equal_decreasing_and_other_rejections_are_atomic`
  6. `test_validation.TestStatelessValidation.test_exact_integer_validation_rejects_bool_float_string_and_none`

### 68. Created the isolated mutation workspace safely

- Requested write permission for the approved temporary subtree and the two approved logs. The sandbox could not create a child under a grant for a nonexistent path, so a project-root write grant was requested for the technical operation; actual writes remained limited to `mutation_gate_a_tmp` and the logs.
- First creation attempt changed nothing: constrained PowerShell rejected a static path-method call and the narrow permission denied directory creation/copying.
- Created a fresh `source/orderbook` copy for each mutation. Original production and test files were never patched, renamed, deleted, overwritten, or restored.
- Each mutation ran in a new Python subprocess with `PYTHONDONTWRITEBYTECODE=1` and its temporary `source` first on `PYTHONPATH`.
- Every subprocess printed the resolved imported module path. Each path pointed to that mutation's temporary `baseline.py` or `validation.py`, never production.
- Recomputed all six original production hashes before and after every mutation. Every comparison was exact.

### 69. Executed six mandatory primary mutations

1. FIFO priority reset after partial fill — `KILLED`.
   - Temporary change: a partially filled maker received a new later arrival sequence.
   - Detector observed `AssertionError` at the expected-snapshot invariant.
   - Activation evidence: after the first partial fill, maker `z` changed from arrival sequence 1 to 3 and sorted behind `a`; the follow-up fills were `a:4` then `z:1`, rather than `z:3` then `a:2`.
2. Taker-price execution — `KILLED`.
   - Temporary change: crossing-limit fills were rewritten to the incoming limit price.
   - Detector observed `AssertionError` at exact result comparison.
   - Activation evidence: the two fill prices were `[100, 100]` instead of maker prices `[99, 100]`.
3. Strict crossing — `KILLED`.
   - Temporary change: inclusive `<=`/`>=` eligibility became strict `<`/`>`.
   - Detector observed `AssertionError` at exact result comparison.
   - Activation evidence: equal-price BUY and SELL orders both rested, with status `resting` and no fills, instead of executing.
4. Cancelled order retained — `KILLED`.
   - Temporary change: successful cancellation returned `cancelled` without removing the order.
   - Detector observed `AssertionError` at the expected-snapshot invariant.
   - Activation evidence: the result reported two units cancelled while order `b` remained active with two units.
5. Mutation before validation — `KILLED`.
   - Temporary change: a market-sell path decremented a resting maker before stateless validation.
   - Detector produced two relevant assertion failures, beginning with rejected-event snapshot atomicity.
   - Activation evidence: invalid zero-quantity market sell returned `rejected`, sequence remained 10, but active quantity changed from 1 to 0. This was an actual pre-rejection state mutation, not a behaviorally neutral statement reorder.
6. Booleans accepted as integers — `KILLED`.
   - Temporary change: exact `type(value) is int` checks became `isinstance(value, int)` for sequence, price, and quantity.
   - Detector produced three directly relevant assertion failures for `False` (`invalid_sequence`/`nonpositive_*` instead of `invalid_field_type`) and three directly related errors for `True`, where accepted validation returned `None` and the test attempted to inspect a rejection.
   - Activation evidence: `validate_event` returned `None` for valid LIMIT events with `True` in each of `seq`, `price_ticks`, and `qty_units`.
- Summary: six `KILLED`, zero `SURVIVED`, zero `INVALID`. No material test-coverage weakness was found. The boolean detector could later use `assertIsNotNone` for clearer diagnostics, but it reliably detects the defect and does not require a Gate A correction.

### 70. Removed temporary artifacts and reverified original Version A

- Removed each verified mutation directory using its exact resolved path after its run. No supplied, generated, production, test, or unrelated file was removed.
- The final staging parent contained zero entries. Its first removal attempt was denied by Windows. Inspection found attributes `ReadOnly, Directory, Archive, ReparsePoint`; constrained PowerShell disallowed changing the property, but the subsequent exact native PowerShell removal succeeded. Final `mutation_gate_a_tmp` existence: false.
- Reran the original Version A projection against `04_implementation`: 46 methods discovered, 45 applicable, exactly one two-engine comparison excluded; 45 run, zero failures, zero errors, zero skips, successful true.
- Final hashes for all six production sources exactly matched the pre-mutation values above.
- Final cache audit: zero `__pycache__` directories and zero `.pyc` files.

No original production source or correctness test was modified. No secondary mutation, Version B implementation, future Version B test file, benchmark, data generation, dependency installation, network access, Git command, or GitHub operation occurred.

### 71. Performed the final Gate A documentation and integrity audit

- Rehashed all six production sources after log updates: every value still matched the immutable Gate A baseline.
- Confirmed the mutation staging directory is absent and cache counts remain zero.
- Confirmed the new Gate A evidence sections exist in both approved logs.
- An auxiliary PowerShell expression incorrectly isolated zero Risk Register rows because of its string-splitting expression; it did not modify anything and was not treated as document evidence.
- Corrected read-only Python check: 25 canonical Risk Register rows, 25 unique IDs, no duplicates.

## 2026-11-23 - Stage 4B Gate B optimized implementation and verification

### 72. Audited the approved contracts, test support, and workload inventory

- Read the optimized stub, package exports, independent transition verifier, existing tests, and generated 1,000-event filenames.
- Confirmed fifteen existing 1,000-event core streams: five scenarios × seeds 42/43/44. No dataset was generated or modified.
- Requested write permission only for the four approved existing files and two approved new test files. A later project-root grant was used solely for approved temporary mutation copies.
- An initial combined patch was rejected before changing anything because it attempted delete and add operations on `optimized.py` in one request. The same content was applied in supported single-target steps.

### 73. Implemented independent Version B and its approved tests

- Replaced the optimized RED stub with implementation-owned order objects, `active_by_id`, bid/ask level dictionaries, `OrderedDict` FIFO queues, side-specific heaps, generation-tagged entries, stale-top cleanup, and bounded rebuilds.
- Implemented Version B's own sequence/live-ID validation, matching, partial fills, cancellation, level cleanup, and canonical inspection. It reuses only shared stateless validation and contracts.
- Compaction condition: `heap_length > 2 * active_level_count + 64`, evaluated after both level insertion and deletion.
- Created `03_tests/test_optimized_invariants.py` with four methods covering index union, unique membership, FIFO, partial fills, cancellation/exhaustion cleanup, generation recreation, heap bounds under 160 churn cycles, rebuild behavior, and post-rebuild price priority.
- Created `03_tests/test_pregenerated_differential.py`, comparing exact results, ordered fills, accepted sequence, canonical snapshots, and independent transition verification after each of 15,000 existing events.

### 74. Ran implementation and internal-invariant gates

- First syntax/import command used `03_tests` as its working directory while resolving root-relative paths. It found zero files and raised `ModuleNotFoundError`; no file changed.
- Corrected root-based gate compiled all 17 implementation/test Python files, imported production `optimized.py`, and constructed an empty engine.
- Optimized internal tests: four run in 0.002 seconds, four passed.
- The first compact full-suite runner returned no usable output or exit code and was treated as inconclusive evidence.
- The ordinary verbose suite ran substantive tests successfully but the two existing replay tests raised `PermissionError` because the sandbox blocked their self-cleaning temporary directories under `03_tests`.
- Requested and received directory-scoped permission only for those replay fixtures. No test source changed and no fixture remained.

### 75. Established complete GREEN evidence

- Reran complete discovery after fixture permission: 51 tests, zero failures, zero errors, zero skips, successful true.
- Exact Version A regression projection: 51 discovered; six Version-B/two-engine-only methods excluded; 45 original applicable tests run; zero failures and errors.
- Version B worked example: six events; exact final market result, final canonical snapshot, and gross proceeds all matched supplied expectations.
- Fixed-seed randomized transition test passed for both engines as part of complete discovery.
- Pre-generated differential test passed for fifteen files and 15,000 events, with comparisons after every event.
- Internal index/FIFO/heap/cleanup tests: four passed.

### 76. Executed three isolated Version B mutations

- Pre-mutation production hashes:
  - `__init__.py`: `3d66c22f15c7324adc9c92c4dc90c2556dca30b94d0516a4e338f4cb8a46f71a`
  - `baseline.py`: `a9836eb21682a82491c01935fe46475b88b69f817f9556964e9ade6f82565f8b`
  - `contracts.py`: `c2d55a0b9eb45fd18e2e9035b71b21652ffbc9a3844857a849026ba04bae1e6b`
  - `optimized.py`: `ba02ec39a8d191cf0b6b2adffeaf0e7057201df27c3687cd0cf6694a3624dbaf`
  - `replay.py`: `0b74f1a87cb396a591b9b853d947c9720336d393853bed2160aac1dda66461ba`
  - `validation.py`: `d22baa7d2c288e200ba5e1a3772bb34c62c15924b9a5882cf2e857202879f517`
- Each detector passed unmodified before mutation. Every mutation used a fresh `mutation_gate_b_tmp` package and subprocess; each printed an imported path inside that temporary copy.
- Retain exhausted order in `active_by_id` — `KILLED` by `test_optimized_invariants.TestOptimizedInternalInvariants.test_exhaustion_and_cancellation_remove_all_indexes`. The union invariant reported exhausted `b1` only in `active_by_id`; direct activation showed zero-quantity `b` retained with no bid level.
- Fail to remove empty price level — `KILLED` by the same detector. It asserted that `OrderedDict()` at an active level was empty; direct activation showed `{100: []}` with an empty active index.
- Disable generation validity — `KILLED` by `test_optimized_invariants.TestOptimizedInternalInvariants.test_recreated_price_invalidates_old_heap_generation`. Generation 1 incorrectly became valid after price 100 was recreated as generation 2.
- All six production hashes matched after every mutation. Summary: three `KILLED`, zero `SURVIVED`, zero `INVALID`.

### 77. Cleaned mutation artifacts and reran final production GREEN

- Removed each exact resolved mutation directory after its experiment and removed the verified empty `mutation_gate_b_tmp` parent. No production, test, data, or unrelated file was removed.
- Final production suite after mutation cleanup: 51 tests, zero failures, zero errors, zero skips, successful true.
- Documented the provisional timeout rule and proposed an unexecuted 12-minute runtime pilot. No benchmark or pilot ran.

No existing correctness test, baseline, validation, replay, contract, package export, supplied dataset, or generated workload was modified. No benchmark, data generation, dependency installation, network access, Git command, or GitHub operation occurred.

### 78. Performed final Gate B integrity audit

- Compiled all 17 implementation/test Python files in memory: passed.
- Final production SHA-256 values matched the post-implementation, pre-mutation set, including optimized `ba02ec39a8d191cf0b6b2adffeaf0e7057201df27c3687cd0cf6694a3624dbaf` and unchanged baseline `a9836eb21682a82491c01935fe46475b88b69f817f9556964e9ade6f82565f8b`.
- README Markdown fences: 34, balanced.
- Canonical Risk Register: 25 rows, 25 unique IDs.
- Mutation staging directories present: zero. Cache directories and `.pyc` files: zero.
- Confirmed the six authorized changed/created documentation, implementation, and test files exist with nonzero content.

## 2026-11-23 - Stage 4C benchmark pilot

### 79. Reviewed and bounded the authorized pilot

- Confirmed the three authorized output/script paths did not exist before work.
- Rehashed all six production package files before implementation; hashes matched the Gate B checkpoint.
- Pilot scope: five supplied 10,000-event scenarios plus generated 100,000-event `buildup`, `cancel_churn`, and `sweep`, seed 42, both engines, one repeat: 16 runs.
- Limits: 30/120 seconds processing, 15/45 seconds preparation, and 1,200 seconds globally.

### 80. Created the controller and worker

- Created `05_benchmarks/run_benchmarks.py` and `05_benchmarks/_benchmark_worker.py` using only the Python standard library.
- Implemented nonce-matched `READY`, `START`, `STARTED`, and `DONE` messages; preparation and processing deadlines; exact-handle terminate/kill/wait cleanup; fresh engines; pre-timing parsing and `gc.collect`; GC enabled during replay; and post-timing canonical snapshot hashing.
- Implemented 16 incremental JSONL records, explicit statuses, portable workload identifiers, environment metadata, refusal to overwrite, and a hard maximum global limit.
- No matching engine or correctness test changed.

### 81. Ran non-benchmark preflight checks

- Compiled both scripts and displayed controller/worker help successfully.
- Audited plan: 16 runs, ten at 10,000 events and six at 100,000; processing caps totaled 1,020 seconds and preparation caps 420 seconds.
- Confirmed alternating engine order and absence of name/pattern-based termination commands.

### 82. Executed the single authorized pilot

- Exact command: `python '05_benchmarks/run_benchmarks.py' pilot --output '07_results/pilot/pilot_runs.jsonl' --global-timeout-seconds 1200` with `PYTHONDONTWRITEBYTECODE=1`.
- Controller summary: 16 planned and written records; 14 `completed`, two `timed_out`; total wall time 288.3100479003042 seconds; exit code zero.
- Completed engine times in seconds:
  - 10,000 buildup: Version A 11.660955300554633; Version B 0.04928850010037422.
  - 10,000 crowded: Version A 11.593628799542785; Version B 0.042383600026369095.
  - 10,000 mixed: Version A 0.7229573996737599; Version B 0.04173330031335354.
  - 10,000 sweep: Version A 11.840532699599862; Version B 0.050656200386583805.
  - 10,000 cancel_churn: Version A 0.04027129989117384; Version B 0.03128490038216114.
  - 100,000 buildup: Version B 0.6360587999224663; Version A timed out at the 120-second processing limit.
  - 100,000 cancel_churn: Version A 0.26394759956747293; Version B 0.31906820088624954.
  - 100,000 sweep: Version B 0.6901657003909349; Version A timed out at the 120-second processing limit.
- Both timeouts were censored observations: no engine time, throughput, or final snapshot digest was fabricated.

### 83. Validated pilot integrity and cleanup

- JSONL: 16 records, 17,726 bytes, all `phase: pilot`, sequential planned indexes 1–16, portable workload identifiers, SHA-256 `c731a54589b63e441f0451fe17eaaf93275de765865632a3e07971953ed100f1`.
- All eight engine pairs had equal event-stream digests. Six pairs completed on both engines and had equal final snapshot digests. The two timed-out pairs were correctly not compared.
- Maximum preparation time was 0.8466493999585509 seconds, below every preparation limit.
- Exact-PID inspection after the run found one reused PID belonging to Windows `conhost.exe`, not Python. The controller had already waited/reaped every worker; no benchmark worker remained.
- Production package hashes remained unchanged. A constrained-PowerShell filename-formatting expression raised harmless method-invocation errors while still printing the correct hashes; a Python retry printed filenames and hashes correctly.

### 84. Performed the authorized privacy audit

- Searched README, ACTION_LOG, AI_DECISIONS, AGENTS, and `08_documentation` for Windows/macOS/Linux personal home paths.
- Findings: ten occurrences, all in `ACTION_LOG.md` at lines 10, 17, 31, 46, 66, 77, 254, 395, 421, and 494 at scan time. They are historical command/environment evidence involving the Windows username. No finding occurred in README, AI_DECISIONS, AGENTS, or `08_documentation`.
- No text was redacted or rewritten. Proposed correction requires user approval: if ACTION_LOG is public, replace the personal prefix with `<USERPROFILE>` and the Codex installation prefix with `<CODEX_HOME>`, label the changes as privacy redactions, and preserve the original log hash/private historical copy separately.

No full benchmark, latency, memory, diagnostic, liquidation, dashboard, or report work occurred. No dependency installation, network access, Git command, or GitHub operation occurred.

### 85. Performed final Stage 4C integrity and cleanup audit

- Recompiled both benchmark scripts: passed.
- Revalidated 16 pilot records, 14 completed/two timed out, and unchanged result SHA-256 `c731a54589b63e441f0451fe17eaaf93275de765865632a3e07971953ed100f1`.
- Confirmed only the two approved benchmark scripts and one approved pilot JSONL exist in their new locations.
- Rehashed all production package files: unchanged from Gate B.
- README fences: 38 and balanced; canonical Risk Register: 25 rows and 25 unique IDs.
- Detected `03_tests/__pycache__` containing eleven `.pyc` files timestamped earlier on 23 November. Verified the exact project-contained path, exact count, and `.pyc` extensions; removed each exact file and then the empty directory. No test source was modified. Final cache count: zero.
- Final privacy scan reproduced the same ten historical ACTION_LOG findings and no findings in README, AI_DECISIONS, AGENTS, or `08_documentation`.

## 2026-11-23 - Stage 4D resumable final-primary implementation

### 86. Audited the interrupted implementation read-only

- The user interrupted Stage 4D after one successful partial patch.
- Confirmed only `05_benchmarks/run_benchmarks.py` had changed during the interrupted session. It compiled, but contained only plan/hash/resume parsing helpers; no final runner or CLI existed.
- Confirmed `07_results/raw/timing.jsonl` was absent, the pilot retained 16 records and its checksum, all production hashes matched Gate B, and no cache existed.
- A filtered CIM command-line process query was denied by Windows and its zero count was rejected as evidence. A narrower `Get-Process` check succeeded and found zero Python/PythonW processes; no benchmark worker was running.

### 87. Completed final planning and strict resume integration

- Continued the existing controller without reverting or duplicating helpers.
- Added the 450-repetition plan: five scenarios × three sizes × three seeds × two engines × five repetitions, in increasing event-size order with alternating engine order.
- Added manifest-backed verification of 45 workload hashes, engine-source hashes, environment fingerprint, GC/timeout policy, and controller protocol version.
- Added strict newline-terminated JSONL parsing; malformed, truncated, unexpected, duplicate, contradictory, failed, and incomplete completed records stop resume.
- Added terminal configuration timeout validation and explicit `skipped_after_timeout` behavior.
- Added final start/resume/dry-run CLI paths and preserved the pilot path unchanged.
- Added controller-session IDs and elapsed-session accounting. Resume charges the maximum recorded elapsed time for every prior session against the fixed 5,400-second cumulative budget.

### 88. Ran syntax, help, and non-executing dry-run verification

- Controller syntax and both final/pilot help paths passed.
- Final dry-run emitted 450 plan lines plus one summary and exited zero.
- Dry-run summary: 450 repetitions; 90 engine/workload configurations; 45 unique manifest-verified files; 225 repetitions per engine; 150 per event size; no existing final records; all 450 planned.
- `07_results/raw/timing.jsonl` was absent before and after. The dry-run did not import an engine, launch a worker, replay an event, or write a final measurement.
- Pilot plan regression: unchanged 16 runs, 1,020 processing-cap seconds, and 420 preparation-cap seconds.

### 89. Tested resume safety using isolated synthetic fixtures

- Created fixtures only in a self-cleaning temporary directory under `05_benchmarks`; never used or created the real final timing path.
- Passed: valid completed-record parsing, duplicate logical-key rejection, conflicting engine-hash rejection, malformed JSON rejection, truncated-final-record rejection, and fixture cleanup.
- Passed timeout fixture: one baseline timeout plus four `skipped_after_timeout` records validated; a later completed repetition was rejected. A dry-run containing only the timeout reported exactly four future skip states, one existing timeout, and did not modify the fixture.
- Passed cumulative budget fixture: two records from session A at 100/150 elapsed seconds plus session B at 50 seconds charged 200 seconds, using the maximum elapsed time per session rather than resetting or double-counting.
- Verified exact plan coverage: 50 supplied-file repetitions and 400 generated-file repetitions, corresponding to five supplied and forty generated workload files.

### 90. Performed expanded read-only privacy review

- Scanned project-owned text artifacts, benchmark code/results, manifests, metadata, root documentation, and supplied text using redacted pattern labels rather than printing matched values.
- Absolute personal-path findings: 285 lines in `02_data/generated_manifest.json`, nine lines in `02_data/supplied_verification.json`, and ten historical lines in `ACTION_LOG.md`.
- README matches were portable `Submissions/ErtenZeynep` examples rather than absolute home paths. The AI decision match was a general OneDrive measurement recommendation, not a personal path.
- Pilot records contain repeated environment characteristics (OS, CPU description/count, RAM, Python), which support reproducibility but can contribute to device fingerprinting. They contain no hostname or home path.
- No redaction was performed. Historical logs, manifests, supplied originals, metadata, and pilot results remain byte-preserved.

No final benchmark, result-digest replay, liquidation, concentration generation, latency, memory, diagnostic, dashboard, or report operation occurred. No engine, correctness test, dataset, pilot record, dependency, network state, Git state, or GitHub state was changed.

## 2026-11-23 - Stage 4D resume-fingerprint correction

### 91. Recorded preservation checkpoints and inspected the approved scope

- Read `AGENTS.md`, the final benchmark sections of `README.md`, the Stage 4D decisions and canonical Risk Register in `AI_DECISIONS.md`, and the complete relevant controller/worker source. These were inspection commands only.
- Before correction, SHA-256 values were: baseline `a9836eb21682a82491c01935fe46475b88b69f817f9556964e9ade6f82565f8b`; optimized `ba02ec39a8d191cf0b6b2adffeaf0e7057201df27c3687cd0cf6694a3624dbaf`; validation `d22baa7d2c288e200ba5e1a3772bb34c62c15924b9a5882cf2e857202879f517`; contracts `c2d55a0b9eb45fd18e2e9035b71b21652ffbc9a3844857a849026ba04bae1e6b`; package initializer `3d66c22f15c7324adc9c92c4dc90c2556dca30b94d0516a4e338f4cb8a46f71a`; worker `d81442db198c256424e3d60faa692669b2d7e41451611ec3a44712aca5ee0a64`; pilot result `c731a54589b63e441f0451fe17eaaf93275de765865632a3e07971953ed100f1`.
- The first attempted PowerShell data-tree digest was blocked by constrained-language restrictions on .NET method invocation. It produced a file count of 106 but no digest; this failed result was not treated as evidence.

### 92. Implemented complete implementation and harness fingerprints

- Modified only `05_benchmarks/run_benchmarks.py`, `README.md`, `ACTION_LOG.md`, and `AI_DECISIONS.md`.
- Replaced the engine-module-only resume field with ordered component records and an aggregate implementation SHA-256. Fixed order is selected engine, `validation.py`, `contracts.py`, `__init__.py`.
- Added ordered harness component records and an aggregate harness SHA-256. Fixed order is controller, then worker.
- Every component contains a normalized project-relative POSIX path and its content SHA-256. Aggregate serialization uses UTF-8 JSON with sorted object keys, compact separators, ASCII escaping, and preserved list order.
- Added both aggregate hashes and both component lists to every final record and to `_RESUME_FIELDS`. Bumped `FINAL_PROTOCOL_VERSION` from `final-primary-v1` to `final-primary-v2`. Pilot schema and pilot data were untouched.

### 93. Ran isolated synthetic verification

- Command form: set `PYTHONDONTWRITEBYTECODE=1`, pipe an assertion-only Python script to `python -`, then remove the temporary environment variable. The script imported the controller by file path; it did not invoke its CLI entry point or import an engine.
- The first run passed syntax, identical-fingerprint, five mismatch, duplicate, and contradictory assertions, then stopped with `PermissionError` when the sandbox denied creation of the project-local temporary fixture directory. No fixture or result file was created. After narrowly granting temporary write access to `05_benchmarks`, the complete script was rerun.
- Passed: AST syntax; identical fingerprints recognized; simulated `validation.py`, `contracts.py`, selected `baseline.py`, worker, and controller changes rejected; duplicate and contradictory records rejected; malformed and truncated JSONL rejected; timeout plus four later skips accepted; post-timeout completion rejected.
- Passed cumulative-budget fixture: one synthetic prior completed record charged exactly 5,400 seconds; all 449 remaining repetitions became `skipped_global_budget`; a patched `Popen` assertion proved no worker launch occurred.
- Passed dry-run fixture: 450 plan lines, 90 configurations, 45 workloads, all 450 states planned, no worker launch, and `07_results/raw/timing.jsonl` absent before and after.
- A final in-memory sensitivity pass changed every component position independently. It passed for both baseline and optimized implementation sets, including `__init__.py`, and for both harness files.
- Verified aggregate fingerprints: baseline implementation `afa06981e3b1d79b8c10903bd6f8d0cc9d648373b7fc9b20e8e14f431a5770fc`; optimized implementation `06e5ebb794e11852f4b6b6c49df54134a2dd3d3e2e489a4ef269afc35aef9490`; harness `484913af7e980803308968794bc9c7b4f1d722974fff12c98b818754b5448925`.

### 94. Verified preservation after correction

- All seven protected engine/shared/worker/pilot hashes matched the pre-correction values recorded above.
- The 106-file `02_data` tree digest, calculated from sorted `project-relative-path|file-SHA-256` rows, was `16718acb281d3f2a3a041a33f7dcef1fdf5d2ea134dab0005570d52f60135cb6` both before documentation edits and after all verification.
- Final controller SHA-256: `8f44e4204354d042c58f410e0d7f85b40e80189cb38388002b71add78351fd8f`.
- `07_results/raw/timing.jsonl` remained absent. The self-cleaning fixture directory left no artifact. No Python/PythonW process remained.
- No pilot, final benchmark, performance experiment, dataset generation, dependency installation, network access, Git operation, or GitHub operation occurred.

## 2026-11-23 - Stage 4D final-primary execution and checkpoint

### 95. Performed final execution preflight

- The user confirmed that the laptop would be connected to power, automatic sleep prevented, and other heavy applications closed. OneDrive remained enabled and is retained as an environmental limitation.
- A read-only preflight recalculated all 45 workload hashes and current source fingerprints, confirmed 450 planned repetitions and 90 configurations, verified `final-primary-v2`, matched the pilot checksum, found `07_results/raw/timing.jsonl` absent, and found zero Python/PythonW processes.
- Observed environment: Windows 11 platform `Windows-11-10.0.26200-SP0`, CPython 3.13.17, AMD64 Family 26 Model 104 CPU description, 12 logical CPUs, 16,268,513,280 RAM bytes, and Windows Balanced power scheme. The battery/AC query was unavailable because Windows denied access; power connection is therefore user-confirmed rather than independently observed.

### 96. Recorded two failed Codex launch attempts without measurements

- First attempted command: `python '05_benchmarks/run_benchmarks.py' final --output '07_results/raw/timing.jsonl' --global-budget-seconds 5400`, with `PYTHONDONTWRITEBYTECODE=1`, in a managed foreground execution session.
- The execution sandbox rejected process creation because an individual-file permission did not provide a writable-root capability. Verification found the output absent and zero Python processes.
- After explicit user approval for one retry and project-local result-directory permission, the exact command reached the controller but exited one with `PermissionError` while opening `07_results/raw/timing.jsonl`. The failure occurred before the repetition loop, so no worker or engine replay started. No further automatic retry occurred.

### 97. Preserved the successful user-executed final benchmark

- The user subsequently reported executing the approved final command in a local foreground PowerShell terminal: `python '05_benchmarks/run_benchmarks.py' final --output '07_results/raw/timing.jsonl' --global-budget-seconds 5400`.
- The user-reported controller summary was 450 planned/total records: 390 `completed`, 12 `timed_out`, and 48 `skipped_after_timeout`; charged wall time 1,765.189204200171 seconds; phase `final`; measurement mode `primary_timing`.
- This log does not treat the local terminal report alone as file-integrity proof. The following independent read-only audit recalculated the retained evidence.

### 98. Audited the final result read-only

- Parsed all 450 newline-terminated JSON objects and ran the controller's strict current-template validator. Found 450 unique repetition keys, exact plan order and indices 1-450, all 90 configurations, all 45 workloads, and no duplicate, contradictory, malformed, truncated, unexpected, failed, or nonterminal evidence.
- Recalculated `07_results/raw/timing.jsonl`: 1,155,659 bytes, SHA-256 `fa6366bae35d7876cccd7abba2357d2d0d10c045d966c72f0cd2a21c2db7fa7f`, statuses 390 completed/12 timed out/48 skipped after timeout, and charged wall time 1,765.189204200171 seconds.
- All workload, implementation, harness, environment, GC, timeout-policy, and protocol identities matched. The pilot was absent from final evidence. Every completed duration was finite and positive; timed-out/skipped records had no engine duration or throughput.
- The 12 timeouts were Version A at 100,000 events for seeds 42, 43, and 44 in each of `buildup`, `crowded`, `mixed`, and `sweep`. Every timeout occurred on repetition 1 and was followed by exactly four skips. Version A `cancel_churn` and every Version B configuration completed.
- One controller session contained all 450 records. Session elapsed values were monotonic, the 5,400-second allowance was not exhausted, and no `skipped_global_budget` record occurred. No engine replay, benchmark, chart, report, or result modification occurred during the audit.

### 99. Completed Stage 4D documentation and artifact metadata

- Before documentation edits, recalculated both retained artifacts: pilot 17,726 bytes/SHA-256 `c731a54589b63e441f0451fe17eaaf93275de765865632a3e07971953ed100f1`; final 1,155,659 bytes/SHA-256 `fa6366bae35d7876cccd7abba2357d2d0d10c045d966c72f0cd2a21c2db7fa7f`. Counts and charged wall time matched the approved evidence.
- Recorded a preservation fingerprint over 129 non-approved project files: SHA-256 `d9ebadf9023b4837d7b9372a823c8efe4a75068418300deeb68935521077e75d`.
- Updated only `README.md`, `AI_DECISIONS.md`, and `01_environment/environment.json`; created `07_results/results_manifest.json`; and appended this section to `ACTION_LOG.md`.
- The first multi-file patch updated `environment.json` but reported failure when its later manifest-creation context was not applied. Inspection confirmed only the authorized environment update had occurred and the manifest remained absent; the manifest was then created in a separate authorized patch.
- Preliminary verification parsed both JSON metadata files, matched the manifest against both raw JSONL files, confirmed 46 balanced README fences and all dry-run/start/resume arguments, found 26 unique canonical risk rows, and reproduced the unchanged 129-file preservation fingerprint.
- Privacy scan of the newly updated README, AI decisions, environment metadata, and results manifest found no personal home-directory paths. Historical privacy findings remain: 10 lines in `ACTION_LOG.md`, 285 in `02_data/generated_manifest.json`, and nine in `02_data/supplied_verification.json`; no redaction was authorized or performed.
- No raw result, engine, shared contract/validation file, benchmark script, test, supplied/generated dataset or manifest, `AGENTS.md`, `.gitignore`, dependency, network state, Git state, or GitHub state was changed.

## 2026-11-24 - Stage 4E implementation and non-executing verification

### 100. Created and verified the approved concentration inputs

- Created `02_data/generate_concentration_pairs.py`, three 10,000-event four-level gzip workloads, three separate metadata files, and `02_data/concentration_10000_manifest.json`. All targets were confirmed absent before execution; no existing file was overwritten.
- Executed `python 02_data\generate_concentration_pairs.py --execute` once. Generation completed successfully in 1.2880664998665452 seconds and produced 338,578 compressed workload bytes, below the approved 30-second and 5-MiB limits.
- Executed `python 02_data\generate_concentration_pairs.py --verify-only` twice during final verification. Both checks exited zero and reported three verified pairs.
- Each pair contains 10,000 events, zero non-price mismatches, zero formula mismatches, unchanged side quantity totals, monotonic mapping, exactly four BUY and four SELL prices, and an uncrossed book. Each finalized hash equals the independently regenerated deterministic second-pass hash.
- Output hashes: seed 42 `a29c3240118951391b89092893948ba283caa9dba63626de925766e5701d9f5e`; seed 43 `08dea51b872a43c8e2278c0055a2bec73192ce9696f0b6a03c06bfad86e68fd0`; seed 44 `317724ffc8ed5fae0708d0665e22087746c3d9f5026e6884cb5363d649a1b852`.

### 101. Implemented the separate Stage 4E harness

- Created `05_benchmarks/_stage4e_worker.py` and `05_benchmarks/run_stage4e.py`. The measured engines and Stage 4D controller/worker were not edited.
- Implemented separate latency, traced-memory, liquidation, concentration, and diagnostic paths. The controller plans 50/4/30/120/8 observations, respectively, for 212 total, uses one subprocess at a time, and writes separate append-only evidence only when execution is later authorized.
- Implemented stable workload/implementation/harness/environment identities, strict JSONL parsing, duplicate and contradictory record rejection, timeout-terminal configuration skips, explicit mode/global budget skips, and manual-review stop behavior for failures.
- Enforced mode ceilings of 900/600/600/1,800/300 seconds. Their 4,200-second sum plus the 300-second verification reserve equals the fixed shared 4,500-second ceiling. Preflight reservation includes preparation, handshake, measurement, liquidation's second timing window, and cleanup.
- Implemented disposable same-engine warm-up with the existing mixed 1,000-event stream, followed by `gc.collect()` and construction of a fresh empty measured engine. Warm-up and parsing remain outside measurement and apply identically to both engines.

### 102. Ran only authorized syntax, self-test, dry-run, and integrity checks

- Ran `python -m py_compile 02_data\generate_concentration_pairs.py 05_benchmarks\_stage4e_worker.py 05_benchmarks\run_stage4e.py`; it exited zero.
- Ran `python 05_benchmarks\_stage4e_worker.py --self-test`; the percentile and independent liquidation-oracle checks passed.
- Ran `python 05_benchmarks\run_stage4e.py self-test`; plan counts, shared-budget arithmetic, liquidation reservation, strict newline parsing, malformed/truncated input rejection, and duplicate/contradictory resume rejection passed. It reported 212 planned observations and zero workers launched.
- Ran `python 05_benchmarks\run_stage4e.py dry-run`; it reported latency 50, memory 4, liquidation 30, concentration 120, diagnostics 8, and 212 total. It created no `07_results/stage4e` directory or measurement record.
- Ran `python 05_benchmarks\run_stage4e.py verify`; it verified all planned input paths and current fingerprints and reported zero Stage 4E observations, zero charged seconds, and no result creation.
- Recalculated preservation evidence after all checks: final primary SHA-256 `fa6366bae35d7876cccd7abba2357d2d0d10c045d966c72f0cd2a21c2db7fa7f`; pilot SHA-256 `c731a54589b63e441f0451fe17eaaf93275de765865632a3e07971953ed100f1`. No Stage 4D result, engine, correctness test, Stage 4D benchmark script, supplied workload, or original Stage 2B manifest was modified.
- Removed only the three exact `.pyc` files created by these syntax checks and their now-empty project-local cache directories after resolving and validating their paths. Final Stage 4E bytecode-cache count is zero.
- Final documentation checks found 52 balanced README fences and exactly 26 unique current Risk Register IDs. Six additional risk-ID mentions are confined to the separate Risk Status History table and are not duplicate current rows.
- Tightened the liquidation construction check so its nonce-derived order/event identifiers are absent from the source stream as well as active state and `last_accepted_seq + 1` is absent from source sequences. Re-ran cache-free syntax compilation, worker self-test, controller self-test, and the 212-observation dry-run with `python -B`; all passed and `07_results/stage4e` remained absent.

## 2026-11-24 - Stage 4E final compliance and implementation-integrity review

### 103. Rechecked the instructor's exact performance requirements

- Read the preserved instructor README directly. Line 116 requires `time.perf_counter`, warm-up, five repeats, every raw repeat, and the median. Line 118 requires separate per-event median/P95/P99 with a documented convention and beginning/end comparison during growing submission bursts.
- Confirmed memory lines 120-122 require a separate `tracemalloc` run, peak traced bytes, declared inclusion/exclusion boundaries, growth during insertion, and post-cancellation-churn measurement. Returned fills must be disclosed as included or excluded; retaining them or complete trade history is not mandatory. Line 56 makes full trade history optional extra storage.
- Confirmed line 108 requires fresh-book 10%/100%/200% liquidation sizes, integer 10% rounded up, maker orders touched, price levels visited, fill count, and unfilled remainder. Five repeats are supplied by the general timing rule at line 116 rather than repeated in the liquidation paragraph.
- Preserved Stage 4D as independently audited cold-process evidence. Its 450 records and checksum remain unchanged; it is documented as lacking explicit matching-engine warm-up rather than relabelled.

### 104. Corrected narrow pre-execution Stage 4E defects

- Modified only `05_benchmarks/run_stage4e.py`, `05_benchmarks/_stage4e_worker.py`, `README.md`, this log, and `AI_DECISIONS.md`.
- Added the documented `--global-budget-seconds` option and fixed it to the approved 4,500 seconds. Added the budget and timeout policies to resume identity.
- Made every latency artifact derive from the selected project-contained `--results-root`; a results root outside the approved project is rejected.
- Before execution/resume, every mode file now receives strict identity, phase, status, duplicate, contradiction, timeout-transition, and skip-duration validation. Any prior failed record stops execution for manual review.
- Added explicit 30-second liquidation-construction and 30-second sale windows. A sale timeout now retains the already observed construction time, active depth, and requested quantity evidence.
- Removed traced checkpoint-state inspection from the memory measurement. An equivalent untraced fresh-engine pass now records exact active-order/price-level peaks and checkpoint states, is discarded and garbage-collected, and a second fresh engine performs the traced replay. Current-event outputs are transiently traced but not retained; saved history is absent.
- Labelled Version A scan/comparison diagnostic counts as analytical estimates. Version B wrapper calls, heap pops/rebuilds, fills, and state peaks are distinguished as directly observed or exact.
- Added `phase: stage4e` and a separate measurement-mode field to every future record. No performance record was created.

### 105. Ran the permitted final verification gates

- Cache-free syntax compilation passed for the generator, Stage 4E controller, and Stage 4E worker. Controller and generator help checks passed.
- The first controller self-test attempt was blocked before fixture creation by project-local managed filesystem permissions. No fixture or measurement was created. After requesting and receiving write permission limited to `05_benchmarks`, the isolated temporary-fixture suite passed and removed its directory.
- Final controller self-test passed 21 named checks: plan counts, budget arithmetic, liquidation reservation, valid resume, identity mismatch, duplicate, contradictory, timeout-then-skip, orphan skip, invalid status, invalid phase/version labels, incomplete completed-result rejection, nonzero skip time, mode/global budget skips, malformed/truncated JSONL, cross-mode charging, custom-results-root latency derivation, and corrupted latency-artifact rejection. It launched zero workers.
- Worker percentile/liquidation-oracle self-tests passed. The non-executing dry-run reported 212 observations and exact 50/4/30/120/8 mode counts. A custom dry-run result root was not created. An outside-project root and a 4,499-second budget were both rejected with exit code 2.
- Read-only `verify` reported all 212 observations planned, zero recorded, and zero charged seconds. Concentration verification again reported all three pairs valid. No `07_results/stage4e`, temporary fixture directory, or bytecode cache remained.
- Final/pilot hashes remain `fa6366bae35d7876cccd7abba2357d2d0d10c045d966c72f0cd2a21c2db7fa7f` and `c731a54589b63e441f0451fe17eaaf93275de765865632a3e07971953ed100f1`. Engines, shared implementation files, Stage 4D harness, supplied/generated manifests, and concentration data hashes all remained unchanged.

## 2026-11-24 - Memory retention, Stage 4E smoke, and warmed-primary preparation

### 106. Verified the PDF memory requirement

- Attempted the PDF skill's preferred `pdfinfo`, `pdftotext`, and `pdftoppm` tools against the preserved original PDF. All three commands were unavailable; no PNG or other temporary artifact was created. Confirmed `pypdf`, `pdfplumber`, and `fitz` were also absent. No dependency was installed.
- Used a read-only standard-library extraction of decompressed original PDF content streams. Physical PDF page 21, carrying slide footer `20 / 23`, contains the exact passage: “Retain the event's returned output while reading its allocation measurement.”
- Corrected only `_stage4e_worker.py`: each current result is strongly referenced through its per-event `tracemalloc.get_traced_memory()` call and then deleted. No historical result list or trade history was introduced.

### 107. Executed the isolated Stage 4E real-worker smoke test

- Created a temporary project-local smoke driver and an exact, refusal-on-existing result path `07_results/.stage4e_smoke`. Ran optimized-engine 1,000-event workers for latency, memory, liquidation, concentration, and diagnostics under a 300-second ceiling.
- All five completed with READY/STARTED/DONE protocol validation. Total smoke wall time was 1.2554763006046414 seconds; per-mode controller times were latency 0.2841105004772544, memory 0.27491309959441423, liquidation 0.22213800065219402, concentration 0.2279629996046424, and diagnostics 0.23464450053870678 seconds.
- Verified the latency gzip path, existence, size/hash schema; 1,000 memory allocation reads and current-result retention semantics; liquidation independent oracle; diagnostic uninstrumented-equivalence check; and expected result schemas for every mode.
- The controller reaped each exact worker. The smoke driver removed the exact validated temporary result tree in `finally`; its own exact temporary source file was then removed after outcomes were captured. Final smoke result/driver counts are zero. No production Stage 4E result was written.

### 108. Implemented and verified separate warmed-primary infrastructure

- Created `05_benchmarks/run_warmed_primary.py` and `05_benchmarks/_warmed_primary_worker.py`. Did not edit the retained Stage 4D controller or worker.
- The wrapper reuses the audited Stage 4D scheduling/resume implementation while assigning separate phase/mode/protocol/output identities and fingerprinting the wrapper, warmed worker, and imported Stage 4D controller dependency.
- Warm-up is the retained 1,000-event mixed seed-42 stream, SHA-256 `8c3455dc8370f2e006eda834f5bfeb47abdb7dc3766775cf12cdc8444f974d9d`. Each worker verifies the hash, processes it on a disposable same-class engine, deletes that engine, calls `gc.collect()`, creates a fresh engine, verifies empty state, and then waits for START.
- Cache-free syntax/help checks passed. The warmed synthetic self-test passed 12 checks covering valid resume; warm-up hash/policy; implementation, harness, environment and protocol changes; duplicate records; timeout-to-skip; post-timeout completion; and malformed/truncated JSONL. It launched zero workers.
- Warmed dry-run reported 450 planned repetitions, 90 configurations, 45 workloads, 225 repetitions per engine, 150 per size, zero existing records, zero charged seconds, and no output creation.
- No full Stage 4E experiment or warmed-primary repetition was executed.

## 2026-11-24 - Final pre-execution real-worker checks

### 109. Verified Version A Stage 4E modes and one warmed-primary repetition

- Confirmed zero Python/PythonW processes before testing and confirmed the production Stage 4E/warmed result paths were absent. Created one refusal-on-existing temporary result root and one temporary smoke driver inside the project.
- Ran Version A on existing 1,000-event workloads through the real Stage 4E controller/worker path for all five modes. All completed with READY/STARTED/DONE validation: latency 0.3869790993630886 controller seconds; memory 0.3116678996011615; liquidation 0.39386089984327555; concentration 0.318499400280416; diagnostics 0.34151449985802174.
- Version A checks included required result fields, latency raw-artifact hash, 1,000 current-result allocation reads, liquidation oracle verification, and diagnostic equivalence with an uninstrumented replay.
- Ran one real baseline warmed-primary controller repetition using the existing 1,000-event buildup seed-42 workload. Captured exact message order READY/STARTED/DONE; verified the warm-up path/count/hash, disposable same-class engine, fresh empty measured engine, positive `engine_seconds` 0.05535379983484745, controller wall 0.286765999160707 seconds, fsynced JSONL output, and strict resume validation.
- Combined smoke duration was 2.4855626998469234 seconds under the 300-second ceiling. The exact temporary result tree was removed by validated `finally` cleanup, then the exact temporary driver was removed. Zero Python/PythonW processes, temporary artifacts, warmed results, Stage 4E final results, and benchmark bytecode caches remained afterward.
- Reparsed immutable Stage 4D evidence: 450 records, 90 configurations, 45 workloads, 390 completed, 12 timed out, 48 skipped after timeout, and SHA-256 `fa6366bae35d7876cccd7abba2357d2d0d10c045d966c72f0cd2a21c2db7fa7f`. Pilot SHA-256 remained `c731a54589b63e441f0451fe17eaaf93275de765865632a3e07971953ed100f1`.
- Re-ran the non-executing Stage 4E self-test and dry-run. They retained 212 observations/52 configurations, 4,200 seconds of mode ceilings plus 300 verification seconds under the shared 4,500-second ceiling, and all strict resume/timeout/corruption safeguards.

## 2026-11-24 - Stage 4E measurement execution

### 110. Executed all five authorized Stage 4E modes in one managed foreground session

- Preflight found zero Python/PythonW processes, no `07_results/stage4e` directory, and no latency, memory, liquidation, concentration, diagnostics, or warmed-primary result file.
- Ran latency, memory, liquidation, concentration, then diagnostics sequentially through `run_stage4e.py`, using one worker at a time, the shared 4,500-second ceiling, approved mode limits, append-only fsynced files, and no resume flag because every output was initially absent.
- The managed foreground sequence began at `2026-11-24T10:29:33.9499543+01:00`, ended at `2026-11-24T10:51:30.3375556+01:00`, exited zero, and consumed 1,316.387601 foreground seconds. Durable per-attempt controller charging totals 1,304.143308589235 seconds.
- Results: latency 50 completed; memory four completed; liquidation 30 completed; concentration 90 completed/six timed out/24 skipped after timeout; diagnostics eight completed. Overall: 212 records, 182 completed, six timed out, 24 skipped, zero failed, zero mode-budget skips, and zero global-budget skips.
- The six censored configurations are Version A `buildup` at 100,000 events for seeds 42/43/44, each in original and four-level-paired form. Every timeout occurred at repetition 1 during measurement; repetitions 2-5 are explicit `skipped_after_timeout`. All Version B concentration repetitions and all 10,000-event concentration comparisons completed.
- No automatic retry, unexpected failure, abnormal interruption, warmed-primary timing, dashboard generation, or report generation occurred.

### 111. Audited retained Stage 4E evidence read-only

- The strict controller verifier accepted all 212 records, all source/harness/environment/budget/timeout identities, all timeout transitions, and every latency raw artifact.
- Result hashes: latency `826f28dbf294d6c46092ce1c593350a32410b33915dfbd4721a774ae939e88bd`; memory `0292aedef063eb540c1635957fd1317873c247f094168644a0c4e21358b870ce`; liquidation `f533c30b5649e9b737c2aa4c96882c61793a8e1680f6c9398d14a0dde9fb6983`; concentration `ce448548c66dce84cb98337064c32f9275e31f16fa71f1c02191181aa0f5a585`; diagnostics `71780ec459bac00730505d797bb3fd31dc33d955e954b7622ffe624149d8a0e4`.
- Fifty latency gzip CSV files total 2,048,747 bytes. A stable ordered path/size/file-hash list has aggregate SHA-256 `1a5954c578f0de1fea6b98d7b27b3c4452ac2699b76f331e03743196251f675f`; per-file hashes remain embedded in and checked against latency JSONL records.
- Post-run process count was zero. `warmed_primary.jsonl` remained absent. Stage 4D and pilot hashes remained `fa6366bae35d7876cccd7abba2357d2d0d10c045d966c72f0cd2a21c2db7fa7f` and `c731a54589b63e441f0451fe17eaaf93275de765865632a3e07971953ed100f1`.

## 2026-11-24 - Warmed-primary execution

### 112. Executed the separately authorized warmed-primary matrix

- Read-only preflight verified 450 planned repetitions, 90 configurations, 45 workloads, increasing sizes 1,000/10,000/100,000, five repeats, 30/120-second limits, `warmed-primary-v1`, correct implementation/harness/environment/workload identities, warm-up hash `8c3455dc8370f2e006eda834f5bfeb47abdb7dc3766775cf12cdc8444f974d9d`, zero existing warmed records, and zero Python/PythonW processes.
- Started one managed foreground controller: `python 05_benchmarks/run_warmed_primary.py --output 07_results/stage4e/warmed_primary.jsonl --global-budget-seconds 5400`. No background process, retry, resume, concurrent workload, code change, dataset change, or protocol change occurred.
- Controller exited zero after writing all 450 append-only fsynced records. Statuses: 392 completed, 12 timed out, 46 skipped after timeout, zero failed, and zero global-budget skips. Charged controller wall time was 1,997.3183167995885 seconds.

### 113. Audited warmed-primary evidence read-only

- Strict dry-run/resume validation accepted all 450 records, 90 configurations, 45 workloads, terminal timeout transitions, complete implementation/harness/environment/warm-up identities, positive completed durations, and absence of fabricated durations in timeout/skip records.
- Result: `07_results/stage4e/warmed_primary.jsonl`, 1,367,400 bytes, SHA-256 `7777cdea1b4c9cb9d798fd5e8fc1e7da97b8c31fdd7ac7776463c74c4bf27660`.
- Twelve Version A 100,000-event configurations timed out: buildup, crowded, mixed and sweep for seeds 42/43/44. Eleven timed out on repetition 1 and have four skips. Mixed seed 42 completed repetitions 1 and 2, timed out on repetition 3, and has two skips. No ordinary five-repeat median or speedup is valid for these configurations.
- All 450 records carry the single approved warm-up path/count/hash/policy. The worker can emit READY only after verifying the warm-up hash, processing 1,000 mixed events on a disposable same-class engine, deleting it, collecting garbage, constructing a fresh engine, and verifying empty state. Completed records therefore provide protocol evidence without mixing warm-up into `engine_seconds`.
- Post-run Python/PythonW process count was zero. Stage 4D, pilot, and all five Stage 4E hashes exactly matched preflight. Cold-process and warmed-primary evidence remain separate.

## 2026-11-24 - Final experimental-evidence documentation

### 114. Re-derived retained evidence before editing

- Read `AGENTS.md`, inventoried `07_results`, and inspected the current manifest, environment metadata, README, action history, and AI decisions. No file was changed by these inspections.
- Parsed the pilot, cold-primary, five Stage 4E JSONL files, warmed-primary JSONL, and all 50 compressed latency CSV files with Python standard-library code. The first summary command failed with a `TypeError` because a pilot field was `null`; it changed nothing. The corrected command explicitly treated absent numeric fields as zero and completed successfully.
- Verified Stage 4E at 212 records across 52 configurations: 182 completed, six timed out, 24 skipped after timeout, zero failures, protocol `stage4e-v1`, and 1,304.143308589235 charged controller seconds.
- Verified warmed primary at 450 records across 90 configurations and 45 workloads: 392 completed, 12 timed out, 46 skipped after timeout, zero failures, 1,367,400 bytes, SHA-256 `7777cdea1b4c9cb9d798fd5e8fc1e7da97b8c31fdd7ac7776463c74c4bf27660`, protocol `warmed-primary-v1`, and 1,997.3183167995885 charged controller seconds.
- Verified every latency artifact against its parent JSONL record: 50 gzip files, 500,000 observations, and 2,048,747 total bytes, with matching individual sizes and SHA-256 values.

### 115. Recorded pre-edit preservation inventories

- Calculated stable path-and-content inventory digests for protected groups: engines/shared source `5c6fd47cbaadc018a397435394344785c9abbe3264ea1d42031b289ce1b0062c` (six files); tests `294998a21fd061ab4f83371ffc77c2fd8bc11b2a2031c9f62214d45187812cd2` (11 files); datasets `804739b7aaab3577b185779fe2d043de763539aa4487cc9a13296ee8b0bf0e57` (114 files); benchmark scripts `1b8bfa2fc61d2b4f7e5221a88da386b3b66ca7ac1a4231d8894da8419dd7c03d` (six files); and raw measurements `67b05a1cec977cba583edeca0e714620a7895470c075de2d0740de902a46f70d` (58 files).
- Requested and received write access limited to `README.md`, `ACTION_LOG.md`, `AI_DECISIONS.md`, `01_environment/environment.json`, and `07_results/results_manifest.json`.

### 116. Finalized current-status documentation and the results manifest

- Updated `README.md` with completed Stage 4E and warmed-primary evidence, portable reproduction safeguards, and the explicit classification of warmed primary as the main instructor-compliant timing evidence and Stage 4D cold primary as supplementary evidence.
- Updated `AI_DECISIONS.md` so pre-execution decisions are explicitly historical and point to DEC-049/DEC-050, without altering the canonical 26-risk register. Added the final evidence-role distinction to DEC-050.
- Extended `01_environment/environment.json` with record-derived Stage 4E and warmed-primary protocol, limits, fingerprints, results, and limitations. Existing Stage 1 and Stage 4D metadata was preserved.
- Replaced schema-v1 `07_results/results_manifest.json` with schema 2. An attempted single patch containing both delete and add operations for the same path was rejected before any change. The manifest was then replaced through two scoped patch operations. Schema 2 covers pilot, supplementary cold primary, all five Stage 4E JSONL files, all 50 latency gzip files, and main warmed-primary evidence. It contains no analytical medians or speedups and does not hash itself.

### 117. Validated documentation and preservation

- Parsed `environment.json` and `results_manifest.json` as JSON. Recomputed every manifest-listed JSONL and latency artifact size, SHA-256, record/observation count, status count, protocol, Stage 4E charged-time sum, and warmed final cumulative charged time; all checks passed.
- Verified 26 canonical Risk Register rows with 26 unique IDs, balanced README command fences, and no remaining current README phrase claiming Stage 4E or warmed-primary evidence is absent.
- New documentation hashes: `results_manifest.json` SHA-256 `d74d1216e22a5a963cd85020adcebe3e7c949ad98dadb80749f7cfd5900f2e0b`; `environment.json` SHA-256 `330433799b79c6325d2b949d54986f4435bd071a86f195c9d7c17c7fb62d5e00`.
- Post-edit inventory digests exactly matched all five pre-edit protected-group digests. Therefore engines, shared contracts/validation, tests, datasets, benchmark scripts, pilot evidence, cold-primary evidence, Stage 4E evidence, warmed-primary evidence, and all 50 latency files remained byte-identical.

No experiment, analytical summary, dashboard, technical report, dependency installation, network access, Git command, or GitHub operation occurred.

### 118. Performed the final consistency check

- Reparsed both updated JSON files successfully, searched README and AI decisions for five obsolete pre-execution phrases, and found none as current text.
- Recalculated the pilot, cold-primary, warmed-primary, results-manifest, and environment-metadata hashes once more. The retained evidence hashes remained unchanged; the documentation hashes matched the values recorded above.

## 2026-11-24 - Results aggregation and dashboard

### 119. Re-verified instructor requirements and selected the lean implementation

- Read the user-provided stage request, the persistent project rules, the visualization and PDF inspection instructions, the supplied instructor README, and the decompressed text of PDF slides 16-23. The unrelated embedded AI naming instruction remained rejected and had no effect.
- Confirmed mandatory saved-result/dashboard coverage: warmed five-repeat medians, throughput, latency distributions and percentiles, memory and post-cancellation state, construction/replay/liquidation scaling, correctness outcomes, raw-repeat/stopped labels, units, and at least one operation-count/complexity bottleneck explanation. One-million-event testing and Docker remain optional.
- Inspected the existing results/dashboard directories, dependency availability, Stage 4E schemas, per-event latency CSV schema, and Gate B correctness evidence. Chose a standard-library aggregator plus dependency-free static HTML dashboard; no dependency was installed.

### 120. Implemented and ran deterministic aggregation

- Created `05_benchmarks/aggregate_results.py`. It derives its project root from its own path, validates schema-2 manifest evidence, refuses escaping output paths, reopens all JSONL/gzip inputs, and does not import either engine.
- Its first execution passed syntax/help and source validation but was denied while creating the new `07_results/processed` directory. No output was created. Requested and received the minimal parent-directory write permission, then reran the unchanged command.
- Created `07_results/processed/aggregated_results.json`: 206,127 bytes, SHA-256 `0b08c398bb5321ab3e98ea82345da8fddd256886d0dcb3aa9b5b07ff7699dce7`. A subsequent `--verify-only` regeneration was byte-identical.
- Verified output coverage: 90 primary configurations, 78 complete, 12 censored, 33 valid paired speedups, ten latency groups/500,000 events, four memory observations, six liquidation groups, 24 concentration configurations/nine valid comparisons, eight diagnostics, and zero pilot records used in statistics.

### 121. Implemented and validated the saved-result dashboard

- Created `06_dashboard/index.html`, a single dependency-free page that fetches only the processed JSON. It presents warmed-primary runtime/throughput/speedups, censored states, latency percentiles/distributions and event/window breakdowns, memory growth/cleanup, construction versus liquidation time/outcomes, concentration comparisons, diagnostic counts/provenance, correctness evidence, and limitations.
- Static HTML parsing passed with 31 unique IDs and one script. One PowerShell capability-report expression failed under constrained language while the independent HTML parser in the same command passed; it changed nothing. A corrected capability check found Edge available and Node absent.
- Started one managed project-root HTTP server for browser validation. Headless Edge failed before rendering because its GPU process was unusable; no successful visual-browser render is claimed. The exact project-local `.edge_validation` profile was resolved, verified inside `06_dashboard`, and removed. The validation Python server initially survived the rejected session-control request; its exact start time identified PID 67320 as the assistant-created server, and it was stopped. Final Python/PythonW count and port-8765 listener count are zero.
- A separate short-lived in-process HTTP server successfully served both dashboard HTML and processed JSON, then shut down. Dashboard checks found 31 DOM IDs, 23 JavaScript element references, zero missing targets, correct 90/33 data counts, and zero pilot contamination. Cross-working-directory `--verify-only` also passed.
- A final supervised Chrome attempt used an exact hidden local-server process, isolated project-local profile, and `finally` cleanup. Chrome returned `ERR_CONNECTION_REFUSED` inside its sandbox and created no screenshot. PowerShell constrained language also rejected `WaitForExit`; the exact server was nevertheless already stopped, and both the profile and screenshot paths were absent afterward. No browser-render success is claimed.

### 122. Updated documentation and performed preservation checks

- Updated `README.md` with schemas, calculation definitions, exact Windows/macOS/Linux commands, local-server launch instructions, evidence boundaries, and the processed-output hash.
- Updated `AI_DECISIONS.md` with DEC-051, changed RR-021 from OPEN to MITIGATED with measurement evidence, and added its status history without duplicating the canonical row.
- Verified 26 canonical risk IDs with no duplicate; README code fences are balanced; all new output paths are project-relative and contain no personal absolute path.
- Preservation inventory hashes remained exact for engines/shared source `5c6fd47c...62c`, tests `294998a2...cd2`, datasets `804739b7...57`, raw measurements `67b05a1c...70d`, and the six pre-existing benchmark scripts `1b8bfa2f...03d`. `results_manifest.json` remained byte-identical at SHA-256 `d74d1216e22a5a963cd85020adcebe3e7c949ad98dadb80749f7cfd5900f2e0b`.
- New file hashes: aggregator `b1e11bbc6eb68de786480d0fd2f78659f1d3ee73704070cc4b0b620ab14772c9`; dashboard `1b4f39164ab7f22b1cf16de1fd27260375b779cb82d87d2a94b34fdb4e385da3`; processed JSON `0b08c398bb5321ab3e98ea82345da8fddd256886d0dcb3aa9b5b07ff7699dce7`.

No matching engine, test, existing benchmark controller/worker, workload, raw measurement, results manifest, dashboard experiment, dependency, external network resource, Git state, or GitHub state was modified.

## 2026-11-24 - Dashboard compliance closure and parsing-only evidence

### 123. Designed and dry-ran the parsing-only protocol

- Re-read the instructor requirements, persistent project rules, actual engine implementations, warmed-primary evidence and current dashboard artifacts. Confirmed that the remaining mandatory gaps were raw-repeat visibility, parsing-only timing, explicit memory checkpoints, controller invocation cost and code-grounded complexity notation.
- Created `05_benchmarks/measure_parsing.py` with no order-book import. Syntax/help checks passed. The non-executing command `python 05_benchmarks/measure_parsing.py --dry-run --budget-seconds 300` planned 45 workloads and 225 repeats: five scenarios, sizes 1,000/10,000/100,000, seeds 42/43/44, and five repeats. It planned 8,325,000 JSON decodes and 100,046,355 compressed input bytes across repeats without creating output.
- The first execution preflight refused to start because it observed an unexpected Python process left from the command environment. No parsing result existed. A narrowly targeted `Stop-Process` request for that exact PID was denied by the operating system and changed nothing. Inspection found no network connection or benchmark-worker command line; the unchanged parsing command was then run in the managed foreground.

### 124. Executed and verified parsing-only measurements

- Ran `python 05_benchmarks/measure_parsing.py --output 07_results/parsing/parsing_runs.jsonl --budget-seconds 300`. It completed all 225 records across 45 configurations with zero failures in 17.92946740053594 seconds.
- Ran the matching `--verify-only` command. It revalidated the protocol, complete matrix, session/environment/workload identities, positive component durations, input hashes and five repeats per workload.
- Created `07_results/parsing/parsing_runs.jsonl`: 410,030 bytes, SHA-256 `7973ab2822f2707edbc1e7ddcb68bdcddd3529e0e5c24239be952361fb68d146`. The script SHA-256 was `8ad3130aa7f3947d3d86c4cf6d7d507c2ea0a9d6567f0c157355689cc017d384`.
- Extended `07_results/results_manifest.json` with project-relative parsing evidence, measurement boundaries, protocol, budget, actual wall time and hashes. No prior manifest entry or raw measurement was rewritten.

### 125. Extended aggregation and dashboard presentation

- Updated `05_benchmarks/aggregate_results.py` to validate and aggregate the parsing artifact, preserve warmed-primary raw repetition fields, and calculate a controller invocation wall median only for configurations with five completed repetitions.
- Regenerated `07_results/processed/aggregated_results.json`: 350,185 bytes, SHA-256 `0f8c7a88f7360900c5c385496222ae6da4b4dbe7a8724edeeff1de8099a231d5`. `--verify-only` reproduced identical bytes. Coverage remained 90 warmed-primary configurations, 78 complete, 12 censored and 33 valid speedups, plus 45 parsing configurations; pilot contribution remained zero.
- Updated `06_dashboard/index.html` with workload-level raw repetition/status/hash details, parsing controls and raw repeats, traced-current/peak checkpoint presentation, controller invocation wall cost and code-grounded complexity notation. Updated README and AI decisions with exact boundaries, portable commands, results and limitations.
- Two attempted patch hunks intended only to replace encoding-damaged decorative symbols did not match the existing byte sequence and therefore made no change. Functional dashboard wiring was applied separately.

### 126. Completed integrity, loading and preservation verification

- A `py_compile` check was denied because the environment did not permit writing `05_benchmarks/__pycache__`; both scripts were subsequently parsed successfully with `ast.parse`, which performs the same syntax parse without writing bytecode. Parsing `--verify-only` and aggregation `--verify-only` both passed.
- The first combined validation script used an outdated processed-JSON key name and stopped with `KeyError` after already passing syntax and manifest checks. A corrected read-only run passed: 90 primary configurations, 45 parsing configurations, exactly five retained repeats in each, null timing aggregates for censored primary configurations, workload hashes present, 10%/50%/100% memory checkpoints present, and pilot evidence excluded.
- Verified all machine-readable manifest entries reachable through path/size/hash triples, 41 unique dashboard element IDs, 32 JavaScript element references with no missing target, balanced README fences, and 26 unique canonical Risk Register IDs.
- Started a short-lived in-process loopback HTTP server. Requests for `/06_dashboard/` and `/07_results/processed/aggregated_results.json` both returned HTTP 200; the served JSON contained 45 parsing configurations. The server was shut down in `finally`.
- Final hashes: results manifest `3a0da3ff377860b2e6d1c72820d91dfa80e33ddef6930831945f6c621bf79e67`; processed JSON `0f8c7a88f7360900c5c385496222ae6da4b4dbe7a8724edeeff1de8099a231d5`; parsing script `8ad3130aa7f3947d3d86c4cf6d7d507c2ea0a9d6567f0c157355689cc017d384`; aggregator `068d6010184ef9d7a44cd4da6c363deb40784da6a8b4cfb07a7523445f165644`; dashboard `85f1d5eb013f624522825d61c32aa06b1af85a70e26a5e02f9b0252b556a69bd`.
- Protected inventory digests remained byte-identical: engines/shared `5c6fd47cbaadc018a397435394344785c9abbe3264ea1d42031b289ce1b0062c`; correctness tests `294998a21fd061ab4f83371ffc77c2fd8bc11b2a2031c9f62214d45187812cd2`; datasets `804739b7aaab3577b185779fe2d043de763539aa4487cc9a13296ee8b0bf0e57`; six retained benchmark harness scripts `1b8bfa2fc61d2b4f7e5221a88da386b3b66ca7ac1a4231d8894da8419dd7c03d`; prior raw evidence `67b05a1cec977cba583edeca0e714620a7895470c075de2d0740de902a46f70d`.
- A privacy scan found no personal absolute path in the new scripts, parsing result, processed result, manifest, dashboard, README or AI decisions. Existing machine-specific paths remain only in the historical action evidence, where they were intentionally preserved.

No matching benchmark was rerun. No engine, correctness test, dataset, existing benchmark controller/worker, or prior raw evidence was modified. No dependency, network, Git or GitHub operation occurred.

## 2026-11-24 - Dashboard presentation closure

### 127. Corrected four display-only defects

- Modified only `06_dashboard/index.html`. Null numeric table cells now render an em dash rather than coercing their wrapper object to `[object Object]`.
- Replaced full-width warning bars for absent/censored values with an empty striped track and explicit `TIMEOUT / CENSORED` text. Added a visible logarithmic-scale note to every chart rendered with logarithmic bar lengths.
- Added fixed diagnostic-column proportions and wrapping rules without changing diagnostic data or analytical claims.
- Lightweight verification parsed the HTML, found 41 unique IDs and 32 resolved JavaScript element references, confirmed six logarithmic chart calls were labelled, and served both dashboard and processed JSON through a short-lived loopback server with HTTP 200 responses.
- Cold-primary, warmed-primary, parsing, and processed-result hashes remained unchanged. Final dashboard SHA-256: `ba43c1c1e828abf1bc405c31e1894db9c609c6eb33a68cc330acf3e88385f7c3`.

## 2026-11-24 - Final technical report

### 128. Mapped instructor requirements and retained evidence

- Read the complete preserved instructor README, persistent project instructions, both engine implementations, shared validation/contracts/replay, environment metadata, results manifest, aggregate, correctness/decision evidence, and relevant action history.
- Attempted fresh original-PDF inspection with `pdfinfo`/`pdftotext`; both executables were unavailable. Attempts with installed Python for `pypdf` and `PyPDF2` also reported missing modules. No dependency was installed. The report therefore uses the complete instructor README for mandatory requirement wording and the prior recorded direct PDF slide review only as corroboration; it makes no new visual-layout claim.
- Built an internal requirement map covering specification, actual revision, invariants/pseudocode/complexity, unchanged correctness tests, timing/memory/profiling methodology, interpretation, AI assistance, reproducibility, report contents, and submission commit identification.
- Extracted representative primary, latency, memory, liquidation, concentration, parsing, controller-wall, and diagnostic values from `07_results/processed/aggregated_results.json`. Pilot, cold-primary, warmed-primary, parsing, and instrumented evidence remained distinctly labelled.

### 129. Created and verified the report draft

- Created `08_documentation/technical_report.md` with the approved structure: executive summary; system design; baseline/revision; complexity; correctness; methodology; results; decisions; limitations; AI assistance; reproducibility; conclusion.
- Updated README current-status wording, linked the report, recorded verified Python-version compatibility evidence, corrected its optimized complexity notation from active levels alone to actual heap length `H` with explicit `O(P)` rebuilding, and replaced three remaining pre-completion statements with current project-relative instructions/evidence.
- Added DEC-053 to `AI_DECISIONS.md`; the canonical Risk Register was not changed.
- The first report-consistency script stopped on an exact wording check for `supplementary cold-primary`; the report already separated the evidence but used a space rather than the expected compound label. The wording was corrected without changing data. A later broad coverage assertion expected the literal phrase `Supported event types` rather than the report's equivalent `three event types`; only the read-only checker was corrected.
- Detailed numerical validation then exposed one real draft defect: the stated Version A concentration range omitted the seed-44 minimum. The report was corrected from `1.020-1.064x` to the verified all-seed range `1.017-1.064x`. A subsequent checker assumption that excluded the seed-42 table value was corrected; it did not change the report.
- Final verification confirmed all required headings and topics, balanced Markdown fences, exactly three `[STUDENT REVIEW REQUIRED]` placeholders, no absolute personal path, project-relative evidence links, explicit censoring, representative primary/latency/memory/liquidation/concentration/parsing/controller/diagnostic values, source-grounded complexity, and the retained 51-test correctness outcome.
- Final draft size: 4,949 words, 379 lines, 35,122 bytes. SHA-256: `c3100b4f2dadc6d96eeae91dabda0b6d6461ac1a25fdbb97ff3aeecc23c82d5d`.
- Preservation inventories remained exact: engines/shared source `5c6fd47cbaadc018a397435394344785c9abbe3264ea1d42031b289ce1b0062c`; tests `294998a21fd061ab4f83371ffc77c2fd8bc11b2a2031c9f62214d45187812cd2`; datasets `804739b7aaab3577b185779fe2d043de763539aa4487cc9a13296ee8b0bf0e57`; prior raw measurements `67b05a1cec977cba583edeca0e714620a7895470c075de2d0740de902a46f70d`.

No benchmark, workload generation, engine/test edit, raw-evidence edit, dependency installation, external network access, Git command, or GitHub operation occurred.


## 2026-11-25 - Public-submission privacy redaction

### 130. Captured the immutable baseline and validated isolated redacted copies

- Read `AGENTS.md` before acting and confined all work to the five approved production files plus the exact project-local temporary staging directory. No Git, network, dependency, benchmark, generation, engine, test, workload, or raw-result operation occurred.
- The first PowerShell baseline command partially failed because constrained language rejected custom-object/hash construction; its `rg` path scan still completed. A later combined command was rejected by PowerShell parsing before execution because of nested quoting. Both failures changed nothing.
- A standard-library Python read-only command captured the five original file hashes and the manifest structure. A corrected semantic-inventory calculation matched the retained digest `c3c374d10e98c2b1b8a6ee226636e98458676248f514f04f8833ed96f3324c41` for 40 direct plus three paired records.
- Pre-change checks ran `python 02_data/generate_workloads.py --verify-only`, `python 02_data/generate_concentration_pairs.py --verify-only`, `python 05_benchmarks/run_benchmarks.py final --output 07_results/raw/timing.jsonl --global-budget-seconds 5400 --dry-run`, and `python 05_benchmarks/aggregate_results.py --verify-only`. Concentration verification, aggregation, and the non-executing 450-repetition/90-configuration/45-workload dry-run passed.
- The Stage 2B verifier exposed a pre-existing limitation: it hard-codes exactly 43 files in `02_data/generated`, but the current directory correctly contains those 43 plus three later approved Stage 4E 10,000-event concentration pairs. It reported `found 46 and 46` before redaction. This is not a redaction regression.
- Write permission was requested only for the approved project root. A project-local `.privacy_redaction_staging_20261125` directory was created. The first staging build stopped on an underestimated expected substitution count before writing either staged JSON; the corrected build produced all five isolated copies.
- Deterministic substitutions totaled 304: ten historical `ACTION_LOG.md` paths; 285 generated-manifest paths (81 Python-executable placeholders, 161 project-root placeholders, and 43 project-relative structural paths); and nine project-relative supplied-verification paths.
- The first isolated verifier import failed because direct loading did not expose the sibling `validate_inputs` module. Repeating it with a temporary process-local `02_data` import path succeeded through all workload validation and reproduced only the same pre-existing 46-versus-43 count limitation. No persistent import or environment setting changed.
- Isolated validation passed JSON parsing, exact allowed-difference auditing, credential/path scanning, all referenced workload and metadata hashes, all 45 core workload identities, the unchanged semantic inventory, and the dedicated concentration verifier. The generated manifest does not store its own final SHA-256.

### 131. Applied the verified redactions and completed post-change verification

- A canonical-section-only staging check passed: both JSON files parsed, README fences were balanced, the canonical Risk Register contained 26 unique IDs, and all five staged public files were free of personal Windows home paths. An earlier checker assertion had incorrectly counted Risk Status History rows as canonical rows; correcting only the checker resolved it.
- One guarded standard-library Python command resolved all five production targets inside the approved project root, confirmed every original SHA-256, wrote same-directory temporary files, and atomically replaced only the five approved paths with the exact verified staged bytes.
- Post-change commands reran the dedicated concentration verifier, aggregation `--verify-only`, the non-executing final-primary dry-run, and the Stage 2B verifier. Concentration and aggregation passed; the dry-run again reported 450 repetitions, 90 configurations, and 45 workloads. The Stage 2B verifier reproduced only its documented pre-existing `46 and 46` versus hard-coded `43` limitation.
- A post-change standard-library audit reparsed both JSON files, confirmed 40 direct plus three paired records and semantic digest `c3c374d10e98c2b1b8a6ee226636e98458676248f514f04f8833ed96f3324c41`, compared protected source/result hashes, checked 26 unique canonical risks, and scanned 105 public text files. Personal absolute-path hits and credential-marker hits were both zero.
- Protected hashes remained exact for both engines, shared validation/contracts/package initializer, the retained Stage 4D controller and worker, results manifest, cold-primary raw timing, and warmed-primary raw timing. The benchmark dry-run also revalidated current workload, implementation, harness, environment, policy, and protocol identities against retained records.
- The first cleanup attempt used standard-library `shutil.rmtree` after validating the exact staging directory, but OneDrive's read-only reparse-point attribute blocked removal of an empty subdirectory. It stopped before changing either production log. A read-only inspection confirmed that only the assistant-created staging files remained. Native PowerShell then removed those explicit files and directories with `-LiteralPath -Force`; the staging path was confirmed absent. No other path was deleted.
- The generated manifest intentionally contains no self-hash. Stable final hashes for it, supplied verification, and README are recorded in DEC-054. This ACTION_LOG final hash is inserted into DEC-054 during finalization; AI_DECISIONS cannot contain its own final digest, which is reported externally.

No benchmark, workload generation, engine/test edit, raw-evidence edit, processed-value edit, dependency installation, external network access, Git command, GitHub operation, or Git-history rewrite occurred.

## 2026-11-25 - Final clean-checkout reproducibility verification

### 132. Verified committed extraction and identified generation preconditions

- Extracted the committed Assignment1 subtree into a new isolated directory outside the repository and OneDrive. The corrected `.gitattributes` policy produced exact equality across authoritative local bytes, committed blobs, ZIP entries, and extracted bytes for all 98 byte-sensitive tracked files. All nine result-manifest artifacts, three corrected metadata records, and recorded engine/harness fingerprints matched.
- The isolated submission contained 116 committed files. Fifty tests not requiring ignored generated workloads passed, the supplied worked example passed for both engines, and retained aggregation verification reproduced SHA-256 `0f8c7a88f7360900c5c385496222ae6da4b4dbe7a8724edeeff1de8099a231d5`.
- The first reproduction attempt established that Git does not retain the empty `02_data/generated/` directory. After that directory was created in an isolated staging copy, a second preflight established that `generate_workloads.py --execute` correctly refuses to overwrite the retained `generated_manifest.json`. Both attempts stopped before generating a workload and changed no authoritative file.
- Inspected the unchanged generator. It anchors paths to its own location and requires an existing empty generated directory, no pre-existing generated manifest, the approved instructor-generator hash, and sufficient disk space. A separate minimal workspace was therefore required to preserve the retained submission manifest.

### 133. Completed isolated workload reproduction and full verification

- Created a minimal isolated generation workspace containing byte-identical copies of only `generate_workloads.py`, `generate_concentration_pairs.py`, `validate_inputs.py`, the instructor generator, and the five supplied 10,000-event inputs. No retained generated-data manifest was copied into that workspace.
- Generated and natively verified the 43 Stage 2B workloads before adding later files. Stage 2B generation plus its historical verifier took 46.345 seconds. All 43 workload filenames, sizes, and SHA-256 values matched the retained manifest; all 40 direct metadata files were byte-identical.
- The three 100,000-event paired workload files were byte-identical. Their regenerated metadata differed from the retained historical metadata only in `transform_script_sha256`: the retained metadata records the earlier transformation-script revision, while regenerated metadata records the currently committed script. Seeds, event counts, source hashes, formula, levels, quantities, paths, workload relationships, and all other fields matched.
- Generated and natively verified the three Stage 4E 10,000-event concentration pairs in 1.224 seconds. All three workload and metadata filenames, sizes, and SHA-256 values matched `02_data/concentration_10000_manifest.json`. Cumulative generation and native-verification time was 47.569 seconds of the approved 600-second limit.
- Copied only the 46 verified workloads and 46 suitable metadata files into the extracted clean submission after confirming its destination was absent. No retained manifest or authoritative historical metadata was overwritten.
- The complete unchanged correctness suite passed 51/51 tests in 18.790 seconds, including the supplied worked example and the pre-generated differential test.
- Lightweight saved-result checks all passed: Stage 4E represented 212 observations; the concentration verifier accepted three pairs; the warmed-primary dry-run represented 450 repetitions, 90 configurations, and 45 workloads without launching workers; aggregation verification reproduced SHA-256 `0f8c7a88f7360900c5c385496222ae6da4b4dbe7a8724edeeff1de8099a231d5` with zero pilot contamination.
- No matching benchmark, dependency installation, external network access, Git/GitHub operation, or authoritative-repository write occurred. Temporary clean-check and generation workspaces remain pending separate cleanup authorization.

## 2026-11-25 - Git-history publication decision

### 134. Recorded the approved provenance choice

- Performed a read-only assessment of the 15 reachable Assignment1 development commits. Historical local paths and Git author identity were present, but no high-confidence credential, private key, sensitive configuration file, or direct remote-access mechanism was detected; pattern scanning cannot prove absolute absence.
- The student reviewed snapshot-only publication, history sanitization, and preservation of the existing incremental history, then approved preservation for academic transparency, test-first evidence, methodology corrections, and project provenance. The current committed snapshot is privacy-redacted, while earlier path-bearing commits will remain reachable after publication.
- Added DEC-056 and this action record only. No Git/GitHub operation, test, benchmark, source edit, data edit, or result edit was performed.
