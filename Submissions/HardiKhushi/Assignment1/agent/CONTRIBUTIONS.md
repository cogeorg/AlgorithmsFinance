# Codex contribution

Codex reviewed the supplied README, manifest, generator and complete PDF text;
organized this separate Assignment1 project; and preserved original source/data.
The initial matching tests were written and run before engine files existed.
Codex wrote both matching implementations, validation/results, file reader and
replay CLI, measurement harness, saved-data verifier, offline dashboard and report.
It executed the workloads, recorded raw observations including stops/regressions,
and created the approved local checkpoints. No generated observations are invented.

Codex designed independent hand-calculated cases and a passive-order sale oracle;
per-event differential/conservation tests supplement these. The revision uses
OrderedDict FIFO queues, an ID index and sorted occupied prices. Its O(P) array
updates, Python allocation retention and expected/amortized hash assumptions are
documented. Timing, counters, per-event latency and memory runs are separate.

Codex also wrote clean-checkpoint/export verifiers and browser QA. It corrected
an export working-directory bug and a Chrome narrow-viewport/screenshot mismatch.
Chrome could not launch under the initial sandbox; the approved external local
browser check succeeded. Screenshots and browser profiles stay ignored; no
external site, data service, network download or publication was needed.

The user's contributions in this session are the assignment materials, desired
test-first/traceable organization, instructions, authorization changes and each
commit approval. The student has not yet independently reviewed the code,
reasoning or numerical conclusions. This record does not claim otherwise.

AI/INSTRUCTIONS.md records user instructions separately from source-document
content. AI/DECISIONS.md records accepted, corrected and rejected suggestions.
