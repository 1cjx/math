"""核心算法模块2：完整可行批次枚举 + 计数状态动态规划（精确，不是启发式）。
Python 3.13.5；仅标准库。质量、体积、物资类型相同的箱子在Q1中等价。
Q1不使用逐箱截止时间作约束，不据此宣称满足Q2时限/资源调度。
"""
from itertools import product
from collections import defaultdict
import math
from config import CFG
from physics import trip_energy, trip_time


def objective_key(metrics,order):
    # 1e-10 kWh/1e-6 s以下视为浮点计算同值，随后按确定性枚举顺序破同分。
    n,e,t=metrics
    d={'N':n,'E':round(e,CFG.comparison_energy_decimals),'T':round(t,CFG.comparison_time_decimals)}
    return tuple(d[c] for c in order)

def add_metrics(a,b):return (a[0]+b[0],a[1]+b[1],a[2]+b[2])

def make_groups(boxes):
    grouped=defaultdict(list)
    for b in boxes:grouped[(b['material_type'],b['weight_kg'],b['volume_m3'])].append(b)
    groups=[]
    for key,rows in sorted(grouped.items()):
        rows=sorted(rows,key=lambda b:(not b['is_first_batch'],b['box_id']))
        groups.append({'type':key[0],'weight':key[1],'volume':key[2],'boxes':rows})
    return groups

def enumerate_patterns(groups,models,route,reserve=None):
    target=tuple(len(g['boxes']) for g in groups);patterns=[]
    for counts in product(*(range(n+1) for n in target)):
        n=sum(counts)
        if n==0:continue
        weight=sum(c*g['weight'] for c,g in zip(counts,groups))
        volume=sum(c*g['volume'] for c,g in zip(counts,groups))
        for m in sorted(models,key=lambda r:r['model_id']):
            rho=m['reserve_fraction'] if reserve is None else reserve
            if weight>m['max_payload_kg']+CFG.capacity_tolerance_kg or volume>m['volume_m3']+CFG.geometry_tolerance:continue
            energy=trip_energy(m,route,weight)
            if energy['energy_kwh']>(1-rho)*m['usable_energy_kwh']+CFG.energy_tolerance_kwh:continue
            times=trip_time(m,route,n)
            patterns.append({'counts':counts,'model_id':m['model_id'],'box_count':n,'weight_kg':weight,'volume_m3':volume,
                **energy,**times,'reserve_fraction':rho,'return_soc_fraction':1-energy['energy_kwh']/m['usable_energy_kwh'],
                'energy_margin_kwh':(1-rho)*m['usable_energy_kwh']-energy['energy_kwh'],
                'payload_utilization':weight/m['max_payload_kg'],'volume_utilization':volume/m['volume_m3']})
    return patterns,target

def solve_service(boxes,models,route,order='NET',reserve=None,patterns_input=None):
    groups=make_groups(boxes)
    patterns,target=enumerate_patterns(groups,models,route,reserve) if patterns_input is None else patterns_input
    states=sorted(product(*(range(n+1) for n in target)),key=lambda x:(sum(x),x));zero=tuple(0 for _ in target)
    dp={zero:(0,0.0,0.0)};parent={};transitions=0
    for state in states[1:]:
        best=None;choice=None
        for idx,p in enumerate(patterns):
            cnt=p['counts']
            if any(a>b for a,b in zip(cnt,state)):continue
            prev=tuple(b-a for a,b in zip(cnt,state))
            if prev not in dp:continue
            transitions+=1
            cand=add_metrics(dp[prev],(1,p['energy_kwh'],p['operation_time_s']))
            if best is None or objective_key(cand,order)<objective_key(best,order):best=cand;choice=(prev,idx)
        if best is not None:dp[state]=best;parent[state]=choice
    info={'service_id':route['service_id'],'order':order,'reserve_fraction':reserve if reserve is not None else models[0]['reserve_fraction'],
        'groups':len(groups),'box_count':len(boxes),'states_total':len(states),'states_reachable':len(dp),'patterns_count':len(patterns),'evaluated_transitions':transitions,
        'feasible':target in dp,'optimality':'exact_complete_enumeration_dynamic_programming'}
    if target not in dp:return None,info
    seq=[];state=target
    while state!=zero:
        prev,idx=parent[state];seq.append(patterns[idx]);state=prev
    seq.reverse()
    offsets=[0]*len(groups);batches=[]
    for p in seq:
        ids=[]
        for k,(n,g) in enumerate(zip(p['counts'],groups)):
            ids.extend(b['box_id'] for b in g['boxes'][offsets[k]:offsets[k]+n]);offsets[k]+=n
        batch={k:v for k,v in p.items() if k!='counts'}
        batch['service_id']=route['service_id'];batch['box_ids']=';'.join(sorted(ids));batch['composition']=str(p['counts'])
        batches.append(batch)
    info.update(trips=dp[target][0],energy_kwh=dp[target][1],operation_time_s=dp[target][2])
    return batches,info

