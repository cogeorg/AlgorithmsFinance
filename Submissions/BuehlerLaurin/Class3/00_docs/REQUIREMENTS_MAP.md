# Requirements → evidence map
Step 0b: specification only. “todo” means implementation/verification remains; a spec link is planning evidence, not proof of completion.

| ID | Requirement / source | Status | Current documentation; planned evidence |
|---|---|---|---|
| R01 | PriceAmericanPut model, domain, scalar price, unchanged inputs; p.21 | todo | SPEC model/D11; planned domain, immutability and Fraction checks |
| R02 | Node formula, q and American recurrence; pp.22–25 | todo | SPEC formulas; planned hand-oracle/differential/mutant checks |
| R03 | Two N+1 arrays; increasing-j backward update; pp.23/25 | todo | SPEC two arrays/invariant; future code review and tests |
| R04 | Stable construction, boundary in backward pass, no tree; Laurin D11 | todo | SPEC numerical risks; planned high-s/large-N per-node regression |
| R05 | Task 1: implement and check 7.9932; p.31, p.27 | todo | SPEC D7; planned TRACE and exact/rounded American test |
| R06 | European 6.2925 comparison; p.27, Laurin D7 | todo | SPEC D7; planned exact 925/147 comparison |
| R07 | Last N+1 closes, ATM first close, exercise dates 0..N; p.29 | todo | SPEC D1; planned selection/gap/contract checks |
| R08 | Log returns, sample std denominator N-1, u/d/R; p.30 | todo | SPEC calibration/D2; planned exact small calibration checks |
| R09 | Task 2: BTC N=8760 value and boundary at every t; p.31 | todo | SPEC D1/D3–D5; planned boundary contract and BTC results |
| R10 | Task 3: earliest observed crossing, UTC date, payoff or never; p.31 | todo | SPEC D6; planned path tests and BTC results |
| R11 | Task 4: repeat full BTC file; p.31 | todo | SPEC D10; inventory full_N=43822, pricing results pending |
| R12 | Task 5: all 40 assets in one process, 1y and full file; p.31 | todo | SPEC D9/D10; planned batch results and error-continuation tests |
| R13 | Task 6: N, assets, seconds, peak memory; p.31 | todo | SPEC D8/measurement contract; planned timing and separate tracemalloc logs |
| R14 | Submit code and table in own Class3 folder; p.31 | partial | Scaffold here; code/table still pending |
| R15 | Data integrity, actual row counts, missing hours; data README/workflow | done | 06_data/supplied/DATA_INVENTORY.json and MANIFEST.json; step0-data-inventory / step0-manifest evidence. Own snapshot only, no upstream authenticity claim |
| R16 | Decisions D1–D11; Laurin's approved interpretation | done | SPEC Decisions and numerical correction; implementation checks still pending |
| R17 | Approved artifacts and applicability, predictions; session scope | done | SPEC/README/REPORT/TRACE/AI_LOG; TRACE calculation deferred, no algorithm code or task-specific tests |
| R18 | A/B differential, independent Fraction oracle, mutants, audit; approved workflow | todo | SPEC planned checks; later TDD and Claude audit/attack evidence |
| R19 | Wall-time/memory growth; profile before B; approved Step 0a | todo | SPEC complexity predictions; later benchmark/profiling evidence |
| R20 | Dashboard | out of scope | Step 0a: README/REPORT tables only |
| R21 | S&P 500 download | out of scope | Laurin's scope; no network/data edits |

Update statuses and replace planned evidence with actual evidence each phase. Do not mark pricing tasks complete from data/documentation checks.
