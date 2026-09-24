"""Q4独立验证：不调用solve_q4或其枚举、着色、分组缓存。
Python 3.13.5。独立DFS重建同组关系；锚定集合递归枚举；二分图最大匹配求最小链覆盖。
最终配置与资源台账从CSV/Excel读取；额外用既有独立物理器从原DEM重算两组方案。
验证通过指固定任务和所需配置一致；不等于无需增补即可在原库存下执行。
"""
from pathlib import Path
from collections import defaultdict,Counter
from itertools import combinations
import copy,json,math
from io_utils import read_csv,write_csv,save_json,sha256
from q4_config import Q4CFG,RESOURCE_KEYS,Q4_HEADERS,SOURCE_Q3_FILES


def minimum_chain_cover(intervals):
    """最小路径覆盖=n-最大匹配；边 i→j 当i已充满/周转完毕可接j。
    输入为(start,ready,task)。算法不使用主算法的堆或峰值着色。
    """
    n=len(intervals);edges=[[] for _ in intervals]
    for i,(a,b,_) in enumerate(intervals):
        for j,(c,d,_) in enumerate(intervals):
            if i!=j and b<=c+Q4CFG.time_tolerance_s:edges[i].append(j)
    matched={}
    def augment(i,seen):
        for j in edges[i]:
            if j in seen:continue
            seen.add(j)
            if j not in matched or augment(matched[j],seen):matched[j]=i;return True
        return False
    for i in range(n):augment(i,set())
    return n-len(matched)


def anchor_partitions(items,k):
    items=tuple(sorted(items))
    if k==1:
        if items:yield (items,)
        return
    if len(items)<k:return
    first=items[0];rest=items[1:]
    for size in range(len(items)-k+1):
        for tail in combinations(rest,size):
            left=tuple(i for i in rest if i not in tail)
            for sub in anchor_partitions(left,k-1):yield ((first,)+tail,)+sub


def component_dfs(vertices,adj):
    left=set(vertices);out=[]
    while left:
        stack=[min(left)];one=set()
        while stack:
            u=stack.pop()
            if u in one:continue
            one.add(u);stack.extend(adj[u]-one)
        left-=one;out.append(tuple(sorted(one)))
    return tuple(sorted(out))


def normalize_groups(groups):return tuple(sorted(tuple(sorted(x)) for x in groups))


def independent_charge_q4(soc,full):
    # 源附录2：低于90%的阶段占65%，末10%占35%。与主模块不同表达式。
    fast=0.65*full/0.90;slow=0.35*full/0.10
    return (max(0.,0.90-soc)*fast)+(1.-max(0.90,soc))*slow


