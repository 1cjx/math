"""闭环增量实验：固定已验证排程的能耗/充电/共同延迟压力测试及场景继承台账。
Python3.13.5；参数集中closure_config.py。压力测试不重新优化，不把失败点包装成可行解。
"""
from pathlib import Path
from collections import defaultdict,Counter
import json,math
from io_utils import read_csv,write_csv,save_json,sha256
from closure_config import CLOSURE_CFG

def independent_charge(soc,full):
    """直接从题面两段SOC增量独立积分，不调用求解器充电函数。"""
    if not 0<=soc<=1:raise ValueError('SOC越界')
    return full*((max(0.,.9-soc)/.9)*.65+((1-max(.9,soc))/.1)*.35)

def run_closure_experiments(root):
    root=Path(root);out=root/'results/closure';out.mkdir(parents=True,exist_ok=True)
    data=json.loads((root/'data/cleaned/model_inputs.json').read_text());model={m['model_id']:m for m in data['transport_models']}
    sums={q:json.loads((root/f'results/{q}/summary.json').read_text()) for q in ('q1','q2','q3','q4')}
    energyrows=[];chargerows=[];delayrows=[];room=[]
    for q in ('q2','q3'):
        tr=read_csv(root/f'results/{q}/trips.csv');cycles=read_csv(root/f'results/{q}/battery_cycles.csv');bytid={r['trip_id']:r for r in tr};batches=defaultdict(list)
        for c in cycles:batches[c['battery_id']].append(c)
        # 等效充电时间从已核验的逐次充电量反推不需要；直接读同机型附件值。
        full_by_model={g:next(float(x['full_charge_s']) for x in data['transport_batteries'] if x['model_id']==g) for g in model}
        for scale in CLOSURE_CFG.energy_scale_grid:
            reservebad=0;overempty=0;reusebad=0;slacks=[];socs=[];total=0.
            for r in tr:
                m=model[r['model_id']];e=float(r['energy_kwh'])*scale;soc=1-e/m['usable_energy_kwh'];socs.append(soc);total+=e
                reservebad+=soc<m['reserve_fraction']-1e-8;overempty+=soc<0
            for bid,cc in batches.items():
                cc=sorted(cc,key=lambda x:float(x['task_start_s']))
                for a,b in zip(cc,cc[1:]):
                    r=bytid[a['trip_id']];m=model[r['model_id']];soc=1-scale*float(r['energy_kwh'])/m['usable_energy_kwh']
                    if soc<0:reusebad+=1;continue
                    ready=float(a['return_s'])+independent_charge(soc,full_by_model[r['model_id']]);margin=float(b['task_start_s'])-ready;slacks.append(margin);reusebad+=margin<-1e-6
            energyrows.append({'question':q.upper(),'energy_multiplier':scale,'transport_energy_kwh':total,'minimum_soc_fraction':min(socs),
                'reserve_violating_sorties':reservebad,'negative_soc_sorties':overempty,'battery_reuse_conflicts':reusebad,'minimum_reuse_slack_s':min(slacks) if slacks else None,
                'energy_and_battery_feasible':reservebad==0 and reusebad==0,'experiment_scope':'只扰动运输能耗并重算充电；时刻/机身/中继/通信保持不变，不重优化'})
        for factor in CLOSURE_CFG.charging_scale_grid:
            gaps=[];bad=0
            for cc in batches.values():
                cc=sorted(cc,key=lambda x:float(x['task_start_s']))
                for a,b in zip(cc,cc[1:]):
                    duration=independent_charge(float(a['return_soc_fraction']),full_by_model[a['model_id']]);margin=float(b['task_start_s'])-float(a['return_s'])-factor*duration;gaps.append(margin);bad+=margin<-1e-6
            chargerows.append({'question':q.upper(),'full_charge_time_multiplier':factor,'reused_battery_transitions':len(gaps),'conflicting_transitions':bad,'minimum_reuse_slack_s':min(gaps) if gaps else None,'feasible':bad==0,'scope':'仅运输电池充电时间乘数；冻结任务/资源编号，不重排'})
        boxes=read_csv(root/f'results/{q}/box_deliveries.csv')
        for delay in CLOSURE_CFG.common_delay_grid_s:
            hard=[float(r['hard_deadline_s'])-float(r['delivery_complete_s'])-delay for r in boxes if r['hard_deadline_s']!='']
            late=sum(float(r['delivery_complete_s'])+delay>float(r['expected_s'])+1e-6 for r in boxes)
            delayrows.append({'question':q.upper(),'common_delay_s':delay,'minimum_hard_slack_s':min(hard),'hard_late_boxes':sum(x<-1e-6 for x in hard),'expected_late_boxes':late,'hard_feasible':min(hard)>=-1e-6,'scope':'运输、中继及充电整体平移；不改变相对占用/通信，截止时刻固定'})
        for r in tr:
            m=model[r['model_id']];base=float(r['energy_kwh']);room.append({'question':q.upper(),'trip_id':r['trip_id'],'model_id':r['model_id'],'energy_kwh':base,
                'maximum_energy_multiplier_from_SOC_only':(1-m['reserve_fraction'])*m['usable_energy_kwh']/base,
                'scope':'仅返航能量约束；不是含充电/通信的总鲁棒上界'})
    write_csv(out/'fixed_energy_sweep.csv',energyrows);write_csv(out/'fixed_charging_sweep.csv',chargerows);write_csv(out/'common_delay_fine_sweep.csv',delayrows);write_csv(out/'per_trip_energy_threshold.csv',room)
    q3=sums['q3'];cert=json.loads((root/'results/q3/closure_repair_certificate.json').read_text());base=cert.get('baseline_summary',q3)
    write_csv(out/'closed_loop_cost.csv',[
      {'方案':'旧Q3独立寻优对照','运输架次':base['trips'],'中继架次':base['relay_trips'],'联合完成时间_s':base['joint_makespan_s'],'总能耗_kwh':base['total_energy_kwh'],'严格不可拆单元数':len(cert['strict_components_before']),'允许中继复制':False},
      {'方案':'最终Q3严格继承主方案','运输架次':q3['trips'],'中继架次':q3['relay_trips'],'联合完成时间_s':q3['joint_makespan_s'],'总能耗_kwh':q3['total_energy_kwh'],'严格不可拆单元数':len(cert['strict_components_after']),'允许中继复制':False}])
    # 提交依据矩阵：题定规则、实现范围和额外假设严格分列。
    requirements=[
      ('共同','原始坐标、需求、装备以附件为准','题面2页','data/raw；results/audit/source_cell_trace.csv','没有覆盖题定值'),
      ('共同','质量、体积、时间、能量单位统一','题面5页','data/cleaned/data_dictionary.csv','质量kg、体积m³、时间s、能量kWh'),
      ('共同','水平直线；全部穿越DEM像元最高值加50米','附录2','results/q2/all_arc_independent_check.csv','全像元几何；不是均匀抽样代替峰值'),
      ('共同','O01地面；服务区30米作业；每段重新爬升','附录2','results/q3/independent_transport_energy.csv','去程与返程分段载荷'),
      ('共同','货箱不可拆；每箱恰好交付一次','问题1—4','results/q3/independent_box_checks.csv','逐箱身份守恒'),
      ('共同','额定质量、总体积和返航余量同时满足','问题1—4','results/q3/independent_transport_checks.csv','无箱长宽高，未声称三维装箱'),
      ('共同','下降附加能耗为0','附录2','src/physics.py；src/q2_physics.py','下降仍计飞行时间'),
      ('共同','水平能耗和爬升能耗分项模型闭合','附录2未展开分项','src/physics.py','补充假设，不冒充唯一题定公式'),
      ('Q1','15服务区×3机型连续最大安全载荷','问题1首段','results/q1/max_safe_payload.csv','加现有整箱可实现载荷对照'),
      ('Q1','O01—单一区域—O01；不跨区组批','问题1','results/q1/validation_checks.csv','不强加后续实体/通信排程'),
      ('Q1','多指标优先关系明示','问题1-2','results/q1/objective_comparison.csv','主N→E→累计作业时间，非三指标同时最小'),
      ('Q1','安全余量敏感性','问题1-3','results/q1/reserve_sensitivity.csv','主实验不低于附件20%，不可行值不补0'),
      ('Q1','精确最少架次与DP证明','问题1','results/q1/independent_optimality.csv','适用于明示物理口径'),
      ('Q2','多点访问、卸货后剩余载荷更新','问题2','results/q2/legs.csv','每段计质量，不把全部路程都按起飞质量'),
      ('Q2','无人机机身与同型共享电池分别排程','问题2','results/q2/resource_interval_checks.csv','库存含初装与备用，不额外扩充'),
      ('Q2','医疗期望时限和首批截止是硬约束','问题2','results/q2/independent_box_recalculation.csv','其他物资期望时间为软评价'),
      ('Q2','返回后的两阶段充电至100%再复用','附录2','results/q2/battery_cycles.csv','不同电池并行充电；未虚设充电桩瓶颈'),
      ('Q2','全部任务时间取最后运输返回','问题2-1','results/q2/summary.json','不取最后一箱送达或充满电时刻'),
      ('Q2','不考虑通信约束','问题2首句','results/q3/q2_direct_only_audit.json','Q2通信有缺口不构成Q2违法'),
      ('Q3','爬升、巡航、下降、交接全过程连续通信','问题3','results/q3/independent_continuous_certificate.csv','区间与孤立点检查，稠密采样仅交叉验证'),
      ('Q3','直连优先；单架中继；接入/回传同刻可用','附录3','results/q3/Q3_通信保障.csv','没有多跳中继或同刻多提供者'),
      ('Q3','收发双向取更严格预算','附录3','results/q3/radio_bidirectional_budgets.csv','灵敏度加衰落裕量，不忽略地形附加损耗'),
      ('Q3','悬停点在DEM内，离地高度不超上限','问题3','results/q3/independent_relay_checks.csv','有限候选搜索，不声称连续空间全局最优'),
      ('Q3','中继准备、建链、周转、服务及充电','附录2','results/q3/relay_sorties.csv','含建链悬停能耗，服务结束再返回'),
      ('Q3','联合完工取运输/中继最晚返回','问题3-1','results/q3/summary.json','独立核验最后中继返回，非充电结束'),
      ('Q3','最终方案在源库存内可执行','问题3','results/q3/independent_resources.csv','与Q4增补配置明确区分'),
      ('Q3→Q4','在Q3定稿前筛选严格三组可分区候选','四问联合继承','results/q3/closure_existing_candidates.csv','增加下游可分区选择准则并公开代价'),
      ('Q4','15服务区各一次，2/3组都非空','问题4','results/q4/independent_partition_certificate.csv','运输和共同中继依赖联合并查集'),
      ('Q4','保持货箱、访问序、时刻、中继任务和通信关系','问题4','results/q4/K3/independent_inheritance_resource_checks.csv','严格不复制/不拆分/不缩短中继任务'),
      ('Q4','资源执行期间不跨组调配','问题4','results/q4/K3/resource_allocations.csv','仅在开始前重新指派同型资源'),
      ('Q4','资源规模、冗余、均衡、库存缺口比较','问题4-1','results/q4/selected_comparison.csv','不同类型库存不能相互抵扣'),
      ('Q4','资源不足报告缺口，不伪称原库存可行','问题4-2','results/q4/inventory_gap.csv','需求配置补足后物理可行'),
      ('提交','原模板表名/表头/单位，Q3配套不覆盖Q2','四、提交要求','submission/提交验收.json','模板没有Q3运输表则另附配套'),
      ('提交','CSV→Excel精确浮点往返及实际表格物理检查','四、提交要求','src/submission.py','防止16有效位序列化造成通信边界误判'),
      ('论文','中文图与数值可追溯、假设及范围明示','四、提交要求','paper/figure_catalog.csv','重复视图不谎称独立实验次数')]
    write_csv(out/'requirement_traceability.csv',[{'问题':a,'题意要求':b,'来源定位':c,'实现与证据':d,'边界说明':e} for a,b,c,d,e in requirements])
    summary={'additional_energy_scenarios':len(energyrows),'additional_charging_scenarios':len(chargerows),'common_delay_scenarios':len(delayrows),
      'per_trip_energy_bounds':len(room),'source_requirement_rows':len(requirements),
      'Q3_standalone_vs_closure_time_cost_s':q3['joint_makespan_s']-base['joint_makespan_s'],
      'Q3_standalone_vs_closure_energy_cost_kwh':q3['total_energy_kwh']-base['total_energy_kwh'],
      'strict_Q4_no_replication':True,'Q4_source_inventory_feasible':sums['q4']['inventory_feasible_partition_counts'],
      'scope':'固定排程压力测试不重新优化，失败点保留；不用于声明鲁棒全局保证'}
    save_json(out/'experiment_summary.json',summary)
    return summary
