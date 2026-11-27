# Final pre-submission review (Claude Code, read-only)

Target: `Submissions/BuehlerLaurin/Assignment1` @ `1b7adca` (clean tree)
Reviewer: Claude Code (aif-review + aif-verify). Date: 2026-11-25. Deadline: 2026-11-26 18:00.
Scope: requirements → evidence, claim tracing, cross-document consistency, readability.
No code, docs or results were changed. The only writes are this file and `scratch/final_review/`.

Course sources read: package `README.md` (sha256 `17ce011b…`, matches SPEC) and
`AlgorithmsFinance_Exercise1.pdf` (text extracted to `scratch/final_review/slides.txt`).
The hidden instruction recorded in AI_LOG.md (PDF pages 1, 7 and 14) was ignored.
The original review scan found only the AI_LOG entry. Fix-round note: this
report's duplicate marker quotation and literal query were redacted so AI_LOG
retains the sole quotation; the original review findings are unchanged.

Commands run (logs and scripts in `scratch/final_review/`):
- `recompute2.py` … `recompute7.py`: recompute the headline numbers from the committed CSV/JSON files
- `links.py`: check every relative link and backticked path in README/REPORT/FINAL_SELECTION/REQUIREMENTS_MAP/SPEC
- `python run.py lob.replay 06_data/supplied/worked_example.jsonl` (default) → `submission_tools check-worked`: **OK**; output identical to `--version A`
- `python -m pytest --collect-only -q`: **1033 tests collected**
- `python -m pytest -q --basetemp=scratch/final_review/pytest-tmp` at HEAD: see section E

---

## A. MUST-FIX before submission

**M1. FINAL_SELECTION.md says that B still points to B1, and the dashboard's first tab shows this.**
`00_docs/FINAL_SELECTION.md:64`: *"Open follow-up: the registry alias "B" still points to B1; it must point to B3r before submission."*
This is false. `01_code/lob/__init__.py:14` maps `("lob","B")` to `OrderBookB3r`, and the default replay matches A on the worked example.
This is a regression from commit `5785e9f`: it replaced the correct line *"Registry follow-up completed 2026-11-23: "B" points to B3r; …"* with the stale one (see `git show 5785e9f -- 00_docs/FINAL_SELECTION.md`).
`04_dashboard/views.py:89` renders this file in full on the **first** dashboard tab, so a grader is likely to see it early.
Fix: restore the three-line 2026-11-23 text. Then rerun `02_tests/test_dashboard.py`, because some dashboard tests compare the rendered document.

**M2. FINAL_SELECTION.md speedup numbers differ from REPORT, README and the dashboard Overview.**
FINAL_SELECTION uses the ratio of seed medians. REPORT, README and the Overview use the median of per-seed ratios. All of them call it "median across seeds":

| Claim | FINAL_SELECTION | REPORT / README / Overview | Recomputed from `…00bb1ad…/summary.csv` |
|---|---|---|---|
| 10k speedup range | "139x-181x" (l.36, l.54); drops mixed | "21x to 186x" (non-churn) | seed-median ratios 21.2 / 139.0 / 169.6 / 185.8; ratio of medians crowded = 180.9 |
| mixed 100k | "290x" | "299x" | 299.4 (median of ratios); 289.8 (ratio of medians) |
| cancel_churn | "A is 1.3-1.8x faster" (includes 1M) | "ratios about 0.7-0.8" (1k–100k) | 0.70–0.77 at 1k–100k; 1M A 2.66 s vs B3r 4.79 s = 1.8x |

The Final selection tab and the Overview tab therefore show different headline numbers.
Fix: use one convention everywhere (the REPORT one) and label the 1M churn figure separately.

**M3. Submitted commit placeholder.** `README.md:71` says *"Submitted commit: `<to be filled at submission>`"* and `README.md:419` says *"Commit to audit: <hash>"*.
The commit identifier is a required item (R §Submit; S23). Laurin has to fill it in at submission time, and the second placeholder should be removed or filled.

