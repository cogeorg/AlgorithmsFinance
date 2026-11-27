# Second review of the complete Class 3 submission

Reviewed 27 November 2026 at the user's request to reassess everything and make
necessary changes. Fresh current-code calculations reproduce all 80 delivered
prices and all 52,584 Bitcoin boundary entries exactly. The original four-row
table rebuilds byte for byte. The review nevertheless found API edge cases
and verification gaps worth fixing.

## Reproduced findings

| Finding | Before | Fix |
| --- | --- | --- |
| Exact input payoffs were treated as computed-node noise | At N=0, spot=100 and strike=nextafter(100,+infinity), the value was positive but the boundary was None. An immediately optimal tiny root payoff at N=1 was also omitted. | Treat the supplied date-zero price exactly: every positive root/expiry-only payoff counts. |
| Unnecessary expiry range restriction | A representable payoff from spot=1e-310, strike=2e-310, N=0 was rejected. | Apply the normal-range guard to positive-period trees; expiry-only pricing constructs no tree. |
| Caller mutation bypassed PriceWindow validation | Validated caller lists could later change the frozen object's price/date lengths. | Own tuple copies before validating. The CSV loader already returned tuples, so calibrations are unchanged. |
| Numerical checker could verify zero contracts | Empty case lists bypassed repricing loops while retained Bitcoin prices allowed status verified with cases_checked=0. | Require the exact 40 supplied assets, ordered case coverage and correct horizon/price maps for each batch, and 80 distinct final contracts. |
| Table builder could mislabel a horizon | A valid full-file batch reused under the one-year directory was accepted and labelled one year. Parent completion was not checked. | Share a completed-collection verifier, check expected horizons and Bitcoin asset/window identity, and require completion hashes. |
| Generic-input console unit was wrong | ETHUSDT metadata was correct but the console printed USDT/BTC. | Derive the native unit from the actual asset. Printing remains outside timing. |

Eight new regression methods produced nine failing assertions and two error
subcases before repair. Two more end-to-end tests verify valid summary-source
mapping and reject relabelled rows even with an updated CSV hash. All 52 test
methods now pass; original rational expected answers are unchanged.

## End-to-end evidence

`verify_submission.py` ties the four performance rows to measured source runs,
the complete 40-asset collection, independent numerical evidence and a fresh
current-code report. It checks coverage and semantic relationships as well as
hashes. Historical source versions resolve from preserved snapshots.

Fresh `recheck_current.py` execution recalibrated every contract from raw files,
recomputed all 80 prices, and reconstructed both complete Bitcoin boundaries.
Every result matches exactly. No delivered market price, exercise date,
payoff or table value needed correction.

The earlier independent numerical evidence contains all 80 real contracts,
bound to the delivered batch hashes. Its pricing routine's syntax tree is
unchanged; checker changes concern coverage. This review checked that evidence
and freshly executed the production calculations. It does not claim another
execution of the independent 80-contract reference from the final batch stage.

The strengthened builder's CSV is byte-identical to results/final_summary.csv.
All 52 pre-review files under results/ are unchanged. Measured source versions
are preserved in versions/pre_second_review. Times and allocation peaks retain
their original source identities and were not relabelled as fresh performance
samples for the edge-case revisions.

## Files

- `regressions_before.txt`: reproduced pre-fix failures and error subcases.
- `tests_final_current.txt`: 52 passing tests after all code changes.
- `current_prices.json`: 80 fresh recalibrations/prices and both exact Bitcoin
  boundary comparisons, with pricing-source hashes.
- `submission_check.json`: successful complete-submission verification.
- `rebuilt_summary.csv` and its manifest: fresh derivation of the same table.
- `preserved_results.json`: identities of all 52 pre-review result files.
- `../../versions/pre_second_review/`: exact pre-review sources/documents.

The executed recheck driver is preserved in versions/second_review_initial_driver.
A subsequent CLI revision adds optional new output paths and a read-only
default. Its computation functions match the executed driver; the complete
verifier checks their syntax trees and exact current pricing-source hashes.

## Reproduction and limits

Run the test suite and `verify_submission.py` from the repository root. For
a new current-code calculation, run `recheck_current.py --output NEW_JSON`
and pass the report to `verify_submission.py --current-check NEW_JSON`. Use
new filenames inside Class3. The summary builder now accepts explicit Bitcoin
and batch directories for new runs.

Documented choices remain: positive-payoff boundaries, a relative cutoff for
computed stock-node noise, zero-rate indifference tolerance, reciprocal CRR
central nodes, Actual/365 Fixed and no gap filling. These are finite-precision
calculations. Exercise dates are retrospective; gross payoff excludes the
premium. Traced memory excludes preloaded histories and is not process RSS.
Price-only batch rows and Bitcoin boundary rows have different output workloads.
No memory limit was reached.

All six tasks remain complete locally. Work stayed inside Class3. No staging,
commits, pushes or external submission were performed.
