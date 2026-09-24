"""第三问候选生成：全DEM规则网格、直接缺链轨迹、两机两轮覆盖启发式。
Python3.13.5 / numpy2.3.5 / numba0.65.1。60m采样只用于候选筛选；最终用连续证明。
不是全连续选址最优算法；候选的最大高度遵守题定巡航海拔与300m AGL双上限。
"""
from __future__ import annotations
import math,time
from pathlib import Path
import numpy as np
from io_utils import write_csv,save_json,read_csv
from physics import GEOD
from config import CFG
from q3_config import Q3CFG
from q3_communication import _batch_cover,_line_peak
from q3_trajectory import load_phases,position


def direct_deficit_points(radio,arc):
    groups={}
    for n in radio.data['services']:
        sid=n['node_id'];segments=[]
        for u,v in [('O01',sid),(sid,'O01')]:
            a=radio.workpoint(u);b=radio.workpoint(v);H=arc[u,v]['cruise_altitude_m']
            ah=(a[0],a[1],H);bh=(b[0],b[1],H);segments.extend([(a,ah),(ah,bh),(bh,b)])
        segments.append((radio.workpoint(sid),radio.workpoint(sid)));pts=[]
        for a,b in segments:
            p=radio.profile(radio.gateway,a,b,'direct',Q3CFG.search_budget_buffer_db)
            for sec in p['pieces']:
                if sec['available']:continue
                aa=np.array(a)+(np.array(b)-np.array(a))*sec['s0'];bb=np.array(a)+(np.array(b)-np.array(a))*sec['s1']
                ns=max(2,math.ceil(radio.distance(aa,bb)/Q3CFG.search_sample_spacing_m)+1)
                pts.extend(tuple(float(x) for x in aa+(bb-aa)*s) for s in np.linspace(0,1,ns))
        groups[sid]=sorted(set(pts))
    return groups


