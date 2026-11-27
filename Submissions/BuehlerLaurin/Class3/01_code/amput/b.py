"""B: NumPy layer operations; same induction, stable stocks and exercise rule."""
import math
import numpy as np
from .common import Result,validate,LOG_MAX,LOG_MIN


def stock_layer(S0,u,d,t):
    j=np.arange(t+1,dtype=np.float64)
    lu,ld=math.log(u),math.log(d)
    offset=(2*j-t)*lu if d==1/u else j*lu+(t-j)*ld
    return _from_offsets(S0,offset)


def _from_offsets(S0,offset):
    z=math.log(S0)+offset
    # Use S0*exp(offset) where both intermediate and result are representable.
    ordinary=(offset>=LOG_MIN)&(offset<=LOG_MAX)
    with np.errstate(over='ignore',under='ignore'):
        result=np.exp(np.clip(offset,LOG_MIN,LOG_MAX))*S0
        fallback=np.exp(np.clip(z,LOG_MIN,LOG_MAX))
    result=np.where(ordinary,result,fallback)
    result[z<LOG_MIN]=0.0
    result[z>LOG_MAX]=np.inf
    result[offset==0]=S0
    return result


def price_with_boundary(S0,K,u,d,R,N,*,european=False,observer=None):
    validate(S0,K,u,d,R,N)
    reciprocal=d==1/u
    lu,ld=math.log(u),math.log(d)
    # CRR node offsets are integer multiples of log(u). There are only
    # 2N+1 distinct prices, shared across all layers, not an N² tree.
    lattice=_from_offsets(S0,np.arange(-N,N+1,dtype=np.float64)*lu) if reciprocal else None
    payoffs=np.maximum(K-lattice,0.0) if reciprocal else None
    S=lattice[::2] if reciprocal else stock_layer(S0,u,d,N)
    V=np.maximum(K-S,0.0)
    boundary=[None]*(N+1); near=[False]*(N+1)
    if not european:
        candidate=float(np.max(S,where=S<K,initial=-np.inf))
        boundary[N]=None if candidate==-np.inf else candidate
    if observer is not None:
        observer(N,S.copy(),V.copy(),None)
    if N==0:
        return Result(float(V[0]),boundary,near)
    q=(R-d)/(u-d)
    log0=math.log(S0)
    low=N*min(lu,ld,0); high=N*max(lu,ld,0)
    safe=(LOG_MIN<=low and high<=LOG_MAX and LOG_MIN<=log0+low and log0+high<=LOG_MAX)
    indices=np.arange(N+1,dtype=np.float64)
    C=np.empty(N+1); H=np.empty(N+1)
    for t in range(N-1,-1,-1):
        m=t+1
        if reciprocal:
            S=lattice[N-t:N+t+1:2]
            H=payoffs[N-t:N+t+1:2]
        elif safe:
            S[:m]=indices[:m]*lu+(t-indices[:m])*ld
            np.exp(S[:m],out=S[:m]); S[:m]*=S0
        else:
            S[:m]=stock_layer(S0,u,d,t)
        np.subtract(V[1:m+1],V[:m],out=C[:m]); C[:m]*=q; C[:m]+=V[:m]; C[:m]/=R
        if not reciprocal:
            np.subtract(K,S[:m],out=H[:m]); np.maximum(H[:m],0,out=H[:m])
        if european:
            V[:m]=C[:m]
        else:
            positive=H[:m]>0
            eligible=positive & (H[:m]>=C[:m])
            best=float(np.max(S[:m],where=eligible,initial=-np.inf))
            boundary[t]=None if best==-np.inf else best
            near[t]=bool(np.any(positive & (np.abs(H[:m]-C[:m])<=1e-12*K)))
            np.maximum(H[:m],C[:m],out=V[:m])
        if observer is not None:
            observer(t,S[:m].copy(),V[:m].copy(),C[:m].copy())
    return Result(float(V[0]),boundary,near)
