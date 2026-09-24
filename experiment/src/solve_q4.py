"""第四问核心算法：多点必须同组分量→全划分枚举→固定区间精确资源配置。
Python 3.13.5；numpy 2.3.5（仅沿用I/O），其余核心仅使用标准库。
参数见q4_config.py。读取当次Q3主方案，不读取任何参考解作为优化输入。
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
import json, math, heapq, itertools
from io_utils import read_csv, write_csv, save_json, sha256
from q2_physics import charge_duration
from q4_config import Q4CFG, RESOURCE_KEYS, RESOURCE_NAMES, Q4_HEADERS, SOURCE_Q3_FILES

@dataclass(frozen=True)
class Interval:
    task_id: str
    resource_type: str
    start_s: float
    ready_s: float
    return_s: float
    source_resource_id: str

class UnionFind:
    def __init__(self, items): self.parent={x:x for x in items}
    def find(self,x):
        if x not in self.parent: raise ValueError(f'未知节点 {x}')
        if self.parent[x]!=x: self.parent[x]=self.find(self.parent[x])
        return self.parent[x]
    def union(self,a,b):
        x,y=sorted((self.find(a),self.find(b))); self.parent[y]=x
    def groups(self):
        out=defaultdict(list)
        for x in sorted(self.parent): out[self.find(x)].append(x)
        return sorted(out.values(),key=lambda r:r[0])

def canonical_partitions(n:int,k:int):
    """限制增长串：每个无标签非空划分恰枚举一次，无随机性，无候选截断。"""
    if not 1<=k<=n: return
    def rec(a,maximum):
        if len(a)==n:
            if maximum+1==k: yield tuple(a)
            return
        if maximum+1+n-len(a)<k: return
        for g in range(min(maximum+1,k-1)+1): yield from rec(a+[g],max(maximum,g))
    yield from rec([0],0)

def interval_coloring(intervals, tolerance=Q4CFG.time_tolerance_s):
    """最少资源着色：最早可用实体复用。半开占用[start, ready)。
    ready≤next_start+tol仅吸收源浮点舍入，不允许跳过真实充电或周转。
    返回分配、峰值证书和每个事件时刻的活跃量。
    """
    items=sorted(intervals,key=lambda a:(a.start_s,a.ready_s,a.task_id))
    if any(not math.isfinite(x.start_s+x.ready_s) or x.start_s<0 or x.ready_s<=x.start_s for x in items):
        raise ValueError('无效资源占用区间')
    busy=[];free=[];total=0;assign={}
    for x in items:
        while busy and busy[0][0]<=x.start_s+tolerance:
            _,slot=heapq.heappop(busy);heapq.heappush(free,slot)
        if free: slot=heapq.heappop(free)
        else:total+=1;slot=total
        assign[x.task_id]=slot;heapq.heappush(busy,(x.ready_s,slot))
    levels=[];peak=0;witness_time=None;witness=[]
    for t in sorted({x.start_s for x in items}|{x.ready_s for x in items}):
        active=[x.task_id for x in items if x.start_s<=t and x.ready_s>t+tolerance]
        levels.append({'time_s':t,'active':len(active)})
        if len(active)>peak:peak=len(active);witness_time=t;witness=active
    if total!=peak:raise AssertionError('着色上界与同刻占用下界不相等')
    return total,assign,{'time_s':witness_time,'task_ids':witness,'peak':peak},levels

def cv(values):
    avg=math.fsum(values)/len(values)
    return math.sqrt(math.fsum((x-avg)**2 for x in values)/len(values))/avg if avg else 0.

def frozen_hashes(root):
    return {p:sha256(Path(root)/'results/q3'/p) for p in SOURCE_Q3_FILES}

class FrozenQ3:
    """运输任务、原中继任务和通信关系只读；组内实体重新分配在开始前完成。"""
    def __init__(self,root):
        self.root=Path(root);self.data=json.loads((self.root/'data/cleaned/model_inputs.json').read_text('utf-8'))
        self.services=sorted(x['node_id'] for x in self.data['services'])
        self.trips=read_csv(self.root/'results/q3/trips.csv');self.relays=read_csv(self.root/'results/q3/relay_sorties.csv')
        self.comm=read_csv(self.root/'results/q3/Q3_通信保障.csv')
        self.trip={t['trip_id']:t for t in self.trips};self.relay={r['relay_trip_id']:r for r in self.relays}
        self.deps=defaultdict(set)
        for c in self.comm:
            if c['运输架次编号'] not in self.trip: raise ValueError('通信行引用未知运输架次')
            if c['保障方式']=='中继':
                if c['中继架次编号'] not in self.relay:raise ValueError('通信行引用未知中继架次')
                self.deps[c['中继架次编号']].add(c['运输架次编号'])
        uf=UnionFind(self.services);self.edges=[]
        for t in self.trips:
            ss=t['visit_order'].split(';')
            for s in ss[1:]:
                uf.union(ss[0],s);self.edges.append({'trip_id':t['trip_id'],'from_service':ss[0],'to_service':s,'reason':'同一运输架次访问'})
        self.transport_components=uf.groups()
        self.communication_edges=[]
        for rid,tids in sorted(self.deps.items()):
            ss=sorted({s for tid in tids for s in self.trip[tid]['visit_order'].split(';')})
            for v in ss[1:]:
                uf.union(ss[0],v)
                self.communication_edges.append({'relay_trip_id':rid,'from_service':ss[0],'to_service':v,'reason':'同一中继任务不可跨组共享或复制'})
        self.components=uf.groups()
        if len(self.components)>Q4CFG.expected_component_limit:raise ValueError('分量数超过明确的全枚举规模上限；未删减候选')
        self.component_index={s:i for i,c in enumerate(self.components) for s in c}
        self.fullcharge={x['model_id']:x['full_charge_s'] for x in self.data['transport_batteries']}
        self.relay_model=self.data['relay_models'][0];self.relay_charge=self.data['relay_energy'][0]['full_charge_s']
        self.inventory=[];self.inventory_ids=[]
        for g in 'ABC':
            ids=sorted(d['drone_id'] for d in self.data['transport_drones'] if d['model_id']==g)
            self.inventory.append(len(ids));self.inventory_ids.append(ids)
        for g in 'ABC':
            n=next(x['count'] for x in self.data['transport_batteries'] if x['model_id']==g)
            self.inventory.append(n);self.inventory_ids.append([f'{g}-BAT-{i+1:02d}' for i in range(n)])
        self.inventory.append(len(self.data['relay_drones']));self.inventory_ids.append(sorted(x['drone_id'] for x in self.data['relay_drones']))
        n=self.data['relay_energy'][0]['count'];self.inventory.append(n);self.inventory_ids.append([f'R-ENG-{i+1:02d}' for i in range(n)])
        self.cache={}
        self.baseline=self.group((1<<len(self.components))-1)
        self.horizon=max((x.ready_s for x in self.intervals(set(self.trip),set(self.relay))),default=0.)
        self.source_unique=[]
        for j,key in enumerate(RESOURCE_KEYS):
            self.source_unique.append(len({x.source_resource_id for x in self.intervals(set(self.trip),set(self.relay)) if x.resource_type==key}))

    def intervals(self,trip_ids,relay_ids):
        out=[]
        for tid in sorted(trip_ids):
            t=self.trip[tid];g=t['model_id'];s=float(t['start_s']);e=float(t['return_s'])
            out.extend((Interval(tid,'transport_'+g,s,e,e,t['drone_id']),
                Interval(tid,'battery_'+g,s,e+charge_duration(float(t['return_soc_fraction']),self.fullcharge[g]),e,t['battery_id'])))
        for rid in sorted(relay_ids):
            r=self.relay[rid];s=float(r['start_s']);e=float(r['return_s'])
            out.extend((Interval(rid,'relay_drone',s,e+self.relay_model['turnaround_s'],e,r['relay_drone_id']),
                Interval(rid,'relay_energy',s,e+charge_duration(float(r['return_soc_fraction']),self.relay_charge),e,r['energy_module_id'])))
        return out

    def group(self,mask):
        if mask in self.cache:return self.cache[mask]
        ss=sorted(s for j,c in enumerate(self.components) if mask>>j&1 for s in c);ns=set(ss)
        ts={tid for tid,t in self.trip.items() if t['visit_order'].split(';')[0] in ns}
        rs={rid for rid,dep in self.deps.items() if dep&ts}
        iv=self.intervals(ts,rs);counts=[];original=[];witness={}
        for key in RESOURCE_KEYS:
            one=[x for x in iv if x.resource_type==key];count,_,w,_=interval_coloring(one)
            counts.append(count);original.append(len({x.source_resource_id for x in one}));witness[key]=w
        W=math.fsum(float(self.trip[t]['operation_time_s']) for t in sorted(ts));Wr=math.fsum(float(self.relay[r]['return_s'])-float(self.relay[r]['start_s']) for r in sorted(rs))
        boxes=[b for b in self.data['boxes'] if b['service_id'] in ns]
        r={'mask':mask,'services':ss,'trip_ids':sorted(ts),'relay_ids':sorted(rs),'counts':counts,'source_unique_counts':original,
           'transport_workload_s':W,'relay_workload_s':Wr,'joint_workload_s':W+Wr,'transport_trips':len(ts),'relay_copies':len(rs),
           'boxes':len(boxes),'weight_kg':math.fsum(b['weight_kg'] for b in boxes),'volume_m3':math.fsum(b['volume_m3'] for b in boxes),
           'transport_energy_kwh':math.fsum(float(self.trip[t]['energy_kwh']) for t in sorted(ts)),
           'relay_energy_kwh':math.fsum(float(self.relay[r]['energy_kwh']) for r in sorted(rs)),
           'joint_makespan_s':max([float(self.trip[t]['return_s']) for t in ts]+[float(self.relay[r]['return_s']) for r in rs],default=0),
           'peak_witnesses':witness}
        self.cache[mask]=r;return r

    def evaluate(self,labels):
        k=max(labels)+1;masks=[sum((1<<j) for j,x in enumerate(labels) if x==g) for g in range(k)];gs=[self.group(x) for x in masks]
        counts=[sum(g['counts'][j] for g in gs) for j in range(len(RESOURCE_KEYS))]
        gaps=[max(0,x-i) for x,i in zip(counts,self.inventory)];spares=[max(0,i-x) for x,i in zip(counts,self.inventory)]
        w=[g['transport_workload_s'] for g in gs];joint=[g['joint_workload_s'] for g in gs]
        row={'K':k,'partition_id':f'K{k}-'+''.join(str(x+1) for x in labels),'labels':';'.join(map(str,labels)),'group_masks':';'.join(map(str,masks)),
            'groups':' | '.join(';'.join(g['services']) for g in gs),'shortage_units':sum(gaps),'resource_units':sum(counts),
            'transport_workload_cv':cv(w),'joint_workload_cv':cv(joint),'max_transport_workload_share':max(w)/sum(w),
            'inventory_feasible':not any(gaps),'relay_mission_copies':sum(g['relay_copies'] for g in gs),'relay_unique_execution_count':sum(g['relay_copies'] for g in gs),
            'extra_relay_mission_copies':sum(g['relay_copies'] for g in gs)-len(self.relays),
            'transport_energy_kwh':math.fsum(g['transport_energy_kwh'] for g in gs),'relay_energy_kwh':math.fsum(g['relay_energy_kwh'] for g in gs),
            'joint_makespan_s':max(g['joint_makespan_s'] for g in gs),
            'structural_extra_units':sum(counts)-sum(self.baseline['counts']) if hasattr(self,'baseline') else 0,
            'original_ID_locked_resource_units':sum(sum(g['source_unique_counts']) for g in gs)}
        row['total_energy_kwh']=row['transport_energy_kwh']+row['relay_energy_kwh']
        for j,key in enumerate(RESOURCE_KEYS):
            row['need_'+key]=counts[j];row['gap_'+key]=gaps[j];row['spare_'+key]=spares[j]
        return row,gs

def objective(row):
    return tuple(row[k] for k in Q4CFG.objective_order)+(row['partition_id'],)

def mark_pareto(rows):
    metrics=Q4CFG.objective_order;eps=Q4CFG.metric_tolerance
    for r in rows:
        r['pareto_resource_balance']=not any(all(q[k]<=r[k]+eps for k in metrics) and any(q[k]<r[k]-eps for k in metrics) for q in rows)
        r['pareto_resource_vector']=not any(all(q['need_'+k]<=r['need_'+k] for k in RESOURCE_KEYS) and any(q['need_'+k]<r['need_'+k] for k in RESOURCE_KEYS) for q in rows)
    return rows

def strict_no_copy(q):
    uf=UnionFind(q.services)
    for c in q.components:
        for s in c[1:]:uf.union(c[0],s)
    for rid,ids in q.deps.items():
        ss=sorted({s for tid in ids for s in q.trip[tid]['visit_order'].split(';')})
        for s in ss[1:]:uf.union(ss[0],s)
    cs=uf.groups()
    return {'meaning':'正式模型禁止中继任务复制及组间共享；共同依赖同一中继任务的服务区必须同组。',
            'components':cs,'component_count':len(cs),
            'feasible_partition_counts':{str(k):sum(1 for _ in canonical_partitions(len(cs),k)) for k in Q4CFG.group_counts},
            'not_equivalent_to_inventory_feasibility':True,'input_Q3_not_modified':True}

def expand_solution(q,row,groups,out):
    """输出独立执行的实体指派证据。不把增补设备伪装成原库存。"""
    k=row['K'];out=Path(out);out.mkdir(parents=True,exist_ok=True)
    counters=[0]*len(RESOURCE_KEYS);alloc=[];catalog=[];peaks=[];series=[];group_rows=[]
    tasks=[];relaycopies=[];commout=[];commtrace=[];source_transport=read_csv(q.root/'results/q3/Q3_运输架次.csv')
    source_relay={r['中继架次编号']:r for r in read_csv(q.root/'results/q3/Q3_中继架次.csv')}
    assignment={};physical={}
    for gidx,g in enumerate(groups,1):
        gid=f'K{k}-G{gidx}';iv=q.intervals(set(g['trip_ids']),set(g['relay_ids']))
        gr={key:value for key,value in g.items() if key not in ('peak_witnesses','services','counts','trip_ids','relay_ids','source_unique_counts')}
        gr.update(K=k,group_id=gid,services=';'.join(g['services']),trip_ids=';'.join(g['trip_ids']),relay_ids=';'.join(g['relay_ids']))
        for j,key in enumerate(RESOURCE_KEYS):
            one=[x for x in iv if x.resource_type==key];n,colors,witness,levels=interval_coloring(one)
            gr[key]=n;gr['source_ID_locked_'+key]=g['source_unique_counts'][j]
            peaks.append({'K':k,'group_id':gid,'resource_type':key,'minimum_count':n,'witness_time_s':witness['time_s'],'simultaneous_tasks':';'.join(witness['task_ids'])})
            for lv in levels:series.append({'K':k,'group_id':gid,'resource_type':key,**lv})
            for slot in range(1,n+1):
                counters[j]+=1;index=counters[j];pool=q.inventory_ids[j]
                if index<=len(pool):pid=pool[index-1];status='existing_inventory'
                else:
                    status='required_addition_not_in_source'
                    if key.startswith('battery_'):pid=f'{key[-1]}-BAT-{index:02d}'
                    elif key=='relay_energy':pid=f'R-ENG-{index:02d}'
                    else:pid=f'Q4-ADD-{key}-{index-len(pool):02d}'
                local=f'{gid}-{key}-{slot:02d}';physical[gid,key,slot]=pid
                totalbusy=sum(x.ready_s-x.start_s for x in one if colors[x.task_id]==slot)
                catalog.append({'K':k,'group_id':gid,'resource_type':key,'local_resource_id':local,'physical_resource_id':pid,
                    'supply_status':status,'busy_until_ready_s':totalbusy,'accounting_horizon_s':q.horizon,'utilization_fraction':totalbusy/q.horizon})
            for x in one:
                slot=colors[x.task_id];pid=physical[gid,key,slot];local=f'{gid}-{key}-{slot:02d}'
                local_task=x.task_id if x.task_id in q.trip else f'{x.task_id}@{gid}'
                assignment[gid,key,x.task_id]=pid
                alloc.append({'K':k,'group_id':gid,'resource_type':key,'source_task_id':x.task_id,'local_task_id':local_task,
                    'local_resource_id':local,'physical_resource_id':pid,'source_resource_id':x.source_resource_id,
                    'start_s':x.start_s,'return_s':x.return_s,'ready_s':x.ready_s,'unavailable_after_return_s':x.ready_s-x.return_s})
        group_rows.append(gr)
        for r in source_transport:
            if r['架次编号'] not in g['trip_ids']:continue
            x=dict(r);typ=x['机型编号'];tid=x['架次编号']
            x['无人机编号']=assignment[gid,'transport_'+typ,tid];x['电池编号']=assignment[gid,'battery_'+typ,tid];tasks.append(x)
        for rid in g['relay_ids']:
            r=dict(source_relay[rid]);r['中继架次编号']=f'{rid}@{gid}'
            r['中继无人机编号']=assignment[gid,'relay_drone',rid];r['能源组件编号']=assignment[gid,'relay_energy',rid];relaycopies.append(r)
        for idx,r in enumerate(q.comm,1):
            if r['运输架次编号'] not in g['trip_ids']:continue
            x=dict(r);source=x['中继架次编号']
            if source:x['中继架次编号']=f'{source}@{gid}'
            commout.append(x);commtrace.append({'K':k,'group_id':gid,'source_communication_row':idx,
                'transport_trip_id':r['运输架次编号'],'source_relay_trip_id':source,'local_relay_trip_id':x['中继架次编号'],
                'start_s':r['开始时刻（s）'],'end_s':r['结束时刻（s）'],'mode':r['保障方式']})
    if Counter(r['中继架次编号'].split('@')[0] for r in relaycopies)!=Counter(q.relay.keys()):
        raise AssertionError('严格Q4不得漏用或复制源中继任务')
    tasks.sort(key=lambda r:r['架次编号']);commout.sort(key=lambda r:(r['运输架次编号'],float(r['开始时刻（s）']),float(r['结束时刻（s）'])))
    import copy
    augmented=copy.deepcopy(q.data)
    augmented['transport_drones']=[{'drone_id':r['physical_resource_id'],'model_id':r['resource_type'][-1],'initial_node':'O01'} for r in catalog if r['resource_type'].startswith('transport_')]
    augmented['relay_drones']=[{'drone_id':r['physical_resource_id'],'model_id':'R','initial_node':'O01'} for r in catalog if r['resource_type']=='relay_drone']
    for r in augmented['transport_batteries']:r['count']=max(r['count'],row['need_battery_'+r['model_id']])
    augmented['relay_energy'][0]['count']=max(augmented['relay_energy'][0]['count'],row['need_relay_energy'])
    save_json(out/'configured_inventory.json',{'basis':'仅用于验证满足配置需求后的独立执行；source库存不变，不等于现库存可行','data':augmented})
    write_csv(out/'groups.csv',group_rows);write_csv(out/'resource_catalog.csv',catalog);write_csv(out/'resource_allocations.csv',alloc)
    write_csv(out/'peak_certificates.csv',peaks);write_csv(out/'concurrency_events.csv',series)
    write_csv(out/'运输任务_固定Q3时间.csv',tasks);write_csv(out/'中继任务_唯一执行.csv',relaycopies)
    write_csv(out/'通信保障_源关系映射.csv',commout);write_csv(out/'communication_lineage.csv',commtrace)
    write_csv(out/'逐箱交付_完全继承Q3.csv',read_csv(q.root/'results/q3/Q3_逐箱交付.csv'))
    write_csv(out/'relay_copy_mapping.csv',[{'K':k,'group_id':r['中继架次编号'].split('@')[1],
        'source_relay_trip_id':r['中继架次编号'].split('@')[0],'local_relay_trip_id':r['中继架次编号'],
        'physical_relay_id':r['中继无人机编号'],'physical_module_id':r['能源组件编号'],
        'start_s':r['开始时刻（s）'],'link_complete_s':r['建链完成时刻（s）'],'service_end_s':r['服务结束时刻（s）'],
        'return_s':r['返回O01时刻（s）'],'energy_kwh':r['架次能耗（kWh）']} for r in relaycopies])
    save_json(out/'summary.json',row)
    return group_rows

def run_q4(root):
    root=Path(root);before=frozen_hashes(root);q=FrozenQ3(root);out=root/'results/q4';out.mkdir(parents=True,exist_ok=True)
    comp_rows=[]
    for j,c in enumerate(q.components):
        g=q.group(1<<j);comp_rows.append({'component_id':f'C{j+1:02d}','services':';'.join(c),'service_count':len(c),
            'transport_trips':g['transport_trips'],'boxes':g['boxes'],'weight_kg':g['weight_kg'],'transport_workload_s':g['transport_workload_s'],
            'transport_workload_share':g['transport_workload_s']/q.baseline['transport_workload_s']})
    write_csv(out/'must_link_communication_edges.csv',q.communication_edges)
    write_csv(out/'transport_only_components.csv',[{'component_id':f'T{i+1:02d}','services':';'.join(c)} for i,c in enumerate(q.transport_components)])
    write_csv(out/'atomic_components.csv',comp_rows);write_csv(out/'must_link_transport_edges.csv',q.edges)
    write_csv(out/'relay_dependency_sets.csv',[{'source_relay_trip_id':rid,'transport_trip_ids':';'.join(sorted(ids)),
        'services':';'.join(sorted({s for tid in ids for s in q.trip[tid]['visit_order'].split(';')}))} for rid,ids in sorted(q.deps.items())])
    baseline_rows=[]
    for j,key in enumerate(RESOURCE_KEYS):baseline_rows.append({'resource_type':key,'resource_name':RESOURCE_NAMES[j],
        'source_inventory':q.inventory[j],'Q3_used_distinct_IDs':q.source_unique[j],'Q3_fixed_schedule_minimum':q.baseline['counts'][j],
        'source_unused_vs_minimum':q.inventory[j]-q.baseline['counts'][j]})
    write_csv(out/'inventory_and_baseline.csv',baseline_rows);save_json(out/'no_relay_copy_interpretation.json',strict_no_copy(q))
    allrows=[];selected=[];alternatives=[];formal=[];gaps=[];sweep=[];group_counts={}
    for k in Q4CFG.group_counts:
        rows=[q.evaluate(l)[0] for l in canonical_partitions(len(q.components),k)]
        if not rows:raise ValueError(f'{k}个非空组不存在：原运输必须同组分量不足')
        rows=mark_pareto(rows);group_counts[str(k)]=len(rows);best=min(rows,key=objective)
        for r in rows:r['selected_main']=r['partition_id']==best['partition_id']
        allrows.extend(rows);selected.append(best)
        labels=tuple(map(int,best['labels'].split(';')));_,gs=q.evaluate(labels)
        gr=expand_solution(q,best,gs,out/f'K{k}')
        for g in gr:formal.append(dict(zip(Q4_HEADERS,[k,g['group_id'],g['services']]+[g[key] for key in RESOURCE_KEYS])))
        for j,key in enumerate(RESOURCE_KEYS):gaps.append({'K':k,'resource_type':key,'resource_name':RESOURCE_NAMES[j],'inventory':q.inventory[j],
            'required':best['need_'+key],'shortage':best['gap_'+key],'unused_inventory':best['spare_'+key],
            'structural_extra_vs_Q3_minimum':best['need_'+key]-q.baseline['counts'][j],
            'extra_vs_Q3_used_IDs':best['need_'+key]-q.source_unique[j]})
        # 保留完整前沿及明确的最均衡对照，而不隐含主方案同时最均衡。
        balanced=min(rows,key=lambda r:(r['transport_workload_cv'],r['shortage_units'],r['resource_units'],r['partition_id']))
        alternatives.extend([{'selection':'resource_first',**best},{'selection':'balance_first',**balanced}])
        _,bg=q.evaluate(tuple(map(int,balanced['labels'].split(';'))));expand_solution(q,balanced,bg,out/'balance_alternatives'/f'K{k}')
        for cap in Q4CFG.balance_sweep_caps:
            feasible=[r for r in rows if r['transport_workload_cv']<=cap+Q4CFG.metric_tolerance]
            w=min(feasible,key=objective) if feasible else None
            sweep.append({'K':k,'cv_cap':cap,'partition_exists':bool(w),'partition_id':w['partition_id'] if w else '',
                'shortage_units':w['shortage_units'] if w else None,'resource_units':w['resource_units'] if w else None,
                'actual_cv':w['transport_workload_cv'] if w else None})
    write_csv(out/'all_partitions.csv',allrows);write_csv(out/'pareto_frontier.csv',[r for r in allrows if r['pareto_resource_balance']])
    write_csv(out/'selected_comparison.csv',selected);write_csv(out/'resource_balance_alternatives.csv',alternatives)
    write_csv(out/'inventory_gap.csv',gaps);write_csv(out/'balance_constraint_sensitivity.csv',sweep);write_csv(out/'Q4_分区配置.csv',formal,Q4_HEADERS)
    hypothesis={'basis':'题面问题四：冻结已修订且通过独立核验的Q3，再作严格分区。',
        'independent_execution_convention':'每个原Q3运输和中继任务均恰好执行一次，不复制、不拆分、不裁剪服务窗口。共依赖同一中继任务的服务区必须同组。',
        'physical_resource_identity':'执行前按组配置兼容实体；各组物理ID互斥；源ID仅追溯，不在执行期间借调。',
        'not_allowed':'改变箱子、访问顺序、任务开始/结束、悬停位置/海拔、通信保障关系，或增加任务副本。',
        'inventory_feasibility':'需求可以超过源库存，逐类列出缺口；可行指补足配置后独立执行，不修改源数据。',
        'objective':'缺口总件数→资源总件数→运输作业时长CV；件数不是成本；另列均衡优先方案。',
        'fixed_gateway':'G01是共用固定基础设施，不属于禁止跨组调配的可移动资源。',
        'strict_no_copy_enforced':True,'Q3_repair_is_prior_to_Q4_freeze':True}
    save_json(out/'assumptions.json',hypothesis)
    after=frozen_hashes(root)
    if before!=after:raise AssertionError('Q4改变了冻结Q3源记录')
    save_json(out/'frozen_input_hashes.json',{'files':before,'source_Q3_unchanged':True,'scope':'Q4执行前后关键主方案及独立证书字节相同；此前Q3闭环修复已完成'})
    summary={'component_count':len(q.components),'components':q.components,'partition_counts':group_counts,
        'total_enumerated_partitions':len(allrows),'inventory':dict(zip(RESOURCE_KEYS,q.inventory)),
        'baseline_minimum_resources':dict(zip(RESOURCE_KEYS,q.baseline['counts'])),'Q3_used_ID_resources':dict(zip(RESOURCE_KEYS,q.source_unique)),
        'minimum_shortage_units':{str(k):min(r['shortage_units'] for r in allrows if r['K']==k) for k in Q4CFG.group_counts},
        'inventory_feasible_partition_counts':{str(k):sum(r['inventory_feasible'] for r in allrows if r['K']==k) for k in Q4CFG.group_counts},
        'selected':{str(r['K']):r for r in selected},'minimum_transport_workload_cv':{str(k):min(r['transport_workload_cv'] for r in allrows if r['K']==k) for k in Q4CFG.group_counts},
        'pareto_counts':{str(k):sum(r['pareto_resource_balance'] for r in allrows if r['K']==k) for k in Q4CFG.group_counts},
        'frozen_Q3_unchanged':True,'optimality':'全分量划分空间及给定区间资源重配置下字典序精确最优；不是对可重排Q3或所有物理解释的全局最优',
        'source_Q3_heuristic_not_globally_optimal':True,'relay_inheritance_mode':Q4CFG.relay_inheritance_mode,
        'source_task_identity_no_copy':strict_no_copy(q),'config':asdict(Q4CFG)}
    save_json(out/'summary.json',summary)
    return summary
