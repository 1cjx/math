"""独立结果复核：仅从提交表与原始DEM重新构造时序、能耗和资源占用。
不调用q2_physics、q2_search或其缓存；Python 3.13.5，rasterio 1.5.0。
本模块验证模型内计算与约束，不把验证通过解释为真实飞行安全认证。
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter,defaultdict
import math,json
import numpy as np
import rasterio
from rasterio.features import rasterize
from pyproj import Geod
from io_utils import read_csv,write_csv,save_json,xlsx_read
from config import CFG

VERIFY_TIME_TOL_S=1e-6
VERIFY_ENERGY_TOL_KWH=1e-8
VERIFY_VOLUME_TOL_M3=1e-9
VERIFY_MASS_TOL_KG=1e-8
CHARGE_KNEE=0.90   # 题面附录2；独立实现与主计算分开
CHARGE_FAST_FRACTION=0.65
CHARGE_SLOW_FRACTION=0.35


def independent_arcs(root,data):
    raw_tifs=sorted((Path(root)/'data/raw').rglob('*.tif'))
    if len(raw_tifs)!=1:raise ValueError('原始DEM文件不是唯一')
    with rasterio.open(raw_tifs[0]) as ds:a=ds.read(1);tr=ds.transform
    nodes={r['node_id']:r for r in data['depots']+data['services']};g=Geod(ellps='WGS84');out={}
    for u in sorted(nodes):
        for v in sorted(nodes):
            if u>=v:continue
            p,q=nodes[u],nodes[v]
            shape={'type':'LineString','coordinates':[(p['lon_deg'],p['lat_deg']),(q['lon_deg'],q['lat_deg'])]}
            mask=rasterize([(shape,1)],out_shape=a.shape,transform=tr,all_touched=True,dtype='uint8').astype(bool)
            z=a[mask]
            if not np.all(np.isfinite(z)) or np.any(z==CFG.nodata_value):raise AssertionError('独立航段扫描发现无效地形')
            H=float(z.max())+CFG.terrain_clearance_m
            d=g.inv(p['lon_deg'],p['lat_deg'],q['lon_deg'],q['lat_deg'])[2]
            for fr,to in ((p,q),(q,p)):
                z0=fr['ground_elevation_m']+(CFG.depot_work_height_m if fr['node_id']=='O01' else CFG.service_work_height_m)
                z1=to['ground_elevation_m']+(CFG.depot_work_height_m if to['node_id']=='O01' else CFG.service_work_height_m)
                out[fr['node_id'],to['node_id']]={'d':d,'up':H-z0,'down':H-z1,'H':H,'peak':float(z.max())}
    return out


def independent_charge(soc,full):
    if soc<CHARGE_KNEE:
        return full*(CHARGE_FAST_FRACTION*(CHARGE_KNEE-soc)/CHARGE_KNEE+CHARGE_SLOW_FRACTION)
    return full*CHARGE_SLOW_FRACTION*(1-soc)/(1-CHARGE_KNEE)


def validate_rows(data,arc,trips,delivery_rows,allow_hard_late=False):
    checks=[];details=[];boxchecks=[];resources=[];models={m['model_id']:m for m in data['transport_models']}
    fleet={d['drone_id']:d['model_id'] for d in data['transport_drones']};bp={b['model_id']:b for b in data['transport_batteries']}
    battery_map={f'{g}-BAT-{i+1:02d}':g for g,p in bp.items() for i in range(p['count'])}
    boxes={b['box_id']:b for b in data['boxes']};done=[];bytrip=defaultdict(list)
    def ck(code,ok,detail=''):checks.append({'check':code,'pass':bool(ok),'details':str(detail)})
    ck('unique_trip_ids',len({t['架次编号'] for t in trips})==len(trips))
    ck('exact_once_box_coverage',Counter(r['货箱编号'] for r in delivery_rows)==Counter(boxes.keys()))
    for r in delivery_rows:
        bytrip[r['架次编号']].append(r)
        ck('delivery_known_trip/'+r['货箱编号'],r['架次编号'] in {t['架次编号'] for t in trips})
    all_e=0.0;cmax=0.0;tardy=0.0;hardlate=0.0;min_soc=1.0;min_hard=math.inf
    maxeerr=0.0;maxterr=0.0
    for r in trips:
        tid=r['架次编号'];g=r['机型编号'];uid=r['无人机编号'];bid=r['电池编号']
        ck(tid+'/known_model',g in models)
        if g not in models:continue
        m=models[g];ck(tid+'/compatible_drone',fleet.get(uid)==g);ck(tid+'/compatible_battery',battery_map.get(bid)==g)
        ss=r['访问服务区顺序'].split(';');ck(tid+'/valid_stops',len(ss)>0 and len(set(ss))==len(ss) and all(s!='O01' and (s,'O01') in arc for s in ss))
        ds=bytrip[tid];ids=[d['货箱编号'] for d in ds];ck(tid+'/has_boxes',bool(ids));ck(tid+'/known_boxes',all(i in boxes for i in ids))
        if not ids or not all(i in boxes for i in ids) or not all((s,'O01') in arc for s in ss):continue
        bs=[boxes[i] for i in ids];dm={d['货箱编号']:d for d in ds}
        ck(tid+'/stop_box_matching',set(ss)=={b['service_id'] for b in bs})
        w=math.fsum(b['weight_kg'] for b in bs);v=math.fsum(b['volume_m3'] for b in bs)
        ck(tid+'/capacity_mass',w<=m['max_payload_kg']+VERIFY_MASS_TOL_KG);ck(tid+'/capacity_volume',v<=m['volume_m3']+VERIFY_VOLUME_TOL_M3)
        start=float(r['开始时刻（s）']);returned=float(r['返回O01时刻（s）']);er=float(r['架次能耗（kWh）'])
        ck(tid+'/finite_times_energy',all(math.isfinite(x) for x in (start,returned,er)))
        ck(tid+'/nonnegative_start',start>=0);t=start+m['prepare_s']+len(bs)*m['load_per_box_s'];remaining=bs[:];energies=[];u='O01';flight=0.0
        for k,st in enumerate(ss+['O01']):
            ar=arc[u,st];q=math.fsum(b['weight_kg'] for b in remaining)
            L=m['empty_range_m']-(m['empty_range_m']-m['full_range_m'])*(q/m['max_payload_kg'])**CFG.range_load_exponent
            eh=CFG.horizontal_energy_multiplier*m['usable_energy_kwh']*ar['d']/L
            eu=CFG.climb_energy_multiplier*(m['empty_mass_kg']+q)*CFG.gravity_m_s2*ar['up']/(m['climb_efficiency']*CFG.joules_per_kwh)
            energies.append(eh+eu);dt=ar['up']/m['climb_speed_mps']+ar['d']/m['cruise_speed_mps']+ar['down']/m['descent_speed_mps'];t+=dt;flight+=dt
            ck(tid+f'/leg{k+1}_nonnegative_altitudes',ar['up']>=0 and ar['down']>=0)
            ck(tid+f'/leg{k+1}_mass_range',0<=q<=m['max_payload_kg']+VERIFY_MASS_TOL_KG)
            if st!='O01':
                def key(b):
                    hard=[]
                    if b['material_type']=='医疗物资':hard.append(b['expected_s'])
                    if b['is_first_batch']:hard.append(b['first_deadline_s'])
                    return (min(hard,default=math.inf),b['expected_s'],-b['priority'],b['box_id'])
                served=sorted((b for b in remaining if b['service_id']==st),key=key)
                ck(tid+f'/{st}_nonempty_delivery',len(served)>0);t+=m['handoff_base_s']
                for b in served:
                    t+=m['handoff_per_box_s'];rbox=dm[b['box_id']];reported=float(rbox['交付完成时刻（s）'])
                    err=abs(reported-t);maxterr=max(maxterr,err)
                    ck(b['box_id']+'/service_id',rbox['服务区编号']==b['service_id'])
                    ck(b['box_id']+'/handoff_completed_time',err<=VERIFY_TIME_TOL_S,err)
                    ck(b['box_id']+'/during_trip',start<=reported<=returned+VERIFY_TIME_TOL_S)
                    medical=b['material_type']=='医疗物资';first=b['is_first_batch'];hard=[]
                    if medical:hard.append(b['expected_s'])
                    if first:hard.append(b['first_deadline_s'])
                    slack=min((h-t for h in hard),default=math.inf)
                    if hard:
                        min_hard=min(min_hard,slack);hardlate+=max(0,-slack)
                        if not allow_hard_late:ck(b['box_id']+'/hard_deadline',slack>=-VERIFY_TIME_TOL_S,slack)
                    lateness=max(0,t-b['expected_s']);tardy+=b['priority']*lateness
                    boxchecks.append({'box_id':b['box_id'],'trip_id':tid,'recomputed_completion_s':t,'exported_completion_s':reported,
                        'error_s':err,'is_medical':medical,'is_first_batch':first,'expected_s':b['expected_s'],
                        'hard_deadline_s':None if not hard else min(hard),'hard_slack_s':None if not hard else slack,
                        'tardiness_s':lateness,'priority':b['priority']})
                    done.append(b['box_id'])
                servedids={b['box_id'] for b in served};remaining=[b for b in remaining if b['box_id'] not in servedids]
            else:ck(tid+'/empty_return',q==0)
            u=st
        e=math.fsum(energies);soc=1-e/m['usable_energy_kwh'];ct=independent_charge(soc,bp[g]['full_charge_s'])
        terr=abs(t-returned);eerr=abs(e-er);maxterr=max(maxterr,terr);maxeerr=max(maxeerr,eerr)
        ck(tid+'/return_time_recalculation',terr<=VERIFY_TIME_TOL_S,terr)
        ck(tid+'/energy_recalculation',eerr<=VERIFY_ENERGY_TOL_KWH,eerr)
        ck(tid+'/source_reserve_floor',soc>=m['reserve_fraction']-VERIFY_ENERGY_TOL_KWH,soc)
        ck(tid+'/all_boxes_unloaded',not remaining)
        ck(tid+'/charging_duration_nonnegative',ct>=0)
        details.append({'trip_id':tid,'model_id':g,'drone_id':uid,'battery_id':bid,'weight_kg':w,'volume_m3':v,'box_count':len(bs),
            'recomputed_energy_kwh':e,'energy_error_kwh':eerr,'recomputed_return_s':t,'return_time_error_s':terr,
            'return_soc_fraction':soc,'start_s':start,'recomputed_charge_complete_s':returned+ct,'recomputed_charge_s':ct,'flight_time_s':flight})
        all_e+=e;cmax=max(cmax,returned);min_soc=min(min_soc,soc)
    ck('exact_once_recomputed_delivery',Counter(done)==Counter(boxes.keys()))
    for kind,mapping in [('drone',fleet),('battery',battery_map)]:
        col='drone_id' if kind=='drone' else 'battery_id'
        for rid,g in sorted(mapping.items()):
            rows=sorted((r for r in details if r[col]==rid),key=lambda x:(x['start_s'],x['trip_id']))
            for idx,r in enumerate(rows):
                if idx==0:
                    ck(rid+'/initial_SOC_100',r['start_s']>=0)
                else:
                    prev=rows[idx-1]
                    ready=prev['recomputed_return_s'] if kind=='drone' else prev['recomputed_charge_complete_s']
                    slack=r['start_s']-ready
                    ck(rid+'/'+r['trip_id']+'/no_overlap_and_full_recharge',slack>=-VERIFY_TIME_TOL_S,slack)
                    resources.append({'resource_type':kind,'resource_id':rid,'previous_trip':prev['trip_id'],'next_trip':r['trip_id'],
                        'resource_ready_s':ready,'next_start_s':r['start_s'],'slack_s':slack,'pass':slack>=-VERIFY_TIME_TOL_S})
    summary={'checks_total':len(checks),'checks_passed':sum(c['pass'] for c in checks),'checks_failed':sum(not c['pass'] for c in checks),
        'trips':len(trips),'recomputed_boxes':len(done),'energy_kwh':all_e,'makespan_s':cmax,'min_return_soc_fraction':min_soc,
        'weighted_tardiness_s':tardy,'hard_late_s':hardlate,'min_hard_slack_s':min_hard if math.isfinite(min_hard) else None,
        'max_energy_error_kwh':maxeerr,'max_time_error_s':maxterr,'allow_hard_late_for_diagnostic_baseline':allow_hard_late}
    return summary,checks,details,boxchecks,resources


def run_q2_validation(root,workbook_rows=None):
    root=Path(root);out=root/'results/q2';data=json.loads((root/'data/cleaned/model_inputs.json').read_text('utf-8'))
    arc=independent_arcs(root,data)
    trips=read_csv(out/'Q2_运输架次.csv') if workbook_rows is None else workbook_rows['Q2_运输架次']
    boxes=read_csv(out/'Q2_逐箱交付.csv') if workbook_rows is None else workbook_rows['Q2_逐箱交付']
    summary,ck,tr,bx,res=validate_rows(data,arc,trips,boxes)
    save_json(out/'independent_validation.json',summary);write_csv(out/'validation_checks.csv',ck)
    write_csv(out/'independent_trip_recalculation.csv',tr);write_csv(out/'independent_box_recalculation.csv',bx);write_csv(out/'resource_interval_checks.csv',res)
    # 所有240条有向地形结果与原始DEM上的独立rasterio扫描比较。
    gc=[]
    for r in read_csv(out/'arc_geometry.csv'):
        a=arc[r['from_id'],r['to_id']]
        err=max(abs(a['d']-float(r['distance_m'])),abs(a['peak']-float(r['terrain_max_m'])))
        gc.append({'from_id':r['from_id'],'to_id':r['to_id'],'max_discrepancy_m':err,'pass':err<1e-6})
    write_csv(out/'all_arc_independent_check.csv',gc)
    summary['arc_checks']=len(gc);summary['arc_checks_failed']=sum(not x['pass'] for x in gc)
    save_json(out/'independent_validation.json',summary)
    if summary['checks_failed'] or summary['arc_checks_failed']:raise AssertionError('第二问独立复核失败，禁止生成最终提交标志')
    return summary
