# Independent checks by Claude (chat)

These scripts were written by Claude (chat), the reviewing assistant, **separately from the engine code** (they import only the public registry `lob.METHODS`). They back three claims in `00_docs/REPORT.md` and `00_docs/FINAL_SELECTION.md` that were first run outside the repository and are now reproduced at commit `1b7adca`.

| Claim | Script | Log | Result |
|---|---|---|---|
| B3r (and B3r_fast) agree with an independent reference on the professor's five 10k streams (50,000 events) and 135,000 stress events in three regimes, compared after every event (result, snapshot, best bid/ask) | `check_b3r_vs_reference.py` + `reference_oracle.py` | `log_b3r_vs_reference.txt` | 0 differences |
| The B3r_fast fast validator returns exactly what the shared validator returns | `check_validator_and_speed.py` | `log_validator_equivalence.txt` | 300,000 random events, 0 differences (the speed lines are a sanity check, not a benchmark) |
| About one third of B3r's per-event time is input validation | `profile_b3r.py` | `log_profile_b3r.txt` | validation 0.77-0.88 us of 1.9-3.2 us per event (27-41 %); cProfile: `validate` 0.280 s cumulative of 0.610 s |

`reference_oracle.py` is a deliberately simple order book (one list, full scans, the SPEC validation order); it shares no code with `01_code/`.

Run from this folder, passing the Assignment1 folder: `python check_b3r_vs_reference.py ../..` (and likewise for the other two). Environment of the recorded run: `env.txt` (Linux, CPython 3.13); absolute times differ from the Windows benchmark machine, the ratios and the zero-difference results are what matter.
