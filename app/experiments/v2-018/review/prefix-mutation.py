"""Mutate actual retained future observations and replay the fixed 018 head."""
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review018',HERE/'review.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
spec=importlib.util.spec_from_file_location('context018',HERE.parent/'context.py')
context=importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


def audit():
    history=r.frame(r.EXP/'inputs/history-predictions.csv','target_time',True)
    observed=r.pd.concat([r.frame(r.EXP/'inputs/observations-training.csv','target_time',True),
        r.frame(r.EXP/'inputs/observations-validation-stream.csv','target_time',True)])
    valid=r.frame(r.PREVIOUS/'inputs/validation.csv',original_parser=True)
    saved=r.frame(r.RESULT/'validation-decisions.csv')
    model=r.lgb.Booster(model_file=str(r.RESULT/'expanded-final.txt'))
    cutoff=r.read_json(r.RESULT/'head-freeze.json')['selected_training_thresholds']['expanded']['threshold']
    checks=[]
    for number in (0,24,1000,2000,3500):
        origin=valid.index[number]
        altered=observed.copy()
        future=altered.index>=origin
        assert future.any()
        altered.loc[future,'actual']=1e12+r.np.arange(int(future.sum()))
        before,before_coverage=context.build(r.pd.DatetimeIndex([origin]),history,observed)
        after,after_coverage=context.build(r.pd.DatetimeIndex([origin]),history,altered)
        r.pd.testing.assert_frame_equal(before,after,check_exact=True)
        r.pd.testing.assert_frame_equal(before_coverage,after_coverage,check_exact=True)
        base=r.h.features(valid.loc[[origin]],True)
        p_before=float(model.predict(r.pd.concat([base,before],axis=1),num_threads=2)[0])
        p_after=float(model.predict(r.pd.concat([base,after],axis=1),num_threads=2)[0])
        assert p_before==p_after
        r.close(p_before,float(saved.at[origin,'expanded_probability']))
        assert (p_before>cutoff)==bool(saved.at[origin,'expanded_call'])
        checks.append(dict(origin=str(origin),altered_current_or_future_observations=int(future.sum()),
            maximum_feature_change=0,probability_change=0,call_unchanged=True))
    return dict(status='PASS',source_sha256=r.sha(Path(__file__)),context_source_sha256=r.sha(r.EXP/'context.py'),
        model_sha256=r.sha(r.RESULT/'expanded-final.txt'),checks=checks,fits_executed=0,test_files_read=False)


if __name__=='__main__':
    with r.h.h.threadpool_limits(limits=2):
        result=audit()
    with (HERE/'prefix-mutation.json').open('x') as out:
        json.dump(result,out,indent=2)
        out.write('\n')
    print(json.dumps(result))