**M4. The README "Detailed reference" contradicts "Start here" in several places.** A grader who scrolls past line 72 reads these statements, which are all false at HEAD:
- l.218: "latest checkpoint: 1027 passed" (Start here says 1,033). l.115: "983 standard tests". l.196: "999". l.208: "1,032". l.420: "848 passed".
- l.220: `bench.run_all` "(planned)". l.296–299: "Phase 4 … chooses the final B"; "official runtime/memory work remain later phases".
- l.403–406: long-run commands "have not been executed here".
- l.408–414 **Results summary**: only the smoke run; "Long runs remain pending".
- l.416: **Revision summary** is an empty heading.
- l.421–422: "full grid pending"; "Fresh-venv check: pending Phase 7" (a fresh `.venv` run exists in `05_evidence/20261125T132117Z_d885f6e-dirty_handoff-run-all.txt`).
- l.466: "Current checkpoint starts no long engine run".
- l.199 and l.261 say "eight tabs"; l.129 and Start here say nine.

Minimum fix: rewrite "Results summary", "Revision summary" and "Evidence block" from REPORT §6/§9 and the latest evidence. Label everything below as a dated history ("Phase log, superseded counts kept for traceability"), or move it to `00_docs/`.

**M5. REQUIREMENTS_MAP status columns are stale for the benchmark requirements.** The map is the grader's checklist, but rows R40–R57 still say "Full long grid pending", "1M … engine runs deferred", "scaling pending", "Smoke only", and so on.
Other stale rows: R2 ("final README/report work remains Phase 7"), R30 (lists A vs B1/B2/B3 but not B3r), R37 ("Phase 4a recorded"), R61 "partial", R68 and R69 "todo", O2 "todo" (the peer audit is optional).
The dated checkpoint sections at the end are current, but the main table is not.
Fix: update the Status/Evidence cells to point at the four committed run folders, REPORT sections and dashboard tabs.

## B. SHOULD-FIX

**S1. Some REPORT/FINAL_SELECTION evidence is attributed to chat work and was not committed.** REPORT:5 says *"Every number in this report comes from committed result files"*. These do not:
- REPORT §4 row "Independent reference … vs **B3r**: supplied 50,000 events + 135,000 stress events | 0 differences" (also FINAL_SELECTION:32). The only committed source, `AI_LOG.md:226-230`, says Claude (chat) checked **B1, B2 and B3**, not B3r, and calls it "attributed external review". No reference implementation or log for that check is committed.
  (B3r *is* covered by the committed attack: `07_attack/ATTACK_REPORT.md:213-216` reports 1,152,000 every-event comparisons, and `logs/final_b_campaign.txt` is tracked.)
- "300,000 random validator cases" (REPORT:172, FINAL_SELECTION:43): no committed file contains this.
- "about one third of per-event time is input validation" (REPORT:155, FINAL_SELECTION:42): `AI_LOG.md:597-601` says this was Claude (chat)'s profile, and no profile output or cProfile script is committed.
  **Profiling is one of the report aspects the course requires** (R §Submit; S23 "report on the five aspects"). Right now its only committed support is the A operation counts, which are strong evidence for A but not a profile of B3r.
Fix: either commit a small cProfile script and its output (B3r on one supplied 10k stream), or reword these three claims as "attributed external check (AI_LOG)". Change the B3r reference row to cite the attack campaign.

**S2. "measured: exactly 2.00" is overstated and has no source.** REPORT:168 and FINAL_SELECTION:28 give no file. In `counts.csv` of the B3r session, rebuild keys scanned per cancel reach **1.999** (post_attack dead_slot_rebuild 100k, construction) and are about 1.0 elsewhere (`scratch/final_review/recompute7.py`). The committed trap probe reports 1.602 and 0.397 (`05_evidence/20261122T115730Z_958c8b4-dirty_b3r-trap-mutation-probes.txt`).
Suggested wording: "at most 2 per cancel (bound); worst measured 1.999 on dead_slot_rebuild 100k".

**S3. No full-suite evidence at the final commit.** The last full standard-suite evidence is `d885f6e-dirty` (1,033 passed). Commits `5785e9f` and `1b7adca` changed dashboard code and tests and only have targeted evidence (22 dashboard + 2 portability tests). Section E records a fresh run at `1b7adca`. Save it with `evidence.py` after the M1/M2 doc fixes so the submitted commit has its own log.

**S4. `.\run_all.ps1` may be blocked on a default Windows machine.** On many Windows client machines the default PowerShell execution policy blocks local scripts. Add to Start here:
`powershell -ExecutionPolicy Bypass -File .\run_all.ps1`.
Also, `run_all.ps1:9` uses whatever `python` is on PATH, with no version check. A Store alias or Python 3.11 fails or diverges silently. A `py -3.13` fallback or a version check would make the failure clear.