def candidate_sites(root,data,radio,arc,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);groups=direct_deficit_points(radio,arc)
    pts=sorted({p for v in groups.values() for p in v});idx={p:i for i,p in enumerate(pts)}
    gridpoints=np.array([radio.grid_point(p) for p in pts]);step=Q3CFG.candidate_grid_stride_pixels
    origin=radio.grid_point(radio.workpoint('O01'));rm=data['relay_models'][0];sites=[];coverage=[]
    scanned=0;terrain_valid=0;backhaul_valid=0
    for row in range(step//2,radio.dem.shape[0],step):
        for col in range(step//2,radio.dem.shape[1],step):
            scanned+=1;z=float(radio.dem[row,col])
            if not math.isfinite(z) or z==CFG.nodata_value:continue
            terrain_valid+=1;pgrid=np.array([col+.5,row+.5,z]);H=float(_line_peak(origin,pgrid,radio.dem))+CFG.terrain_clearance_m
            alt=min(H,z+rm['max_hover_agl_m'])
            if not math.isfinite(H) or alt<z+Q3CFG.candidate_min_agl_m-1e-8:continue
            point=radio.geo_point((col+.5,row+.5,alt));back=radio.link(radio.gateway,point,'backhaul')
            if back['margin_db']<Q3CFG.search_budget_buffer_db:continue
            backhaul_valid+=1
            cover=_batch_cover(radio.grid_point(point),gridpoints,radio.dem,radio.kx,radio.ky,
                   radio.max_range('access',False,Q3CFG.search_budget_buffer_db),radio.max_range('access',True,Q3CFG.search_budget_buffer_db))
            if not cover.any():continue
            dist=GEOD.inv(radio.gateway[0],radio.gateway[1],point[0],point[1])[2]
            cost=(2*dist/rm['cruise_speed_mps']+(H-radio.workpoint('O01')[2])*(1/rm['climb_speed_mps']+1/rm['descent_speed_mps']))
            sites.append({'site_id':f'GRID-{row}-{col}','row':row,'col':col,'lon':point[0],'lat':point[1],
                'alt':alt,'agl':alt-z,'ground':z,'route_H':H,'gateway_distance':dist,
                'backhaul_margin':back['margin_db'],'covered_search_points':int(cover.sum()),'travel_score_s':cost})
            coverage.append(cover)
    cov=np.array(coverage,dtype=bool)
    if not len(cov):raise ValueError('未找到中继候选')
    # 时限分组完全从逐箱源参数派生，不硬编码服务区编号。
    hard={}
    for n in data['services']:
        ds=[]
        for b in data['boxes']:
            if b['service_id']!=n['node_id']:continue
            if b['material_type']=='医疗物资':ds.append(b['expected_s'])
            if b['is_first_batch']:ds.append(b['first_deadline_s'])
        hard[n['node_id']]=min(ds,default=math.inf)
    earliest=min(hard.values());urgent=sorted(s for s in groups if groups[s] and hard[s]==earliest)
    late=sorted(s for s in groups if groups[s] and s not in urgent)
    selected_indices={s:np.array([idx[p] for p in ps],dtype=int) for s,ps in groups.items()}
    lm=sorted({idx[p] for sid in late for p in groups[sid]});C=cov[:,lm];scores=C.sum(axis=1);order=np.argsort(-scores,kind='stable')
    bits=[int.from_bytes(np.packbits(x,bitorder='little').tobytes(),'little') for x in C];full=(1<<len(lm))-1;pairs=[]
    for ii in order:
        if scores[ii]<len(lm)-scores[order[0]]:break
        for jj in order:
            if jj<ii:continue
            if scores[ii]+scores[jj]<len(lm):break
            if bits[ii]|bits[jj]==full:pairs.append((sites[ii]['gateway_distance']+sites[jj]['gateway_distance'],int(ii),int(jj)))
    pairs.sort();pairs=pairs[:Q3CFG.maximum_late_pairs]
    if not pairs:raise ValueError('两机第二轮候选网格未覆盖晚期区域；应增加候选/时空结构，不能漏运')
    proposals=[]
    # 两轮启发式：首轮第一机先保障一个紧时限区域后迁至晚期区域；
    # 第二机保障剩余紧时限区中第一台晚期中继不能覆盖的部分，再迁至另一晚期点。
    for singleton in urgent:
        firstids=np.flatnonzero(cov[:,selected_indices[singleton]].all(axis=1))
        if not len(firstids):continue
        early=min(firstids,key=lambda i:(sites[i]['travel_score_s'],i))
        rest=sorted({idx[p] for s in urgent if s!=singleton for p in groups[s]})
        for _,i,j in pairs:
            for n,w in ((i,j),(j,i)):
                otherids=np.flatnonzero((cov[:,rest]|cov[n,rest]).all(axis=1))
                if not len(otherids):continue
                east=min(otherids,key=lambda k:(sites[k]['travel_score_s'],k));inds=(int(early),int(east),n,w)
                value=sum(sites[k]['travel_score_s'] for k in inds)
                proposals.append((value,singleton,inds))
    proposals=sorted(set(proposals));families=[]
    for k,(score,single,inds) in enumerate(proposals[:Q3CFG.max_candidate_finalists],1):
        families.append({'family_rank':k,'travel_score_s':score,'early_single_service':single,
                         'site_indices':list(inds),'site_ids':[sites[i]['site_id'] for i in inds]})
    if not families:raise ValueError('两机两轮候选结构不存在；不发布不可行方案')
    save_json(out/'candidate_families.json',families);write_csv(out/'candidate_sites.csv',sites)
    write_csv(out/'candidate_search_points.csv',[{'point_id':i,'lon_deg':p[0],'lat_deg':p[1],'altitude_m':p[2]} for i,p in enumerate(pts)])
    save_json(out/'candidate_service_groups.json',{'earliest_hard_deadline_s':earliest,'urgent':urgent,'late':late,
            'service_point_indices':{k:v.tolist() for k,v in selected_indices.items()}})
    save_json(out/'candidate_search_summary.json',{'grid_stride_pixels':step,'grid_positions_scanned':scanned,
          'valid_dem_positions':terrain_valid,'backhaul_valid_positions':backhaul_valid,'retained_candidates':len(sites),
          'sample_points':len(pts),'late_pair_finalists':len(pairs),'four_sortie_families':len(proposals),
          'screening_is_not_continuous_proof':True,'full_continuous_global_optimum_claimed':False,
          'coordinate_model':'局部平面：以O01的WGS84曲率半径将经纬度差映射为米，垂直坐标为题定海拔；DEM射线与距离同一坐标'})
    # 候选覆盖矩阵仅作搜索复核，不替代最终连续空间证明。
    np.savez_compressed(out/'candidate_coverage.npz',coverage=cov)
    return [[sites[i] for i in f['site_indices']] for f in families]
