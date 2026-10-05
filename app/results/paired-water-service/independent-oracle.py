#!/usr/bin/env python3
"""Independent rational clipping/contact oracle. Never imports product code."""
from fractions import Fraction as F
import bisect, json, math, sys

def q(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x): raise ValueError('finite binary64 number required')
    return F.from_float(float(x))
def exact(x): return {'numerator':str(x.numerator),'denominator':str(x.denominator)}
def model(m):
    if set(m)!={'start_epoch','start_hour','end_hour','initial','capacity','reserve','target','segments'}: raise ValueError('model fields')
    a,b=q(m['start_hour']),q(m['end_hour']);c,r,s,t=[q(m[k]) for k in ('capacity','reserve','initial','target')]
    epoch=q(m['start_epoch'])
    if epoch.denominator!=1 or not (0<=a<b and b-a<=8784) or c<=0 or not all(0<=x<=c for x in (r,s,t)):raise ValueError('invalid model boundary')
    rows=[];at=a
    for v in m['segments']:
        if set(v)!={'from','to','production','demand'}:raise ValueError('segment fields')
        x,y,p,d=[q(v[k]) for k in ('from','to','production','demand')]
        if x!=at or y<=x or y>b or p<0 or d<0:raise ValueError('invalid segment')
        rows.append((x,y,p,d));at=y
    if at!=b:raise ValueError('incomplete horizon')
    return {'start':a,'end':b,'capacity':c,'reserve':r,'initial':s,'target':t,'epoch':epoch,'segments':rows}
def trajectory(m):
    """Construct storage formula separately on each clipping and reserve piece."""
    stock=m['initial'];out=[]
    for a,b,p,d in m['segments']:
        slope=p-d;cuts={a,b}
        if slope:
            for level in (F(0),m['reserve'],m['capacity']):
                hit=a+(level-stock)/slope
                if a<hit<b:cuts.add(hit)
        cuts=sorted(cuts)
        for x,y in zip(cuts,cuts[1:]):
            sx=min(m['capacity'],max(F(0),stock+slope*(x-a)))
            sy=min(m['capacity'],max(F(0),stock+slope*(y-a)))
            rate=max(F(0),d-p) if sx==0 and slope<0 else F(0)
            out.append((x,y,sx,sy,rate))
        stock=min(m['capacity'],max(F(0),stock+slope*(b-a)))
    return out,stock
def value(piece,t):
    a,b,x,y,u=piece
    return x+(y-x)*(t-a)/(b-a)
def groups(spans):
    n=0;end=None
    for x,y in spans:
        if end!=x:n+=1
        end=y
    return n

def oracle(case):
    a,b=model(case['original']),model(case['revised'])
    for k in ('start','end','capacity','reserve','initial','target','epoch'):
        if a[k]!=b[k]:raise ValueError('incomparable '+k)
    i=j=0
    while i<len(a['segments']) and j<len(b['segments']):
        x,y=a['segments'][i],b['segments'][j]
        if x[3]!=y[3]:raise ValueError('incomparable demanded rates')
        if x[1]<=y[1]:i+=1
        if y[1]<=x[1]:j+=1
    aa,af=trajectory(a);bb,bf=trajectory(b);i=j=0
    delivery=[];reserve=[];r=a['reserve']
    while i<len(aa) and j<len(bb):
        pa,pb=aa[i],bb[j];x=max(pa[0],pb[0]);y=min(pa[1],pb[1]);delta=pb[4]-pa[4]
        if delta>0:delivery.append({'from':x,'to':y,'rate':delta,'original_rate':pa[4],'revised_rate':pb[4]})
        ax=max(F(0),r-value(pa,x));ay=max(F(0),r-value(pa,y));bx=max(F(0),r-value(pb,x));by=max(F(0),r-value(pb,y));dx=bx-ax;dy=by-ay
        if dx>0 or dy>0:
            lo,hi=x,y
            if dx<=0:lo=x+(y-x)*(-dx)/(dy-dx)
            if dy<=0:hi=x+(y-x)*dx/(dx-dy)
            peak=x if dx>=dy else y
            reserve.append({'from':lo,'to':hi,'start_open':dx<=0,'end_open':dy<=0,'peak':peak,'maximum':max(dx,dy),'original_deficit':ax if dx>=dy else ay,'revised_deficit':bx if dx>=dy else by})
        if pa[1]<=pb[1]:i+=1
        if pb[1]<=pa[1]:j+=1
    sd=sum((x['rate']*(x['to']-x['from']) for x in delivery),F(0))
    dd=sum((x['to']-x['from'] for x in delivery),F(0));rd=sum((x['to']-x['from'] for x in reserve),F(0))
    rm=max((x['maximum'] for x in reserve),default=F(0));dm=max((x['rate'] for x in delivery),default=F(0))
    def serialize(v):
        if isinstance(v,F):return exact(v)
        if isinstance(v,dict):return {k:serialize(x) for k,x in v.items()}
        return v
    criteria={'delivery_no_worse':not delivery,'reserve_no_worse':not reserve,'end_stock_no_lower':bf>=af}
    return {'status':'no_modeled_regression' if all(criteria.values()) else 'regression_detected','criteria':criteria,
      'delivery':{'interval_count':groups([(x['from'],x['to']) for x in delivery]),'duration_hours':exact(dd),'shifted_shortfall_m3':exact(sd),'max_added_unserved_rate_m3_h':exact(dm),'first':serialize(delivery[0]) if delivery else None,'maximum':serialize(next(x for x in delivery if x['rate']==dm)) if delivery else None},
      'reserve':{'interval_count':groups([(x['from'],x['to']) for x in reserve]),'duration_hours':exact(rd),'max_added_deficit_m3':exact(rm),'first':serialize(reserve[0]) if reserve else None,'maximum':serialize(next(x for x in reserve if x['maximum']==rm)) if reserve else None},
      'end_stock':{'original_m3':exact(af),'revised_m3':exact(bf),'delta_m3':exact(bf-af)}}

if __name__=='__main__':
    from pathlib import Path
    import hashlib,datetime
    src,out=map(Path,sys.argv[1:3]);cases=json.loads(src.read_text());records=[]
    for case in cases['cases']:
        try:result=oracle(case['input']);actual={'accepted':True,**result}
        except ValueError as e:actual={'accepted':False,'reason':str(e)}
        wanted=case['expected'];ok=actual==wanted if wanted.get('accepted') else not actual['accepted']
        records.append({'id':case['id'],'status':'PASS' if ok else 'FAIL','actual':actual})
    receipt={'schema':1,'method':'Independent Fraction.from_float clipping/contact oracle; no product imports','input_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'oracle_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS' if all(r['status']=='PASS' for r in records) else 'FAIL','passed':sum(r['status']=='PASS' for r in records),'total':len(records),'records':records}
    with out.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps({k:receipt[k] for k in ('status','passed','total','input_sha256','oracle_sha256')}));sys.exit(receipt['status']!='PASS')
