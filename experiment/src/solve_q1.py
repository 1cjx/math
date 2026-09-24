"""第一问结果编排：载荷矩阵、精确组批、优先级权衡、安全余量敏感性。"""
from pathlib import Path
from collections import defaultdict,Counter
import json,copy
import rasterio
from config import CFG,PARAMETER_PROVENANCE
from io_utils import write_csv,save_json
from physics import route_info,safe_payload,trip_energy
from optimizer import solve_all,global_flight_energy_frontier,singleton_baseline


def run_q1(root,data=None):
    root=Path(root);out=root/'results/q1';out.mkdir(parents=True,exist_ok=True)
    if data is None:data=json.loads((root/'data/cleaned/model_inputs.json').read_text(encoding='utf-8'))
    with rasterio.open(root/'data/cleaned/geospatial/dem_clean.tif') as ds:arr=ds.read(1);transform=ds.transform
    routes=[];profiles=[]
    for s in data['services']:
        route,profile=route_info(data['depots'][0],s,arr,transform);routes.append(route);profiles+=profile
    write_csv(out/'route_geometry.csv',routes);write_csv(out/'route_dem_cells.csv',profiles)
    cap=[safe_payload(m,r) for r in routes for m in data['transport_models']]
    write_csv(out/'max_safe_payload.csv',cap)
    matrix=[{'service_id':r['service_id'],**{m['model_id']+'_kg':next(c['max_safe_payload_kg'] for c in cap if (c['service_id'],c['model_id'])==(r['service_id'],m['model_id'])) for m in data['transport_models']}} for r in routes]
    write_csv(out/'max_safe_payload_matrix.csv',matrix)
    alternatives=[];main=None;maininfo=None;mainplan=None
    for order in CFG.priority_orders:
        plan,info,summary=solve_all(data,routes,order)
        alternatives.append(summary)
        if plan is not None:write_csv(out/f'batches_{order}.csv',plan)
        write_csv(out/f'optimality_{order}.csv',info)
        if order==CFG.main_priority:main=summary;maininfo=info;mainplan=plan
    if not main['feasible']:raise ValueError('默认安全余量下全部货箱不可交付，见结果中的不可行服务区')
    save_json(out/'objective_comparison.json',alternatives)
    write_csv(out/'objective_comparison.csv',[{k:v for k,v in s.items() if not isinstance(v,(dict,list))} for s in alternatives])
    # 与模板Q1字段同名、同顺序的CSV，是跨平台可复现提交数据。
    template=[]
    for b in mainplan:
        template.append({'架次编号':b['trip_id'],'服务区编号':b['service_id'],'机型编号':b['model_id'],'货箱编号列表':b['box_ids'],
          '总质量（kg）':b['weight_kg'],'总体积（m³）':b['volume_m3'],'往返时间（s）':b[CFG.template_time_basis],
          '架次能耗（kWh）':b['energy_kwh'],'返航SOC（%）':b['return_soc_fraction']*CFG.percent_base})
    write_csv(out/'Q1_单点组批.csv',template)
    assignment=[]
    for b in mainplan:
        assignment.extend({'box_id':bid,'trip_id':b['trip_id'],'service_id':b['service_id'],'model_id':b['model_id']} for bid in b['box_ids'].split(';'))
    write_csv(out/'box_assignment.csv',sorted(assignment,key=lambda x:x['box_id']))
    service=[]
    for r in routes:
        pp=[b for b in mainplan if b['service_id']==r['service_id']]
        payloadmax=max(c['max_safe_payload_kg'] or 0 for c in cap if c['service_id']==r['service_id'])
        # 解析下界仅作直观检查；最终最优性依据完整DP，不把未达到此下界称为不最优。
        import math
        lower=max(math.ceil(sum(b['weight_kg'] for b in pp)/payloadmax-CFG.capacity_tolerance_kg),
                  math.ceil(sum(b['volume_m3'] for b in pp)/max(m['volume_m3'] for m in data['transport_models'])-CFG.geometry_tolerance))
        service.append({'service_id':r['service_id'],'distance_m':r['distance_m'],'terrain_max_m':r['terrain_max_m'],'cruise_altitude_m':r['cruise_altitude_m'],
          'trips':len(pp),'model_mix':';'.join(f'{k}:{v}' for k,v in sorted(Counter(b['model_id'] for b in pp).items())),
          'box_count':sum(b['box_count'] for b in pp),'weight_kg':sum(b['weight_kg'] for b in pp),'volume_m3':sum(b['volume_m3'] for b in pp),
          'energy_kwh':sum(b['energy_kwh'] for b in pp),'operation_time_s':sum(b['operation_time_s'] for b in pp),
          'aggregate_capacity_lower_bound':lower,'exact_min_trips':len(pp)})
    write_csv(out/'service_summary.csv',service)
    # 安全余量扫掠：不可行保持明确状态，不用0填充，也不丢弃无法交付货箱。
    sensitivity=[];allcaps=[]
    for previous in (out/'sensitivity_plans').glob('reserve_*'):
        if previous.is_file() and previous.suffix in ('.csv','.json'):previous.unlink()
    for rho in CFG.reserve_scenarios:
        plan,info,ss=solve_all(data,routes,CFG.main_priority,rho)
        ss['reserve_fraction']=rho;sensitivity.append(ss)
        allcaps.extend(safe_payload(m,r,rho) for r in routes for m in data['transport_models'])
        label=f'{int(round(rho*CFG.percent_base)):02d}'
        if plan is not None:write_csv(out/'sensitivity_plans'/f'reserve_{label}.csv',plan)
        save_json(out/'sensitivity_plans'/f'reserve_{label}_status.json',ss)
    save_json(out/'reserve_sensitivity.json',sensitivity)
    write_csv(out/'reserve_sensitivity.csv',[{'reserve_fraction':s['reserve_fraction'],'feasible':s['feasible'],'trips':s.get('trips'),
      'energy_kwh':s.get('energy_kwh'),'operation_time_s':s.get('operation_time_s'),'min_return_soc_fraction':s.get('min_return_soc_fraction'),
      'model_mix':';'.join(f'{k}:{v}' for k,v in sorted(s.get('model_trip_counts',{}).items())),'infeasible_services':';'.join(s.get('infeasible_services',[]))} for s in sensitivity])
    write_csv(out/'capacity_sensitivity.csv',allcaps)
    # 任意货箱允许单独飞时的全局安全余量理论上界。
    threshold=[];rm={r['service_id']:r for r in routes}
    for b in data['boxes']:
        options=[]
        for m in data['transport_models']:
            if b['weight_kg']<=m['max_payload_kg'] and b['volume_m3']<=m['volume_m3']:
                rho=1-trip_energy(m,rm[b['service_id']],b['weight_kg'])['energy_kwh']/m['usable_energy_kwh']
                options.append((rho,m['model_id']))
        rho,model=max(options)
        threshold.append({'box_id':b['box_id'],'service_id':b['service_id'],'material_type':b['material_type'],
                          'max_reserve_fraction':rho,'best_model_for_reserve':model})
    write_csv(out/'single_box_reserve_thresholds.csv',threshold)
    critical=min(threshold,key=lambda b:b['max_reserve_fraction'])
    frontier,localfront=global_flight_energy_frontier(data,routes)
    write_csv(out/'flight_energy_frontier.csv',frontier);write_csv(out/'service_flight_energy_frontier.csv',localfront)
    baseline=singleton_baseline(data,routes);save_json(out/'single_box_baseline.json',baseline)
    # 仅用于不确定性评估：将全部节点高程改用DEM像元，不覆盖正式清洗数据。
    d_alt=copy.deepcopy(data);nm={r['node_id']:r for r in data['nodes']}
    for r in d_alt['depots']+d_alt['services']:r['ground_elevation_m']=nm[r['node_id']]['dem_at_node_m']
    alt_routes=[route_info(d_alt['depots'][0],s,arr,transform)[0] for s in d_alt['services']]
    altplan,_,altsum=solve_all(d_alt,alt_routes)
    if altplan is not None:write_csv(out/'alternative_dem_node_elevation_batches.csv',altplan)
    save_json(out/'alternative_dem_node_elevation_summary.json',altsum)
    main.update({'baseline':baseline,'critical_common_reserve_fraction':critical['max_reserve_fraction'],'critical_box':critical['box_id'],
      'critical_service':critical['service_id'],'capacity_energy_limited_count':sum(c['limiting_factor']=='energy' for c in cap),
      'max_route_geometry_discrepancy_m':max(abs(r['geodesic_max_difference_m']) for r in routes),
      'max_coarse_sample_underestimate_m':max(r['coarse_sampling_underestimate_m'] for r in routes),
      'supplementary_assumptions':PARAMETER_PROVENANCE,'exact_algorithm':'enumerated_feasible_patterns + count_state_DP',
      'pareto_N_E_points':sum(r['pareto_efficient_N_E'] for r in frontier)})
    save_json(out/'summary.json',main)
    return main