**S5. A grader with 20 minutes cannot use the one-command path.** `run_all` runs the 13-minute suite and a several-minute smoke **before** the dashboard opens.
Add a line near the top of Start here: "To look at results only (about 1 min): `python -m pip install -r requirements.txt` then `python -m streamlit run 04_dashboard/app.py`". Also suggest the dashboard tabs to read first (Final selection → Overview → Bottleneck explained).

**S6. The far_end_flicker and deep_book ratios come from different sources but are not labelled.** README:457-458 gives "about 20.8x B1/B3" (attack, `ATTACK_REPORT.md:59`). REPORT §8/§9 and FINAL_SELECTION give 18.4x (B3r-session 100k). Deep_book appears as 3.05 (README:457, SPEC), 3.06 (REPORT, FINAL_SELECTION) and 2.80 (re-run). All are traceable, but each should name its source run, or one figure should be used throughout.

**S7. Memory requirement only partly met in the report.** R §Memory asks to *explain why* measured allocation differs from auxiliary space and process/native memory. REPORT §7 only states that it does. Add one or two sentences, for example: tracemalloc counts Python-allocator blocks, including the current result and allocator rounding; it misses interpreter/native and freed-but-retained memory, while RSS includes them. The explanation exists in BENCHMARK_PLAN.md (R55), so a link would also work.
Also, active-order and price-level **peaks** (R §Benchmark 1) are in `counts.csv` and the dashboard but are not mentioned in REPORT §6. One sentence with the 100k peaks would close this.

**S8. REPORT_FACT_CHECK.md:5 is out of date.** It says *"The historical FINAL_SELECTION.md is unchanged, including its older 26-faster wording"*, but commit `5785e9f` changed FINAL_SELECTION to 25/27 (and introduced M1). Correct the sentence or remove it.

## C. NICE-TO-HAVE

- FINAL_SELECTION:38 says "57 ms vs 0.03 ms for B1, ratio 1,866". 1,866 is the ratio against **B2** (0.031 ms), the fastest B. Against B1 (0.034 ms) it is 1,696. Write "vs best B (B2)".
- FINAL_SELECTION:54 says "B3r is about 13 % slower than B3r_fast". It is fast that is 12.7 % faster; B3r is about 14.5 % slower.
- FINAL_SELECTION says "professor's 50,000 events / 10k streams". Use "supplied" as in REPORT.
- `00_docs/LEARNING.md` is an unfilled template, although README:305 lists it as a "learning note". Fill it or remove the README mention.
- `00_docs/REVISION.md` ends at the B3r_fast trial. Add a two-line final entry: the binding rematch was rejected and B = B3r.
- SPEC.md:227 "(prepared, not yet run)" and SPEC.md:541 "Final B selection … wait for Phase 4" are stale; SPEC.md:11/33 are correct.
- Typo "At16000 levels" (README:448), plus several missing spaces in the REQUIREMENTS_MAP and SPEC tables ("ratio3.05", "retained501", "checks208").
- REPORT §11 uses `python run.py …` while README Start here uses `python -m run …`. Both work; use one.
- The branch diff against `main` also adds `Submissions/BuehlerLaurin/1st_Lab_ungraded/` and the AGENTS/CLAUDE files. That is fine because it is your own folder, but make sure it is intended in the PR.

## D. Requirement → evidence map (independent, from package README + slides)

Legend: ✔ met with committed evidence · ◐ met but weakly evidenced or documented · ✖ missing

