"""新增复核：补充载荷、能耗假设、Q2对照、导出分项与延误边界。
Python 3.13.5；依赖锁定requirements.txt。参数与误差限集中于文件头。
"""
from pathlib import Path
from collections import Counter
import json, math
from io_utils import read_csv,write_csv,save_json
from config import CFG
from q2_validation import independent_arcs,validate_rows,independent_charge
TIME_TOL=1e-6
ENERGY_TOL=1e-8
STRESS_DELAY_S=(0,5,30,60,120)

def run_additional_checks(root):
    root=Path(root);q1=root/'results/q1';q2=root/'results/q2'
    data=json.loads((root/'data/cleaned/model_inputs.json').read_text('utf-8'))
    models={m['model_id']:m for m in data['transport_models']};boxes={b['box_id']:b for b in data['boxes']}
    arcs=independent_arcs(root,data);checks=[]
    def ck(name,ok,detail=''):checks.append({'check':name,'pass':bool(ok),'detail':str(detail)})
    def energy(g,u,v,q,hfactor=1.0,ufactor=1.0):
        m=models[g];a=arcs[u,v];L=m['empty_range_m']-(m['empty_range_m']-m['full_range_m'])*(q/m['max_payload_kg'])**CFG.range_load_exponent
        return hfactor*m['usable_energy_kwh']*a['d']/L+ufactor*(m['empty_mass_kg']+q)*CFG.gravity_m_s2*a['up']/(m['climb_efficiency']*CFG.joules_per_kwh)
    # 第二套枚举保留每一真实箱身份，不复用主求解器的物资数量压缩。
    exact_max={}
    for sid in sorted({b['service_id'] for b in boxes.values()}):
        bs=[b for b in boxes.values() if b['service_id']==sid];weights=[0.]*(1<<len(bs));volumes=[0.]*(1<<len(bs))
        for mask in range(1,len(weights)):
            bit=mask & -mask;i=bit.bit_length()-1;prev=mask^bit
            weights[mask]=weights[prev]+bs[i]['weight_kg'];volumes[mask]=volumes[prev]+bs[i]['volume_m3']
        for g,m in models.items():
            best=0.
            for w,v in zip(weights[1:],volumes[1:]):
                if w<=best or w>m['max_payload_kg']+1e-8 or v>m['volume_m3']+1e-9:continue
                ee=energy(g,'O01',sid,w,CFG.horizontal_energy_multiplier,CFG.climb_energy_multiplier)+energy(g,sid,'O01',0,CFG.horizontal_energy_multiplier,CFG.climb_energy_multiplier)
                if ee<=(1-m['reserve_fraction'])*m['usable_energy_kwh']+ENERGY_TOL:best=w
            exact_max[sid,g]=best
    for r in read_csv(q1/'payload_continuous_discrete.csv'):
        g=r['model_id'];sid=r['service_id'];key=g+sid;ids=r['max_payload_witness_box_ids'].split(';') if r['max_payload_witness_box_ids'] else []
        w=sum(boxes[b]['weight_kg'] for b in ids);v=sum(boxes[b]['volume_m3'] for b in ids)
        ck(key+'/witness_distinct_ids',len(ids)==len(set(ids)));ck(key+'/witness_service',all(boxes[b]['service_id']==sid for b in ids))
        ck(key+'/independent_exact_discrete_max',abs(exact_max[sid,g]-float(r['available_box_max_payload_kg']))<TIME_TOL)
        ck(key+'/witness_weight',abs(w-float(r['available_box_max_payload_kg']))<TIME_TOL)
        ck(key+'/witness_capacity',w<=models[g]['max_payload_kg']+TIME_TOL and v<=models[g]['volume_m3']+1e-9)
        ee=energy(g,'O01',sid,w,CFG.horizontal_energy_multiplier,CFG.climb_energy_multiplier)+energy(g,sid,'O01',0,CFG.horizontal_energy_multiplier,CFG.climb_energy_multiplier)
        ck(key+'/witness_energy',abs(ee-float(r['witness_energy_kwh']))<ENERGY_TOL)
        ck(key+'/witness_reserve',ee<=(1-models[g]['reserve_fraction'])*models[g]['usable_energy_kwh']+ENERGY_TOL)
    for r in read_csv(q1/'reserve_sensitivity.csv'):
        ck('formal_reserve_floor/'+str(r),float(r['reserve_fraction'])>=max(m['reserve_fraction'] for m in models.values()))
    for sc in read_csv(q1/'energy_assumption_sensitivity.csv'):
        h=float(sc['horizontal_multiplier']);u=float(sc['climb_multiplier']);p=q1/'energy_assumption_plans'/f'h{h:.1f}_u{u:.1f}.csv'
        if not p.exists():continue
        seen=[];es=[]
        for r in read_csv(p):
            ids=r['box_ids'].split(';');seen+=ids;w=sum(boxes[b]['weight_kg'] for b in ids);sid=r['service_id'];g=r['model_id']
            ee=energy(g,'O01',sid,w,h,u)+energy(g,sid,'O01',0,h,u);es.append(ee)
            ck(p.stem+'/'+r['trip_id']+'/energy',abs(ee-float(r['energy_kwh']))<ENERGY_TOL)
            ck(p.stem+'/'+r['trip_id']+'/reserve',ee<=(1-models[g]['reserve_fraction'])*models[g]['usable_energy_kwh']+ENERGY_TOL)
        ck(p.stem+'/coverage',Counter(seen)==Counter(boxes.keys()))
        ck(p.stem+'/sumenergy',abs(sum(es)-float(sc['energy_kwh']))<ENERGY_TOL)
    # 只读主方案输出分项，独立由输入与DEM重算，防止详细台账与模板分别写错。
    tasks={r['trip_id']:r for r in read_csv(q2/'trips.csv')};qsum={t:0. for t in tasks}
    for r in read_csv(q2/'legs.csv'):
        tid=r['trip_id'];g=r['model_id'];u=r['from_id'];v=r['to_id'];w=float(r['remaining_payload_at_departure_kg'])
        ee=energy(g,u,v,w,CFG.horizontal_energy_multiplier,CFG.climb_energy_multiplier)
        ck(tid+'/leg'+r['leg_index']+'/energy',abs(ee-float(r['leg_energy_kwh']))<ENERGY_TOL);qsum[tid]+=ee
        ids=r['delivered_box_ids'].split(';') if r['delivered_box_ids'] else []
        ck(tid+'/leg'+r['leg_index']+'/load_balance',abs(w-sum(boxes[b]['weight_kg'] for b in ids)-float(r['remaining_payload_after_handoff_kg']))<TIME_TOL)
        m=models[g];a=arcs[u,v];dt=a['up']/m['climb_speed_mps']+a['d']/m['cruise_speed_mps']+a['down']/m['descent_speed_mps']
        ck(tid+'/leg'+r['leg_index']+'/time',abs(dt-float(r['flight_s']))<TIME_TOL)
    for tid,r in tasks.items():ck(tid+'/legs_sum',abs(qsum[tid]-float(r['energy_kwh']))<ENERGY_TOL)
    bp={r['model_id']:r for r in data['transport_batteries']}
    for r in read_csv(q2/'battery_cycles.csv'):
        t=tasks[r['trip_id']];soc=1-qsum[t['trip_id']]/models[t['model_id']]['usable_energy_kwh'];ct=independent_charge(soc,bp[t['model_id']]['full_charge_s'])
        ck(t['trip_id']+'/charge_duration',abs(ct-float(r['charge_duration_s']))<TIME_TOL)
        ck(t['trip_id']+'/charge_complete',abs(float(t['return_s'])+ct-float(r['charge_end_s']))<TIME_TOL)
    # 对照实验也从逐箱表独立验证。冻结Q1方案只作为“不能直接继承”的诊断，允许记录硬逾期。
    exp=[]
    for name in ['q1_frozen','direct_only','energy_tradeoff']:
        folder=q2/'experiments'/name;tr=read_csv(folder/'trips.csv');bx=read_csv(folder/'box_deliveries.csv')
        ts=[dict(zip(['架次编号','无人机编号','机型编号','电池编号','开始时刻（s）','访问服务区顺序','返回O01时刻（s）','架次能耗（kWh）'],
                    [r['trip_id'],r['drone_id'],r['model_id'],r['battery_id'],r['start_s'],r['visit_order'],r['return_s'],r['energy_kwh']])) for r in tr]
        bs=[dict(zip(['货箱编号','架次编号','服务区编号','交付完成时刻（s）'],[r['box_id'],r['trip_id'],r['service_id'],r['delivery_complete_s']])) for r in bx]
        ss,cc,tt,bb,rr=validate_rows(data,arcs,ts,bs,allow_hard_late=name=='q1_frozen')
        save_json(folder/'independent_validation.json',ss);write_csv(folder/'independent_checks.csv',cc)
        ck('experiment/'+name,ss['checks_failed']==0)
        exp.append({'scenario':name,**ss})
    write_csv(q2/'experiment_validation_summary.csv',exp)
    # 冻结方案统一整体延后：不是允许迟交的正式方案，也不宣称进行了鲁棒重优化。
    stress=[];ds=read_csv(q2/'box_deliveries.csv')
    for delay in STRESS_DELAY_S:
        hardbad=[r for r in ds if r['hard_deadline_s'] and float(r['delivery_complete_s'])+delay>float(r['hard_deadline_s'])+TIME_TOL]
        late=[r for r in ds if float(r['delivery_complete_s'])+delay>float(r['expected_s'])+TIME_TOL]
        stress.append({'uniform_delay_s':delay,'hard_violated_boxes':len(hardbad),'expected_violated_boxes':len(late),
            'hard_violated_box_ids':';'.join(r['box_id'] for r in hardbad),'type':'frozen_plan_delay_diagnostic_not_optimized_solution'})
    write_csv(q2/'delay_stress_diagnostic.csv',stress)
    write_csv(root/'results/logs/additional_checks.csv',checks)
    s={'checks_total':len(checks),'checks_passed':sum(r['pass'] for r in checks),'checks_failed':sum(not r['pass'] for r in checks),'experiment_checks_total':sum(r['checks_total'] for r in exp),'experiment_checks_failed':sum(r['checks_failed'] for r in exp)}
    save_json(root/'results/logs/additional_validation.json',s)
    if s['checks_failed']:raise AssertionError('新增独立检查未通过')
    return s
