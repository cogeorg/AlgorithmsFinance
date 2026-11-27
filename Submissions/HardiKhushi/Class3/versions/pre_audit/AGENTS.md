# Class 3 working agreement

- The user explicitly requires all work for this lab, including progress and
  AI-use notes, to stay in `Submissions/HardiKhushi/Class3/`. Do not change the
  parent submission documentation, course data, other labs or other submissions.
- Teach step by step and briefly explain each completed stage and its result.
- The user approved the first described implementation/check batch with
  "Okay lets go". This batch implements and checks the small pricing algorithm;
  it does not authorize large market-data benchmarks or publication.
- Ask before committing. No commit is authorized by the PDF or these notes.
- The user next approved data loading/calibration with "Lets go ahead into the
  next step". This batch may read the Bitcoin CSV, save its calibration report
  locally and run relevant checks. A large pricing benchmark is a later stage.
- Follow the parent's provenance and results-preservation rules. Keep lab
  progress in this directory's `PROGRESS.md` and AI notes in `AI_USAGE.md` to
  respect the user's latest location requirement.
- The user then approved "Okay lets go ahead" after the proposal to add the
  boundary, price one year of Bitcoin and compare the observed path. This
  batch includes relevant correctness checks and separate runtime/peak-memory
  calls for that one-asset, one-year case. Larger horizons/batches remain later
  stages. Preserve the earlier pricing version and saved calibration report.
- Preserve unrelated user edits and Git merge state. The earlier empty
  `american_put.py/` directory is no longer present; this batch did not remove
  it. The implementation file is `price_american_put.py`.
- The user approved the full-file Bitcoin stage with "Okay let us move on to
  doing the next step". This includes range/gap checks, a validated NumPy
  rolling-row engine, a one-year bridge comparison and the full-file Bitcoin
  run with separate timing/memory calls. Keep original results/source history;
  the 40-asset batch remains the next stage. Ask before committing.