| Requirement (source) | Evidence | Status |
|---|---|---|
| Sequential BTC LOB with own FillMarketSell, A and B (R §Task; S2) | `01_code/lob/book_a.py`, `book_b3r.py`; REPORT §3 | ✔ |
| Model boundaries, not production, synthetic not historical (R §Task; S4, S15) | REPORT §1, §10; SPEC "Model boundaries" | ✔ |
| Integer units, proceeds / 1e10 (R §Integer units; S5) | README:241-244 (3594000000000000 → 359,400.00 USD); TRACE.md | ✔ |
| JSONL/gzip with stdlib; replay command (R §Input; S6) | `lob/replay.py`; README:36, 100-110; tested here | ✔ |
| AddLimitOrder/CancelOrder/FillMarketSell/dispatcher/inspection, documented (R §Input; S6) | REPORT §2; SPEC "Interface" | ✔ |
| Matching rules 1–5, cancel, validation rule 6 (R §Matching; S7, S8) | SPEC; `02_tests/contract.py`, `test_validation.py`; REQUIREMENTS_MAP R10–R18 | ✔ |
| Required result fields and statuses (R §Required results; S9) | SPEC "Output"; worked expected check OK | ✔ |
| Worked example: b1:1, b2:1, b3:3, b4:1; 359,400 USD (R §Worked; S3) | README:231-244; `check-worked` OK (this review) | ✔ |
| Tests first, listed edge cases, red run (R §Worked; S11) | `06_data/own/` 18 cases; `05_evidence/*tests-red*` | ✔ |
| Conservation and every-event A/B comparison (R §Worked; S12) | `contract.step_check`; `test_stateful.py`; attack 1,152,000 comparisons | ✔ |
| Agreement plus independent expectations (S12) | Hand-calculated own cases plus the attack oracle; the "independent reference vs B3r" row is not committed (S1) | ◐ |
| Version A baseline, Version B justified (R §Implement; S13) | REPORT §3, §9; FINAL_SELECTION | ✔ |
| Invariants, pseudocode, runtime/space with B/P/M/F; worst/expected/amortized (R §Implement; S13) | REPORT §3–§5; SPEC D1 and B3 bounds | ✔ |
| Preserve versions; unchanged tests; AI accepted/corrected/rejected (R §Implement; S13) | Registry keeps 7 names; REPORT §11; AI_LOG; REVISION | ✔ (REVISION lacks the final entry) |
| M = 1k/10k/100k, seeds 42/43/44, five workloads, same limits (R §Bench; S16) | `03_results/runs/…5eaeb03_phase4`, `…00bb1ad_phase4_b3r…`; recomputed here | ✔ |
| 1M attempt, declared limits, stopped runs reported (R §Bench; S16) | `stops.csv`; REPORT §6; A stopped 4/5 at 1M (verified) | ✔ |
| Submission flood + active/level peaks (R §Bench 1; S17) | `counts.csv` active_order_peak / price_level_peak; dashboard | ◐ (not in REPORT, S7) |
| Large liquidation 10/100/200 %, fresh book, counts (R §Bench 2; S17) | REPORT §6; recomputed 1,003 makers / 100 levels; 15 ms / 132 ms | ✔ |
| Queue concentration 4 vs 1,000 prices (R §Bench 3; S16) | REPORT §6: 189x vs 167x (verified) | ✔ |
| Cancellation churn: time and memory, stale growth (R §Bench 4; S17, S20) | REPORT §7; B3 37 MB vs B3r about 5 KB (verified) | ✔ |
| perf_counter, warm-up, 5 repeats, raw repeats + median; fresh book (R §Time; S18) | `timing.csv`; BENCHMARK_PLAN; dashboard "Method & data" | ✔ (A at 100k/1M single trial, declared before measuring) |
| Parse vs replay separate; construction not hidden (R §Time; S18) | summary.csv phases; REPORT §8: 461 vs 463 ms (verified) | ✔ |
| Throughput; latency p50/p95/p99, convention, by type, early/late (R §Time; S19) | `latency.csv` nearest-rank; REPORT §6 4.1/11.2 µs (verified) | ✔ |
| tracemalloc separate, inclusions stated (R §Memory; S20) | `memory.csv` "includes" column; REPORT §7 | ✔ |
| Explain traced allocation vs auxiliary space vs RSS (R §Memory; S20) | Stated in REPORT §7, explained only in BENCHMARK_PLAN | ◐ (S7) |
| Machine-readable results + env metadata (R §Results; S23) | `summary.csv`, `timing.csv`, `env.json` per run | ✔ |
| Dashboard from saved files; all required views; units; stopped runs (R §Results; S22) | `04_dashboard/`; nine tabs; dashboard tests | ✔ (but M1/M2 show on its first tab) |
| Explain one bottleneck with code, counts, complexity (R §Results; S22) | REPORT §8: A id-scan M(M-1)/2 = 499,500 / 49,995,000 (verified) | ✔ |
| Report: spec, correctness, runtime, memory, **profiling**, revision, limitations (R §Submit; S23) | REPORT §2–§10 | ◐ (profiling not committed, S1) |
| README: clean-env path, expected worked output, data definitions (R §Submit; S23) | README Start here, l.231-244, l.352-395 | ◐ (stale sections, M4) |
| Submitted commit identifier (R §Submit; S23) | Placeholder only | ✖ until submission (M3) |
| No million-event files; commands + checksums (R §Submit; S23) | `.gitignore` 06_data/generated; DATA_MANIFEST / POST_ATTACK_MANIFEST | ✔ |
| Course folders and other students' work unchanged (R §Submit; S23) | `git diff main...HEAD` outside `Submissions/BuehlerLaurin`: 0 files | ✔ |
| No credentials or proprietary data (R §Submit) | grep for secrets: none; synthetic data only | ✔ (REQUIREMENTS_MAP R68 still says "todo") |

