import math
import unittest
from fractions import Fraction as F
import numpy as np
from american_put import PriceAmericanPut, calibrate, first_crossing, _kernel


class LabTests(unittest.TestCase):
    def test_slide_example(self):
        price, b = PriceAmericanPut(100,100,1.2,.8,1.05,2)
        self.assertAlmostEqual(price, float(F(1175,147)), places=11)
        european = (36*.375**2 + 4*2*.625*.375)/(1.05**2)
        self.assertAlmostEqual(european, float(F(925,147)), places=11)
        self.assertGreater(price,european)
        self.assertTrue(math.isnan(b[0]))
        np.testing.assert_allclose(b[1:],[80,96],rtol=1e-14)

    def test_independent_fraction_tree(self):
        # Full exact-rational tree, independent of the rolling/log algorithm.
        u,d,R = F(6,5),F(4,5),F(21,20)
        q=(R-d)/(u-d)
        def exact(s,n):
            if n == 0: return max(F(100)-s,0)
            return max(F(100)-s,((1-q)*exact(s*d,n-1)+q*exact(s*u,n-1))/R)
        for n in range(7):
            self.assertAlmostEqual(PriceAmericanPut(97,100,float(u),float(d),float(R),n)[0],float(exact(F(97),n)),places=10)

    def test_reference_and_compiled(self):
        args=(103.,110.,math.log(1.07),math.log(.94),math.log(1.001),35)
        a,b=_kernel(*args)
        c,d=_kernel.py_func(*args)
        self.assertAlmostEqual(a,c,places=11)
        np.testing.assert_allclose(b,d,equal_nan=True)

    def test_terminal_and_zero_strike(self):
        self.assertAlmostEqual(PriceAmericanPut(80,100,1.2,.8,1.05,0)[0],20)
        p,b=PriceAmericanPut(100,0,1.2,.8,1.05,10)
        self.assertEqual(p,0)
        self.assertTrue(np.isnan(b).all())

    def test_invalid(self):
        for args in [(100,100,1.2,.8,1.3,2),(0,100,1.2,.8,1.05,2),(100,100,1.2,.8,1.05,-1),(100,100,1.2,.8,1.05,True)]:
            with self.assertRaises(ValueError): PriceAmericanPut(*args)

    def test_large_tree_no_overflow(self):
        p,b=PriceAmericanPut(100,100,math.exp(.8),math.exp(-.8),1.001,2000)
        self.assertTrue(math.isfinite(p))
        self.assertTrue(0 <= p <= 100)
        self.assertTrue(np.all(b[np.isfinite(b)] < 100))

    def test_calibration_and_no_mutation(self):
        times=np.array([0,3600,10800,14400])
        prices=np.array([100.,103.,99.,102.])
        saved=prices.copy()
        p=calibrate(times,prices)
        self.assertAlmostEqual(p['sigma'],np.std(np.diff(np.log(prices)),ddof=1))
        self.assertEqual(p['missing_hours'],1)
        self.assertAlmostEqual(p['R'],math.exp(.04*4/(365*24*3)))
        np.testing.assert_array_equal(saved,prices)

    def test_crossing(self):
        self.assertEqual(first_crossing([100,90,70],[np.nan,91,80],100)['index'],1)
        self.assertIsNone(first_crossing([100,90],[np.nan,80],100))

if __name__ == '__main__': unittest.main(verbosity=2)
