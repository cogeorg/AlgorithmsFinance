"""Report exercise contiguity; never use it to prune or reject a result."""
import json
import math
import random
import sys
from pathlib import Path


def main():
    root=Path.cwd(); sys.path.insert(0,str(root/'01_code'))
    from amput import METHODS
    rng=random.Random(42); observations=[]
    for case in range(30):
        n=rng.randint(1,32); S0=rng.randint(20,200); K=rng.randint(0,240)
        u=math.exp(rng.uniform(.01,.3)); args=(S0,K,u,1/u,1.0001,n)
        for (_,version),method in METHODS.items():
            maxima={}; islands={}
            def observe(t,stocks,values,continuation):
                # With V=max(intrinsic,c), positive intrinsic==V identifies
                # exactly the qualifying exercise nodes, including ties.
                flags=[K-s>0 and v==max(K-s,0) for s,v in zip(stocks,values)]
                candidates=[float(s) for s,flag in zip(stocks,flags) if flag]
                maxima[t]=max(candidates) if candidates else None
                runs=sum(flag and (i==0 or not flags[i-1]) for i,flag in enumerate(flags))
                if runs>1: islands[t]=runs
            result=method(*args,observer=observe)
            assert result.boundary==[maxima[t] for t in range(n+1)]
            observations.append(dict(case=case,version=version,N=n,noncontiguous_layers=islands))
    target=root/'00_docs/CONTIGUITY_DIAGNOSTIC.json'
    target.write_text(json.dumps(observations,indent=2)+'\n',encoding='utf-8')
    count=sum(len(r['noncontiguous_layers']) for r in observations)
    print(f'CONTIGUITY DIAGNOSTIC: {len(observations)} version/case runs; {count} noncontiguous layers (diagnostic only)')
    print('Every returned boundary equals the maximum of all qualifying nodes; no contiguity assertion or pruning used.')


if __name__=='__main__':
    main()
