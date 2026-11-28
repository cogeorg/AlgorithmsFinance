# Tests-first plan

The suite is written before implementation and uses an independent recursive
exercise-tree oracle for small examples.

Coverage:

- exact two-period value `1175/147`, displayed as `7.9932`;
- two-period boundary `(None, 80, 96)`;
- exhaustive small valid trees against the independent oracle;
- nonnegative value and boundary invariants;
- invalid numeric inputs, including `bool`, nonfinite values, and no-arbitrage
  violations;
- strict positive-close and UTC timestamp validation;
- gap reporting without interpolation;
- exact 8,761-row Bitcoin one-year window;
- calibration formulas and `0 < q < 1`;
- first observed boundary crossing and `never` behavior;
- Bitcoin one-year acceptance invariants.
- deterministic multi-process batch agreement and full-history preparation;
- compiled-kernel equivalence to the Python reference;
- saved-results-only reporting, four required scenarios, and 40 joined values.

The initial command, exit status, and failure reason are saved in
`results/tests_before_implementation.txt` before implementation is added.
