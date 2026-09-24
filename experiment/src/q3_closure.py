"""Q3→Q4严格继承的闭环修复，不在Q4复制中继任务。
Python3.13.5；参数见closure_config.py、q3_config.py。
优先筛选已独立验证的Q3候选；只有全部候选均不满足严格三分区时，
才枚举单架次分量的专属中继修复。最终方案重新通过独立验证后才供Q4读取。
这是明确的有限候选修复方法，不是联合问题全局最优证明，也不把旧Q4副本解释隐瞒掉。
"""
from pathlib import Path
import copy,json,math,shutil
from collections import Counter
from io_utils import read_csv,write_csv,save_json,sha256
from q2_physics import Problem,charge_duration
from q3_joint import relay_geometry
from q3_communication import Radio
from q3_trajectory import load_phases,serialize_phases
from q3_relay_schedule import communication_atoms,export_communication
from solve_q3 import geometry_from_q2
from solve_q2 import export_plan
from solve_q4 import FrozenQ3,strict_no_copy
from q3_config import Q3CFG
from closure_config import CLOSURE_CFG

class FixedProblem(Problem):
    """共享物理模型、显式任务时刻的导出器；不通过最早可用解码器悄悄改排程。"""
    def __init__(self,root,data,geom,records):
        super().__init__(root,data,geom);self.fixed=records
    def schedule(self,trips,detailed=False):
        rows=[];hard=soft=wc=energy=cmax=0.
        for tr in trips:
            ev=self.evaluate(tr)
            if ev is None:raise ValueError('闭环修复中出现物理不可行货箱组合')
            r=self.fixed[tr];s=r['start'];end=s+ev['duration']
            energy+=ev['energy'];cmax=max(cmax,end)
            for i,off in ev['offsets']:
                t=s+off;hard+=max(0.,t-self.hard[i]);soft+=float(self.priority[i])*max(0.,t-self.expected[i]);wc+=float(self.priority[i])*t
            if detailed:rows.append(dict(trip=tr,eval=ev,start=s,end=end,drone_id=r['drone_id'],battery_id=r['battery_id'],charge_start=end,charge_end=end+ev['charge']))
        return dict(hard_late_s=hard,source_hard_late_s=hard,communication_window_violations=0,
                    weighted_tardiness_s=soft,weighted_completion_s=wc,makespan_s=cmax,energy_kwh=energy,trips=len(trips),records=rows)

