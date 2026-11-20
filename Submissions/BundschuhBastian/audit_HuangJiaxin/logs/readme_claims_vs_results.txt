README: binary query ~23 ms vs 0.14 ms (~170x). results: 23.23 ms vs 0.140 ms -> 166x
README: linear ~220 ms vs 65 ms (~3.4x). results: 219.5 vs 64.9 -> 3.38x
README: binary_v2 ~7x slower than bisect. results: 7.3x
n=1000 q=1 h=0.5 total: linear_v2 0.022 ms, hash 0.017 ms, binary_v2 0.062 ms
n=10000 q=1 h=0.5 total: linear_v2 0.092 ms, hash 0.241 ms, binary_v2 0.939 ms
n=100000 q=1 h=0.5 total: linear_v2 0.905 ms, hash 3.102 ms, binary_v2 13.150 ms

q=1: hit 0.5 vs hit 0.0 (identical query, see 02_hit_rate.txt)
  linear_v2 n=1000: hit0.5 21.82 us, hit0.0 9.60 us, ratio 2.27
  linear_v2 n=100000: hit0.5 905.15 us, hit0.0 930.29 us, ratio 0.97
  binary_v2 n=1000: hit0.5 1.10 us, hit0.0 0.93 us, ratio 1.17
  binary_v2 n=100000: hit0.5 1.50 us, hit0.0 1.45 us, ratio 1.03
  hash n=1000: hit0.5 0.18 us, hit0.0 0.33 us, ratio 0.56
  hash n=100000: hit0.5 0.10 us, hit0.0 0.25 us, ratio 0.40

breakeven_points.csv:
    method      n  breakeven_q
binary_v2   1000     7.445123
     hash   1000     1.627927
binary_v2  10000    13.606062
     hash  10000     3.457183
binary_v2 100000    19.185204
     hash 100000     4.531556
   method      n  q  hit_rate  prepare_median_s  query_median_s  total_median_s
linear_v2 100000  1       0.5      4.211803e-08    8.827360e-04        0.000883
binary_v2 100000  1       0.5      1.321383e-02    1.448702e-06        0.013215
     hash 100000  1       0.5      3.126166e-03    9.992706e-08        0.003126

memory peak KiB n=100000:
 method  binary_v1  binary_v2  bisect_ref    hash  linear_v1  linear_v2
q                                                                     
1          1562.6     1171.8      1171.8  6144.3        0.1        0.1
100        1563.5     1171.8      1171.8  6144.3        1.0        0.9

max |total - (prepare+query)| in summary: 1.7666999610900513e-05