class IndependentQ4:
    def __init__(self,root):
        self.root=Path(root);self.data=json.loads((self.root/'data/cleaned/model_inputs.json').read_text('utf-8'))
        self.tr={r['trip_id']:r for r in read_csv(self.root/'results/q3/trips.csv')}
        self.rr={r['relay_trip_id']:r for r in read_csv(self.root/'results/q3/relay_sorties.csv')}
        self.comm=read_csv(self.root/'results/q3/Q3_通信保障.csv')
        self.services={s['node_id'] for s in self.data['services']};adj=defaultdict(set)
        for t in self.tr.values():
            ss=t['visit_order'].split(';')
            for a in ss:
                for b in ss:
                    if a!=b:adj[a].add(b)
        self.components=component_dfs(self.services,adj)
        self.deps=defaultdict(set)
        for c in self.comm:
            if c['保障方式']=='中继':self.deps[c['中继架次编号']].add(c['运输架次编号'])
        strict=copy.deepcopy(adj)
        for ids in self.deps.values():
            ss={s for tid in ids for s in self.tr[tid]['visit_order'].split(';')}
            for a in ss:strict[a]|=ss-{a}
        self.strict_components=component_dfs(self.services,strict)
        self.transport_components=self.components
        self.components=self.strict_components
        self.full={x['model_id']:x['full_charge_s'] for x in self.data['transport_batteries']}
        self.inventory=[sum(x['model_id']==g for x in self.data['transport_drones']) for g in 'ABC']
        self.inventory += [next(x['count'] for x in self.data['transport_batteries'] if x['model_id']==g) for g in 'ABC']
        self.inventory += [len(self.data['relay_drones']),self.data['relay_energy'][0]['count']]
        self.cache={};self.records={}
        for part_k in Q4CFG.group_counts:
            rows={}
            for chunks in anchor_partitions(range(len(self.components)),part_k):
                groups=[tuple(sorted(s for i in ch for s in self.components[i])) for ch in chunks]
                rows[normalize_groups(groups)]=self.metrics(groups)
            self.records[part_k]=rows

    def intervals(self,group):
        ns=set(group);tids={i for i,t in self.tr.items() if set(t['visit_order'].split(';'))<=ns}
        rids={r for r,ids in self.deps.items() if ids&tids};result=defaultdict(list)
        for tid in sorted(tids):
            t=self.tr[tid];g=t['model_id'];start=float(t['start_s']);ret=float(t['return_s'])
            result['transport_'+g].append((start,ret,tid))
            result['battery_'+g].append((start,ret+independent_charge_q4(float(t['return_soc_fraction']),self.full[g]),tid))
        for rid in sorted(rids):
            r=self.rr[rid];start=float(r['start_s']);ret=float(r['return_s'])
            result['relay_drone'].append((start,ret+self.data['relay_models'][0]['turnaround_s'],rid))
            result['relay_energy'].append((start,ret+independent_charge_q4(float(r['return_soc_fraction']),self.data['relay_energy'][0]['full_charge_s']),rid))
        return result,tids,rids

    def group(self,group):
        key=tuple(sorted(group))
        if key in self.cache:return self.cache[key]
        iv,ts,rs=self.intervals(group);counts=[minimum_chain_cover(iv[j]) for j in RESOURCE_KEYS]
        w=sum(float(self.tr[t]['operation_time_s']) for t in sorted(ts));wr=sum(float(self.rr[r]['return_s'])-float(self.rr[r]['start_s']) for r in sorted(rs))
        x={'counts':counts,'workload':w,'joint_workload':w+wr,'trip_ids':ts,'relay_ids':rs,
            'transport_energy':sum(float(self.tr[t]['energy_kwh']) for t in sorted(ts)),'relay_energy':sum(float(self.rr[r]['energy_kwh']) for r in sorted(rs))}
        self.cache[key]=x;return x

    def metrics(self,groups):
        gs=[self.group(g) for g in groups];counts=[sum(x['counts'][j] for x in gs) for j in range(len(RESOURCE_KEYS))]
        gaps=[max(0,x-y) for x,y in zip(counts,self.inventory)]
        def variance_ratio(vals):
            a=sum(vals)/len(vals)
            return math.sqrt(sum((v-a)**2 for v in vals)/len(vals))/a
        return {'counts':counts,'gaps':gaps,'shortage_units':sum(gaps),'resource_units':sum(counts),
            'transport_workload_cv':variance_ratio([g['workload'] for g in gs]),'joint_workload_cv':variance_ratio([g['joint_workload'] for g in gs]),
            'relay_mission_copies':sum(len(x['relay_ids']) for x in gs),
            'total_energy_kwh':sum(x['transport_energy']+x['relay_energy'] for x in gs)}


