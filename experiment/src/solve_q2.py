"""问题二：重新联合组批/访问次序/机型/实体/电池/时间，输出全部交付记录。
Python 3.13.5；依赖与核心配置分别见requirements.txt及q2_config.py。
不读取参考答案或旧方案作为求解结果；第一问仅作为物理继承与对照基线。
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter,defaultdict
from dataclasses import asdict
import copy,json,math,time
from q2_config import Q2CFG
from config import CFG
from q2_physics import Problem,charge_duration
from q2_search import greedy_initial,search,objective,urgency_order
from q2_bounds import workload_lower_bound
from io_utils import read_csv,write_csv,save_json


def export_plan(pb,trips,out,name,write_template=False,trip_prefix="Q2",template_prefix="Q2"):
    """所有表由同一解对象导出；时刻保持浮点全精度，显示小数不改变存储。"""
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    result=pb.schedule(trips,True);records=sorted(result.pop('records'),key=lambda r:(r['start'],r['drone_id'],r['end'],r['trip']))
    tasks=[];deliveries=[];legs=[];charges=[];events=[];assignment=[]
    for num,r in enumerate(records,1):
        tid=f'{trip_prefix}-{num:03d}';g,stops,ids=r['trip'];m=pb.models[g];ev=r['eval']
        start=r['start'];t=start+m['prepare_s']+len(ids)*m['load_per_box_s'];q=ev['weight'];vol=ev['volume'];u='O01'
        events.append({'resource_type':'drone','resource_id':r['drone_id'],'trip_id':tid,'phase':'prepare_load','start_s':start,'end_s':t})
        for k,v in enumerate(stops+('O01',),1):
            ar=pb.geom[u,v];L=m['empty_range_m']-(m['empty_range_m']-m['full_range_m'])*(q/m['max_payload_kg'])**CFG.range_load_exponent
            ehor=CFG.horizontal_energy_multiplier*m['usable_energy_kwh']*ar['distance_m']/L
            eup=CFG.climb_energy_multiplier*(m['empty_mass_kg']+q)*CFG.gravity_m_s2*ar['climb_m']/(m['climb_efficiency']*CFG.joules_per_kwh)
            climb=ar['climb_m']/m['climb_speed_mps'];cruise=ar['distance_m']/m['cruise_speed_mps'];descent=ar['descent_m']/m['descent_speed_mps']
            legstart=t
            for phase,dur in [('climb',climb),('cruise',cruise),('descent',descent)]:
                events.append({'resource_type':'drone','resource_id':r['drone_id'],'trip_id':tid,'phase':phase,'start_s':t,'end_s':t+dur});t+=dur
            arrival=t;service_ids=[]
            if v!='O01':
                service_ids=sorted((i for i in ids if pb.sid[i]==v),key=lambda i:pb.delivery_key[i])
                st=t;t+=m['handoff_base_s']
                for ix in service_ids:
                    t+=m['handoff_per_box_s'];b=pb.boxes[ix]
                    hard=None if not math.isfinite(pb.hard[ix]) else float(pb.hard[ix])
                    deliveries.append({'box_id':b['box_id'],'trip_id':tid,'service_id':v,'model_id':g,'drone_id':r['drone_id'],
                        'delivery_complete_s':t,'expected_s':b['expected_s'],'hard_deadline_s':hard,
                        'first_deadline_s':b['first_deadline_s'],'is_first_batch':b['is_first_batch'],
                        'is_medical':b['material_type']=='医疗物资','priority':b['priority'],
                        'tardiness_s':max(0.0,t-b['expected_s']),'hard_slack_s':None if hard is None else hard-t,
                        'weight_kg':b['weight_kg'],'volume_m3':b['volume_m3']})
                    q-=b['weight_kg'];vol-=b['volume_m3']
                    assignment.append({'box_id':b['box_id'],'trip_id':tid,'service_id':v,'stop_index':k})
                events.append({'resource_type':'drone','resource_id':r['drone_id'],'trip_id':tid,'phase':'handoff','start_s':st,'end_s':t})
            legs.append({'trip_id':tid,'leg_index':k,'model_id':g,'from_id':u,'to_id':v,'departure_s':legstart,
                'arrival_s':arrival,'handoff_complete_s':t,'remaining_payload_at_departure_kg':ev['weight'] if k==1 else legs[-1]['remaining_payload_after_handoff_kg'],
                'remaining_payload_after_handoff_kg':q,'remaining_volume_after_handoff_m3':max(0.0,vol),
                'distance_m':ar['distance_m'],'terrain_max_m':ar['terrain_max_m'],'cruise_altitude_m':ar['cruise_altitude_m'],
                'climb_m':ar['climb_m'],'descent_m':ar['descent_m'],'flight_s':climb+cruise+descent,
                'horizontal_energy_kwh':ehor,'climb_energy_kwh':eup,'leg_energy_kwh':ehor+eup,
                'delivered_box_ids':';'.join(pb.bid[ix] for ix in service_ids)})
            u=v
        if abs(t-r['end'])>1e-7:raise AssertionError('导出时序与优化时序不一致')
        tasks.append({'trip_id':tid,'drone_id':r['drone_id'],'model_id':g,'battery_id':r['battery_id'],
            'start_s':start,'takeoff_s':start+ev['preparation'],'visit_order':';'.join(stops),'route':'O01→'+'→'.join(stops)+'→O01',
            'return_s':r['end'],'energy_kwh':ev['energy'],'return_soc_fraction':ev['soc'],'initial_soc_fraction':1.0,
            'weight_kg':ev['weight'],'volume_m3':ev['volume'],'box_count':len(ids),'box_ids':';'.join(pb.bid[i] for i in ids),
            'stop_count':len(stops),'flight_time_s':ev['flight'],'operation_time_s':ev['duration'],
            'preparation_load_s':ev['preparation'],'handoff_s':ev['duration']-ev['preparation']-ev['flight']})
        charges.append({'battery_id':r['battery_id'],'model_id':g,'trip_id':tid,'drone_id':r['drone_id'],
            'task_start_s':start,'return_s':r['end'],'return_soc_fraction':ev['soc'],'charge_start_s':r['end'],
            'charge_end_s':r['end']+ev['charge'],'charge_duration_s':ev['charge'],'charged_soc_fraction':1.0})
    deliveries.sort(key=lambda d:d['box_id']);assignment.sort(key=lambda d:d['box_id'])
    write_csv(out/'trips.csv',tasks);write_csv(out/'box_deliveries.csv',deliveries);write_csv(out/'legs.csv',legs)
    write_csv(out/'battery_cycles.csv',charges);write_csv(out/'phase_events.csv',events);write_csv(out/'box_assignment.csv',assignment)
    drones=[];bats=[]
    for g in pb.models:
        for uid in pb.fleet[g]:
            rr=[r for r in tasks if r['drone_id']==uid]
            drones.append({'drone_id':uid,'model_id':g,'trip_count':len(rr),'operation_time_s':sum(r['operation_time_s'] for r in rr),
                'last_return_s':max((r['return_s'] for r in rr),default=0.0),'utilization':sum(r['operation_time_s'] for r in rr)/result['makespan_s'],
                'energy_kwh':sum(r['energy_kwh'] for r in rr),'total_weight_kg':sum(r['weight_kg'] for r in rr)})
        for bid in pb.batteries[g]:
            rr=sorted((r for r in charges if r['battery_id']==bid),key=lambda r:r['task_start_s'])
            bats.append({'battery_id':bid,'model_id':g,'usage_count':len(rr),'different_drones':';'.join(sorted({r['drone_id'] for r in rr})),
                'last_return_soc_fraction':rr[-1]['return_soc_fraction'] if rr else 1.0,
                'last_charge_complete_s':rr[-1]['charge_end_s'] if rr else 0.0,
                'total_charge_s':sum(r['charge_duration_s'] for r in rr)})
    write_csv(out/'drone_usage.csv',drones);write_csv(out/'battery_usage.csv',bats)
    result.update({'scenario':name,'feasible':result['hard_late_s']<=Q2CFG.numeric_tolerance,'delivered_boxes':len(deliveries),
        'delivered_weight_kg':sum(b['weight_kg'] for b in deliveries),'delivered_volume_m3':sum(b['volume_m3'] for b in deliveries),
        'medical_boxes':sum(b['is_medical'] for b in deliveries),'first_batch_boxes':sum(b['is_first_batch'] for b in deliveries),
        'medical_on_time':sum(b['is_medical'] and b['delivery_complete_s']<=b['expected_s']+1e-7 for b in deliveries),
        'first_batch_on_time':sum(b['is_first_batch'] and b['delivery_complete_s']<=b['first_deadline_s']+1e-7 for b in deliveries),
        'all_expected_on_time':sum(b['tardiness_s']<=1e-7 for b in deliveries),'model_trip_counts':dict(Counter(r['model_id'] for r in tasks)),
        'multipoint_trips':sum(r['stop_count']>1 for r in tasks),'max_stops_in_solution':max(r['stop_count'] for r in tasks),
        'min_return_soc_fraction':min(r['return_soc_fraction'] for r in tasks),'min_hard_deadline_slack_s':min(b['hard_slack_s'] for b in deliveries if b['hard_slack_s'] is not None),
        'battery_reuses':sum(max(0,r['usage_count']-1) for r in bats),'battery_units_used':sum(r['usage_count']>0 for r in bats),
        'battery_sharing_across_drones_units':sum(len(r['different_drones'].split(';'))>1 for r in bats),
        'flight_time_sum_s':sum(r['flight_time_s'] for r in tasks),'operation_time_sum_s':sum(r['operation_time_s'] for r in tasks),
        'last_box_delivery_s':max(b['delivery_complete_s'] for b in deliveries),'optimality':'verified_feasible_heuristic_upper_bound_not_global_optimum'})
    save_json(out/'summary.json',result)
    save_json(out/'solution_genome.json',{'trips':trips,'box_index_order':list(pb.bid),'schedule_rule':'earliest_available_compatible_drone_and_battery'})
    if write_template:
        write_csv(out/f'{template_prefix}_运输架次.csv',[{'架次编号':r['trip_id'],'无人机编号':r['drone_id'],'机型编号':r['model_id'],
            '电池编号':r['battery_id'],'开始时刻（s）':r['start_s'],'访问服务区顺序':r['visit_order'],
            '返回O01时刻（s）':r['return_s'],'架次能耗（kWh）':r['energy_kwh']} for r in tasks])
        write_csv(out/f'{template_prefix}_逐箱交付.csv',[{'货箱编号':b['box_id'],'架次编号':b['trip_id'],'服务区编号':b['service_id'],
            '交付完成时刻（s）':b['delivery_complete_s']} for b in deliveries])
    return result


def optimize_family(pb,out,maxstops,label):
    history=[];stats=[];initials=[];best=None;bm=None
    for seed in Q2CFG.seeds:
        tr=greedy_initial(pb,seed,maxstops)
        initial=pb.schedule(tr)
        initials.append({'seed':seed,'family':label,**{k:v for k,v in initial.items() if k!='records'}})
        tr,m,h,s=search(pb,tr,seed,maxstops=maxstops)
        history.extend({'family':label,**x} for x in h);stats.append({'family':label,'round_kind':'independent_warmup',**s})
        if best is None or objective(m)<objective(bm):best=tr;bm=m
    for rd,seed in enumerate(Q2CFG.polish_seeds,1):
        best,bm,h,s=search(pb,best,seed,iterations=Q2CFG.polish_iterations,lns=Q2CFG.polish_lns_iterations,maxstops=maxstops)
        history.extend({'family':label,**x} for x in h);stats.append({'family':label,'round_kind':'sequential_refinement',**s})
        print(f'    {label} refine {rd}/{len(Q2CFG.polish_seeds)}: hard={bm["hard_late_s"]:.3f}, tardy={bm["weighted_tardiness_s"]:.3f}, Cmax={bm["makespan_s"]:.6f}, E={bm["energy_kwh"]:.6f}, N={bm["trips"]}',flush=True)
    write_csv(out/f'{label}_search_history.csv',history);write_csv(out/f'{label}_search_rounds.csv',stats);write_csv(out/f'{label}_initials.csv',initials)
    return best


def run_q2(root,data=None):
    root=Path(root);out=root/'results/q2';out.mkdir(parents=True,exist_ok=True)
    if data is None:data=json.loads((root/'data/cleaned/model_inputs.json').read_text('utf-8'))
    pb=Problem(root,data);save_json(out/'solver_config.json',asdict(Q2CFG))
    # 生成库存中的14个可追溯资源编号，不是额外增加电池数量。
    write_csv(root/'data/cleaned/transport_battery_units.csv',[{'battery_id':bid,'model_id':g,'initial_soc_fraction':1.0,
        'full_charge_s':pb.battery_par[g]['full_charge_s'],'provenance':'按原共享电池库存顺序编号，库存含初装电池'} for g in sorted(pb.models) for bid in pb.batteries[g]])
    inherited=[pb.trip(r['model_id'],(r['service_id'],),[pb.box_index[x] for x in r['box_ids'].split(';')]) for r in read_csv(root/'results/q1/batches_NET.csv')]
    inherited=urgency_order(pb,inherited)
    base=export_plan(pb,inherited,out/'experiments/q1_frozen','q1_frozen')
    main=optimize_family(pb,out,Q2CFG.maximum_stops,'multipoint')
    sm=export_plan(pb,main,out,'main',write_template=True)
    if not sm['feasible']:raise RuntimeError('第二问未获得硬时限可行解；拒绝生成可提交标志')
    direct=optimize_family(pb,out,1,'direct_only')
    sd=export_plan(pb,direct,out/'experiments/direct_only','direct_only')
    energy=main;history=[];rounds=[];cap=sm['makespan_s']*Q2CFG.alternative_energy_budget_ratio
    for seed in Q2CFG.energy_seeds:
        energy,me,h,s=search(pb,energy,seed,iterations=Q2CFG.energy_iterations,lns=Q2CFG.energy_lns_iterations,mode='energy',cap=cap)
        history+=h;rounds.append(s)
    se=export_plan(pb,energy,out/'experiments/energy_tradeoff','energy_tradeoff')
    write_csv(out/'energy_search_history.csv',history);write_csv(out/'energy_search_rounds.csv',rounds)
    compare=[]
    for s in [base,sd,sm,se]:
        compare.append({k:s[k] for k in ['scenario','feasible','hard_late_s','weighted_tardiness_s','makespan_s','energy_kwh','trips','multipoint_trips','min_return_soc_fraction','all_expected_on_time']})
    write_csv(out/'scenario_comparison.csv',compare)
    lower=workload_lower_bound(pb,out)
    sm.update({'makespan_lower_bound_s':lower['lower_bound_s'],
        'relative_upper_lower_gap':(sm['makespan_s']-lower['lower_bound_s'])/sm['makespan_s'],
        'zero_tardiness_global_lower_bound_attained':sm['weighted_tardiness_s']==0,
        'energy_tradeoff_makespan_cap_s':cap,'energy_tradeoff_cap_ratio':Q2CFG.alternative_energy_budget_ratio,
        'main_objective':'hard feasibility; priority-weighted tardiness; Cmax; energy; number of trips',
        'same_search_budget_direct_and_multi':True,
        'algorithm_limits':['启发式箱级邻域与退火，未证明Cmax/E/N全局最优','一次架次不重复访问同一服务区','点内交接采用公开的截止时间优先规则','机身和电池从准备开始独占；未给工位数，不虚构单工位约束']})
    save_json(out/'summary.json',sm)
    return sm
