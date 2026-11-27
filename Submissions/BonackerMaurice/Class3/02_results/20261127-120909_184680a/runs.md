| run | version | N | assets | workers | wall_s | traced_peak_mb | process_peak_mb | status |
|---|---|---|---|---|---|---|---|---|
| btc-1y | vectorised | 8760 | 1 | 1 | 0.242 | 0.5 | 1.5 | ok |
| btc-1y | reference | 8760 | 1 | 1 | 5.959 |  | 0.7 | ok |
| btc-5y | vectorised | 43822 | 1 | 1 | 8.198 | 2.7 | 4.5 | ok |
| curve | reference | 1000 | 1 | 1 | 0.075 | 0.1 | 0.1 | ok |
| curve | vectorised | 1000 | 1 | 1 | 0.009 | 0.1 | 1.9 | ok |
| curve | fulltree | 1000 | 1 | 1 | 0.015 | 4.0 | 6.2 | ok |
| curve | reference | 2000 | 1 | 1 | 0.280 | 0.2 | 0.2 | ok |
| curve | vectorised | 2000 | 1 | 1 | 0.020 | 0.1 | 2.1 | ok |
| curve | fulltree | 2000 | 1 | 1 | 0.041 | 15.6 | 18.2 | ok |
| curve | reference | 5000 | 1 | 1 | 2.081 | 0.4 | 0.5 | ok |
| curve | vectorised | 5000 | 1 | 1 | 0.082 | 0.3 | 1.6 | ok |
| curve | fulltree | 5000 | 1 | 1 | 0.167 | 96.3 | 98.8 | ok |
| curve | reference | 10000 | 1 | 1 | 7.232 |  | 0.9 | ok |
| curve | vectorised | 10000 | 1 | 1 | 0.278 | 0.6 | 2.3 | ok |
| curve | fulltree | 10000 | 1 | 1 | 0.647 | 383.3 | 386.0 | ok |
| curve | reference | 20000 | 1 | 1 | 30.033 |  | 2.0 | ok |
| curve | vectorised | 20000 | 1 | 1 | 1.153 | 1.2 | 3.2 | ok |
| curve | fulltree | 20000 | 1 | 1 | 2.672 | 1529.5 | 1532.3 | ok |
| curve | reference | 43822 | 1 | 1 | 152.418 |  | 4.4 | ok |
| curve | vectorised | 43822 | 1 | 1 | 8.586 | 2.7 | 4.5 | ok |
| curve | fulltree | 43822 | 1 | 1 | 15.949 | 7333.5 | 7337.4 | ok |
| curve | reference | 55000 | 1 | 1 |  |  |  | not run: pure Python too slow beyond the data length |
| curve | vectorised | 55000 | 1 | 1 | 14.718 | 3.4 | 5.3 | ok |
| curve | fulltree | 55000 | 1 | 1 | 23.656 | 11549.3 | 11553.5 | ok |
| curve | reference | 70000 | 1 | 1 |  |  |  | not run: pure Python too slow beyond the data length |
| curve | vectorised | 70000 | 1 | 1 | 26.284 | 4.3 | 6.9 | ok |
| curve | fulltree | 70000 | 1 | 1 |  |  |  | out of memory: tree needs 18.3 GB, 20.9 GB free (not attempted) |
| assets-1y | vectorised | 8760 | 40 | 1 | 21.277 | 0.5 per asset (max) | 45.0 per worker (max); 94.7 total (sampled) | ok; sum of per-asset seconds 19.4 |
| assets-1y | vectorised | 8760 | 40 | 4 | 7.067 | 0.5 per asset (max) | 45.2 per worker (max); 229.0 total (sampled) | ok; sum of per-asset seconds 24.2 |
| assets-1y | vectorised | 8760 | 40 | 8 | 4.432 | 0.5 per asset (max) | 45.1 per worker (max); 404.8 total (sampled) | ok; sum of per-asset seconds 28.0 |
| assets-5y | vectorised | 43822 | 40 | 1 | 288.062 | 2.7 per asset (max) | 54.4 per worker (max); 103.2 total (sampled) | ok; sum of per-asset seconds 286.1 |
| assets-5y | vectorised | 43822 | 40 | 4 | 108.858 | 2.7 per asset (max) | 53.8 per worker (max); 255.6 total (sampled) | ok; sum of per-asset seconds 421.5 |
| assets-5y | vectorised | 43822 | 40 | 8 | 63.712 | 2.7 per asset (max) | 52.6 per worker (max); 453.9 total (sampled) | ok; sum of per-asset seconds 488.2 |
