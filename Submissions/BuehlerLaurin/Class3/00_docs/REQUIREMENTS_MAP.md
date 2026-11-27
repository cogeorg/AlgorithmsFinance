# Requirements → evidence map
Blocks 1–2: tests and A/B complete; required benchmark artifacts tracked below. Evidence index: ../05_evidence/INDEX.md. Audit and hand-off verification are later phases.

| ID | Requirement / source | Status | Current documentation; planned evidence |
|---|---|---|---|
| R01 | PriceAmericanPut model, domain, scalar price, unchanged inputs; p.21 | done | contract.check_validation/check_input_not_mutated; shared validation; tests-before-bench 36 passed |
| R02 | Node formula, q and American recurrence; pp.22–25 | done | contract.check_exact_oracle/check_toy; oracle.exact N<=12; tests-green-A/B |
| R03 | Two N+1 arrays; increasing-j backward update; pp.23/25 | done | amput/a.py and TRACE.md; check_layer_invariants; documented stable-S deviation |
| R04 | Stable construction, boundary in backward pass, no tree; Laurin D11 | done | test_stability/test_differential.test_B_large_layer; code layer buffers; tests-before-bench |
| R05 | Task 1: implement and check 7.9932; p.31, p.27 | done | contract.check_toy; TRACE.md; tests-green-A/B |
| R06 | European 6.2925 comparison; p.27, Laurin D7 | done | contract.check_toy vs 925/147 and 6.2925; tests-green-A/B |
| R07 | Last N+1 closes, ATM first close, exercise dates 0..N; p.29 | done | test_data.test_last_rows_not_calendar; boundary endpoint contracts |
| R08 | Log returns, sample std denominator N-1, u/d/R; p.30 | done | test_data.test_tiny_hand_csv; diagnostic CSV; tests-before-bench |
| R09 | Task 2: BTC N=8760 value and boundary at every t; p.31 | done | Final run BTC1y_B_assets.csv and BTC1y_B_boundaries/BTCUSDT.csv; boundary contract and full BTC1y A/B comparison |
| R10 | Task 3: earliest observed crossing, UTC date, payoff or never; p.31 | done | test_data.test_first_exercise_hit_and_never; BTC1y_B_assets.csv: 2026-06-02T14:00:00Z, payoff 41588.71 |
| R11 | Task 4: repeat full BTC file; p.31 | done | BTC5y_B_assets.csv / boundary file; N=43822, value 20719.789430024288; 2022-06-18T06:00:00Z, payoff 42121.23 |
| R12 | Task 5: all 40 assets in one process, 1y and full file; p.31 | done | Final ALL1y_B/ALL5y_B summaries; local boundary CSVs git-ignored with BOUNDARIES_MANIFEST.json hashes/regeneration command; benchmarks-lattice and artifacts-block2 evidence |
| R13 | Task 6: N, assets, seconds, peak memory; p.31 | done | Final summary.csv/timing.csv/memory.csv, all repeats and separate traced scopes; README/REPORT tables |
| R14 | Submit code and table in own Class3 folder; p.31 | done | Implementation and results table are in the required folder; git/submission remains Laurin's action, independent audit still pending |
| R15 | Data integrity, actual row counts, missing hours; data README/workflow | done | 06_data/supplied/DATA_INVENTORY.json and MANIFEST.json; step0-data-inventory / step0-manifest evidence. Own snapshot only, no upstream authenticity claim |
| R16 | Decisions D1–D11; Laurin's approved interpretation | done | SPEC Decisions/Assumptions; shared contracts, calibration/path/stability tests and final artifact verification |
| R17 | Approved artifacts and applicability, predictions; session scope | done | SPEC assumptions, README/REPORT, completed N=2 TRACE and AI_LOG; FAST MODE supersedes historical Step 0b restriction |
| R18 | A/B differential, independent Fraction oracle, mutants, audit; approved workflow | partial | 200 Hypothesis examples, exact oracle, six mutants green; BTC1Y_DIFFERENTIAL.json delta=0/no exceptions. Claude audit/attack pending |
| R19 | Wall-time/memory, timing growth; profile before B; approved Step 0a | done | PROFILE_A_BTC1Y.pstats, final summary/memory/growth CSVs; growth-direct-process evidence; code Θ(N²)/Θ(N) argument in REPORT, memory scales with per-asset N and compact summaries |
| R20 | Dashboard | out of scope | Step 0a: README/REPORT tables only |
| R21 | S&P 500 download | out of scope | Laurin's scope; no network/data edits |

Update statuses and replace planned evidence with actual evidence each phase. Do not mark pricing tasks complete from data/documentation checks.
