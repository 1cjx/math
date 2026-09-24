"""第一问修订：连续/整箱载荷并列，统一时间口径，能耗假设扰动实验。
Python 3.13.5；所有非题定实验参数集中配置，不改原始数据。
"""
from pathlib import Path
from dataclasses import replace
from collections import defaultdict
import json
import physics
from config import CFG
from optimizer import make_groups,enumerate_patterns,solve_all
from io_utils import read_csv,write_csv,save_json

ENERGY_SCENARIOS=((1.0,1.0),(0.9,1.0),(1.1,1.0),(1.0,0.9),(1.0,1.1))

def enhance_q1(root,data):
    root=Path(root);out=root/'results/q1'
    routes=[{k:(v if k=='service_id' else float(v)) for k,v in r.items()} for r in read_csv(out/'route_geometry.csv')]
    caps={(r['service_id'],r['model_id']):r for r in read_csv(out/'max_safe_payload.csv')}
    records=[]
    for r in routes:
        sid=r['service_id'];boxes=[b for b in data['boxes'] if b['service_id']==sid]
        groups=make_groups(boxes)
        for model in data['transport_models']:
            pp,_=enumerate_patterns(groups,[model],r)
            c=caps[sid,model['model_id']]
            best=max(pp,key=lambda p:(p['weight_kg'],-p['energy_kwh'],-p['box_count'])) if pp else None
            ids=[]
            if best:
                for num,g in zip(best['counts'],groups):ids.extend(b['box_id'] for b in g['boxes'][:num])
            records.append({'service_id':sid,'model_id':model['model_id'],'rated_payload_kg':model['max_payload_kg'],
                'continuous_safe_payload_kg':float(c['max_safe_payload_kg']) if c['max_safe_payload_kg'] else None,
                'available_box_max_payload_kg':best['weight_kg'] if best else None,'available_total_weight_kg':sum(b['weight_kg'] for b in boxes),
                'max_payload_witness_box_ids':';'.join(sorted(ids)),'witness_volume_m3':best['volume_m3'] if best else None,
                'witness_energy_kwh':best['energy_kwh'] if best else None,'reserve_fraction':model['reserve_fraction'],
                'note':'逐(服务区,机型)单架次能力见证，不是全箱唯一分配方案'})
    write_csv(out/'payload_continuous_discrete.csv',records)
    # 三个时间量保留，但原模板只有一个列名，不擅自改表头。
    rows=read_csv(out/'batches_NET.csv')
    write_csv(out/'time_components.csv',[{'trip_id':r['trip_id'],'preparation_load_s':r['preparation_load_s'],
        'flight_only_s':r['flight_time_s'],'handoff_s':r['handoff_s'],'airborne_service_s':r['airborne_service_s'],
        'template_roundtrip_s':r[CFG.template_time_basis],'operation_time_s':r['operation_time_s']} for r in rows])
    original=physics.CFG;sc=[]
    try:
        for h,u in ENERGY_SCENARIOS:
            physics.CFG=replace(original,horizontal_energy_multiplier=h,climb_energy_multiplier=u)
            plan,_,s=solve_all(data,routes,CFG.main_priority)
            sc.append({'horizontal_multiplier':h,'climb_multiplier':u,'feasible':s['feasible'],
                       'trips':s.get('trips'),'energy_kwh':s.get('energy_kwh'),'operation_time_s':s.get('operation_time_s'),
                       'min_return_soc_fraction':s.get('min_return_soc_fraction'),
                       'type':'nominal' if (h,u)==(1.0,1.0) else 'assumption_perturbation_not_source_parameter'})
            if plan:
                write_csv(out/'energy_assumption_plans'/f'h{h:.1f}_u{u:.1f}.csv',plan)
    finally:physics.CFG=original
    write_csv(out/'energy_assumption_sensitivity.csv',sc)
    save_json(out/'revision_status.json',{
        'formal_reserve_scenarios':list(CFG.reserve_scenarios),'no_relaxation_below_source_floor':all(r>=min(m['reserve_fraction'] for m in data['transport_models']) for r in CFG.reserve_scenarios),
        'continuous_and_discrete_pairs':len(records),'time_definition':'准备开始至返抵O01；Q1往返时间等于Q2同架次返回时刻减开始时刻',
        'time_definition_is_declared_interpretation':True,'energy_assumptions_explicit':True,
        'notes':['各档均重新优化','仅分项模型假设扰动，不改源机型电量和标准航程','提交表标题与原模板保持不变']})
