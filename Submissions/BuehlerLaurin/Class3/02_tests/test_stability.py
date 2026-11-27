import math
import pytest
from amput.a import stock_layer


def test_high_s_large_n_stable_central_nodes():
    n=43800; s=.03; u=math.exp(s); d=1/u
    stock=stock_layer(100,u,d,n)
    assert stock[0] == 0 and math.isinf(stock[-1])
    assert stock[n//2] == 100
    for j in [n//2-100,n//2-1,n//2+1,n//2+100]:
        assert stock[j] == pytest.approx(100*math.exp((2*j-n)*math.log(u)),rel=1e-12)


def test_high_s_pricing_finite(impl):
    u=math.exp(.8)
    result=impl(100,100,u,1/u,1.001,1000)
    assert math.isfinite(result.value) and 0 <= result.value <= 100
    assert result.boundary[0] is None
