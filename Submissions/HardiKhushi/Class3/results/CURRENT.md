# Current Class 3 results after the audit

Use `final_summary.csv` for the completed four-row performance table.
`final_summary.manifest.json` records the exact source results and builder.

`audit_v1/` contains the two corrected Bitcoin price/boundary measurements.
`all_assets_v1/1y/` and `all_assets_v1/full/` contain the two directly measured
40-asset price-only batches, with all 80 prices, inputs and metadata. Their
completion hashes are recorded in `all_assets_v1/completion.json`. Both use
the same audited log-price implementation, with output modes labelled.

The root-level `bitcoin_*` directories, comparison files, calibration file and
`README.md` are historical stage-2/3/4 records. They are preserved unchanged.
Their prices to the cent and first exercise dates remain correct, but the
old full-file expiry boundary is superseded. Source snapshots resolve their
recorded hashes under `../versions/`.

The completed assignment is in `../REPORT.md`. Audit findings are in
`../audit/AUDIT.md`; final batch evidence is in `../audit/batch_verification.json`
and `../audit/batch_numerics.json`. All 80 prices were independently repriced.
