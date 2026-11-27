"""One isolated growth cell; parent enforces the whole-cell 60 s limit."""
import argparse
import json
import math
from pathlib import Path
from bench.harness import time_repeats
from amput import METHODS


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--version'); ap.add_argument('--n',type=int); ap.add_argument('--out',type=Path)
    a=ap.parse_args()
    method=METHODS[('baseline','A') if a.version=='A' else ('fast','B')]
    u=math.exp(.01); args=(100,100,u,1/u,math.exp(.04/8760),a.n)
    def check(result):
        assert math.isfinite(result.value) and 0<=result.value<=100
    raw=time_repeats(lambda:None,lambda _:method(*args),warmup=1,repeats=5,check=check)
    a.out.write_text(json.dumps(raw,indent=2)+'\n',encoding='utf-8')
    print(f'{a.version} N={a.n}: median={raw["run_median_s"]:.6f}s')


if __name__=='__main__':
    main()
