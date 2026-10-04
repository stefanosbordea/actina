"""Adopted finite-scenario CVaR epigraph with explicit water service."""
import math
import warnings
import numpy as np
from scipy.optimize import linprog, OptimizeWarning
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack

SEC = 3.4
PRICE = np.array([101. if 10 <= h < 17 else 183. if 17 <= h < 23 else 130. for h in range(24)]) / 1000
PRIMARY_TOL = 1e-7
L1_TOL = 1e-7
AUDIT_TOL = 1e-6
ACTION_FLOOR = 1e-5
OPTIONS = dict(threads=1, primal_feasibility_tolerance=1e-9, dual_feasibility_tolerance=1e-9)


def pv(ghi):
    a = np.asarray(ghi, dtype=float)
    if a.shape[-1:] != (24,) or not np.isfinite(a).all(): raise ValueError('Finite 24-hour radiation required')
    return np.minimum(1700., 1.7 * np.maximum(a, 0.))


def cvar(loss):
    values = np.asarray(loss, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all(): raise ValueError('Finite nonempty loss vector required')
    ordered = np.sort(values)[::-1]
    whole, remainder = divmod(len(values), 10)
    return float((10 * math.fsum(ordered[:whole]) + remainder * ordered[whole]) / len(values))


def evaluate(q, solar):
    q = np.asarray(q, dtype=float); solar = np.asarray(solar, dtype=float)
    if q.shape != (24,) or solar.shape[-1:] != (24,) or not np.isfinite(q).all() or not np.isfinite(solar).all() or np.any((solar < 0) | (solar > 1700)):
        raise ValueError('Invalid production or solar inputs')
    grid = np.maximum(SEC * q - solar, 0.)
    used = np.minimum(SEC * q, solar)
    return dict(cost=np.sum(grid * PRICE, axis=-1), grid_energy=np.sum(grid, axis=-1), unused_pv=np.sum(solar-used,axis=-1))


def audit(q, demand=120., capacity=500.):
    q = np.asarray(q, dtype=float)
    if q.shape != (24,) or not np.isfinite(q).all(): raise ValueError('Invalid production')
    stock = 2000 + np.cumsum(q-demand)
    errors = dict(production_below_zero=max(0.,float(-q.min())), production_above_capacity=max(0.,float(q.max()-capacity)),
        stock_below_reserve=max(0.,float(800-stock.min())), stock_above_capacity=max(0.,float(stock.max()-4000)),
        terminal_error=abs(float(stock[-1]-2000)), water_error=abs(float(q.sum()-24*demand)))
    if max(errors.values()) > AUDIT_TOL: raise AssertionError('Water/capacity violation: '+str(errors))
    return dict(**errors, water_m3=float(q.sum()), total_energy_kwh=float(SEC*q.sum()), minimum_stock=float(min(2000.,stock.min())), maximum_stock=float(max(2000.,stock.max())))


def solve(solar, anchor=None, demand=120., capacity=500.):
    p = np.asarray(solar, dtype=float)
    risk = anchor is not None
    if risk:
        if p.ndim != 3 or p.shape[0] != 2 or p.shape[2] != 24 or p.shape[1] < 1: raise ValueError('Two-reference scenario tensor required')
    elif p.shape != (24,): raise ValueError('One point trajectory required')
    if not np.isfinite(p).all() or np.any((p < 0) | (p > 1700)): raise ValueError('Invalid PV')
    if not np.isfinite(demand) or not np.isfinite(capacity) or demand <= 0 or capacity <= 0 or demand > capacity: raise ValueError('Infeasible production capacity')
    a = np.asarray(anchor,dtype=float) if risk else np.full(24,demand)
    audit(a,demand,capacity)
    references, scenarios = (2,p.shape[1]) if risk else (1,1)
    tensor = p if risk else p.reshape(1,1,24)
    count = references*scenarios
    eta = 24+24*count
    z = eta+references
    t = z+count
    variables = t+1 if risk else eta
    rows,cols,vals,rhs = [],[],[],[]
    def add(entries, right):
        row=len(rhs)
        for column,value in entries:
            rows.append(row);cols.append(column);vals.append(value)
        rhs.append(float(right))
    for h in range(24):
        add([(j,1.) for j in range(h+1)],2000+demand*(h+1))
        add([(j,-1.) for j in range(h+1)],1200-demand*(h+1))
    for j in range(count):
        for h in range(24): add([(h,SEC),(24+24*j+h,-1.)],tensor.reshape(count,24)[j,h])
    c=np.zeros(variables)
    bounds=[(0.,capacity)]*24+[(0.,None)]*(24*count)
    baseline = evaluate(a,tensor)['cost']
    if risk:
        bounds += [(None,None)]*references+[(0.,None)]*count+[(None,None)]
        for r in range(references):
            for s in range(scenarios):
                j=r*scenarios+s
                add([(24+24*j+h,PRICE[h]) for h in range(24)]+[(eta+r,-1.),(z+j,-1.)],baseline[r,s])
            add([(eta+r,1.),(t,-1.)]+[(z+r*scenarios+s,10/scenarios) for s in range(scenarios)],0.)
        c[t]=1.
    else: c[24:]=PRICE
    matrix=coo_matrix((vals,(rows,cols)),shape=(len(rhs),variables)).tocsr()
    rhs=np.asarray(rhs)
    equality=csr_matrix((np.ones(24),(np.zeros(24,dtype=int),np.arange(24))),shape=(1,variables))
    logs=[]
    def run(objective,ub,right,eq,variable_bounds,label):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',OptimizeWarning)
            result=linprog(objective,A_ub=ub,b_ub=right,A_eq=eq,b_eq=[24*demand],bounds=variable_bounds,method='highs-ds',options=OPTIONS)
        logs.append(dict(stage=label,status=int(result.status),success=bool(result.success),message=result.message,
                         iterations=int(result.nit),objective=float(result.fun) if result.fun is not None else None,
                         warnings=[str(w.message) for w in caught]))
        if not result.success: raise RuntimeError('LP failed: '+str(logs[-1]))
        return result
    primary=run(c,matrix,rhs,equality,bounds,'primary')
    optimum=float(primary.fun)
    raw=evaluate(primary.x[:24],tensor)['cost']
    independent=max(cvar(v) for v in raw-baseline) if risk else float(raw[0,0])
    if abs(independent-optimum)>AUDIT_TOL: raise AssertionError('Primary epigraph mismatch')
    anchor_value=0. if risk else float(baseline[0,0])
    if anchor_value-optimum<=ACTION_FLOOR+1e-9:
        q=a.copy(); distance=0.; anchor_returned=True
    else:
        base=hstack((matrix,csr_matrix((matrix.shape[0],24))),format='csr')
        objective_cap=csr_matrix(np.r_[c,np.zeros(24)].reshape(1,-1))
        absrows=[]
        for h in range(24):
            row=np.zeros(variables+24);row[h]=1.;row[variables+h]=-1.;absrows.append(row)
            row=np.zeros(variables+24);row[h]=-1.;row[variables+h]=-1.;absrows.append(row)
        ub=vstack((base,objective_cap,csr_matrix(np.asarray(absrows))),format='csr')
        right=np.r_[rhs,optimum+PRIMARY_TOL,np.stack((a,-a),axis=1).reshape(-1)]
        eq=hstack((equality,csr_matrix((1,24))),format='csr');extended=bounds+[(0.,None)]*24
        secondary_objective=np.r_[np.zeros(variables),np.ones(24)]
        secondary=run(secondary_objective,ub,right,eq,extended,'minimum_L1')
        distance=float(secondary.fun)
        ub=vstack((ub,csr_matrix(secondary_objective.reshape(1,-1))),format='csr')
        right=np.r_[right,distance+L1_TOL]
        tertiary_objective=np.zeros(variables+24);tertiary_objective[:24]=np.arange(1,25)/24
        third=run(tertiary_objective,ub,right,eq,extended,'fixed_hour_tie')
        q=third.x[:24];anchor_returned=False
        if np.sum(abs(q-a))>distance+L1_TOL+AUDIT_TOL: raise AssertionError('L1 cap violation')
    water=audit(q,demand,capacity)
    evaluated=evaluate(q,tensor)['cost']
    realized_objective=max(cvar(v) for v in evaluated-baseline) if risk else float(evaluated[0,0])
    if anchor_returned:
        if realized_objective-optimum>ACTION_FLOOR+1e-9: raise AssertionError('Action-floor fallback gap violation')
    elif realized_objective>optimum+PRIMARY_TOL+AUDIT_TOL: raise AssertionError('Actual objective cap violation')
    if risk and optimum>AUDIT_TOL: raise AssertionError('Feasible zero-regret control lost')
    return q,dict(primary_optimum=optimum,primary_direct_audit=independent,final_direct_objective=realized_objective,
                  primary_cap=optimum+PRIMARY_TOL,primary_cap_applies=not anchor_returned,
                  final_optimum_gap=realized_objective-optimum,action_floor_eur=ACTION_FLOOR,
                  L1_optimum=distance,L1_distance=float(np.sum(abs(q-a))),
                  anchor_returned=anchor_returned,water=water,solves=logs)


def shuffled(residuals, permutations):
    a=np.asarray(residuals,dtype=float); order=np.asarray(permutations)
    if a.ndim!=3 or a.shape[0]!=2 or a.shape[2]!=24 or order.shape!=(24,a.shape[1]) or not np.isfinite(a).all(): raise ValueError('Invalid scenario bank')
    if not np.issubdtype(order.dtype,np.integer) or any(not np.array_equal(np.sort(row),np.arange(a.shape[1])) for row in order): raise ValueError('Invalid permutations')
    return np.stack([a[:,order[h],h] for h in range(24)],axis=-1)
