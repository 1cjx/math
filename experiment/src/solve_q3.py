"""第三问完整联合求解：候选覆盖→通信时间窗运输搜索→中继归属/时段MILP。
Python3.13.5。全部配置在q3_config.py；随机种子/迭代预算固定。
"""
from pathlib import Path
import copy,gc,json,time
from q3_config import Q3CFG
from io_utils import read_csv,write_csv,save_json
from q3_communication import Radio
from q3_candidates import candidate_sites
from q3_joint import JointProblem,make_relay_missions
from q2_search import greedy_initial,search,objective
from solve_q2 import export_plan
from q3_trajectory import load_phases,serialize_phases
from q3_relay_schedule import export_communication


def geometry_from_q2(root):
    return {(x['from_id'],x['to_id']):{k:float(v) if k not in ('from_id','to_id') else v for k,v in x.items()} for x in read_csv(Path(root)/'results/q2/arc_geometry.csv')}


def run_q3(root,data):
    root=Path(root);out=root/'results/q3';out.mkdir(parents=True,exist_ok=True);radio=Radio(root,data);geom=geometry_from_q2(root)
    families=candidate_sites(root,data,radio,geom,out/'candidates');trace=[];attempts=[];best=None;best_score=None
    # 以明确预算筛选首个可行四架次选址结构。未将没试的结构称为不可行。
    for fi,sites in enumerate(families):
        try:
            missions=make_relay_missions(radio,sites);pb=JointProblem(root,data,radio,sites,missions,geom)
            tr=greedy_initial(pb,Q3CFG.transport_candidate_seeds[0],len(data['services']))
        except ValueError as exc:
            attempts.append({'family_rank':fi+1,'status':'constructor_rejected','reason':str(exc)});continue
        for seed in Q3CFG.transport_candidate_seeds:
            tr,m,h,stats=search(pb,tr,seed,iterations=Q3CFG.transport_candidate_iterations,lns=Q3CFG.transport_candidate_lns)
            trace.append({'round':'initial','family_rank':fi+1,'seed':seed,**{k:v for k,v in m.items() if k!='records'}})
            print('Q3 initial',fi+1,seed,m['hard_late_s'],m['makespan_s'],flush=True)
        attempts.append({'family_rank':fi+1,'status':'feasible' if m['hard_late_s']<=1e-8 else 'budget_no_feasible_found','hard_late_s':m['hard_late_s']})
        if m['hard_late_s']>1e-8:
            pb.evaluate.cache_clear();del pb;gc.collect();continue
        export_plan(pb,tr,out,'Q3_main',True,trip_prefix='Q3-T',template_prefix='Q3')
        rel,atoms,cert=export_communication(root,out,radio,data,load_phases(root,data,'results/q3'),missions,m['makespan_s'])
        score=(m['weighted_tardiness_s'],max(m['makespan_s'],max(r['return_s'] for r in rel)),m['energy_kwh']+sum(r['energy_kwh'] for r in rel),len(tr)+len(rel))
        best=(copy.deepcopy(tr),copy.deepcopy(missions),copy.deepcopy(rel),copy.deepcopy(sites));best_score=score
        attempts[-1]['joint_cmax_s']=score[1];pb.evaluate.cache_clear();del pb;gc.collect();break
    if best is None:raise RuntimeError('候选/固定搜索预算内没有Q3可行解；禁止输出形式上填满但不可行的答案')
    # 外层根据已优化服务结束点更新机身迁移窗口，内层重新组批、排序、分配电池。
    tr,missions,rel,sites=best
    for rd in range(Q3CFG.outer_polish_rounds):
        initial=make_relay_missions(radio,sites,tuple(r['service_end_s'] for r in rel[:2]))
        pb=JointProblem(root,data,radio,sites,initial,geom)
        if pb.schedule(tr) is None:
            pb.evaluate.cache_clear();del pb;gc.collect();break
        trial=tr
        for k in range(len(Q3CFG.transport_candidate_seeds)):
            seed=Q3CFG.outer_polish_seed+rd*len(Q3CFG.transport_candidate_seeds)+k
            trial,m,h,stats=search(pb,trial,seed,iterations=Q3CFG.outer_polish_iterations,lns=Q3CFG.outer_polish_lns)
            trace.append({'round':f'polish_{rd+1}','family_rank':fi+1,'seed':seed,**{q:v for q,v in m.items() if q!='records'}})
            print('Q3 polish',rd+1,seed,m['hard_late_s'],m['makespan_s'],flush=True)
        if m['hard_late_s']<=1e-8:
            alt=out/'alternatives'/f'polish_{rd+1}';alt.mkdir(parents=True,exist_ok=True)
            export_plan(pb,trial,alt,'Q3_polish',True,trip_prefix='Q3-T',template_prefix='Q3')
            newrel,atoms,cert=export_communication(root,alt,radio,data,load_phases(root,data,str(alt.relative_to(root))),initial,m['makespan_s'])
            sc=(m['weighted_tardiness_s'],max(m['makespan_s'],max(r['return_s'] for r in newrel)),m['energy_kwh']+sum(r['energy_kwh'] for r in newrel),len(trial)+len(newrel))
            if sc<best_score:
                best=(copy.deepcopy(trial),copy.deepcopy(initial),copy.deepcopy(newrel),sites);best_score=sc
                tr,missions,rel,sites=best
        pb.evaluate.cache_clear();del pb;gc.collect()
    tr,missions,rel,sites=best;pb=JointProblem(root,data,radio,sites,missions,geom)
    export_plan(pb,tr,out,'Q3_main',True,trip_prefix='Q3-T',template_prefix='Q3')
    phases=load_phases(root,data,'results/q3');rel,atoms,cert=export_communication(root,out,radio,data,phases,missions,pb.schedule(tr)['makespan_s'])
    write_csv(out/'trajectory_phases.csv',serialize_phases(phases));save_json(out/'sites.json',sites);save_json(out/'initial_service_windows.json',missions)
    save_json(out/'selected_genome.json',{'trips':tr});write_csv(out/'search_trace.csv',trace);save_json(out/'family_attempts.json',attempts)
    s=json.loads((out/'summary.json').read_text());s.update({'transport_makespan_s':s['makespan_s'],
        'joint_makespan_s':max(s['makespan_s'],max(r['return_s'] for r in rel)),
        'relay_energy_kwh':sum(r['energy_kwh'] for r in rel),'total_energy_kwh':s['energy_kwh']+sum(r['energy_kwh'] for r in rel),
        'relay_trips':len(rel),'relay_bodies_used':len({r['relay_drone_id'] for r in rel}),
        'relay_modules_used':len({r['energy_module_id'] for r in rel}),
        'relay_min_soc_fraction':min(r['return_soc_fraction'] for r in rel),
        'communication_atoms':len(atoms),'communication_boundary_points':sum(a['is_boundary'] for a in atoms),
        'radio_coordinate_model':'统一O01原点WGS84尺度局部平面，三维欧氏距离，DEM分片常高',
        'global_optimality_proven':False,'conditional_relay_milp_optimal':cert['stage1_status']==0 and cert['stage2_status']==0})
    save_json(out/'summary.json',s);write_csv(out/'radio_bidirectional_budgets.csv',radio.directions)
    pb.evaluate.cache_clear();del pb;gc.collect();return s