def validate_q4_template(root,rows,independent=None):
    v=independent or IndependentQ4(root);checks=[]
    def ck(k,ok,d=''):checks.append({'check':k,'pass':bool(ok),'details':str(d)})
    for k in Q4CFG.group_counts:
        selected=[r for r in rows if int(float(r[Q4_HEADERS[0]]))==k];ck(f'K{k}/exact_group_count',len(selected)==k)
        seen=[];groups=[];counts=[]
        for r in selected:
            gid=r[Q4_HEADERS[1]];ss=r[Q4_HEADERS[2]].split(';');groups.append(ss);seen+=ss
            ck(f'{gid}/nonempty_and_unique_services',bool(ss) and len(ss)==len(set(ss)) and set(ss)<=v.services)
            ck(f'{gid}/transport_must_link',all(not (set(c)&set(ss)) or set(c)<=set(ss) for c in v.components))
            if not set(ss)<=v.services:continue
            expect=v.group(ss)['counts'];declared=[]
            for j,key in enumerate(RESOURCE_KEYS):
                x=float(r[Q4_HEADERS[j+3]]);ck(f'{gid}/{key}/nonnegative_integer',math.isfinite(x) and x>=0 and x.is_integer());declared.append(x)
                ck(f'{gid}/{key}/minimum_chain_cover_count',x==expect[j],f'{x} != {expect[j]}')
            counts.append(declared)
        ck(f'K{k}/service_partition',Counter(seen)==Counter(v.services))
        key=normalize_groups(groups);ck(f'K{k}/admissible_enumerated_partition',key in v.records[k])
        if key in v.records[k]:
            mine=v.records[k][key];best=min(v.records[k].values(),key=lambda x:tuple(x[m] for m in Q4CFG.objective_order))
            for metric in Q4CFG.objective_order:
                ck(f'K{k}/exact_global_objective_{metric}',math.isclose(mine[metric],best[metric],abs_tol=1e-11,rel_tol=1e-12),mine[metric])
    ck('K_only_2_and_3',len(rows)==sum(Q4CFG.group_counts) and all(float(r[Q4_HEADERS[0]]) in Q4CFG.group_counts for r in rows))
    return checks


