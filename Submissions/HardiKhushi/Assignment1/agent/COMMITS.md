# Approved local checkpoints

All checkpoints are on `assignment1/hardi-khushi`, starting at `ae01998`.
The user explicitly approved each commit after the stage was complete.

| Stage | Commit | Scope | Second verification |
| --- | --- | --- | --- |
| 1 | 8270fac | Organization, preserved materials, working agreement | Clean export has materials and no engine |
| 2 | 35125e8 | Tests before code and recorded red run | Clean export reproduces 37 missing-module errors in 40 tests |
| 3 | 52a6c5e | List baseline, validation and replay | Clean export: 21 pass, one explicit skip |
| 4 | 3276644 | Indexed FIFO revision and storage tests | Clean export: all 43 tests pass |
| 5 | 383b0aaa2d6bac673cd1687261f16d326a2ef530 | Measurement protocol, raw evidence and verifier | 52 files checked against Git blobs; 47 tests, both worked examples, saved-results and CLI checks pass |

The user also explicitly approved the Stage 6 dashboard/report delivery commit
and its post-commit verification. Its final identifier is in Git history and the
completion message after creation. The pre-approval staged tree
1e27381155a98a3a0bec897be739bfc46aab9193 passed a clean 64-file export, 47
tests, both worked examples, all saved-result checks and a byte-identical
dashboard/findings rebuild.
Run `git rev-parse HEAD` to identify the checked-out submission revision.

Measurement identity is distinct: engine base `3276644` and 12 actual measured
source-file SHA-256 fingerprints are in results/environment.json. The benchmark
harness was not committed while it ran; checkpoint 383b0aa preserves its exact
measured source and outputs. No retrospective re-identification of data is made.

Clean-export evidence is in results/evidence/checkpoint_verification.json and
clean_export_383b0aa.json. `agent/verify_submission.py` can verify the eventual
HEAD again, without rerunning the experimental matrix or changing tracked files.

## Public submission references

The table above records the original local checkpoints. PUBLICATION.json maps
them to the equivalent Assignment1-only public commits, preserving their order
and source bytes without publishing the earlier local peer-audit commit.
See PUBLICATION.md for the publication base, destination and scope.
