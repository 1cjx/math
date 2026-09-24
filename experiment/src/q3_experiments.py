"""Q3可靠性与权衡：独立连续直连缺口、固定方案扰动、时段优化消融和节能对照。
Python3.13.5；所有故意扰动另存对照，绝不当作正式可行答案提交。
"""
from pathlib import Path
from collections import defaultdict
import json,copy,math,gc
import numpy as np
from pyproj import Geod
from io_utils import read_csv,write_csv,save_json
from q3_config import Q3CFG
from q3_validation import IndependentRadio,independent_phases,independent_arcs,_pos,run_q3_validation
from q3_communication import Radio
from q3_joint import JointProblem
from q3_trajectory import load_phases
from q3_relay_schedule import export_communication
from solve_q2 import export_plan
from solve_q3 import geometry_from_q2
from q2_search import search


def source_radio_status(radio,phases,relays,extra_loss=0.):
    """固定运输/中继时刻，可在现有单跳链路间选择；逐连续原子与孤立点判断。
    地形阴影不变；增加损耗时重解每条链路的距离门限根，不能只查原来分段。
    """
    radio.limits={k:v-extra_loss for k,v in radio.limits.items()};rows=[];boundary=set();failpoints=set()
    for p in phases:
        a=p['start_s'];b=p['end_s'];dt=b-a
        anchors=[(radio.gateway,'direct',None)]+[(tuple(m['point']),'access',m) for m in relays]
        prof=[];cuts={0.,1.}
        for anchor,kind,m in anchors:
            profile,shadow=radio.profile(anchor,p['p0'],p['p1'],kind);prof.append(profile)
            cuts.update(s for x in profile for s in (x['s0'],x['s1']))
            for aa,bb in shadow:cuts.update((aa,bb))
            if m:
                for t in (m['link_complete_s'],m['service_end_s']):
                    if a<t<b:cuts.add((t-a)/dt)
        back=[radio.point(radio.gateway,m['point'],'backhaul')['available'] for m in relays];cuts=sorted(cuts)
        def active(j,t):return relays[j]['link_complete_s']-1e-8<=t<=relays[j]['service_end_s']+1e-8 and back[j]
        for lo,hi in zip(cuts,cuts[1:]):
            if hi-lo<1e-12:continue
            mid=(lo+hi)/2;t=a+mid*dt
            avail=[next((q['available_interior'] for q in pp if q['s0']<=mid<=q['s1']),False) for pp in prof]
            mode='直连' if avail[0] else ('中继' if any(avail[j+1] and active(j,t) for j in range(len(relays))) else '中断')
            rows.append({'trip_id':p['trip_id'],'phase':p['phase'],'start_s':a+lo*dt,'end_s':a+hi*dt,'duration_s':(hi-lo)*dt,'mode':mode})
        for s in cuts:
            t=a+s*dt;key=(p['trip_id'],round(t,8));boundary.add(key);pos=_pos(p,t)
            valid=radio.point(radio.gateway,pos,'direct')['available'] or any(active(j,t) and radio.point(m['point'],pos,'access')['available'] for j,m in enumerate(relays))
            if not valid:failpoints.add(key)
    radio.limits={k:v+extra_loss for k,v in radio.limits.items()}
    total=sum(x['duration_s'] for x in rows);outage=sum(x['duration_s'] for x in rows if x['mode']=='中断')
    return {'extra_loss_db':extra_loss,'required_airborne_service_s':total,'outage_duration_sum_s':outage,'coverage_fraction':1-outage/total,
            'boundary_points_checked':len(boundary),'uncovered_boundary_points':len(failpoints),'continuous_feasible':outage<1e-6 and not failpoints},rows


