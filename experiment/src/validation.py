"""独立复核：不调用主能耗/时间函数，逐箱位掩码DP复核主组批最优性。
Python 3.13.5；numpy 2.3.5、rasterio 1.5.0。源算法为计数状态DP；
本模块使用每个货箱的身份位掩码，避免等价类压缩实现错误被同一代码掩盖。
"""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import json,math
import numpy as np
import rasterio
from rasterio.features import rasterize
from io_utils import read_csv,write_csv,save_json
from config import CFG


def independent_metrics(m,r,w,n):
    L=m['empty_range_m']-(m['empty_range_m']-m['full_range_m'])*(w/m['max_payload_kg'])**CFG.range_load_exponent
    E=CFG.horizontal_energy_multiplier*m['usable_energy_kwh']*r['distance_m']*(1/L+1/m['empty_range_m'])
    E+=CFG.climb_energy_multiplier*CFG.gravity_m_s2*((m['empty_mass_kg']+w)*r['outbound_climb_m']+m['empty_mass_kg']*r['inbound_climb_m'])/(CFG.joules_per_kwh*m['climb_efficiency'])
    flight=2*r['distance_m']/m['cruise_speed_mps']+(r['outbound_climb_m']+r['inbound_climb_m'])/m['climb_speed_mps']+(r['outbound_descent_m']+r['inbound_descent_m'])/m['descent_speed_mps']
    t=flight+m['prepare_s']+n*m['load_per_box_s']+m['handoff_base_s']+n*m['handoff_per_box_s']
    return E,t

def bitmask_exact(boxes,models,route):
    n=len(boxes);M=1<<n
    weights=[0.0]*M;volumes=[0.0]*M;cost=[None]*M
    for mask in range(1,M):
        bit=mask&-mask;j=bit.bit_length()-1;prev=mask^bit
        w=weights[mask]=weights[prev]+boxes[j]['weight_kg'];v=volumes[mask]=volumes[prev]+boxes[j]['volume_m3']
        for m in models:
            if w>m['max_payload_kg']+CFG.capacity_tolerance_kg or v>m['volume_m3']+CFG.geometry_tolerance:continue
            e,t=independent_metrics(m,route,w,mask.bit_count())
            if e>(1-m['reserve_fraction'])*m['usable_energy_kwh']+CFG.energy_tolerance_kwh:continue
            cand=(1,e,t)
            if cost[mask] is None or (round(e,CFG.comparison_energy_decimals),round(t,CFG.comparison_time_decimals))<(round(cost[mask][1],CFG.comparison_energy_decimals),round(cost[mask][2],CFG.comparison_time_decimals)):cost[mask]=cand
    examined=0
    def key(c):return (c[0],round(c[1],CFG.comparison_energy_decimals),round(c[2],CFG.comparison_time_decimals))
    @lru_cache(None)
    def dp(mask):
        nonlocal examined
        if mask==0:return (0,0.0,0.0)
        anchor=mask&-mask;sub=mask;best=None
        while sub:
            if sub&anchor and cost[sub] is not None:
                examined+=1
                prev=dp(mask^sub)
                if prev is not None:
                    a=cost[sub];cand=(prev[0]+1,prev[1]+a[1],prev[2]+a[2])
                    if best is None or key(cand)<key(best):best=cand
            sub=(sub-1)&mask
        return best
    result=dp(M-1)
    return result,{'bitmask_states':M,'cached_states':dp.cache_info().currsize,'transitions':examined}

