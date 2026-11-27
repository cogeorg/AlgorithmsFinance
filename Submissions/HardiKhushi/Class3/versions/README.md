# Preserved source versions

`step3/` contains all four exact source files used by the original
`results/bitcoin_1y/result.json`, checked against that run's recorded hashes
before the stage-4 runner changes. The snapshot is provenance evidence; its
relative data paths assume the original submission-directory location, so do
not execute the nested copy in place. The scalar pricing implementation in
the active directory remains unchanged.

The stage-4 runner supports both engines and full-file selection. New runs
record their own source hashes and engine; earlier measurements are unchanged.

`pre_audit/` preserves the 15 root source/document files before the comprehensive
review, with source_sha256.json. These files resolve the historical stage-4
result hashes. They include known defects and are provenance evidence, not
the active implementation. See ../audit/AUDIT.md.

`audit_reference_initial/` preserves the first numerical-audit helper so the
source hash of the preliminary audit/numerical_check.json remains resolvable.
The active audit_numerics.py adds a reusable print-only default and optional
exclusive --output; audit/numerical_check_final.json records its current hash.

`pre_second_review/` preserves the 27 root source/document files before the
complete-submission reassessment. It resolves the source hashes of the
delivered timing/memory runs and original final-table builder. Later boundary
edge-case and validation fixes did not change any of the 80 market prices.

`second_review_initial_driver/` preserves the actually executed
recheck_current.py. Its subsequent CLI adds optional new output files; the
complete verifier checks equivalence of its computation functions and exact
current pricing-source hashes. See ../audit/second_review/REVIEW.md.
