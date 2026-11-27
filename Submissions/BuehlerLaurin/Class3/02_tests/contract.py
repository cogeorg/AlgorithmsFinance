"""Named contract checks: check_<rule>(impl) -> None, raise AssertionError on violation.

Used by 02_tests/test_contract.py (real versions) and 02_tests/test_mutants.py (mutants).
Imported as `import contract` (02_tests is on pythonpath, not a package).
"""
import math
from fractions import Fraction as F
import pytest
from oracle import exact

TOY = (100, 100, 1.2, 0.8, 1.05, 2)


def check_toy(impl):
    v = impl(*TOY).value
    assert abs(v-1175/147) <= 1e-12
    assert round(v,4) == 7.9932
    e = impl(*TOY, european=True).value
    assert abs(e-925/147) <= 1e-12
    assert round(e,4) == 6.2925


def check_boundary(impl):
    b = impl(*TOY).boundary
    assert len(b) == 3 and b[0] is None
    assert b[1] == pytest.approx(80, abs=1e-12)
    assert b[2] == pytest.approx(96, abs=1e-12)
    assert impl(100, 0, 1.2, .8, 1.05, 3).boundary == [None]*4


def check_tie(impl):
    # Entire one-period tree is ITM. At R=1 intrinsic=continuation exactly.
    result = impl(50,100,2,.5,1,1)
    assert result.boundary[0] == 50
    assert result.value == pytest.approx(50)
    assert impl(100,100,2,.5,1,1).boundary[0] is None


def check_n_zero(impl):
    result = impl(80,100,1.2,.8,1.05,0)
    assert result.value == 20 and result.boundary == [80]
    assert impl(100,100,1.2,.8,1.05,0).boundary == [None]


def check_exact_oracle(impl):
    for n in range(13):
        for rate in [F(21,20), F(19,20)]:
            args = (F(100),F(103),F(6,5),F(4,5),rate,n)
            v,b = exact(*args)
            actual = impl(*(float(x) for x in args[:-1]), n)
            assert abs(actual.value-float(v)) <= 1e-10
            for got,want in zip(actual.boundary,b):
                if want is None:
                    assert got is None
                else:
                    assert got == pytest.approx(float(want),abs=1e-10)


def check_input_not_mutated(impl):
    args = list(TOY)
    before = args.copy()
    first = impl(*args)
    assert args == before
    assert impl(*args).value == first.value


def check_validation(impl):
    bad = [(0,100,1.2,.8,1.05,2),(-1,100,1.2,.8,1.05,2),
           (100,-1,1.2,.8,1.05,2),(100,100,1.2,-.8,1.05,2),
           (100,100,1.2,.8,1.2,2),(100,100,1.2,.8,.8,2),
           (100,100,1.2,.8,1.05,-1),(100,100,1.2,.8,1.05,1.5),
           (100,100,1.2,.8,1.05,True)]
    for i in range(5):
        for nonfinite in [math.nan,math.inf,-math.inf]:
            args = list(TOY); args[i] = nonfinite; bad.append(args)
    for args in bad:
        with pytest.raises(ValueError):
            impl(*args)


def check_layer_invariants(impl):
    def observe(t, stock, values, continuation):
        assert len(stock) == len(values) == t+1
        for s,v in zip(stock,values):
            assert v >= max(100-s,0)-1e-10
            assert -1e-10 <= v <= 100+1e-10
    for n in [1,2,8,21]:
        result = impl(100,100,1.2,.8,1.05,n,observer=observe)
        assert result.value >= impl(100,100,1.2,.8,1.05,n,european=True).value-1e-10
        assert all(b is None or 0 <= b < 100 for b in result.boundary)
