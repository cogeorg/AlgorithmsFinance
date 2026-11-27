"""Registry: METHODS = {(name, version): callable}.

Register a stub (raise NotImplementedError) before writing tests, so the red
run fails for the right reason instead of collecting nothing."""
from .a import price_with_boundary

from .b import price_with_boundary as vectorized

METHODS = {('baseline', 'A'): price_with_boundary, ('fast', 'B'): vectorized}


def PriceAmericanPut(S0, K, u, d, R, N):
    return price_with_boundary(S0, K, u, d, R, N).value
