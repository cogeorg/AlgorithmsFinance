# Hand trace: N=2 American put
Hand arithmetic with Codex assistance, 27 November 2026. No production code used to derive these fractions.
S0=K=100, u=6/5, d=4/5, R=21/20; q=(21/20-4/5)/(6/5-4/5)=5/8.

| t,j | Stock | Intrinsic | Continuation | American V | Exercise? |
|---|---:|---:|---:|---:|---|
| 2,0 | 64 | 36 | expiry | 36 | yes |
| 2,1 | 96 | 4 | expiry | 4 | yes |
| 2,2 | 144 | 0 | expiry | 0 | no |
| 1,0 | 80 | 20 | ((5/8)*4+(3/8)*36)/(21/20)=320/21 | 20 | yes |
| 1,1 | 120 | 0 | ((5/8)*0+(3/8)*4)/(21/20)=10/7 | 10/7 | no |
| 0,0 | 100 | 0 | ((5/8)*(10/7)+(3/8)*20)/(21/20)=1175/147 | 1175/147 | no |

Boundary: [none,80,96]. American=1175/147≈7.9931972789, rounds to 7.9932.
European replaces t=1 down V=20 by 320/21, so root=((5/8)*(10/7)+(3/8)*(320/21))/(21/20)=925/147≈6.2925170068, rounds to 6.2925.

Array order: start V=[36,4,0]. At t=1, j=0 reads old V[0],V[1], then writes V[0]=20; j=1 reads old V[1],V[2], then writes V[1]=10/7. At t=0 only j=0 reads the new layer and writes 1175/147. Increasing j preserves each old upper neighbor until it is read. Stock prices are stably reconstructed per layer rather than propagated from an underflow-prone edge.
