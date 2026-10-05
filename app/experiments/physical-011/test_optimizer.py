import unittest
import numpy as np
from optimizer import pv, cvar, evaluate, solve, audit, shuffled, PRICE
from run import bank_for
import pandas as pd


class PhysicalFixtures(unittest.TestCase):
    def test_fractional_negative_tied_tail(self):
        self.assertAlmostEqual(cvar(np.arange(64.)), (sum(range(58,64))+.4*57)/6.4)
        self.assertEqual(cvar(np.full(64,-3.)), -3.)
        values=np.r_[np.full(58,-10.),np.full(6,-2.)]
        self.assertAlmostEqual(cvar(values),(-12.-4.)/6.4)
        with self.assertRaises(ValueError):cvar([np.nan])

    def test_solar_conversion_grid_and_allocation(self):
        self.assertEqual(pv(np.full(24,-1.)).sum(),0.)
        self.assertEqual(pv(np.full(24,2000.)).max(),1700.)
        solar=np.zeros(24);solar[10:17]=1700.
        q,record=solve(solar)
        self.assertLess(float(evaluate(q,solar)['cost']),1e-5)
        self.assertLess(float(evaluate(q,solar)['grid_energy']),1e-5)
        self.assertAlmostEqual(q.sum(),2880.,places=6)
        self.assertAlmostEqual(record['water']['total_energy_kwh'],9792.,places=5)
        self.assertGreaterEqual(record['water']['minimum_stock'],800.-1e-6)
        again,_=solve(solar)
        np.testing.assert_array_equal(q,again)

    def test_zero_pv_keeps_q0_and_no_negative_grid(self):
        q0,_=solve(np.zeros(24))
        scenario=np.zeros((2,64,24))
        q,record=solve(scenario,q0)
        np.testing.assert_array_equal(q,q0)
        self.assertTrue(record['anchor_returned'])
        self.assertAlmostEqual(float(evaluate(q,np.zeros(24))['grid_energy']),9792.,places=5)
        self.assertEqual(float(evaluate(q,np.full(24,1700.))['grid_energy']),0.)

    def test_permutations_preserve_marginals_and_expected_cost(self):
        rng=np.random.default_rng(20261004)
        original=rng.uniform(-200,1000,(2,64,24))
        permutations=np.stack([rng.permutation(64) for _ in range(24)])
        changed=shuffled(original,permutations)
        np.testing.assert_array_equal(np.sort(original,axis=1),np.sort(changed,axis=1))
        plan=np.arange(24)*10.
        a=evaluate(plan,pv(original))['cost'].mean(axis=1)
        b=evaluate(plan,pv(changed))['cost'].mean(axis=1)
        np.testing.assert_allclose(a,b,rtol=0,atol=1e-10)
        with self.assertRaises(ValueError):shuffled(original,np.zeros((24,64),dtype=int))

    def test_identical_marginals_different_daily_tail(self):
        solar=np.zeros((2,24));solar[1,:2]=1700.
        other=solar.copy();other[:,1]=other[::-1,1]
        q=np.zeros(24);q[:2]=500.
        a=evaluate(q,solar)['cost'];b=evaluate(q,other)['cost']
        self.assertEqual(a.mean(),b.mean())
        self.assertGreater(cvar(a),cvar(b))

    def test_negative_regret_lp_and_anchor_floor(self):
        flat=np.full(24,120.)
        scenarios=np.zeros((2,64,24))
        q,record=solve(scenarios,flat)
        self.assertLess(record['primary_optimum'],-1.)
        independent=float(evaluate(q,np.zeros(24))['cost']-evaluate(flat,np.zeros(24))['cost'])
        self.assertAlmostEqual(record['final_direct_objective'],independent,places=8)
        q0,_=solve(np.zeros(24))
        retained,guard=solve(scenarios,q0)
        np.testing.assert_array_equal(retained,q0)
        self.assertFalse(guard['primary_cap_applies'])
        self.assertLessEqual(guard['final_optimum_gap'],guard['action_floor_eur']+1e-9)

    def test_bank_is_complete_paired_and_strictly_past(self):
        target=pd.date_range('2024-01-01',periods=70*24,freq='h')
        nwp=np.zeros(len(target));weather=np.ones(len(target));satellite=np.full(len(target),2.)
        satellite[4*24+3]=np.nan
        cutoff=pd.Timestamp('2024-03-10')
        residual,positions,ledger=bank_for(target,nwp,weather,satellite,cutoff)
        self.assertEqual(residual.shape,(2,64,24))
        self.assertTrue((target[positions.reshape(-1)]<cutoff).all())
        self.assertFalse(np.isin(4*24+3,positions))
        np.testing.assert_array_equal(residual[0],np.ones((64,24)))
        np.testing.assert_array_equal(residual[1],np.full((64,24),2.))
        with self.assertRaises(ValueError):bank_for(target,nwp,weather,satellite,target[40*24])

    def test_infeasible_rejection_and_mass_balance(self):
        with self.assertRaises(ValueError):solve(np.zeros(24),demand=501.)
        with self.assertRaises(AssertionError):audit(np.zeros(24))
        with self.assertRaises(ValueError):solve(np.full(24,np.nan))
        record=audit(np.full(24,120.))
        self.assertEqual(record['terminal_error'],0.)
        self.assertEqual(record['water_m3'],2880.)


if __name__=='__main__':unittest.main()