## E. Claims traced (all recomputed from committed files)

Verified (value matches the committed source):
- REPORT/README speedups 11/170/>1,295 (buildup), 17/186/>1,299 (crowded), 11/139/>1,260 (sweep), 2.8/21/299 (mixed), churn 0.74/0.77/0.70. Three A cells stopped at 100k on each of buildup, crowded and sweep.
- Geomeans B1 0.4244, B2 0.4726, B3 0.4289, B3r 0.4247 s.
- B3r 100k throughput 210,032–265,472 events/s (per-workload medians). 1M B3r 4.79–6.76 s.
- Exponents: A 2.09/2.09/2.13/1.91 and B3r 0.92–1.06 (1k→10k); B3r 0.93–1.04 (10k→100k).
- Liquidation: sale 867x–1,165x, construction 70x–100x at 10k; 1,003 makers / 100 levels (10 %); 10,000 / 1,000 (100 %); 100k: 14.7 ms / 131.9 ms.
- Latency, buildup 100k: p50 4.1 µs, p99 11.2 µs; early 4.0/11.3, late 4.1/12.0.
- Memory: A 0.31–1.92 MB, B3r 0.95–2.85 MB at 10k; B3r 3.7–15.6 MB at 100k; churn 1,392 B vs 6,848 B. Post-churn 1M about 3.1 KB. B3 drift 37.8 MB vs B3r 5.1 KB, 18 heap entries.
- A counts 499,500 / 49,995,000 and 249,964 / 24,999,375.
- Spike: 57.66 ms vs B1 0.034 ms; construction + sell 1.777 s vs 4.633 s.
- Worst B3r ratio 1.42 (1M churn).
- Rematch: 0.8732 (12.7 %); 25/27 faster; 26/27 within 1.05; failing cell dead_slot_rebuild 1k 1.068 (3.66 vs 3.42 ms); 10k/100k 0.807/0.833. Cross-session: 0.887, five per-cell losses.
- Attack: 1,152,000 comparisons, 7/7 planted bugs, GC 44–46 ms and 10–13 ms without GC, 13x and 299x rebuild pitfalls.
- 17 mutants; 1,033 tests collected; worked example OK.

Not committed or different: see M1, M2, S1, S2 and the nice-to-have numerical items.

Fresh full suite at HEAD `1b7adca` (clean tree): **1033 passed in 716.86 s**, exit 0, no failures or skips (`scratch/final_review/pytest_full_1b7adca.log`). This is a scratch log only, not saved through `evidence.py`; see S3.

## F. Readability (grader with 20 minutes)

What works: the README "Start here" is short and states the final B, the headline numbers, the losing workload and the rejected variant. REPORT is well structured (11 sections, about 200 lines), has explicit tables and is honest about the post-hoc spike interpretation and the A protocol deviations. The dashboard opens with the decision.

What confuses:
1. Contradictions: the README history sections (M4), FINAL_SELECTION:64 (M1) and two speedup conventions (M2). A grader who finds one false statement starts to distrust the rest.
2. Too many test counts: 848, 983, 999, 1,027, 1,032 and 1,033 all appear in README. Keep one current number and link the rest from a history section.
3. Version zoo: A, B, B1, B2, B3, B3r and B3r_fast, with "historical B means B1" in saved labels. Start here should say in one sentence: "Grade A vs B (= B3r). B1–B3 are measured candidates; B3r_fast is a rejected optimisation."
4. Length: README has 466 lines, most of it a phase log. REQUIREMENTS_MAP has 519 lines, AI_LOG 1,325 and SPEC 1,001. Suggested reading order (put it in Start here): README Start here → REPORT → dashboard Final selection/Overview → FINAL_SELECTION. Mark everything else as audit trail.
5. Time to first result: see S5.

## Limits of this review

- No benchmark was re-run, and the dashboard was not opened in a browser. Its correctness relies on the committed dashboard tests and the full-suite run above.
- Bash runner: syntax evidence only; no macOS/Linux run.
- The aif-review spec-blind attack step was not repeated. The committed `07_attack` campaign against final B (`ATTACK_REPORT.md` addendum) was reviewed instead, as this review covers documents and claims.
- Chat-attributed checks (S1) could not be reproduced because their code is not in the repository.
