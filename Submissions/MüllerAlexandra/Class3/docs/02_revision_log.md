# Revision log

## Measurement correction before final results

The first complete experiment matrix ran timing and `tracemalloc` together. A
comparison with the lecturer's `Class3/class3_evidence.py` showed that this
inflates elapsed time. The harness was corrected to use an untraced timing trial
and a separate traced memory trial. The two trials' compact results are required
to agree. The initial matrix is not retained as a formal result; the corrected
matrix replaces it.
