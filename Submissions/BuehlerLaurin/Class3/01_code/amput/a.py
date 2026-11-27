"""A: transparent two-array induction; stable S reconstructed each layer.

The stock construction deliberately replaces the slides' fragile left-edge
multiplication/division, while preserving the increasing-j V recurrence.
"""
import math
from .common import Result, validate, LOG_MAX, LOG_MIN


def stock_layer(S0,u,d,t):
    lu,ld,log0=math.log(u),math.log(d),math.log(S0)
    reciprocal=d==1/u
    layer=[]
    for j in range(t+1):
        offset=(2*j-t)*lu if reciprocal else j*lu+(t-j)*ld
        z=log0+offset
        layer.append(S0 if offset==0 else (math.inf if z>LOG_MAX else (0.0 if z<LOG_MIN else (S0*math.exp(offset) if LOG_MIN<=offset<=LOG_MAX else math.exp(z)))))
    return layer


def price_with_boundary(S0,K,u,d,R,N,*,european=False,observer=None):
    validate(S0,K,u,d,R,N)
    S=stock_layer(S0,u,d,N)
    V=[max(K-price,0.0) for price in S]
    boundary=[None]*(N+1)
    near=[False]*(N+1)
    if not european:
        for j in range(N+1):
            if K-S[j]>0 and (boundary[N] is None or S[j]>boundary[N]):
                boundary[N]=S[j]
    if observer is not None:
        observer(N,S[:],V[:],None)
    if N==0:
        return Result(float(V[0]),boundary,near)
    q=(R-d)/(u-d)
    lu,ld,log0=math.log(u),math.log(d),math.log(S0)
    reciprocal=d==1/u
    for t in range(N-1,-1,-1):
        best=None
        for j in range(t+1):
            offset=(2*j-t)*lu if reciprocal else j*lu+(t-j)*ld
            z=log0+offset
            if offset==0:
                S[j]=S0
            elif z>LOG_MAX:
                S[j]=math.inf
            elif z<LOG_MIN:
                S[j]=0.0
            else:
                S[j]=S0*math.exp(offset) if LOG_MIN<=offset<=LOG_MAX else math.exp(z)
            # Affine form is algebraically identical, and preserves exact
            # ties such as 75 + (1/3)*(0-75) == 50 in binary64.
            continuation=(V[j]+q*(V[j+1]-V[j]))/R
            intrinsic=max(K-S[j],0.0)
            V[j]=continuation if european else max(intrinsic,continuation)
            if not european and intrinsic>0:
                if abs(intrinsic-continuation)<=1e-12*K:
                    near[t]=True
                if intrinsic>=continuation and (best is None or S[j]>best):
                    best=S[j]
        boundary[t]=best
        if observer is not None:
            observer(t,S[:t+1],V[:t+1],None)
    return Result(float(V[0]),boundary,near)
