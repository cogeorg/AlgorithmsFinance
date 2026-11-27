"""Shared validation and output types; no NumPy dependency for baseline A."""
import math
import sys
from dataclasses import dataclass
from numbers import Real, Integral

LOG_MAX = math.log(sys.float_info.max)
LOG_MIN = math.log(math.ulp(0.0))


@dataclass
class Result:
    value: float
    boundary: list
    near_ties: list

    def __iter__(self):
        yield self.value
        yield self.boundary


def validate(S0,K,u,d,R,N):
    values=(S0,K,u,d,R)
    if any(isinstance(x,bool) or not isinstance(x,Real) or not math.isfinite(x) for x in values):
        raise ValueError('All price/factor inputs must be finite real numbers')
    if isinstance(N,bool) or not isinstance(N,Integral) or N<0:
        raise ValueError('N must be a nonnegative integer')
    if S0<=0 or K<0 or not 0<d<R<u:
        raise ValueError('Require S0>0, K>=0 and 0<d<R<u')
