from fractions import Fraction as F
import unittest
import run


def metrics(p, r, f):
    return {name: run.exact(F(value)) for name,value in zip(('precision','recall','f1'),(p,r,f))}


def candidate(scores, count, changed, failures):
    gains = [F(s['f1']['numerator'],s['f1']['denominator']) - F(1,2) for s in scores]
    return dict(metrics=scores,positive_calls=count,changed_bits=changed,failed_constraints=failures,
        objectives={k:run.exact(v) for k,v in dict(robust=min(gains),pooled=sum(gains,F())/2).items()})


def record(others):
    baseline=metrics('1/2','1/2','1/2')
    raw=candidate([baseline,baseline],2,0,[])
    return dict(stage='synthetic',day='one',bank='synthetic',raw_metrics=[baseline,baseline],candidates=[raw]+others,
        uncertain=[0,1],arms={a:dict(objective=run.exact(F()),changed_bits=0,positive_calls=2) for a in ('robust','pooled')})


class DiagnosticTests(unittest.TestCase):
    def test_overlapping_guards_are_not_arbitrarily_assigned(self):
        precision=metrics('2/5','4/5','8/15')
        recall=metrics('4/5','2/5','8/15')
        rows=list(run.diagnose(record([candidate([precision,precision],10,8,['0/precision','1/precision']),
            candidate([recall,recall],5,3,['0/recall','1/recall'])])))
        for row in rows:
            self.assertEqual(row['positive_before_guards'],2)
            self.assertEqual(row['positive_after_all'],0)
            self.assertEqual(row['precision_alone_blocks_day'],0)
            self.assertEqual(row['recall_alone_blocks_day'],0)
            self.assertEqual(row['precision_necessary_for_rejection'],1)
            self.assertEqual(row['recall_necessary_for_rejection'],1)
            self.assertEqual(row['positive_after_ordered_precision'],1)
            self.assertEqual(row['positive_after_ordered_recall'],0)

    def test_reference_conflict_requires_individual_opportunities(self):
        plus=metrics('3/5','3/5','3/5')
        minus=metrics('2/5','2/5','2/5')
        rows=list(run.diagnose(record([candidate([plus,minus],3,1,['1/precision','1/recall','1/f1']),
            candidate([minus,plus],3,1,['0/precision','0/recall','0/f1'])])))
        for row in rows:
            self.assertEqual(row['reference_f1_conflict_unguarded'],1)
            self.assertEqual(row['reference_f1_conflict_own_guards'],1)
            self.assertEqual(row['positive_before_guards'],0)
            self.assertEqual(row['reference_guard_intersection_conflict'],0)
        no_opportunity=list(run.diagnose(record([])))[0]
        self.assertEqual(no_opportunity['reference_f1_conflict_unguarded'],0)

    def test_corrupt_exact_saved_failure_refused(self):
        bad=metrics('2/5','4/5','8/15')
        with self.assertRaisesRegex(AssertionError,'Saved guard'):
            list(run.diagnose(record([candidate([bad,bad],10,8,[])])))


if __name__=='__main__':
    unittest.main()