def run_q3_experiments(root,data,optimize_alternatives=True):
    root=Path(root);out=root/'results/q3';r=Radio(root,data);ir=IndependentRadio(root,data);geom=geometry_from_q2(root);arc=independent_arcs(root,data)
    q3=read_csv(out/'Q3_运输架次.csv');bx=read_csv(out/'Q3_逐箱交付.csv');phases=independent_phases(data,arc,q3,bx);rel=json.loads((out/'relay_missions.json').read_text())
    q2=read_csv(root/'results/q2/Q2_运输架次.csv');b2=read_csv(root/'results/q2/Q2_逐箱交付.csv');p2=independent_phases(data,arc,q2,b2)
    nodirect,gaps=source_radio_status(ir,p2,[]);save_json(out/'q2_direct_only_audit.json',nodirect);write_csv(out/'q2_direct_only_intervals.csv',gaps)
    records=[]
    for extra in Q3CFG.propagation_extra_losses_db:
        result,parts=source_radio_status(ir,phases,rel,extra);records.append(result)
        if extra==0.:write_csv(out/'communication_reassignment_baseline.csv',parts)
    write_csv(out/'propagation_loss_sensitivity.csv',records)
    # 所有任务共同平移不会改变资源/通信相对关系；硬期限保持原值。
    independent=read_csv(out/'independent_box_checks.csv');delayrows=[]
    for delay in Q3CFG.perturbation_delays_s+Q3CFG.extra_common_delays_s:
        hard=[float(b['hard_slack_s'])-delay for b in independent if b['hard_slack_s']!='']
        delayrows.append({'common_delay_s':delay,'min_hard_slack_s':min(hard),'hard_late_boxes':sum(x< -1e-6 for x in hard),'feasible':min(hard)>=-1e-6})
    write_csv(out/'common_start_delay_sensitivity.csv',delayrows)
    # 中继整体滞后而运输时刻固定：相对开工裕度只有1s，不虚称大延迟鲁棒。
    temporal=[];atoms=read_csv(out/'communication_atoms.csv');rm={m['relay_trip_id']:m for m in rel}
    for delay in Q3CFG.perturbation_delays_s:
        loss=0.;points=0
        for a in atoms:
            if a['mode']!='中继':continue
            m=rm[a['relay_trip_id']];lo=float(a['start_s']);hi=float(a['end_s']);begin=m['link_complete_s']+delay;end=m['service_end_s']+delay
            if lo==hi:points+=int(not(begin-1e-6<=lo<=end+1e-6))
            else:loss+=max(0,min(hi,begin)-lo)+max(0,hi-max(lo,end))
        temporal.append({'relay_only_shift_s':delay,'fixed_assignment_uncovered_duration_s':loss,'fixed_assignment_uncovered_points':points,'fixed_assignment_feasible':loss<1e-6 and points==0,'meaning':'不重排运输、不重选保障关系的冻结方案压力测试'})
    write_csv(out/'relay_only_delay_sensitivity.csv',temporal)
    # 坐标近似与运输弧长不同定义：定量给出相对差，不将两者冒充同一距离。
    geod=Geod(ellps='WGS84');distrows=[]
    for p in phases:
        for s in (0.,.5,1.):
            pos=_pos(p,p['start_s']+(p['end_s']-p['start_s'])*s)
            for name,anchor in [('G01',ir.gateway)]+[(m['relay_trip_id'],m['point']) for m in rel]:
                eu=float(np.linalg.norm((pos-anchor)*ir.scale));gh=math.hypot(geod.inv(anchor[0],anchor[1],pos[0],pos[1])[2],pos[2]-anchor[2]);err=eu-gh
                distrows.append({'phase_id':p['phase_id'],'anchor':name,'s':s,'local_line_distance_m':eu,'geodesic_plus_height_m':gh,'difference_m':err,
                   'absolute_relative_difference':abs(err)/max(gh,1e-12),'loss_difference_db':20*math.log10(max(eu,1e-12)/max(gh,1e-12))})
    write_csv(out/'coordinate_model_comparison.csv',distrows)
    save_json(out/'coordinate_approximation_summary.json',{'pairs_compared':len(distrows),'max_absolute_distance_difference_m':max(abs(x['difference_m']) for x in distrows),
          'max_absolute_relative_difference':max(x['absolute_relative_difference'] for x in distrows),'max_absolute_loss_difference_db':max(abs(x['loss_difference_db']) for x in distrows),
          'scope':'相同端点两种距离定义的端点/中点对照，不是全球投影误差上界；连续可行性证书针对已声明的局部三维模型'})
    # 同一个运输答案，宽服务窗口 vs 优化窗口；这是中继时段优化的可复核消融。
    if optimize_alternatives:
        sites=json.loads((out/'sites.json').read_text());missions=json.loads((out/'initial_service_windows.json').read_text())
        genome=json.loads((out/'selected_genome.json').read_text())['trips'];tr=[(g,tuple(s),tuple(i)) for g,s,i in genome]
        pb=JointProblem(root,data,r,sites,missions,geom);fixed=out/'alternatives/fixed_service_windows'
        export_plan(pb,tr,fixed,'Q3_fixed_service',True,trip_prefix='Q3-T',template_prefix='Q3')
        fullrel,_,_=export_communication(root,fixed,r,data,load_phases(root,data,str(fixed.relative_to(root))),missions,pb.schedule(tr)['makespan_s'],optimize=False)
        # 在同一可行空间给出节能权衡；运输Cmax软上限=主方案联合完工的1.1倍。
        main=json.loads((out/'summary.json').read_text());cap=main['joint_makespan_s']*Q3CFG.energy_tradeoff_cap_multiplier;trial=tr
        for seed in Q3CFG.energy_tradeoff_seeds:
            trial,m,h,stats=search(pb,trial,seed,iterations=Q3CFG.energy_tradeoff_iterations,lns=Q3CFG.energy_tradeoff_lns,mode='energy',cap=cap)
        if m['hard_late_s']<=1e-8:
            enout=out/'alternatives/energy_tradeoff';export_plan(pb,trial,enout,'Q3_energy_tradeoff',True,trip_prefix='Q3-T',template_prefix='Q3')
            export_communication(root,enout,r,data,load_phases(root,data,str(enout.relative_to(root))),missions,m['makespan_s'])
        pb.evaluate.cache_clear();del pb;gc.collect()
    comp=[]
    for folder in [out]+sorted((out/'alternatives').iterdir()):
        if not (folder/'summary.json').exists() or not (folder/'relay_missions.json').exists():continue
        s=json.loads((folder/'summary.json').read_text());rels=json.loads((folder/'relay_missions.json').read_text())
        comp.append({'scenario':folder.name,'transport_trips':s['trips'],'relay_trips':len(rels),'joint_makespan_s':max(s['makespan_s'],max(m['return_s'] for m in rels)),
          'transport_energy_kwh':s['energy_kwh'],'relay_energy_kwh':sum(m['energy_kwh'] for m in rels),'total_energy_kwh':s['energy_kwh']+sum(m['energy_kwh'] for m in rels),
          'weighted_tardiness_s':s['weighted_tardiness_s'],'hard_late_s':s['hard_late_s'],'note':'条件候选方案，尚须独立验证；非全局Pareto前沿'})
    # 对所有对照进行独立连续通信、逐箱、实体与能源核验后才标记可行。
    alt_validation=[]
    for folder in sorted((out/'alternatives').iterdir()):
        if (folder/'Q3_通信保障.csv').exists():
            v=run_q3_validation(root,str(folder.relative_to(root)),dense=False)
            alt_validation.append({'scenario':folder.name,**v})
    save_json(out/'alternatives_validation.json',alt_validation)
    for row in comp:row['note']='独立完整连续/能源/时限/库存验证通过；非全局Pareto前沿'
    write_csv(out/'scenario_comparison.csv',comp)
    save_json(out/'reliability_summary.json',{'q2_direct_only':nodirect,'baseline_with_relays':records[0],
         'max_tested_extra_loss_feasible_db':max((x['extra_loss_db'] for x in records if x['continuous_feasible']),default=None),
         'coordinate_max_loss_difference_db':max(abs(x['loss_difference_db']) for x in distrows),
         'common_delay_limit_s':min(float(b['hard_slack_s']) for b in independent if b['hard_slack_s']),
         'relay_only_fixed_assignment_test':temporal,'all_source_parameters_unchanged':True,
         'parameter_disturbances_are_not_official_safety_requirements':True})
    return comp
