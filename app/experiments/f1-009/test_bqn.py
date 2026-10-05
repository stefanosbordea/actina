import unittest
import numpy as np
from scipy.integrate import quad
import bqn


class BQNTests(unittest.TestCase):
    def test_pinball_uses_separate_reference_losses(self):
        arrays=[np.zeros(shape) for shape in bqn.SHAPES]
        arrays[-1][1:]=-1000
        theta=bqn.pack(arrays);x=np.zeros((1,27));skip=np.array([.5])
        joint=bqn.objective(theta,x,skip,np.array([.3]),np.array([.7]),True)[0]
        averaged=bqn.objective(theta,x,skip,np.array([.5]),np.array([np.nan]),False)[0]
        self.assertAlmostEqual(joint,.1,places=13)
        self.assertEqual(averaged,0)

    def test_gradient_weather_and_joint_away_from_kinks(self):
        rng=np.random.default_rng(31);x=rng.normal(size=(5,27));skip=np.array([0,.2,.55,.8,.4])
        theta=bqn.initialize()+rng.normal(0,.03,size=len(bqn.initialize()))
        w=np.array([.013,.33,.718,.908,.251]);s=np.array([.025,.401,np.nan,.725,.39])
        for joint in (False,True):
            loss,grad=bqn.objective(theta,x,skip,w,s,joint)
            self.assertTrue(np.isfinite(loss))
            for i in range(len(theta)):
                step=1e-6;a=theta.copy();c=theta.copy();a[i]+=step;c[i]-=step
                numeric=(bqn.objective(a,x,skip,w,s,joint)[0]-bqn.objective(c,x,skip,w,s,joint)[0])/(2*step)
                self.assertAlmostEqual(numeric,grad[i],delta=3e-7,msg=f'{joint}:{i}')

    def test_bernstein_and_censoring(self):
        linear=np.linspace(-.5,.5,13)[None,:]
        self.assertAlmostEqual(bqn.cdf(linear,0)[0],.5,places=13)
        self.assertAlmostEqual(bqn.cdf(linear,.25)[0],.75,places=13)
        self.assertEqual(bqn.cdf(np.full((1,13),.6),.6)[0],1)
        self.assertEqual(bqn.cdf(np.full((1,13),.7),.6)[0],0)
        np.testing.assert_allclose(bqn.basis(np.linspace(0,1,101)).sum(axis=1),1,atol=1e-14)
        rng=np.random.default_rng(3);x=rng.normal(size=(10,27));skip=np.linspace(0,1,10)
        pred=bqn.predict(bqn.initialize(),x,skip)
        np.testing.assert_allclose(pred['median'],skip*1000,atol=1e-12)
        self.assertTrue((np.diff(pred['quantiles'],axis=1)>=0).all())
        for a,mean in zip(pred['coefficients'],pred['mean']):
            integral=quad(lambda t:max(0,float(a@bqn.basis(t))),0,1,epsabs=1e-10,points=[bqn.cdf(a[None,:],0)[0]])[0]*1000
            self.assertAlmostEqual(mean,integral,places=8)

    def test_missing_reference_and_train_only_scaler(self):
        x=np.array([[1.,np.nan,3.],[3.,4.,3.],[np.nan,6.,3.]])
        mean,scale=bqn.fit_scaler(x);np.testing.assert_array_equal(mean,[2,5,3])
        self.assertEqual(scale[-1],1);self.assertTrue(np.isfinite(bqn.transform(x,mean,scale)).all())
        with self.assertRaises(ValueError):bqn.fit_scaler(np.full((2,3),np.nan))
        data=np.zeros((2,27));theta=bqn.initialize();skip=np.array([.3,.7]);w=np.array([.2,.8])
        weather=bqn.objective(theta,data,skip,w,np.full(2,np.nan),False)
        missing=bqn.objective(theta,data,skip,w,np.full(2,np.nan),True)
        self.assertEqual(weather[0],missing[0]);np.testing.assert_array_equal(weather[1],missing[1])
        same=bqn.objective(theta,data,skip,w,w,True)
        self.assertEqual(weather[0],same[0]);np.testing.assert_array_equal(weather[1],same[1])


if __name__=='__main__':unittest.main()