def run_validation(root):
    root=Path(root);out=root/'results/q1'
    data=json.loads((root/'data/cleaned/model_inputs.json').read_text('utf-8'))
    rawroutes=read_csv(out/'route_geometry.csv')
    routes={r['service_id']:{k:(v if k=='service_id' else float(v)) for k,v in r.items()} for r in rawroutes}
    models={r['model_id']:r for r in data['transport_models']};boxes={r['box_id']:r for r in data['boxes']}
    checks=[];tripchecks=[]
    def check(label,ok,details=''):
        checks.append({'check':label,'pass':bool(ok),'details':str(details)})
    plans=list(out.glob('batches_*.csv'))+list((out/'sensitivity_plans').glob('reserve_*.csv'))
    for p in sorted(plans):
        allids=[]
        for b in read_csv(p):
            ids=b['box_ids'].split(';');m=models[b['model_id']];r=routes[b['service_id']]
            exists=all(bid in boxes for bid in ids);check(p.name+'/'+b['trip_id']+' known ids',exists)
            if not exists:continue
            bs=[boxes[bid] for bid in ids];w=sum(bb['weight_kg'] for bb in bs);v=sum(bb['volume_m3'] for bb in bs)
            e,t=independent_metrics(m,r,w,len(bs));rho=float(b['reserve_fraction']);soc=1-e/m['usable_energy_kwh']
            conditions={'single_service':all(bb['service_id']==b['service_id'] for bb in bs),'no_duplicate_within_trip':len(set(ids))==len(ids),
                'weight_feasible':w<=m['max_payload_kg']+CFG.capacity_tolerance_kg,
                'volume_feasible':v<=m['volume_m3']+CFG.geometry_tolerance,'energy_feasible':e<=(1-rho)*m['usable_energy_kwh']+CFG.energy_tolerance_kwh,
                'weight_export_equal':abs(w-float(b['weight_kg']))<CFG.capacity_tolerance_kg,'volume_export_equal':abs(v-float(b['volume_m3']))<CFG.geometry_tolerance,
                'energy_export_equal':abs(e-float(b['energy_kwh']))<CFG.capacity_tolerance_kg,
                'time_export_equal':abs(t-float(b['operation_time_s']))<CFG.capacity_tolerance_kg,
                'soc_export_equal':abs(soc-float(b['return_soc_fraction']))<CFG.geometry_tolerance}
            for label,ok in conditions.items():check(p.name+'/'+b['trip_id']+' '+label,ok)
            tripchecks.append({'plan_file':p.name,'trip_id':b['trip_id'],'independent_energy_kwh':e,'independent_time_s':t,'return_soc_fraction':soc,
                'energy_error_kwh':e-float(b['energy_kwh']),'time_error_s':t-float(b['operation_time_s']),**conditions,'all_pass':all(conditions.values())})
            allids+=ids
        check(p.name+' exact once coverage',Counter(allids)==Counter(boxes.keys()))
    # 各服务区在身份空间中的第二套精确算法，与主DP逐项一致。
    maininfo={r['service_id']:r for r in read_csv(out/'optimality_NET.csv')};proof=[]
    for sid in sorted(routes):
        bs=[b for b in data['boxes'] if b['service_id']==sid]
        value,stats=bitmask_exact(bs,list(models.values()),routes[sid]);main=maininfo[sid]
        agree=value is not None and value[0]==int(main['trips']) and abs(value[1]-float(main['energy_kwh']))<CFG.capacity_tolerance_kg and abs(value[2]-float(main['operation_time_s']))<CFG.capacity_tolerance_kg
        check(sid+' independent bitmask optimum',agree,value)
        proof.append({'service_id':sid,'box_count':len(bs),**stats,'independent_min_trips':value[0],
          'independent_energy_kwh':value[1],'independent_operation_time_s':value[2],'agrees_with_count_DP':agree})
    # 栅格库all_touched独立复核沿途最高像元，不调用主Supercover函数。
    with rasterio.open(root/'data/cleaned/geospatial/dem_clean.tif') as ds:
        arr=ds.read(1);transform=ds.transform
    depot=data['depots'][0];terrainchecks=[]
    for s in data['services']:
        geom={'type':'LineString','coordinates':[(depot['lon_deg'],depot['lat_deg']),(s['lon_deg'],s['lat_deg'])]}
        mask=rasterize([(geom,1)],out_shape=arr.shape,transform=transform,all_touched=True,dtype='uint8')
        mx=float(arr[mask.astype(bool)].max());r=routes[s['node_id']]
        agree=abs(mx-r['terrain_max_m'])<CFG.geometry_tolerance
        check(s['node_id']+' independent raster maximum',agree)
        terrainchecks.append({'service_id':s['node_id'],'rasterio_terrain_max_m':mx,'supercover_terrain_max_m':r['terrain_max_m'],
            'agree':agree,'rasterio_cells':int(mask.sum()),'supercover_cells':int(r['crossed_cells'])})
    # 连续最大载荷：可行侧、约束类型与对安全余量的单调性。
    for c in read_csv(out/'max_safe_payload.csv'):
        if c['max_safe_payload_kg']=='':continue
        q=float(c['max_safe_payload_kg']);m=models[c['model_id']];r=routes[c['service_id']]
        e,_=independent_metrics(m,r,q,0);budget=(1-float(c['reserve_fraction']))*m['usable_energy_kwh']
        check(c['service_id']+c['model_id']+' safe capacity feasible',q<=m['max_payload_kg'] and e<=budget+CFG.energy_tolerance_kwh)
        if c['limiting_factor']=='energy':check(c['service_id']+c['model_id']+' active energy bound',abs(e-budget)<CFG.capacity_tolerance_kg)
        values=[independent_metrics(m,r,w,0)[0] for w in np.linspace(0,m['max_payload_kg'],CFG.capacity_monotonicity_test_points)]
        check(c['service_id']+c['model_id']+' monotonic load-energy',bool(np.all(np.diff(values)>=0)))
    cps=read_csv(out/'capacity_sensitivity.csv')
    for sid in sorted(routes):
        for mid in models:
            items=sorted([r for r in cps if r['service_id']==sid and r['model_id']==mid],key=lambda x:float(x['reserve_fraction']))
            seq=[float(r['max_safe_payload_kg']) if r['max_safe_payload_kg'] else -math.inf for r in items]
            check(sid+mid+' nonincreasing capacity vs reserve',all(a>=b-CFG.capacity_tolerance_kg for a,b in zip(seq,seq[1:])))
    main=json.loads((out/'summary.json').read_text('utf-8'))
    lb=sum(int(r['aggregate_capacity_lower_bound']) for r in read_csv(out/'service_summary.csv'))
    check('global minimum trips lower bound attained',lb==main['trips'],f'lower bound {lb}; feasible trips {main["trips"]}')
    write_csv(out/'validation_checks.csv',checks);write_csv(out/'trip_validation.csv',tripchecks)
    write_csv(out/'independent_optimality.csv',proof);write_csv(out/'independent_terrain_check.csv',terrainchecks)
    summary={'checks_total':len(checks),'checks_passed':sum(r['pass'] for r in checks),'checks_failed':sum(not r['pass'] for r in checks),
        'plans_validated':len(plans),'trip_records_validated':len(tripchecks),'independent_optimum_services':len(proof),'minimum_trips_lower_bound':lb,
        'max_energy_recalculation_error_kwh':max(abs(r['energy_error_kwh']) for r in tripchecks),'max_time_recalculation_error_s':max(abs(r['time_error_s']) for r in tripchecks)}
    save_json(out/'validation_summary.json',summary)
    if summary['checks_failed']:raise AssertionError(f'{summary["checks_failed"]}项结果复核失败')
    return summary
