# Predictions (written before the final measurements)

Written by Jiaxin Huang on 21 November 2026, before running the full benchmark.
They are compared with the measured results in REPORT.md.

1. **Version A at 100,000 events:** I expect version A not to finish within the
   30-second limit. It needs about 7 seconds for 10,000 events, and its time grows
   with the square of the number of events, so 10 times more events means about
   100 times more time, roughly 700 seconds.

2. **4 versus 1,000 price levels:** For version A, I expect both to take about the
   same time, because A scans the whole list from the beginning to the end for
   every order, no matter how many price levels there are. For version B, I expect
   4 price levels to be faster, because there are no new price levels, so B does not
   need to add new records to its heap.

3. **Sale of 10 %, 100 % and 200 % of the bids:** I expect the 200 % sale to be
   the slowest, but only slightly slower than the 100 % sale. After all bids are
   filled, the unfilled half still needs some extra work, but not much.

4. **Parsing versus replay:** I expect reading and parsing the input file to take
   longer than version B's replay, because processing one event is very fast.

5. **Latency as the book grows:** I do not expect version B to slow down. With
   100,000 events, I expect the last 10 % of events to be even faster than the
   first 10 %, because B finds the best price with a heap, and as fewer new price
   levels appear, the heap needs less work.