def run_closure_repair(root):
    root=Path(root);out=root/'results/q3';d=json.loads((root/'data/cleaned/model_inputs.json').read_text());radio=Radio(root,d)
    frozen=FrozenQ3(root);strict_before=strict_no_copy(frozen)
    target=CLOSURE_CFG.require_strict_groups
    if strict_before['component_count']>=target:
        save_json(out/'closure_repair_certificate.json',{'repair_required':False,'strict_components_before':strict_before['components'],'strict_components_after':strict_before['components']});return
    # 完整保留前一阶段独立Q3可行方案，作为失去3分区闭环能力的真实对照。
    baseline=out/'alternatives/uncoupled_baseline';baseline.mkdir(parents=True,exist_ok=True)
    for p in list(out.iterdir()):
        if p.is_file():shutil.copyfile(p,baseline/p.name)
    # 先检查已真实求解并独立验证的备选，避免不必要的专属中继/延迟修复。
    # 该筛选发生在Q3定稿前；Q4只读取冻结后的一个最终方案。
    from solve_q4 import UnionFind
    existing=[]
    for folder in sorted((out/'alternatives').iterdir()):
        if not (folder/'trips.csv').exists() or not (folder/'relay_missions.json').exists():continue
        trrows=read_csv(folder/'trips.csv');com=read_csv(folder/'Q3_通信保障.csv')
        uf=UnionFind(frozen.services);vis={r['trip_id']:r['visit_order'].split(';') for r in trrows};deps={}
        for ss0 in vis.values():
            for v in ss0[1:]:uf.union(ss0[0],v)
        for c in com:
            if c['保障方式']=='中继':deps.setdefault(c['中继架次编号'],set()).update(vis[c['运输架次编号']])
        for vv in deps.values():
            ss0=sorted(vv)
            for v in ss0[1:]:uf.union(ss0[0],v)
        summ=json.loads((folder/'summary.json').read_text());mm=json.loads((folder/'relay_missions.json').read_text())
        check=json.loads((folder/'independent_validation.json').read_text())
        valid=check['checks_failed']==0 and check['continuous_atoms_failed']==0
        joint=max(summ['makespan_s'],max(m['return_s'] for m in mm));energy=summ['energy_kwh']+sum(m['energy_kwh'] for m in mm)
        row={'candidate':folder.name,'component_count':len(uf.groups()),'components':uf.groups(),
            'independently_validated':valid,'strict_K3_feasible':len(uf.groups())>=target and valid,
            'weighted_tardiness_s':summ['weighted_tardiness_s'],'joint_makespan_s':joint,'total_energy_kwh':energy,
            'transport_sorties':summ['trips'],'relay_sorties':len(mm)}
        existing.append(row)
    write_csv(out/'closure_existing_candidates.csv',existing)
    admissible=[x for x in existing if x['strict_K3_feasible']]
    if admissible:
        chosen=min(admissible,key=lambda x:(x['weighted_tardiness_s'],x['joint_makespan_s'],x['total_energy_kwh'],x['transport_sorties']+x['relay_sorties'],x['candidate']))
        folder=out/'alternatives'/chosen['candidate'];oldsummary=json.loads((baseline/'summary.json').read_text())
        for p in sorted(folder.iterdir()):
            if p.is_file():shutil.copyfile(p,out/p.name)
        mm=json.loads((out/'relay_missions.json').read_text());ss=json.loads((out/'summary.json').read_text())
        atoms=read_csv(out/'communication_atoms.csv')
        ss.update(transport_makespan_s=ss['makespan_s'],joint_makespan_s=chosen['joint_makespan_s'],
            relay_energy_kwh=sum(m['energy_kwh'] for m in mm),total_energy_kwh=chosen['total_energy_kwh'],relay_trips=len(mm),
            relay_bodies_used=len({m['relay_drone_id'] for m in mm}),relay_modules_used=len({m['energy_module_id'] for m in mm}),
            relay_min_soc_fraction=min(m['return_soc_fraction'] for m in mm),
            communication_atoms=len(atoms),communication_boundary_points=sum(a['is_boundary']=='True' for a in atoms),
            global_optimality_proven=False,conditional_relay_milp_optimal=all(json.loads((out/'relay_milp_certificate.json').read_text())[k]==0 for k in ('stage1_status','stage2_status')),
            conditional_relay_milp_scope='仅所选候选的固定运输/悬停点/实体顺序及规划保护余量MILP子问题，不是Q3全局',
            radio_coordinate_model=oldsummary['radio_coordinate_model'],scenario='Q3_strict_inheritance_pool_selection',
            closure_choice='Q3定稿时按严格三分区可行性筛选独立验证的实算候选，再按及时性、联合返回、总能耗、架次数择优；Q4不改任务。')
        save_json(out/'summary.json',ss)
        if (out/'solution_genome.json').exists():shutil.copyfile(out/'solution_genome.json',out/'selected_genome.json')
        save_json(out/'initial_service_windows.json',mm)
        write_csv(out/'trajectory_phases.csv',serialize_phases(load_phases(root,d,'results/q3')))
        for stale in ('closure_repair_candidates.csv','closure_transport_lineage.csv','fixed_schedule.csv'):(out/stale).unlink(missing_ok=True)
        finalstrict=strict_no_copy(FrozenQ3(root))
        cert={'repair_required':True,'repair_method':'verified_candidate_pool_selection_before_Q3_freeze',
            'status':'selected_existing_independently_verified_candidate_pending_final_recheck',
            'selected_candidate':chosen,'candidate_count':len(existing),'feasible_candidates':len(admissible),
            'strict_components_before':strict_before['components'],'strict_components_after':finalstrict['components'],
            'baseline_summary':oldsummary,'final_summary':ss,'Q4_replication_allowed':False,'source_data_modified':False,
            'added_Q4_relay_missions':0,'dedicated_relay_fallback_used':False,
            'explanation':'最终Q3取先前搜索中已计算的可行备选；相对最快独立Q3牺牲少量完工时间，换取严格K3可分区。不是全局最优证明。'}
        save_json(out/'closure_repair_certificate.json',cert)
        return cert
    oldsummary=json.loads((out/'summary.json').read_text());oldmissions=json.loads((out/'relay_missions.json').read_text());sites=json.loads((out/'sites.json').read_text())
    source_trips=read_csv(out/'trips.csv');geom=geometry_from_q2(root);base=Problem(root,d,geom)
    tripkeys={r['trip_id']:(r['model_id'],tuple(r['visit_order'].split(';')),tuple(sorted(base.box_index[b] for b in r['box_ids'].split(';')))) for r in source_trips}
    fixed={tripkeys[r['trip_id']]:dict(start=float(r['start_s']),drone_id=r['drone_id'],battery_id=r['battery_id']) for r in source_trips}
    keys=list(fixed);phases=load_phases(root,d,'results/q3');model=d['relay_models'][0];full=d['relay_energy'][0]['full_charge_s'];candidates=[];winners=[]
    # 原中继任务完全保留；附加任务只能在某架中继返回并周转后出发。
    drone_ready={r['drone_id']:max((m['turnaround_end_s'] for m in oldmissions if m['relay_drone_id']==r['drone_id']),default=0.) for r in d['relay_drones']}
    module_ready={f'R-ENG-{i+1:02d}':max((m['charge_end_s'] for m in oldmissions if m['energy_module_id']==f'R-ENG-{i+1:02d}'),default=0.) for i in range(d['relay_energy'][0]['count'])}
    for comp in frozen.transport_components:
        tids=[r['trip_id'] for r in source_trips if set(r['visit_order'].split(';'))&set(comp)]
        if len(tids)!=1:continue
        tid=tids[0];key=tripkeys[tid];ev=base.evaluate(key);g=key[0];oldstart=fixed[key]['start'];pp=[p for p in phases if p['trip_id']==tid]
        body_pool={body:max((rr['start']+base.evaluate(k)['duration'] for k,rr in fixed.items() if k!=key and rr['drone_id']==body),default=0.) for body in base.fleet[g]}
        battery_pool={bid:max((rr['start']+base.evaluate(k)['duration']+base.evaluate(k)['charge'] for k,rr in fixed.items() if k!=key and rr['battery_id']==bid),default=0.) for bid in base.batteries[g]}
        body=min(body_pool,key=lambda x:(body_pool[x],x));bat=min(battery_pool,key=lambda x:(battery_pool[x],x))
        ready_t=max(body_pool[body],battery_pool[bat]);rbody=min(drone_ready,key=lambda x:(drone_ready[x],x));module=min(module_ready,key=lambda x:(module_ready[x],x))
        for j,site in enumerate(sites):
            row=dict(candidate_id=f'{tid}-site{j+1}',services=';'.join(comp),source_trip_id=tid,site_id=site['site_id'] if 'site_id' in site else f'site{j+1}')
            try:
                geo=relay_geometry(radio,site,model);dummy=dict(oldmissions[j]);dummy.update(geo)
                parts,_=communication_atoms(radio,pp,[dummy],planning=True)
                nd=[a for a in parts if not a['direct']]
                if not nd:row.update(status='not_needed_all_direct');candidates.append(row);continue
                if radio.link(radio.gateway,geo['point'],'backhaul')['margin_db']<Q3CFG.search_budget_buffer_db-1e-8:raise ValueError('回传链路不足规划裕度')
                lo=min(a['start_s'] for a in nd)-oldstart;hi=max(a['end_s'] for a in nd)-oldstart
                lead=model['prepare_s']+geo['outbound_flight_s']+model['link_setup_s'];buffer=Q3CFG.service_time_buffer_s
                start=max(oldstart,ready_t,max(drone_ready[rbody],module_ready[module])+lead+buffer-lo)
                hard=sum(max(0.,start+off-base.hard[i]) for i,off in ev['offsets']);soft=sum(float(base.priority[i])*max(0.,start+off-base.expected[i]) for i,off in ev['offsets'])
                if hard>1e-7:row.update(status='hard_deadline_infeasible',hard_late_s=hard);candidates.append(row);continue
                rs=start+lo-buffer-lead;arrive=rs+model['prepare_s']+geo['outbound_flight_s'];linked=arrive+model['link_setup_s'];end=start+hi+buffer;returned=end+geo['inbound_flight_s']
                energy=geo['flight_energy_kwh']+(model['hover_power_kw']+model['communication_power_kw'])*(end-arrive)/Q3CFG.seconds_per_hour;soc=1-energy/model['usable_energy_kwh']
                if soc<model['reserve_fraction']-1e-8:raise ValueError('附加中继电量不足')
                mission=dict(relay_trip_id=f'Q3-R-{len(oldmissions)+1:03d}',relay_drone_id=rbody,energy_module_id=module,model_id=model['model_id'],site_id=row['site_id'],
                    start_s=rs,arrival_s=arrive,link_complete_s=linked,service_end_s=end,return_s=returned,turnaround_end_s=returned+model['turnaround_s'],
                    energy_kwh=energy,return_soc_fraction=soc,charge_duration_s=charge_duration(soc,full),charge_end_s=returned+charge_duration(soc,full),**geo)
                trial=copy.deepcopy(fixed);trial[key]=dict(start=start,drone_id=body,battery_id=bat)
                newcmax=max(oldsummary['joint_makespan_s'],start+ev['duration'],returned)
                row.update(status='feasible_candidate',transport_start_s=start,relay_start_s=rs,joint_makespan_s=newcmax,extra_relay_energy_kwh=energy,weighted_extra_tardiness_s=soft)
                score=(soft,newcmax,oldsummary['total_energy_kwh']+energy,row['candidate_id'])
                winners.append((score,trial,mission,site,row))
            except ValueError as e:row.update(status='spatial_or_energy_infeasible',reason=str(e))
            candidates.append(row)
    write_csv(out/'closure_repair_candidates.csv',candidates,fields=list(dict.fromkeys(k for r in candidates for k in r)))
    if not winners:raise RuntimeError('严格三组闭环修复候选全部失败；不允许将Q4复制中继伪装为原题解。')
    score,chosen,newmission,site,row=min(winners,key=lambda x:x[0]);pb=FixedProblem(root,d,geom,chosen)
    export_plan(pb,keys,out,'Q3_strict_Q4_closed_loop',True,trip_prefix='Q3-T',template_prefix='Q3')
    newphases=load_phases(root,d,'results/q3');missions=oldmissions+[newmission]
    rel,atoms,cert=export_communication(root,out,radio,d,newphases,missions,pb.schedule(keys)['makespan_s'],optimize=False)
    write_csv(out/'trajectory_phases.csv',serialize_phases(newphases));save_json(out/'sites.json',sites+[site]);save_json(out/'initial_service_windows.json',missions)
    save_json(out/'selected_genome.json',{'trips':keys,'schedule_rule':'explicit_closure_repair_times_not_earliest_decoder'})
    write_csv(out/'fixed_schedule.csv',[{'model_id':k[0],'box_ids':';'.join(base.bid[i] for i in k[2]),**v} for k,v in chosen.items()])
    newtr=read_csv(out/'trips.csv');byboxes={r['box_ids']:r for r in newtr}
    lineage=[]
    for r in source_trips:
        x=byboxes[r['box_ids']];lineage.append({'source_trip_id':r['trip_id'],'final_trip_id':x['trip_id'],'services':r['visit_order'],
             'source_start_s':float(r['start_s']),'final_start_s':float(x['start_s']),'shift_s':float(x['start_s'])-float(r['start_s']),
             'source_drone_id':r['drone_id'],'final_drone_id':x['drone_id'],'box_ids':r['box_ids'],
             'payload_route_energy_unchanged':all(r[f]==x[f] for f in ('model_id','box_ids','visit_order','energy_kwh'))})
    write_csv(out/'closure_transport_lineage.csv',lineage)
    ss=json.loads((out/'summary.json').read_text());ss.update(transport_makespan_s=ss['makespan_s'],joint_makespan_s=max(ss['makespan_s'],max(m['return_s'] for m in rel)),
        relay_energy_kwh=sum(m['energy_kwh'] for m in rel),total_energy_kwh=ss['energy_kwh']+sum(m['energy_kwh'] for m in rel),relay_trips=len(rel),
        relay_bodies_used=len({m['relay_drone_id'] for m in rel}),relay_modules_used=len({m['energy_module_id'] for m in rel}),relay_min_soc_fraction=min(m['return_soc_fraction'] for m in rel),
        communication_atoms=len(atoms),communication_boundary_points=sum(a['is_boundary'] for a in atoms),global_optimality_proven=False,conditional_relay_milp_optimal=False,
        radio_coordinate_model=oldsummary['radio_coordinate_model'],closure_choice='在Q3定稿前增加下游可分区性要求；Q4绝不再复制、拆分或改排中继任务')
    save_json(out/'summary.json',ss)
    strict_after=strict_no_copy(FrozenQ3(root))
    if strict_after['component_count']<target:raise AssertionError('修复未产生足够严格不可拆单元')
    certificate={'repair_required':True,'status':'candidate_constructed_pending_independent_physics_validation','selected_candidate':row,
        'search_family':CLOSURE_CFG.dedicated_relay_search_family,'candidate_count':len(candidates),'feasible_candidates':len(winners),
        'strict_components_before':strict_before['components'],'strict_components_after':strict_after['components'],
        'baseline_summary':oldsummary,'final_summary':ss,'Q4_replication_allowed':False,'source_data_modified':False,
        'changed_transport_sorties':sum(abs(r['shift_s'])>1e-8 for r in lineage),'added_Q3_relay_missions':1,
        'explanation':'先修订并独立验证Q3，再冻结给Q4；旧独立Q3留作对照。候选族内字典序择优，不声称Q3或四问联合全局最优。'}
    save_json(out/'closure_repair_certificate.json',certificate)
    base.evaluate.cache_clear();pb.evaluate.cache_clear();return certificate
