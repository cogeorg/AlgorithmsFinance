"""Six plausible isolated pricing/boundary faults, checked by named contracts."""
from types import SimpleNamespace
import pytest
import contract
from amput import METHODS


def faulty(mode):
    def run(S0,K,u,d,R,N,*,european=False,observer=None):
        q=(R-d)/(u-d)
        if mode=='wrong_q': q=1-q
        v=[max(K-S0*u**j*d**(N-j),0) for j in range(N+1)]
        boundary=[None]*(N+1)
        if mode!='omit_expiry':
            candidates=[S0*u**j*d**(N-j) for j in range(N+1) if K-S0*u**j*d**(N-j)>0]
            boundary[N]=max(candidates) if candidates else None
        for t in range(N-1,-1,-1):
            candidates=[]
            indices=range(t,-1,-1) if mode=='reverse_update' else range(t+1)
            for j in indices:
                stock=S0*u**j*d**(t-j)
                c=(q*v[j+1]+(1-q)*v[j])/(1 if mode=='no_discount' else R)
                intrinsic=max(K-stock,0)
                v[j]=c if (european or mode=='european_only') else max(intrinsic,c)
                if intrinsic>=c and (intrinsic>0 or mode=='zero_ties'):
                    candidates.append(stock)
            boundary[t]=max(candidates) if candidates else None
        return SimpleNamespace(value=v[0],boundary=boundary)
    return run


@pytest.mark.parametrize('mode,killer',[
    ('wrong_q',contract.check_toy),('no_discount',contract.check_toy),
    ('european_only',contract.check_toy),('reverse_update',contract.check_toy),
    ('zero_ties',contract.check_boundary),('omit_expiry',contract.check_boundary)])
def test_six_mutants_killed(mode,killer):
    for impl in METHODS.values():
        killer(impl)
    with pytest.raises(AssertionError):
        killer(faulty(mode))
