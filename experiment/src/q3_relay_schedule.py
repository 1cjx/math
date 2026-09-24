"""核心模块：固定候选悬停点和运输解下，中继服务归属/开始/结束的MILP。
Python 3.13.5 / scipy1.17.0(HiGHS)。两阶段：最小联合Cmax，再最小中继能耗。
该子问题的最优性不外推为含连续选址与全体运输组合的全局最优。
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict,Counter
import math,copy
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_array
from q3_config import Q3CFG
from q3_trajectory import position
from q2_physics import charge_duration
from io_utils import write_csv,save_json


def communication_atoms(radio,phases,missions,planning=False):
    """正长度开区间+全部边界单点构成互不遗漏的连续时间分割。
    开区间可用集合由所有地形阴影边界、距离根、原时窗边界共同切分。
    零长度行用于明确切换瞬时的唯一归属，避免用采样率掩盖瞬时中断。
    """
    atoms=[];geometry=[]
    for p in phases:
        a=p['start_s'];b=p['end_s'];dt=b-a
        direct=radio.profile(radio.gateway,p['p0'],p['p1'],'direct',Q3CFG.search_budget_buffer_db if planning else 0.)
        access=[radio.profile(m['point'],p['p0'],p['p1'],'access',Q3CFG.search_budget_buffer_db) for m in missions]
        cuts=set([0.,1.]+[s for pp in [direct]+access for s in pp['boundaries']])
        for m in missions:
            for t in (m['link_complete_s']+Q3CFG.service_time_buffer_s,m['service_end_s']-Q3CFG.service_time_buffer_s):
                if a<t<b:cuts.add((t-a)/dt)
        cuts=sorted(cuts)
        def usable(pp,s):return next((r['available'] for r in pp['pieces'] if r['s0']<=s<=r['s1']),False)
        for k,(lo,hi) in enumerate(zip(cuts,cuts[1:])):
            if hi-lo<1e-13:continue
            mid=(lo+hi)/2;dr=usable(direct,mid)
            options=[] if dr else [j for j,pp in enumerate(access) if usable(pp,mid)]
            if not dr and not options:raise ValueError(f'存在空间上不可保障的区间：{p["phase_id"]} {lo} {hi}')
            atoms.append({'phase_id':p['phase_id'],'trip_id':p['trip_id'],'phase':p['phase'],'leg_index':p['leg_index'],
                'start_s':a+dt*lo,'end_s':a+dt*hi,'s0':lo,'s1':hi,'is_boundary':False,'direct':dr,'relay_options':options})
        # 同一架次相邻阶段共享端点，由最终去重保留唯一单点记录。
        for s in cuts:
            t=a+dt*s;pos=position(p,t);lk=radio.link(radio.gateway,pos,'direct');dr=lk['margin_db']>=(Q3CFG.search_budget_buffer_db if planning else 0.)-1e-8
            options=[] if dr else [j for j,m in enumerate(missions) if radio.link(m['point'],pos,'access')['margin_db']>=Q3CFG.search_budget_buffer_db-1e-8]
            if not dr and not options:raise ValueError(f'边界瞬时没有可用接入：{p["phase_id"]} t={t}')
            atoms.append({'phase_id':p['phase_id'],'trip_id':p['trip_id'],'phase':p['phase'],'leg_index':p['leg_index'],
                'start_s':t,'end_s':t,'s0':s,'s1':s,'is_boundary':True,'direct':dr,'relay_options':options})
        for j,pp in enumerate([direct]+access):
            geometry.append({'phase_id':p['phase_id'],'link_endpoint':'G01' if j==0 else missions[j-1]['relay_trip_id'],
                'occluding_cells':pp['occluding_cells'],'tested_terrain_cells':pp['terrain_cells_tested'],
                'shadow_intervals':len(pp['shadows']),'partition_intervals':len(pp['pieces'])})
    # 浮点端点按1ns去重；正长度区间不靠四舍五入改变时序。
    pts={};ints=[]
    for atom in atoms:
        if atom['is_boundary']:
            key=(atom['trip_id'],round(atom['start_s'],9))
            if key in pts:
                old=pts[key]
                if old['direct']!=atom['direct']:raise AssertionError('相邻阶段共享点通信判断不一致')
                if not old['direct']:
                    old['relay_options']=sorted(set(old['relay_options'])&set(atom['relay_options']))
                    if not old['relay_options']:raise AssertionError('相邻阶段共享点不存在共同可用中继')
            else:pts[key]=atom
        else:ints.append(atom)
    atoms=sorted(ints+list(pts.values()),key=lambda a:(a['trip_id'],a['start_s'],a['end_s'],a['phase_id']))
    for i,a in enumerate(atoms,1):a['atom_id']=f'COM-{i:05d}'
    return atoms,geometry


def optimize_relay_times(data,missions,atoms,transport_cmax):
    model=data['relay_models'][0];energypars=data['relay_energy'][0];J=len(missions)
    demands=[i for i,a in enumerate(atoms) if not a['direct']]
    # x_ij只为可用接入建立；回传为静态已核验条件。
    xvars={};nvar=2*J+1
    for i in demands:
        for j in atoms[i]['relay_options']:xvars[i,j]=nvar;nvar+=1
    sidx=list(range(J));eidx=list(range(J,2*J));Cidx=2*J
    H=max([transport_cmax]+[m['return_s'] for m in missions])+1000.;M=H*2
    lbs=np.zeros(nvar);ubs=np.ones(nvar);ubs[:2*J+1]=H;lbints=np.zeros(nvar)
    for v in xvars.values():lbints[v]=1
    rr=[];cc=[];vv=[];lower=[];upper=[]
    def add(d,lo=-np.inf,hi=np.inf):
        row=len(lower)
        for k,v in d.items():rr.append(row);cc.append(k);vv.append(v)
        lower.append(lo);upper.append(hi)
    add({Cidx:1},transport_cmax,np.inf)
    for j,m in enumerate(missions):
        prep=model['prepare_s']+m['outbound_flight_s'];ready=prep+model['link_setup_s']
        maxhover=(model['usable_energy_kwh']*(1-model['reserve_fraction'])-m['flight_energy_kwh'])*Q3CFG.seconds_per_hour/(model['hover_power_kw']+model['communication_power_kw'])
        add({eidx[j]:1,sidx[j]:-1},ready,prep+maxhover)
        add({Cidx:1,eidx[j]:-1},m['inbound_flight_s'],np.inf)
    bydrone=defaultdict(list)
    for j,m in enumerate(missions):bydrone[m['relay_drone_id']].append(j)
    for jj in bydrone.values():
        for prev,j in zip(jj,jj[1:]):add({sidx[j]:1,eidx[prev]:-1},missions[prev]['inbound_flight_s']+model['turnaround_s'],np.inf)
    for i in demands:
        a=atoms[i];add({xvars[i,j]:1 for j in a['relay_options']},1,1)
        for j in a['relay_options']:
            v=xvars[i,j];m=missions[j];ready=model['prepare_s']+m['outbound_flight_s']+model['link_setup_s']
            add({sidx[j]:1,v:M},-np.inf,a['start_s']-Q3CFG.service_time_buffer_s-ready+M)
            add({eidx[j]:1,v:-M},a['end_s']+Q3CFG.service_time_buffer_s-M,np.inf)
    A=coo_array((vv,(rr,cc)),shape=(len(lower),nvar)).tocsc()
    constraints=LinearConstraint(A,np.array(lower),np.array(upper));c=np.zeros(nvar);c[Cidx]=1
    r=milp(c,integrality=lbints,bounds=Bounds(lbs,ubs),constraints=constraints,
           options={'node_limit':Q3CFG.milp_node_limit,'mip_rel_gap':Q3CFG.milp_relative_gap,'presolve':True})
    if r.x is None:raise RuntimeError('中继时段/归属MILP不可行：'+str(r.message))
    # 第二目标严格固定第一目标容差；不把总能耗和最晚返航互相混称。
    optimal_c=float(r.x[Cidx]);ubs[Cidx]=optimal_c+Q3CFG.milp_cmax_tolerance_s
    c=np.zeros(nvar)
    P=(model['hover_power_kw']+model['communication_power_kw'])/Q3CFG.seconds_per_hour
    for j in range(J):c[eidx[j]]=P;c[sidx[j]]=-P
    r2=milp(c,integrality=lbints,bounds=Bounds(lbs,ubs),constraints=constraints,
            options={'node_limit':Q3CFG.milp_node_limit,'mip_rel_gap':Q3CFG.milp_relative_gap,'presolve':True})
    if r2.x is None:raise RuntimeError('中继第二目标MILP无解')
    x=r2.x;out=copy.deepcopy(missions);assignment={}
    for i in demands:
        j=max(atoms[i]['relay_options'],key=lambda j:x[xvars[i,j]])
        if x[xvars[i,j]]<0.5:raise AssertionError('中继分配非整数')
        assignment[i]=j
    for j,m in enumerate(out):
        m['start_s']=float(x[sidx[j]]);m['arrival_s']=m['start_s']+model['prepare_s']+m['outbound_flight_s']
        m['link_complete_s']=m['arrival_s']+model['link_setup_s'];m['service_end_s']=float(x[eidx[j]])
        m['return_s']=m['service_end_s']+m['inbound_flight_s'];m['turnaround_end_s']=m['return_s']+model['turnaround_s']
        setup_e=P*model['link_setup_s'];hover_e=P*(m['service_end_s']-m['link_complete_s'])
        m['setup_energy_kwh']=setup_e;m['service_energy_kwh']=hover_e;m['energy_kwh']=m['flight_energy_kwh']+setup_e+hover_e
        m['return_soc_fraction']=1-m['energy_kwh']/model['usable_energy_kwh'];m['charge_duration_s']=charge_duration(m['return_soc_fraction'],energypars['full_charge_s'])
        m['charge_end_s']=m['return_s']+m['charge_duration_s'];m['served_communication_atoms']=sum(v==j for v in assignment.values())
    # MILP采用浮点，计算解的所有线性约束残差后再发布；整数分配另独立重算。
    ax=A@x;vio=max(float(np.max(np.maximum(np.array(lower)-ax,0))),float(np.max(np.maximum(ax-np.array(upper),0))))
    if vio>1e-5:raise AssertionError('MILP约束数值残差过大')
    certificate={'stage1_status':int(r.status),'stage2_status':int(r2.status),'stage1_message':str(r.message),'stage2_message':str(r2.message),
        'stage1_joint_cmax_s':optimal_c,'stage1_dual_bound':float(r.mip_dual_bound),'stage1_gap':float(r.mip_gap),
        'stage2_gap':float(r2.mip_gap),'variables':nvar,'binary_variables':len(xvars),'constraints':A.shape[0],
        'max_constraint_violation':vio,'scope':'给定运输解、四个候选悬停点及中继实体先后关系的条件子问题；不是原Q3全局最优证明'}
    return out,assignment,certificate


def export_communication(root,out,radio,data,phases,missions,transport_cmax,optimize=True):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    plan_atoms,geo=communication_atoms(radio,phases,missions,planning=True)
    atoms=plan_atoms
    if optimize:
        relays,assignment,certificate=optimize_relay_times(data,missions,atoms,transport_cmax)
    else:
        relays=copy.deepcopy(missions);assignment={};model=data['relay_models'][0]
        for i,a in enumerate(atoms):
            if a['direct']:continue
            possible=[j for j in a['relay_options'] if relays[j]['link_complete_s']<=a['start_s']+1e-7 and relays[j]['service_end_s']>=a['end_s']-1e-7]
            if not possible:raise AssertionError('固定中继时窗对照不能覆盖全部通信区间')
            assignment[i]=possible[0]
        P=(model['hover_power_kw']+model['communication_power_kw'])/Q3CFG.seconds_per_hour
        for j,m in enumerate(relays):
            m['setup_energy_kwh']=P*model['link_setup_s'];m['service_energy_kwh']=P*(m['service_end_s']-m['link_complete_s'])
            m['served_communication_atoms']=sum(v==j for v in assignment.values())
        certificate={'scope':'相同运输解的固定宽中继时窗可行对照，不执行MILP，不声称最优','stage1_status':None,'stage2_status':None}
    # 发布按原题门限（不加规划缓冲）的直连优先状态；规划时可提前部署中继待命。
    # 待命保护不是给直连可用的运输机强行标中继，两种口径明确区分。
    guard=[]
    for i,a in enumerate(plan_atoms):
        guard.append({k:v for k,v in a.items() if k!='relay_options'}|{'guard_margin_db':Q3CFG.search_budget_buffer_db,
             'guard_relay_trip_id':'' if a['direct'] else relays[assignment[i]]['relay_trip_id']})
    write_csv(out/'planning_guard_atoms.csv',guard)
    atoms,source_geo=communication_atoms(radio,phases,relays,planning=False)
    assignment={}
    for i,a in enumerate(atoms):
        if a['direct']:continue
        possible=[j for j in a['relay_options'] if relays[j]['link_complete_s']<=a['start_s']+1e-7 and relays[j]['service_end_s']>=a['end_s']-1e-7]
        if not possible:raise AssertionError('规划缓冲转换为原题直连优先状态时出现覆盖缺口')
        assignment[i]=possible[0]
    for j,m in enumerate(relays):m['served_communication_atoms']=sum(v==j for v in assignment.values())
    certificate['extra_planning_loss_guard_db']=Q3CFG.search_budget_buffer_db
    certificate['guard_atom_count']=len(plan_atoms)
    pmap={p['phase_id']:p for p in phases};rows=[];detailed=[];boundary=[]
    for i,a in enumerate(atoms):
        if a['direct']:mode='直连';rid='';j=None
        else:j=assignment[i];mode='中继';rid=relays[j]['relay_trip_id']
        phase=a['phase']+('·边界点' if a['is_boundary'] else '')
        row={'运输架次编号':a['trip_id'],'通信阶段':phase,'开始时刻（s）':a['start_s'],'结束时刻（s）':a['end_s'],
             '保障方式':mode,'中继架次编号':rid}
        rows.append(row)
        p=pmap[a['phase_id']];pos=position(p,(a['start_s']+a['end_s'])/2)
        dr=radio.link(radio.gateway,pos,'direct');lk=dr if j is None else radio.link(relays[j]['point'],pos,'access')
        br=None if j is None else radio.link(radio.gateway,relays[j]['point'],'backhaul')
        detail={k:v for k,v in a.items() if k!='relay_options'}|{'mode':mode,'relay_trip_id':rid,
               'eligible_relay_indices':';'.join(str(x) for x in a['relay_options']),
               'selected_margin_mid_db':lk['margin_db'],'direct_margin_mid_db':dr['margin_db'],
               'backhaul_margin_db':None if br is None else br['margin_db']}
        detailed.append(detail)
        if a['is_boundary']:boundary.append(detail)
    write_csv(out/'Q3_通信保障.csv',rows);write_csv(out/'communication_atoms.csv',detailed);write_csv(out/'communication_boundary_points.csv',boundary)
    write_csv(out/'continuous_geometry_certificate.csv',source_geo)
    write_csv(out/'planning_geometry_certificate.csv',geo)
    relayrows=[];internal=[]
    for m in relays:
        p=m['point']
        relayrows.append({'中继架次编号':m['relay_trip_id'],'中继无人机编号':m['relay_drone_id'],'能源组件编号':m['energy_module_id'],
            '开始时刻（s）':m['start_s'],'悬停经度（°）':p[0],'悬停纬度（°）':p[1],'悬停海拔（m）':p[2],
            '建链完成时刻（s）':m['link_complete_s'],'服务结束时刻（s）':m['service_end_s'],
            '返回O01时刻（s）':m['return_s'],'架次能耗（kWh）':m['energy_kwh']})
        internal.append({k:v for k,v in m.items() if k!='point'}|{'hover_lon_deg':p[0],'hover_lat_deg':p[1],'hover_altitude_m':p[2]})
    write_csv(out/'Q3_中继架次.csv',relayrows);write_csv(out/'relay_sorties.csv',internal)
    save_json(out/'relay_milp_certificate.json',certificate);save_json(out/'relay_missions.json',relays)
    return relays,atoms,certificate
