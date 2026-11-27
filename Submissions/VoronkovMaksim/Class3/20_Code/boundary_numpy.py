"""Vectorized two-row exercise boundary, without a full binomial tree."""
import math
import numpy as np
from price_american_put import PriceAmericanPut


def boundary_numpy(S0,K,u,d,R,N):
    if type(N) is not int or N < 0:
        raise ValueError('N must be a nonnegative integer')
    PriceAmericanPut(S0,K,u,d,R,0)
    q=(R-d)/(u-d)
    stock=np.empty(N+1,dtype=float); stock[0]=S0
    for _ in range(N): stock[0]*=d
    if stock[0]==0 or not math.isfinite(stock[0]):
        raise ValueError('Stock prices exceed floating-point range')
    for j in range(1,N+1):
        stock[j]=stock[j-1]*(u/d)
        if not math.isfinite(stock[j]): raise ValueError('Stock prices exceed floating-point range')
    values=np.maximum(K-stock,0.0)
    boundaries=np.full(N+1,np.nan)
    mask=values>0
    if mask.any(): boundaries[N]=stock[np.flatnonzero(mask)[-1]]
    for t in range(N-1,-1,-1):
        current=stock[:t+1]
        current/=d
        exercise=np.maximum(K-current,0.0)
        continuation=(q*values[1:t+2]+(1-q)*values[:t+1])/R
        indices=np.flatnonzero((exercise>0)&(exercise>=continuation))
        if indices.size: boundaries[t]=current[indices[-1]]
        values[:t+1]=np.maximum(exercise,continuation)
    return float(values[0]),boundaries
