# Graph restoration and ten-second budget

The user clarified that the reported "11 seconds" was a displayed dashboard
value. The previous interface used milliseconds or microseconds. 11 ms is
0.011 seconds; 11 microseconds is 0.000011 seconds.

## Changes

- Restore the earlier line-graph layout, including original/revised curves,
  all timing components, duplicate policies, versions and axis-scale controls.
- Add an explicit seconds/milliseconds selector. Seconds are the default.
  The plot, tooltips and timing table convert together; stored raw values keep
  their original millisecond units. Nine decimal places in the seconds table
  retain sub-microsecond values instead of rounding them to zero.
- Show the largest saved raw per-batch total and its comparison with ten
  seconds. This budget concerns a complete search batch including preparation,
  not the time needed to run a whole repeated benchmark suite.
- `check_speed.py` checks all 900 saved raw totals and five freshly executed
  optimized searches with 100,000 IDs and 100 queries, including index build.
  It writes source/input hashes, raw seconds and the explicit budget to
  `results/speed_budget.json`. Saved-result verification checks the report.

## Results and provenance

All 900 saved raw totals are below ten seconds; the maximum is approximately
2.028763 seconds. The largest stored median is approximately 0.869965 seconds.
Fresh optimized runs are recorded in `speed_budget.json`; the target is checked
on actual values rather than by changing the graph scale or hiding records.

No timed search implementation or numerical benchmark value was changed.
The exact template from measurement time is preserved in
`template_before_graph_restore.html`. `metadata.source_paths` records that
snapshot; `presentation_sha256` identifies the restored display. New full
algorithm timings are not claimed for this presentation change.

Validation: 21 unit tests, saved data/source/CSV verification, a byte-identical
HTML rebuild, 360 graph-filter/unit combinations and 45 preserved Astra views.
The browser checks confirm both seconds and milliseconds agree with raw data
and report no JavaScript exceptions. The restored graph layout was inspected
from a Chrome screenshot. Fresh-checkout validation is recorded in
`graph_restore_validation.json` before push.
