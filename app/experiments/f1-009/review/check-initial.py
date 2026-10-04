"""Independent saved-weight BQN audit; no fitting or experiment-runner import."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[2]
OUT = EXP / 'result'
LEVELS = np.arange(1, 52) / 52

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    return obj

# Reuse the prior independent exact-count/policy oracle, never its runner.
oracle = module('independent008', EXP.parent / 'f1-008/review/check.py')
sha, load, rows = oracle.sha, oracle.load, oracle.rows

def close(a, b, tolerance=1e-9):
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all()
    error = float(np.max(np.abs(a-b))) if a.size else 0.
    assert error <= tolerance, (error, tolerance)
    return error

def casteljau(alpha, levels):
    """Evaluate the polynomial without the production power-basis formula."""
    t = np.asarray(levels)
    if t.ndim == 1: t = np.broadcast_to(t, (len(alpha), len(t)))
    work = np.broadcast_to(alpha[:, None, :], (*t.shape, 13)).copy()
    for remaining in range(12, 0, -1):
        work = work[..., :remaining] * (1-t[..., None]) + work[..., 1:remaining+1] * t[..., None]
    return work[..., 0]

def inverse(alpha, value):
    lo, hi = np.zeros(len(alpha)), np.ones(len(alpha))
    for _ in range(60):
        mid = (lo+hi)/2
        below = casteljau(alpha, mid[:, None])[:, 0] <= value
        lo = np.where(below, mid, lo); hi = np.where(below, hi, mid)
    return np.where(alpha[:, -1] <= value, 1., np.where(alpha[:, 0] > value, 0., (lo+hi)/2))

def network(theta, x, skip):
    assert theta.shape == (669,)
    w1 = theta[:432].reshape(27, 16); b1 = theta[432:448]
    w2 = theta[448:656].reshape(16, 13); b2 = theta[656:]
    z = np.tanh(x @ w1 + b1) @ w2 + b2
    cumulative = np.c_[np.zeros(len(x)), np.cumsum(np.logaddexp(0, z[:, 1:]), axis=1)]
    center = np.array([math.comb(12, j)/4096 for j in range(13)])
    return skip[:, None]+z[:, :1]+cumulative-(cumulative @ center)[:, None]

def independent_loss(theta, x, skip, weather, satellite, joint):
    q = np.maximum(0, casteljau(network(theta, x, skip), LEVELS))
    available = np.isfinite(satellite) if joint else np.zeros(len(weather), bool)
    def pinball(y):
        difference = y[:, None]-q
        return np.maximum(LEVELS*difference, (LEVELS-1)*difference).mean(axis=1)
    loss = np.where(available, .5, 1.)*pinball(weather)
    loss += np.where(available, .5, 0.)*pinball(np.nan_to_num(satellite))
    penalty = .5e-6*(np.square(theta[:432]).sum()+np.square(theta[448:656]).sum())
    return float(loss.mean()+penalty)

def distribution_stats(pred, y):
    d = y[:, None]-pred['quantiles']; pinball = float(np.maximum(LEVELS*d, (LEVELS-1)*d).mean())
    differences = np.diff(pred['quantiles'], axis=1)
    return {'hours':len(y), 'mean_pinball_51_w_m2':pinball, 'approx_crps_51_w_m2':2*pinball,
        'median_mae_w_m2':float(np.abs(pred['median']-y).mean()),
        'mean_rmse_w_m2':float(np.square(pred['mean']-y).mean()**.5),
        'coverage_90':float(((y>=pred['lower']) & (y<=pred['upper'])).mean()),
        'interval_width_90_w_m2':float((pred['upper']-pred['lower']).mean()),
        'mean_zero_mass':float(pred['zero_mass'].mean()),
        'crossing_count_above_1e_9_w_m2':int((differences < -1e-9).sum()),
        'minimum_quantile_step_w_m2':float(differences.min())}

def check():
    report = load(OUT/'report.json'); report_hash = sha(OUT/'report.json')
    selection = load(OUT/'validation-selection.json')
    assert report['status'] == 'COMPLETE'
    for path, key in [('PROTOCOL.md','protocol_sha256'), ('run.py','code_sha256'), ('bqn.py','core_sha256')]:
        assert sha(EXP/path) == report[key] == selection[{'code_sha256':'runner_sha256'}.get(key,key)]
    assert sha(OUT/'validation-selection.json') == report['selection_sha256']
    def identities():
        for name, digest in report['inputs_sha256'].items(): assert sha(ROOT/name) == digest, name
        for name, digest in report['outputs_sha256'].items(): assert sha(OUT/name) == digest, name
        assert sha(OUT/'report.json') == report_hash
    identities()
    features = pd.read_csv(EXP.parent/'f1-008/result/features.csv', float_precision='round_trip')
    targets = pd.read_csv(EXP.parent/'f1-006/result/feature-targets.csv', float_precision='round_trip')
    reference = pd.read_csv(EXP.parent/'reference-training-001/result/joined-reference.csv', float_precision='round_trip')
    assert features.feature_time.equals(targets.feature_time) and features.feature_time.equals(reference.feature_time)
    assert list(features.columns[1:]) == report['feature_names'] and features.shape == (17832,28)
    origin = pd.to_datetime(features.feature_time); target = pd.to_datetime(targets.target_time)
    assert (target-origin == pd.Timedelta(hours=24)).all()
    assert (origin.diff().dropna() == pd.Timedelta(hours=1)).all()
    # Fixed+03 mapping was independently established from retained archive bytes.
    assert (target-pd.Timedelta(hours=3)).dt.tz_localize('UTC').equals(pd.to_datetime(reference.valid_time_utc, utc=True))
    np.testing.assert_array_equal(targets.actual, reference.weather_actual_w_m2)
    x = features.iloc[:, 1:].to_numpy(); nwp = features.nwp_day2_radiation.to_numpy()
    weather_all = targets.actual.to_numpy(); satellite = reference.satellite_w_m2.to_numpy()
    assert not np.isinf(x).any() and np.isfinite(nwp).all() and np.isfinite(weather_all).all()
    assert not np.isinf(satellite).any() and not np.any(satellite < 0)
    best = {}; replay = []; transitions = {}; count_records = 0; distribution_records = 0; grid_pairs = 0; training_rows = 0
    max_errors = {key:0. for key in ['coefficients','quantiles','probability','zero_mass','median','mean','lower','upper','objective']}
    old_name = load(EXP.parent/'f1-008/result/report.json')['selected_augmented_arm']
    assert report['comparator_008'] == old_name
    nodes, weights = np.polynomial.legendre.leggauss(7) # Exact degree<=13 integration above zero.
    for stage, source in [('validation','cv_predictions.csv'), ('test','test_predictions.csv')]:
        split = pd.read_csv(ROOT/'eval'/source, float_precision='round_trip')
        names = split.iloc[:,0]; indices = pd.Index(features.feature_time).get_indexer(names)
        assert len(indices) == {'validation':3566,'test':3567}[stage] and np.all(indices>=0) and names.is_unique
        y = split.actual.to_numpy(); s = satellite[indices]; b = nwp[indices]>600
        np.testing.assert_array_equal(y, weather_all[indices])
        masks = {'weather_full':np.ones(len(y),bool), 'weather_common':np.isfinite(s), 'satellite_common':np.isfinite(s)}
        truth = {k:(s if k=='satellite_common' else y)[m]>600 for k,m in masks.items()}
        def stats(decisions, expected, p=None):
            nonlocal count_records
            answer = {}
            for basis, mask in masks.items():
                counts = oracle.count(truth[basis], decisions[mask]); oracle.verify(counts, expected[basis]); count_records += 1; answer[basis] = counts
                if p is not None: close(np.mean((p[mask]-truth[basis])**2), expected[basis]['brier'], 1e-14)
            return answer
        def distribution(pred, expected):
            nonlocal distribution_records
            for basis, mask in masks.items():
                score = distribution_stats({k:v[mask] for k,v in pred.items() if k!='coefficients'}, (s if basis=='satellite_common' else y)[mask])
                assert set(score) == set(expected[basis])
                for key, value in score.items(): close(value, expected[basis][key])
                distribution_records += 1
        controls = {k:oracle.count(truth[k], b[m]) for k,m in masks.items()}
        train = np.flatnonzero(target < pd.Timestamp(names.iloc[0])); training_rows += len(train)
        previous = pd.read_csv(EXP.parent/'f1-006/result'/f'{stage}-training-origins.csv')
        assert list(features.feature_time.iloc[train]) == list(previous.feature_time)
        assert list(targets.target_time.iloc[train]) == list(previous.target_time)
        saved_train = pd.read_csv(OUT/f'{stage}-training-rows.csv', float_precision='round_trip')
        assert list(saved_train.feature_time) == list(previous.feature_time) and list(saved_train.target_time) == list(previous.target_time)
        np.testing.assert_array_equal(saved_train.weather_w_m2, weather_all[train]); np.testing.assert_array_equal(saved_train.satellite_w_m2, satellite[train])
        np.testing.assert_array_equal(saved_train.satellite_available, np.isfinite(satellite[train]).astype(int))
        member = pd.read_csv(OUT/f'{stage}-reference-membership.csv', float_precision='round_trip')
        assert member.feature_time.equals(names) and list(member.target_time) == list(targets.target_time.iloc[indices])
        np.testing.assert_array_equal(member.weather_w_m2, y); np.testing.assert_array_equal(member.satellite_w_m2,s)
        np.testing.assert_array_equal(member.satellite_available,np.isfinite(s).astype(int))
        old_ref = pd.read_csv(EXP.parent/'f1-006/result'/f'{stage}-reference-membership.csv',float_precision='round_trip')
        np.testing.assert_array_equal(s, old_ref.satellite_w_m2)
        info = report['splits'][stage]
        assert info['hours']==len(y) and info['training_hours']==len(train) and info['satellite_missing_hours']==int(np.isnan(s).sum())
        assert info['satellite_common_hours']==int(np.isfinite(s).sum()) and info['latest_training_target']==targets.target_time.iloc[train[-1]] and info['first_evaluation_origin']==names.iloc[0]
        scaler = load(OUT/f'{stage}-scaler.json')
        mean = np.array([np.mean(col[np.isfinite(col)]) for col in x[train].T])
        filled = np.where(np.isnan(x[train]), mean, x[train]); scale = np.sqrt(np.mean((filled-mean)**2, axis=0)); scale[scale==0]=1
        close(mean, scaler['mean'],1e-10); close(scale,scaler['scale'],1e-10)
        assert scaler['features']==report['feature_names']
        assert scaler['missing_train']==np.isnan(x[train]).sum(axis=0).tolist() and scaler['missing_evaluation']==np.isnan(x[indices]).sum(axis=0).tolist()
        for method, point in [('original',split.predicted.to_numpy()), ('persistence',split.baseline.to_numpy()), ('nwp_day2',nwp[indices])]:
            p=(point>600).astype(float); stats(p.astype(bool),report['methods'][method][stage]['events'],p)
            pred={'quantiles':np.repeat(point[:,None],51,axis=1),'median':point,'mean':point,'lower':point,'upper':point,'zero_mass':(point==0).astype(float)}
            distribution(pred,report['methods'][method][stage]['distribution'])
        old = pd.read_csv(EXP.parent/'f1-008/result/predictions'/f'{stage}-{old_name}.csv',float_precision='round_trip')
        assert old.feature_time.equals(names)
        stats(old.predicted_positive.to_numpy().astype(bool),report['methods']['f1_008_frozen'][stage]['events'],old.probability.to_numpy())
        for arm in ['weather','joint']:
            modelpath = OUT/'models'/f'{stage}-{arm}.npz'
            with np.load(modelpath,allow_pickle=False) as m: model={k:m[k].copy() for k in m.files}
            np.testing.assert_array_equal(model['training_positions'],train)
            np.testing.assert_array_equal(model['mean'],scaler['mean']); np.testing.assert_array_equal(model['scale'],scaler['scale'])
            xe=(np.where(np.isnan(x[indices]),model['mean'],x[indices])-model['mean'])/model['scale']
            alpha=network(model['theta'],xe,nwp[indices]/1000)
            with np.load(OUT/'predictions'/f'{stage}-{arm}-distribution.npz',allow_pickle=False) as saved: pred={k:saved[k].copy() for k in saved.files}
            max_errors['coefficients']=max(max_errors['coefficients'],close(alpha,pred['coefficients'],0))
            assert np.all(np.diff(alpha,axis=1)>=0)
            zero=inverse(alpha,0); probability=1-inverse(alpha,.6)
            q=np.maximum(0,casteljau(alpha,LEVELS))*1000
            levels=zero[:,None]+(1-zero[:,None])*(nodes+1)/2
            mean_dist=np.sum(casteljau(alpha,levels)*weights,axis=1)*(1-zero)/2*1000
            independent={'quantiles':q,'zero_mass':zero,'probability':probability,'mean':mean_dist,
                'median':np.maximum(0,casteljau(alpha,np.array([.5]))[:,0])*1000,
                'lower':np.maximum(0,casteljau(alpha,np.array([.05]))[:,0])*1000,
                'upper':np.maximum(0,casteljau(alpha,np.array([.95]))[:,0])*1000}
            for key,value in independent.items(): max_errors[key]=max(max_errors[key],close(value,pred[key],1e-11 if key in ['zero_mass','probability'] else 1e-8))
            xt=(np.where(np.isnan(x[train]),model['mean'],x[train])-model['mean'])/model['scale']
            loss=independent_loss(model['theta'],xt,nwp[train]/1000,weather_all[train]/1000,satellite[train]/1000,arm=='joint')
            fit=report['fits'][stage+'-'+arm]; max_errors['objective']=max(max_errors['objective'],close(loss,fit['objective_internal_units'],1e-12))
            assert fit['iterations']==200 and fit['success'] is False and fit['status']==1 and fit['function_evaluations']<=1000
            assert 'ITERATIONS' in fit['message'].upper()
            frame=pd.read_csv(OUT/'predictions'/f'{stage}-{arm}.csv',float_precision='round_trip')
            for col in member.columns: np.testing.assert_array_equal(frame[col],member[col])
            for col in ['probability','zero_mass','median','mean','lower','upper']: np.testing.assert_array_equal(frame[col],pred[col])
            p=pred['probability']; np.testing.assert_array_equal(frame.nwp_positive,b.astype(int))
            if stage=='validation':
                grid=load(OUT/f'validation-grid-{arm}.json')
                assert [(r['policy']['lower'],r['policy']['upper']) for r in grid]==[(lo/20,hi/20) for lo in range(11) for hi in range(10,21)]
                for row in grid:
                    d=np.array([oracle.decide(bool(v),float(prob),row['policy']) for v,prob in zip(b,p)])
                    counts=stats(d,row['metrics']); changed=int(np.sum(d!=b))
                    assert row['changed']==changed and row['qualifies']==oracle.qualifies(counts,controls) and row['strict_gain']==oracle.improves(counts,controls); grid_pairs+=1
                eligible=[r for r in grid if r['strict_gain']]
                chosen=max(eligible,key=lambda r:(*oracle.rank(r),r['policy']['upper'],-r['policy']['lower'])) if eligible else {'policy':{'kind':'control'},'metrics':controls,'changed':0,'qualifies':True,'strict_gain':False}
                assert chosen['policy']==selection['policies'][arm]['policy'] and chosen['changed']==selection['policies'][arm]['changed'] and chosen['strict_gain']==selection['policies'][arm]['strict_gain']; best[arm]=chosen
            policy=selection['policies'][arm]['policy']; assert policy==report['methods'][arm][stage]['policy']
            d=np.array([oracle.decide(bool(v),float(prob),policy) for v,prob in zip(b,p)])
            np.testing.assert_array_equal(d,frame.predicted_positive.astype(bool)); np.testing.assert_array_equal(p>.5,frame.default_positive.astype(bool))
            # The independent polynomial evaluation must preserve every frozen decision, not only float proximity.
            independent_d=np.array([oracle.decide(bool(v),float(prob),policy) for v,prob in zip(b,probability)])
            np.testing.assert_array_equal(independent_d,d); np.testing.assert_array_equal(probability>.5,p>.5)
            stats(d,report['methods'][arm][stage]['events'],p); stats(p>.5,report['methods'][arm][stage]['default_events'],p)
            distribution(pred,report['methods'][arm][stage]['distribution'])
            corrections={'added':int(np.sum(~b&d)),'removed':int(np.sum(b&~d))}
            assert corrections==report['methods'][arm][stage]['corrections']; transitions[stage+'-'+arm]=corrections
            replay.append({'stage':stage,'arm':arm,'rows':len(p),'model_sha256':sha(modelpath),'coefficients_exact':True,'all_frozen_decisions_identical':True,'iterations':fit['iterations'],'optimizer_success':fit['success']})
    chosen=max(['weather','joint'],key=lambda a:(*oracle.rank(best[a]),a=='weather'))
    assert chosen==selection['selected_arm']==report['selected_arm']
    for gate,method in [('test_gate','nwp_day2'),('comparison_008','f1_008_frozen')]:
        a=report['methods'][chosen]['test']['events']; b=report['methods'][method]['test']['events']; saved=report[gate]
        assert saved['passes_frozen_gate']==oracle.improves(a,b)
        assert saved['all_six_strictly_improved']==all(oracle.ratio(a[s],k)>oracle.ratio(b[s],k) for s in oracle.BASES for k in ['precision','recall','f1'])
        expected=[(s,k,'improved' if oracle.ratio(a[s],k)>oracle.ratio(b[s],k) else 'equal' if oracle.ratio(a[s],k)==oracle.ratio(b[s],k) else 'regressed') for s in oracle.BASES for k in ['precision','recall','f1']]
        assert [(r['basis'],r['metric'],r['status']) for r in saved['comparisons']]==expected
    # Independent finite-difference loss checks against the frozen explicit gradient; no optimization.
    core=module('bqn009_review',EXP/'bqn.py'); rng=np.random.default_rng(31)
    fixture_x=rng.normal(size=(5,27)); theta=core.initialize()+rng.normal(0,.03,669)
    skip=np.array([.05,.2,.4,.6,.8]); weather=np.array([.1,.25,.35,.62,.75]); sat=np.array([.2,np.nan,.32,.7,.78])
    max_gradient_error=0.
    for joint in [False,True]:
        loss,gradient=core.objective(theta,fixture_x,skip,weather,sat,joint)
        close(loss,independent_loss(theta,fixture_x,skip,weather,sat,joint),1e-12)
        for index in range(669):
            plus=theta.copy(); minus=theta.copy(); plus[index]+=1e-6; minus[index]-=1e-6
            numerical=(independent_loss(plus,fixture_x,skip,weather,sat,joint)-independent_loss(minus,fixture_x,skip,weather,sat,joint))/2e-6
            max_gradient_error=max(max_gradient_error,close(numerical,gradient[index],3e-7))
    identities()
    return {'status':'PASS','checker_sha256':sha(Path(__file__)),'prior_independent_policy_oracle_sha256':sha(EXP.parent/'f1-008/review/check.py'),
        'report_sha256':report_hash,'inputs_and_outputs_unchanged':True,'feature_rows':17832,'features':27,'purged_training_rows':training_rows,
        'prediction_rows':sum(r['rows'] for r in replay),'quantile_values':sum(r['rows'] for r in replay)*51,'grid_pairs_checked':grid_pairs,
        'event_metric_records':count_records,'distribution_metric_records':distribution_records,'saved_model_replays':replay,'maximum_errors':max_errors,
        'gradient_coordinates_checked':1338,'maximum_gradient_error':max_gradient_error,'selected_arm':chosen,'transitions':transitions,
        'test_gate':report['test_gate'],'comparison_008':report['comparison_008'],'no_fitting_performed':True,
        'limitations':['All four fits stopped at the fixed 200-iteration budget; no optimizer convergence claim.',
            'Previously inspected retrospective references and decision thresholds; no fresh holdout or live publication proof.',
            'Reuses pinned 008 features whose source joins and strict-past histories were independently audited previously.',
            'Independent polynomial arithmetic allows 1e-8 W/m² and inversion 1e-11 absolute; coefficients, memberships and every frozen/default event are exact.']}

if __name__=='__main__':
    try:
        result=check(); oracle.save(HERE/'result.json',result); print(json.dumps(result,indent=2))
    except Exception as error:
        oracle.save(HERE/'failure.json',{'status':'FAIL','error':repr(error),'checker_sha256':sha(Path(__file__))}); raise
