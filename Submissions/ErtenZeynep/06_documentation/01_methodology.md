# Measurement Methodology

## Dataset Matrix

The mandatory matrix contains 18 deterministic configurations: three array
sizes (`1,000`, `10,000`, and `100,000`), two complete query-batch sizes (`1`
and `100`), and three scenarios (`all_present`, `all_absent`, and `mixed`). All
methods and versions receive arrays and ordered queries with identical SHA-256
fingerprints.

## Runtime Measurement

Runtime is measured with `time.perf_counter()` in seconds. Synthetic-data
generation, tests, printing, memory tracing, profiling, dashboard rendering,
and AI calls are excluded. Each configuration and method receives one warm-up
and five measured repetitions. Method order rotates across repetitions. The
reported summary is the median.

Preparation and the complete query batch are measured separately. Sorting and
hash-set construction are preparation. Linear Search has no material
preparation. Very short operations are called multiple times inside a timed
region and divided by the number of calls. A raw total is defined as the sum of
the normalized preparation and complete query-batch measurements.

## Memory Measurement

Memory measurement is separate from timing. Input data is constructed before a
fresh `tracemalloc` session. Preparation and one complete query batch run while
tracing, and both the prepared structure and returned output remain alive when
current and peak traced bytes are read. The tracing session is then stopped.

These figures represent traced Python allocations after tracing begins. They do
not include every native allocation, process RSS, or exact mathematical
auxiliary-space complexity.
