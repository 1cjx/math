"""第二问保守全局下界：将不可拆箱、路线和电池调度松弛成工作量分配LP。
Python 3.13.5；SciPy 1.17.0/HiGHS。下界与可行上界之差不冒充最优性证明。
"""
from collections import defaultdict
import numpy as np
from scipy.optimize import linprog
from io_utils import save_json,write_csv


def workload_lower_bound(pb,out):
    keys=[];bounds=[]
    def var(key,ub=None):keys.append(key);bounds.append((0,ub));return len(keys)-1
    G=sorted(pb.models);S=sorted(set(pb.sid));n=len(pb.boxes)
    x={(g,b):var(('box_fraction',g,pb.bid[b]),1.0) for g in G for b in range(n)}
    t={g:var(('fractional_trips',g)) for g in G}
    v={(g,s):var(('fractional_visits',g,s)) for g in G for s in S}
    C=var(('makespan_s',));N=len(keys);A=[];B=[];EQ=[];EB=[];names=[]
    def row(d,rhs,name):
        r=np.zeros(N)
        for k,a in d.items():r[k]+=a
        A.append(r);B.append(rhs);names.append(name)
    for b in range(n):
        r=np.zeros(N)
        for g in G:r[x[g,b]]=1
        EQ.append(r);EB.append(1)
    for s in S:row({v[g,s]:-1 for g in G},-1,'at_least_one_delivery_visit_'+s)
    for g,m in pb.models.items():
        row({**{x[g,b]:float(pb.weight[b]) for b in range(n)},t[g]:-m['max_payload_kg']},0,g+'_trip_mass')
        row({**{x[g,b]:float(pb.volume[b]) for b in range(n)},t[g]:-m['volume_m3']},0,g+'_trip_volume')
        row({t[g]:1,**{v[g,s]:-1 for s in S}},0,g+'_trips_le_visits')
        minreturn=min(pb.arc_values[g,s,'O01'][0] for s in S)
        work={C:-len(pb.fleet[g]),t[g]:m['prepare_s']+minreturn}
        for b in range(n):work[x[g,b]]=m['load_per_box_s']+m['handoff_per_box_s']
        for s in S:
            bs=[b for b in range(n) if pb.sid[b]==s]
            row({v[g,s]:-m['max_payload_kg'],**{x[g,b]:float(pb.weight[b]) for b in bs}},0,g+s+'_visit_mass')
            row({v[g,s]:-m['volume_m3'],**{x[g,b]:float(pb.volume[b]) for b in bs}},0,g+s+'_visit_volume')
            row({v[g,s]:1,**{x[g,b]:-1 for b in bs}},0,g+s+'_nonempty_visit')
            mint=min(z[0] for (gg,u,w),z in pb.arc_values.items() if gg==g and w==s)
            work[v[g,s]]=m['handoff_base_s']+mint
        row(work,0,g+'_airframe_workload')
    c=np.zeros(N);c[C]=1
    A=np.array(A);B=np.array(B);EQ=np.array(EQ);EB=np.array(EB)
    result=linprog(c,A_ub=A,b_ub=B,A_eq=EQ,b_eq=EB,bounds=bounds,method='highs')
    if not result.success:raise RuntimeError('下界LP未求解成功：'+str(result.message))
    dual_obj=float(B@result.ineqlin.marginals+EB@result.eqlin.marginals+
        sum(ub*result.upper.marginals[i] for i,(lb,ub) in enumerate(bounds) if ub is not None))
    stationarity=c-A.T@result.ineqlin.marginals-EQ.T@result.eqlin.marginals-result.lower.marginals-result.upper.marginals
    residual=max(float(np.max(np.abs(stationarity))),float(max(0,-np.min(result.slack))),float(np.max(np.abs(result.con))))
    if residual>1e-6 or abs(result.fun-dual_obj)>1e-5:raise AssertionError('LP原对偶证书残差异常')
    bound=max(0.0,min(float(result.fun),dual_obj)-1e-5)
    summary={'lower_bound_s':bound,'lp_primal_objective_s':float(result.fun),'lp_dual_objective_s':dual_obj,
        'certificate_residual':residual,'variables':N,'inequalities':len(A),'equalities':len(EQ),
        'status':str(result.message),'relaxations':['货箱允许分数分配','每个目的地入航段取全图最小时间','架次和访问次数允许连续','不约束电池/时限/能耗','只保留各型机身累计工作量上界'],
        'interpretation':'保守的全问题Cmax下界；不是完整原问题最优解。已达零逾期时，仍可用作Cmax下界。'}
    save_json(out/'lower_bound.json',summary)
    write_csv(out/'lower_bound_variables.csv',[{'variable':str(k),'value':float(result.x[i])} for i,k in enumerate(keys)])
    write_csv(out/'lower_bound_certificate.csv',[{'constraint':name,'slack':float(result.slack[i]),'dual':float(result.ineqlin.marginals[i])} for i,name in enumerate(names)])
    return summary