def solve_all(data,routes,order='NET',reserve=None):
    byservice=defaultdict(list)
    for b in data['boxes']:byservice[b['service_id']].append(b)
    route_map={r['service_id']:r for r in routes};allb=[];infos=[];infeasible=[]
    for sid in sorted(byservice):
        batches,info=solve_service(byservice[sid],data['transport_models'],route_map[sid],order,reserve)
        infos.append(info)
        if batches is None:infeasible.append(sid)
        else:allb+=batches
    if infeasible:return None,infos,{'feasible':False,'infeasible_services':infeasible,'order':order,'reserve_fraction':reserve}
    for i,b in enumerate(allb,1):b['trip_id']=f'Q1-{i:03d}'
    summary={'feasible':True,'order':order,'reserve_fraction':reserve if reserve is not None else data['transport_models'][0]['reserve_fraction'],
      'trips':len(allb),'energy_kwh':sum(b['energy_kwh'] for b in allb),'operation_time_s':sum(b['operation_time_s'] for b in allb),
      'flight_time_s':sum(b['flight_time_s'] for b in allb),'airborne_service_s':sum(b['airborne_service_s'] for b in allb),
      'preparation_load_s':sum(b['preparation_load_s'] for b in allb),'handoff_s':sum(b['handoff_s'] for b in allb),
      'delivered_boxes':sum(b['box_count'] for b in allb),'delivered_weight_kg':sum(b['weight_kg'] for b in allb),
      'delivered_volume_m3':sum(b['volume_m3'] for b in allb),'min_return_soc_fraction':min(b['return_soc_fraction'] for b in allb),
      'min_energy_margin_kwh':min(b['energy_margin_kwh'] for b in allb),
      'model_trip_counts':dict(__import__('collections').Counter(b['model_id'] for b in allb))}
    return allb,infos,summary

def service_flight_energy_frontier(boxes,models,route):
    """对每个可行架次数N，精确求最小E（同E取最小T）。"""
    groups=make_groups(boxes);patterns,target=enumerate_patterns(groups,models,route)
    states=sorted(product(*(range(n+1) for n in target)),key=lambda x:(sum(x),x));zero=tuple(0 for _ in target)
    dp={zero:{0:(0.0,0.0,())}}
    for state in states[1:]:
        current={}
        for idx,p in enumerate(patterns):
            if any(a>b for a,b in zip(p['counts'],state)):continue
            prev=tuple(b-a for a,b in zip(p['counts'],state))
            for n,(e,t,path) in dp.get(prev,{}).items():
                new=(e+p['energy_kwh'],t+p['operation_time_s'],path+(idx,))
                if n+1 not in current or (round(new[0],CFG.comparison_energy_decimals),round(new[1],CFG.comparison_time_decimals))<(round(current[n+1][0],CFG.comparison_energy_decimals),round(current[n+1][1],CFG.comparison_time_decimals)):
                    current[n+1]=new
        dp[state]=current
    return dp[target],patterns

def global_flight_energy_frontier(data,routes):
    acc={0:(0.0,0.0,())};locals=[]
    for r in sorted(routes,key=lambda x:x['service_id']):
        boxes=[b for b in data['boxes'] if b['service_id']==r['service_id']]
        fr,patterns=service_flight_energy_frontier(boxes,data['transport_models'],r);new={}
        for n,(e,t,path) in acc.items():
            for ni,(ei,ti,_) in fr.items():
                cand=(e+ei,t+ti,path+((r['service_id'],ni),))
                if n+ni not in new or (round(cand[0],CFG.comparison_energy_decimals),round(cand[1],CFG.comparison_time_decimals))<(round(new[n+ni][0],CFG.comparison_energy_decimals),round(new[n+ni][1],CFG.comparison_time_decimals)):
                    new[n+ni]=cand
        acc=new
        locals += [{'service_id':r['service_id'],'trips':n,'min_energy_kwh':v[0],'operation_time_at_min_energy_s':v[1]} for n,v in sorted(fr.items())]
    rows=[];best_energy=math.inf
    for n,(e,t,path) in sorted(acc.items()):
        efficient=e<best_energy-CFG.energy_tolerance_kwh
        rows.append({'trips':n,'min_energy_kwh':e,'operation_time_at_min_energy_s':t,'pareto_efficient_N_E':efficient,
                     'trip_allocation':';'.join(f'{s}:{nn}' for s,nn in path)})
        best_energy=min(best_energy,e)
    return rows,locals

def singleton_baseline(data,routes):
    rm={r['service_id']:r for r in routes};batches=[]
    for b in data['boxes']:
        sol,_=solve_service([b],data['transport_models'],rm[b['service_id']],order='ENT')
        if sol is None:raise ValueError('单箱基线不可行')
        batches.extend(sol)
    return {'name':'single_box_energy_best','trips':len(batches),'energy_kwh':sum(p['energy_kwh'] for p in batches),'operation_time_s':sum(p['operation_time_s'] for p in batches)}
