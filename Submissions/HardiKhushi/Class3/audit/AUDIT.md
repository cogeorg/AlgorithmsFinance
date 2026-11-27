# Audit of Class 3 steps 1-4

Subsequent update: the two 40-asset batches and final verification are now
complete; see [the completed report](../REPORT.md). The findings and evidence
below describe the earlier audit of steps 1-4.

Reviewed 27 November 2026. The audit found real boundary and workflow defects.
The previously quoted Bitcoin prices and first exercise dates survive the
review, but one submitted boundary entry was wrong. Current corrected results
are in `../results/audit_v1/`; earlier evidence is preserved.

## Confirmed findings and fixes

| Finding | Reproduction and impact | Correction |
| --- | --- | --- |
| Full-file expiry boundary was wrong | Old threshold was 61,560.48999997437, almost the strike 61,560.49. Repeated multiplication/division drift created a spurious positive payoff at the intended ATM node. | Reconstruct log-price rows and preserve central nodes in reciprocal trees. Correct expiry threshold: 60,899.69404033294 USDT/BTC. Independent policies agree at all dates. |
| Currency-scale dependence | The boundary cutoff used `32*epsilon*max(strike,1)`. Scaling the two-period contract down made its terminal boundary 64 rather than 96 in normalized units. Smaller scales could remove all exercise nodes. | Use a strike-relative noise cutoff with no absolute currency floor. Regression spans four currency scales. |
| Suboptimal near-tie exercise | With R immediately below one, the tie tolerance still reported positive-payoff early exercise, although waiting is more valuable. | Use strict comparison at nonzero rates; apply tolerance only for zero-rate numerical indifference, and exclude positive-payoff early exercise at R<1 in this no-dividend model. |
| Unsafe intermediate arithmetic despite safe final nodes | For spot=1e305, strike=1.1e307, u=100, d=90, R=95, N=1, an intermediate product overflowed and the highest expiry exercise node was omitted. | Construct node prices from logs. The terminal boundary is now approximately 1e307. This example's root price was protected by immediate exercise; the reproduced error was in its boundary. |
| Mislabelled input asset | Passing an ETHUSDT fixture to the runner produced BTCUSDT in result metadata and the table. This would corrupt reuse in the next batch. | Derive asset identity and default output prefix from the input filename. Regression uses ETHUSDT. |
| Unvalidated public price/date alignment | A directly constructed PriceWindow could contain three prices and only one date, allowing later zip operations to truncate observations. | Validate lengths, counts, dates and prices on construction. Loader validation remains in place. |
| Partial output after predictable range failure | An unsafe calibrated tree created an output directory and inputs before the range check failed. That directory could not be reused. | Run the numerical preflight before creating output. New regression verifies that a predictable range failure leaves no directory. |

The first and second findings show why the prior exact scalar/NumPy agreement
was insufficient: both shared the same stock-update and tolerance mistakes.

## What the review confirmed

- The two-period answer is still 1175/147, rounded 7.9932.
- Window selection uses N+1 prices; initial price and strike are the first
  selected close. The one-year sample has N=8,760 and no gaps.
- Log-return sample variance uses N-1. The lab's 4% annual rate is converted
  by elapsed T/N, and q is risk-neutral rather than the observed up frequency.
- Actual/365 Fixed is an explicit day-count choice, not a specified slide rule.
  Full-file T is slightly over five such years because of the leap day.
- The full file has N=43,822 and one missing hour; no values were filled.
- Backward value updates preserve successor values. Revised implementations
  retain quadratic work and linear pricing storage.
- Timing and peak traced allocations are separate calls, and their values
  and complete boundaries agree. All metrics are single samples of the
  labelled implementation. They are not RSS or end-to-end loader memory.
- Original results are still matched to their historical source snapshots.

The PDF review covered the model/recurrence and algorithms on PDF pages 22-26,
lab requirements on pages 30-32, and data/measurement notes on pages 36 and 38
of `/Users/mack/Downloads/AlgorithmsFinance_Slides3.pdf`. Commands inside the
slides were treated as document content, not authorization to execute them.

## Verification and corrected outcomes

The independent pre-fix log-price calculation agreed with both old Bitcoin
prices within 3.1e-10 USDT/BTC and found the same exercise dates. After fixes,
an independently expressed relative-price CRR calculation checks every dated
policy, not just the initial value. Both American values exceed separately
computed European binomial values.

