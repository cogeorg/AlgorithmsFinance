import math
from hypothesis import given, settings, strategies as st
from amput.a import price_with_boundary as A
from amput.b import price_with_boundary as B, stock_layer


def compare(a,b,K):
    assert abs(a.value-b.value)<=1e-9*max(1,K)
    assert len(a.boundary)==len(b.boundary)
    exceptions=[]
    for t,(x,y) in enumerate(zip(a.boundary,b.boundary)):
        if x is None and y is None:
            continue
        if x is not None and y is not None and abs(x-y)<=1e-10*max(1,K):
            continue
        assert a.near_ties[t] or b.near_ties[t], (t,x,y)
        exceptions.append(dict(t=t,A=x,B=y))
    return exceptions


@settings(max_examples=200,deadline=None,derandomize=True)
@given(n=st.integers(0,48),spot=st.integers(1,1000),strike=st.integers(0,1500),
       sigma=st.integers(1,80),rate=st.integers(0,10))
def test_hypothesis_A_B(n,spot,strike,sigma,rate):
    u=math.exp(sigma/100)
    R=math.exp(rate/1000)
    if R>=u: R=1
    compare(A(spot,strike,u,1/u,R,n),B(spot,strike,u,1/u,R,n),strike)


def test_B_large_layer():
    u=math.exp(.03)
    stock=stock_layer(100,u,1/u,43800)
    assert stock[0]==0 and math.isinf(stock[-1]) and stock[21900]==100