def verify_case(root,folder,v,check_physics=True):
    root=Path(root);out=root/folder;checks=[]
    def ck(k,ok,d=''):checks.append({'check':k,'pass':bool(ok),'details':str(d)})
    groups=read_csv(out/'groups.csv');catalog=read_csv(out/'resource_catalog.csv');alloc=read_csv(out/'resource_allocations.csv')
    tr=read_csv(out/'运输任务_固定Q3时间.csv');bx=read_csv(out/'逐箱交付_完全继承Q3.csv');rr=read_csv(out/'中继任务_唯一执行.csv');com=read_csv(out/'通信保障_源关系映射.csv')
    key=normalize_groups([r['services'].split(';') for r in groups]);k=len(groups);ck('partition_admissible',key in v.records[k]);tgroup={};rgroup={};igroups={}
    for g in groups:
        gid=g['group_id'];ss=g['services'].split(';');igroups[gid]=ss;expected=v.group(ss)
        ck(gid+'/fixed_task_membership',set(g['trip_ids'].split(';'))==expected['trip_ids'])
        for tid in expected['trip_ids']:tgroup[tid]=gid
        for rid in expected['relay_ids']:rgroup[gid,rid]=f'{rid}@{gid}'
        for j,res in enumerate(RESOURCE_KEYS):ck(gid+'/'+res+'/count',int(g[res])==expected['counts'][j])
    ck('all_26_source_transport_tasks_once',Counter(r['架次编号'] for r in tr)==Counter(v.tr.keys()))
    src_tr={r['架次编号']:r for r in read_csv(root/'results/q3/Q3_运输架次.csv')}
    for r in tr:
        if r['架次编号'] not in src_tr:continue
        src=src_tr[r['架次编号']]
        for h in src:
            if h not in ('无人机编号','电池编号'):ck(r['架次编号']+'/frozen_'+h,r[h]==src[h])
    ck('all_boxes_exactly_frozen',bx==read_csv(root/'results/q3/Q3_逐箱交付.csv'))
    src_rr={r['中继架次编号']:r for r in read_csv(root/'results/q3/Q3_中继架次.csv')}
    ck('strict_source_relays_exactly_once_no_copy',Counter(r['中继架次编号'].split('@')[0] for r in rr)==Counter(v.rr.keys()))
    ck('exact_required_relay_copies',Counter(r['中继架次编号'] for r in rr)==Counter(rgroup.values()))
    for r in rr:
        rid=r['中继架次编号'];source=rid.split('@')[0]
        ck(rid+'/known_source',source in src_rr)
        if source not in src_rr:continue
        for h,x in src_rr[source].items():
            if h not in ('中继架次编号','中继无人机编号','能源组件编号'):ck(rid+'/frozen_'+h,r[h]==x)
    expected_comm=[]
    for c in v.comm:
        x=dict(c)
        if x['中继架次编号']:x['中继架次编号']=rgroup.get((tgroup[x['运输架次编号']],x['中继架次编号']),'INVALID')
        expected_comm.append(x)
    def sig(r):return tuple((key,str(value)) for key,value in sorted(r.items()))
    ck('entire_communication_relation_including_points_frozen',Counter(map(sig,com))==Counter(map(sig,expected_comm)))
    trace=read_csv(out/'communication_lineage.csv')
    ck('source_communication_rows_exact_once',Counter(int(r['source_communication_row']) for r in trace)==Counter(range(1,len(v.comm)+1)))
    for x in trace:
        idx=int(x['source_communication_row'])-1
        if not 0<=idx<len(v.comm):continue
        c=v.comm[idx];ck('comm_lineage_'+str(idx),x['source_relay_trip_id']==c['中继架次编号'] and x['transport_trip_id']==c['运输架次编号'] and x['group_id']==tgroup[c['运输架次编号']] and x['mode']==c['保障方式'] and float(x['start_s'])==float(c['开始时刻（s）']) and float(x['end_s'])==float(c['结束时刻（s）']))
    cat={r['local_resource_id']:r for r in catalog};ck('unique_local_resource_IDs',len(cat)==len(catalog))
    ck('no_physical_resource_across_groups',len({(r['resource_type'],r['physical_resource_id']) for r in catalog})==len(catalog))
    source_pools={}
    for typ in 'ABC':
        source_pools['transport_'+typ]={r['drone_id'] for r in v.data['transport_drones'] if r['model_id']==typ}
        source_pools['battery_'+typ]={f'{typ}-BAT-{i+1:02d}' for i in range(v.inventory[RESOURCE_KEYS.index('battery_'+typ)])}
    source_pools['relay_drone']={r['drone_id'] for r in v.data['relay_drones']}
    source_pools['relay_energy']={f'R-ENG-{i+1:02d}' for i in range(v.inventory[-1])}
    for c in catalog:
        key=c['resource_type'];pid=c['physical_resource_id'];status=c['supply_status']
        ck(c['local_resource_id']+'/existing_vs_planned_identity',key in source_pools and ((status=='existing_inventory' and pid in source_pools[key]) or (status=='required_addition_not_in_source' and pid not in source_pools[key])))
    expected_iv={}
    for gid,ss in igroups.items():
        iv,_,_=v.intervals(ss)
        for res,vals in iv.items():
            for s,e,tid in vals:expected_iv[gid,res,tid]=(s,e)
        for j,res in enumerate(RESOURCE_KEYS):
            entries=[r for r in catalog if r['group_id']==gid and r['resource_type']==res]
            ck(gid+'/'+res+'/catalog_count',len(entries)==v.group(ss)['counts'][j])
    ck('exact_task_resource_interval_coverage',Counter((r['group_id'],r['resource_type'],r['source_task_id']) for r in alloc)==Counter(expected_iv.keys()))
    used=defaultdict(list);task_resource={}
    for i,r in enumerate(alloc):
        tag=(r['group_id'],r['resource_type'],r['source_task_id']);s=float(r['start_s']);e=float(r['ready_s']);local=r['local_resource_id']
        ck(f'alloc{i}/known_catalog',local in cat)
        if local in cat:
            ck(f'alloc{i}/one_group_and_compatible_type',cat[local]['group_id']==r['group_id'] and cat[local]['resource_type']==r['resource_type'] and cat[local]['physical_resource_id']==r['physical_resource_id'])
        ck(f'alloc{i}/valid_task_interval',tag in expected_iv)
        if tag in expected_iv:
            ck(f'alloc{i}/start_and_ready_include_charge_turnaround',abs(s-expected_iv[tag][0])<1e-8 and abs(e-expected_iv[tag][1])<1e-6,(s,e,expected_iv[tag]))
            source_task=v.tr.get(r['source_task_id'],v.rr.get(r['source_task_id']))
            ret=float(source_task['return_s'])
            ck(f'alloc{i}/return_and_post_return_busy',abs(float(r['return_s'])-ret)<1e-8 and abs(float(r['unavailable_after_return_s'])-(e-ret))<1e-6)
        used[local].append((s,e,r['source_task_id']));task_resource[tag]=r['physical_resource_id']
    for local,xs in used.items():
        xs.sort()
        for a,b in zip(xs,xs[1:]):ck(local+'/no_double_booking_'+a[2]+'_'+b[2],b[0]>=a[1]-Q4CFG.time_tolerance_s,b[0]-a[1])
    ck('no_unoccupied_catalog_resource',set(cat)==set(used))
    for local,entries in used.items():
        c=cat.get(local)
        if c is None:continue
        busy=math.fsum(b-a for a,b,_ in entries);h=float(c['accounting_horizon_s'])
        ck(local+'/utilization_recalculation',abs(busy-float(c['busy_until_ready_s']))<1e-6 and h>0 and abs(float(c['utilization_fraction'])-busy/h)<1e-12 and 0<=busy/h<=1+1e-10)
    peaks=read_csv(out/'peak_certificates.csv')
    ck('peak_certificate_all_groups_and_types',len(peaks)==len(igroups)*len(RESOURCE_KEYS))
    for p in peaks:
        gid=p['group_id'];key=p['resource_type'];iv,_,_=v.intervals(igroups[gid]);n=int(p['minimum_count'])
        ck(gid+'/'+key+'/peak_matches_chain_cover',n==minimum_chain_cover(iv[key]))
        if n:
            time=float(p['witness_time_s']);active={tid for a,b,tid in iv[key] if a<=time and b>time+Q4CFG.time_tolerance_s}
            ck(gid+'/'+key+'/concurrent_lower_bound_witness',active==set(p['simultaneous_tasks'].split(';')) and len(active)==n)
        else:ck(gid+'/'+key+'/zero_no_artificial_witness',p['witness_time_s']=='' and p['simultaneous_tasks']=='')
    for r in tr:
        tid=r['架次编号'];gid=tgroup.get(tid,'INVALID');g=r['机型编号']
        ck(tid+'/actual_resource_matches_certificate',task_resource.get((gid,'transport_'+g,tid))==r['无人机编号'] and task_resource.get((gid,'battery_'+g,tid))==r['电池编号'])
    for r in rr:
        rid,gid=r['中继架次编号'].split('@')
        ck(r['中继架次编号']+'/actual_resource_matches_certificate',task_resource.get((gid,'relay_drone',rid))==r['中继无人机编号'] and task_resource.get((gid,'relay_energy',rid))==r['能源组件编号'])
    row=json.loads((out/'summary.json').read_text('utf-8'));metric=v.metrics([r['services'].split(';') for r in groups]);counts=metric['counts']
    for field in ('shortage_units','resource_units','transport_workload_cv','joint_workload_cv','relay_mission_copies','total_energy_kwh'):
        ck('summary_'+field,math.isclose(float(row[field]),metric[field],abs_tol=1e-9,rel_tol=1e-12))
    if 'balance_alternatives' in str(folder):
        ck('balance_alternative_exact_minimum_CV',abs(metric['transport_workload_cv']-min(m['transport_workload_cv'] for m in v.records[k].values()))<1e-12)
    for j,res in enumerate(RESOURCE_KEYS):
        xs=[r for r in catalog if r['resource_type']==res];extra=sum(r['supply_status']=='required_addition_not_in_source' for r in xs)
        ck(res+'/inventory_deficit_honest',extra==max(0,counts[j]-v.inventory[j]))
        ck(res+'/reported_total',int(row['need_'+res])==counts[j]);ck(res+'/reported_gap',int(row['gap_'+res])==metric['gaps'][j])
    ck('existing_stock_feasibility_not_confused_with_required_stock',row['inventory_feasible']==(not any(metric['gaps'])))
    # 以源参数为起点独立构造所需库存，只扩大资源数量；不改能耗、时限、通信规则。
    data=copy.deepcopy(v.data)
    data['transport_drones']=[{'drone_id':r['physical_resource_id'],'model_id':r['resource_type'][-1],'initial_node':'O01'} for r in catalog if r['resource_type'].startswith('transport_')]
    data['relay_drones']=[{'drone_id':r['physical_resource_id'],'model_id':'R','initial_node':'O01'} for r in catalog if r['resource_type']=='relay_drone']
    for r in data['transport_batteries']:r['count']=max(r['count'],counts[RESOURCE_KEYS.index('battery_'+r['model_id'])])
    data['relay_energy'][0]['count']=max(data['relay_energy'][0]['count'],counts[-1])
    declared_data=json.loads((out/'configured_inventory.json').read_text('utf-8'))['data'];ck('configured_data_only_allowed_resource_changes',data==declared_data)
    physical_summary={}
    if check_physics:
        from q2_validation import validate_rows,independent_arcs
        from q3_validation import IndependentRadio,validate_relay,independent_phases,validate_communication
        if not hasattr(v,'arc'):v.arc=independent_arcs(root,v.data);v.radio=IndependentRadio(root,v.data)
        stats,ct,details,cb,resources=validate_rows(data,v.arc,tr,bx)
        cr,rel=validate_relay(data,v.radio,rr)
        phases=independent_phases(data,v.arc,tr,bx)
        cc,certificate,dense=validate_communication(data,v.radio,phases,rel,com,dense=Q4CFG.source_phase_validation_dense)
        phys=ct+cr+cc
        write_csv(out/'independent_physics_checks.csv',phys);write_csv(out/'independent_continuous_certificate.csv',certificate)
        write_csv(out/'independent_transport_recalculation.csv',details);write_csv(out/'independent_box_recalculation.csv',cb)
        write_csv(out/'independent_relay_recalculation.csv',[{k:x for k,x in r.items() if k!='point'} for r in rel])
        physical_summary={'checks_total':len(phys),'checks_failed':sum(not x['pass'] for x in phys),'communication_intervals_and_points':len(certificate),
            'communication_failed':sum(not c['pass'] for c in certificate),'transport_energy_kwh':stats['energy_kwh'],
            'relay_energy_kwh':sum(r['energy_kwh'] for r in rel),'joint_makespan_s':max(stats['makespan_s'],max((r['return_s'] for r in rel),default=0.)),
            'boxes':stats['recomputed_boxes'],'hard_late_s':stats['hard_late_s'],'source_inventory_sufficient':not any(metric['gaps']),
            'feasible_with_declared_additions':not any(not x['pass'] for x in phys),'not_a_field_safety_certification':True}
        ck('all_independent_physical_checks_pass',physical_summary['checks_failed']==0)
        ck('total_energy_matches_original_plus_full_copies',abs(physical_summary['transport_energy_kwh']+physical_summary['relay_energy_kwh']-row['total_energy_kwh'])<1e-8)
        ck('joint_end_unchanged',abs(physical_summary['joint_makespan_s']-row['joint_makespan_s'])<1e-6)
        save_json(out/'independent_physics_summary.json',physical_summary)
    write_csv(out/'independent_inheritance_resource_checks.csv',checks)
    return checks,physical_summary