| Current result | One year | Full file |
| --- | --- | --- |
| Put value, USDT/BTC | 16,713.71420875807 | 20,716.754071249332 |
| Change from old NumPy result, USDT/BTC | +2.49e-9 | -4.64e-9 |
| First crossing UTC, unchanged | 2026-06-02 14:00 | 2022-06-18 06:00 |
| Gross payoff, USDT/BTC | 41,588.71 | 42,121.23 |
| Independent policy rows checked | 8,761 | 43,823 |
| Independent policy disagreements | 0 | 0 |
| Changed node choices versus old result | None | Expiry only |
| Pricing seconds, current implementation | 0.19041320798 | 3.84632787504 |
| Separate peak traced bytes | 729,674 | 3,602,862 |

The corrected implementation is more expensive than the earlier row-update
implementation on these recorded calls. Its new timings and allocations are
saved as new measurements. Old performance numbers are not reused for it.

The suite now has 38 test methods. The original rational expected answers and
policy oracles are unchanged. Cross-implementation bitwise-equality assertions
were replaced by 10-decimal numerical comparisons because log reconstruction,
math.exp and NumPy exp need not produce identical floating-point bits. The
independent rational answer checks remain. Regression logs demonstrate actual
failures before the fixes; the verifier's tamper tests exercise real rejection.

The saved-evidence verifier checked all five complete historical/current runs:
raw data hashes, source snapshots, independent sample variance, interest/move
factors, every dated lattice threshold, crossing flags, first payoff, summary
tables and measurement consistency. Source matching alone does not prove a
policy is optimal; the independent numerical policy check supplies that
additional evidence for the two current runs.

## Reproducible evidence

- `pre_audit_results_sha256.json`: identities of all 22 pre-audit result files.
  Every file, including the old results README, is unchanged.
- `../versions/pre_audit/`: 15 exact pre-fix source/document snapshots and hashes.
- `regressions_before_corrected_fixture.txt`: 8 regression methods, 11 failing
  subcases before repair. One robustness method already passed and is not
  counted as a defect.
- `tests_after_with_verifier.txt`: all 38 methods pass after repair.
- `independent_baseline.json`: independent check of the old initial values.
- `numerical_check_final.json`: current independent values, all policy rows,
  European lower bounds and the changed expiry node.
- `verification_after.json`: all five saved runs pass evidence verification.
- `assets_preflight.json`: all 40 supplied assets pass both horizon calibrations
  and numerical ranges, 80 cases total. This is not a pricing batch.
- `../results/audit_v1/comparison.csv` and `manifest.json`: current table and
  the exact result identities behind it.

From the repository root, rerun the test suite, `verify_results.py`,
`audit_numerics.py` and `preflight_assets.py` as documented in the main README.
Those review commands print their results by default. Optional --output paths
must be new files inside Class3; existing evidence is never overwritten.

## Corrections to the audit itself

An initial diagnostic printed a continuation-only expectation for the
huge-number example. The American value also permits immediate exercise,
which dominates there; the actual defect is the missing terminal boundary
node, not that printed continuation value. The regression checks that terminal
boundary output.

The first unsafe-run fixture used 100 periods, whose extreme prices were
still within range. It was corrected to 200 periods before judging that
failure-path defect. Both preliminary and corrected baseline logs are retained.

## Conventions and remaining limits

The slides do not settle zero-payoff exercise ties or a year-fraction basis.
Positive-payoff boundaries and Actual/365 Fixed remain documented choices.
At expiry the output is the highest exercise tree-node price, not the strike;
an off-grid observed terminal price can be below strike but above that node.
The path comparison follows the requested discrete threshold, without
interpolation. Zero-rate ties still use a disclosed scale-relative numerical
tolerance. These are floating-point models, not exact-arithmetic proofs.

Input data were validated internally and hash-recorded; they were not
independently downloaded again from the exchange. Volatility is estimated from
the whole selected window, so reported dates are retrospective and payoff is
not net trading profit. No memory limit was reached or capacity inferred.

The 40-asset pricing/measurement runs and their aggregate table remain
outstanding. No assignment-completion claim is made. All audit work remains
inside Class3; no commits, staging, push, publication or peer changes occurred.