def run_q4_validation(root,check_physics=True,alternatives=True):
    root=Path(root);v=IndependentQ4(root);out=root/'results/q4';checks=[]
    def ck(k,ok,d=''):checks.append({'check':k,'pass':bool(ok),'details':str(d)})
    source=json.loads((out/'frozen_input_hashes.json').read_text('utf-8'))
    for p,h in source['files'].items():ck('source_hash_'+p,h==sha256(root/'results/q3'/p))
    summary=json.loads((out/'summary.json').read_text('utf-8'))
    ck('component_reconstruction_DFS',v.components==tuple(tuple(c) for c in summary['components']))
    strict=json.loads((out/'no_relay_copy_interpretation.json').read_text('utf-8'))
    ck('no_copy_components_independent',v.strict_components==tuple(tuple(c) for c in strict['components']))
    for k in Q4CFG.group_counts:
        ck(f'K{k}/strict_no_copy_count',sum(1 for _ in anchor_partitions(range(len(v.strict_components)),k))==strict['feasible_partition_counts'][str(k)])
    rows=read_csv(out/'all_partitions.csv');seen={k:set() for k in Q4CFG.group_counts};every=[]
    for i,r in enumerate(rows):
        k=int(r['K']);key=normalize_groups([g.strip().split(';') for g in r['groups'].split('|')]);valid=key in v.records[k]
        ck(f'partition{i}/admissible',valid);ck(f'partition{i}/no_label_duplicate',key not in seen[k]);seen[k].add(key)
        if not valid:continue
        val=v.records[k][key]
        for field in ('shortage_units','resource_units','transport_workload_cv','joint_workload_cv','relay_mission_copies','total_energy_kwh'):
            ck(f'partition{i}/{field}',math.isclose(float(r[field]),val[field],abs_tol=1e-9,rel_tol=1e-12))
        for j,res in enumerate(RESOURCE_KEYS):
            ck(f'partition{i}/{res}/independent_matching_count',int(r['need_'+res])==val['counts'][j])
            ck(f'partition{i}/{res}/gap',int(r['gap_'+res])==val['gaps'][j])
        every.append({'K':k,'partition_id':r['partition_id'],'independent_resource_units':val['resource_units'],'independent_shortage_units':val['shortage_units'],
            'independent_transport_workload_cv':val['transport_workload_cv'],'all_counts_match':all(int(r['need_'+key])==val['counts'][j] for j,key in enumerate(RESOURCE_KEYS))})
    for r in rows:
        k=int(r['K']);vals=v.records[k][normalize_groups([g.strip().split(';') for g in r['groups'].split('|')])]
        eps=Q4CFG.metric_tolerance
        pareto=not any(all(m[f]<=vals[f]+eps for f in Q4CFG.objective_order) and any(m[f]<vals[f]-eps for f in Q4CFG.objective_order) for m in v.records[k].values())
        ck(r['partition_id']+'/pareto_mark',pareto==(r['pareto_resource_balance']=='True'))
    for k in Q4CFG.group_counts:
        ck(f'K{k}/exhaustive_partition_coverage',seen[k]==set(v.records[k]))
        ck(f'K{k}/global_minimum_gap',summary['minimum_shortage_units'][str(k)]==min(x['shortage_units'] for x in v.records[k].values()))
        ck(f'K{k}/inventory_feasible_count',summary['inventory_feasible_partition_counts'][str(k)]==sum(x['shortage_units']==0 for x in v.records[k].values()))
    checks+=validate_q4_template(root,read_csv(out/'Q4_分区配置.csv'),v)
    cases={}
    for k in Q4CFG.group_counts:
        cc,ps=verify_case(root,f'results/q4/K{k}',v,check_physics);checks.extend({'check':f'K{k}/'+x['check'],'pass':x['pass'],'details':x['details']} for x in cc);cases[str(k)]=ps
    if alternatives:
        for k in Q4CFG.group_counts:
            cc,ps=verify_case(root,f'results/q4/balance_alternatives/K{k}',v,check_physics);checks.extend({'check':f'balance_K{k}/'+x['check'],'pass':x['pass'],'details':x['details']} for x in cc);cases[f'balance_{k}']=ps
    result={'checks_total':len(checks),'checks_passed':sum(c['pass'] for c in checks),'checks_failed':sum(not c['pass'] for c in checks),
        'full_partitions_checked':len(rows),'independent_group_subsets':len(v.cache),'physical_cases':cases,
        'physical_checks_total':sum(x.get('checks_total',0) for x in cases.values()),'physical_checks_failed':sum(x.get('checks_failed',0) for x in cases.values()),
        'source_Q3_hashes_checked':len(source['files']),'verified_for_declared_required_resources':True,
        'main_solutions_inventory_feasible':{str(k):not any(v.records[k][normalize_groups([s.strip().split(';') for s in summary['selected'][str(k)]['groups'].split('|')])]['gaps']) for k in Q4CFG.group_counts},
        'scope':'冻结Q3下的全部划分、区间资源最少配置、资源不跨组、完整通信继承、增配后物理可行；禁止复制中继任务，正式源任务各恰好一次'}
    write_csv(out/'independent_partition_certificate.csv',every);write_csv(out/'independent_checks.csv',checks);save_json(out/'independent_validation.json',result)
    if result['checks_failed'] or result['physical_checks_failed']:
        raise AssertionError('Q4独立核验失败：'+str([c for c in checks if not c['pass']][:5]))
    return result
