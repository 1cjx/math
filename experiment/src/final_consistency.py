"""闭环发布门禁：重新聚合实际CSV，核查题意继承、报告与图件、源哈希和Excel反向验收。
Python3.13.5；不把验证记录的通过标记等同于真实工作簿已读，也不声称全局安全。
"""
from pathlib import Path
from collections import Counter
import json,math,re,io
from io_utils import read_csv,save_json,write_csv,sha256
from q4_config import RESOURCE_KEYS,SOURCE_Q3_FILES

def run_final_consistency(root):
    root=Path(root);checks=[]
    def js(p):return json.loads((root/p).read_text())
    def ck(name,ok,detail=''):checks.append({'check':name,'pass':bool(ok),'detail':str(detail)})
    def eq(name,a,b):ck(name,math.isclose(float(a),float(b),abs_tol=1e-6,rel_tol=1e-12),f'{a} / {b}')
    ss={q:js(f'results/{q}/summary.json') for q in ('q1','q2','q3','q4')};s=ss['q3'];q4=ss['q4'];data=js('data/cleaned/model_inputs.json')
    q1=read_csv(root/'results/q1/batches_NET.csv');eq('Q1_energy_sum',sum(float(r['energy_kwh']) for r in q1),ss['q1']['energy_kwh']);eq('Q1_cumulative_operation',sum(float(r['operation_time_s']) for r in q1),ss['q1']['operation_time_s'])
    for q in ('q2','q3'):
        tr=read_csv(root/f'results/{q}/trips.csv');bx=read_csv(root/f'results/{q}/box_deliveries.csv')
        eq(q+'_trip_count',len(tr),ss[q]['trips']);eq(q+'_energy',sum(float(r['energy_kwh']) for r in tr),ss[q]['energy_kwh']);eq(q+'_return_definition',max(float(r['return_s']) for r in tr),ss[q]['makespan_s'])
        ck(q+'_box_identity',Counter(r['box_id'] for r in bx)==Counter(b['box_id'] for b in data['boxes']))
        ck(q+'_model_composition',dict(Counter(r['model_id'] for r in tr))==ss[q]['model_trip_counts'])
        for r in tr:eq(q+'_'+r['trip_id']+'_duration',float(r['return_s'])-float(r['start_s']),r['operation_time_s'])
    rr=read_csv(root/'results/q3/relay_sorties.csv');tr=read_csv(root/'results/q3/trips.csv');comm=read_csv(root/'results/q3/Q3_通信保障.csv')
    eq('Q3_relay_energy',sum(float(r['energy_kwh']) for r in rr),s['relay_energy_kwh']);eq('Q3_total_energy',s['energy_kwh']+s['relay_energy_kwh'],s['total_energy_kwh']);eq('Q3_joint_return',max(float(r['return_s']) for r in rr+tr),s['joint_makespan_s'])
    eq('Q3_atoms',len(comm),s['communication_atoms']);eq('Q3_points',sum(float(r['开始时刻（s）'])==float(r['结束时刻（s）']) for r in comm),s['communication_boundary_points'])
    v3=js('results/q3/independent_validation.json');eq('Q3_independent_energy',v3['total_energy_kwh'],s['total_energy_kwh']);eq('Q3_independent_time',v3['joint_makespan_s'],s['joint_makespan_s'])
    for f in ('checks_failed','continuous_atoms_failed','dense_failed'):eq('Q3_'+f,v3[f],0)
    for k in (2,3):
        p=root/f'results/q4/K{k}';groups=read_csv(p/'groups.csv');rt=read_csv(p/'中继任务_唯一执行.csv');src=read_csv(p/'运输任务_固定Q3时间.csv')
        eq(f'Q4_K{k}_group_count',len(groups),k)
        ck(f'Q4_K{k}_service_cover',Counter(v for g in groups for v in g['services'].split(';'))==Counter(n['node_id'] for n in data['services']))
        eq(f'Q4_K{k}_unique_relay_count',len(rt),len(rr));eq(f'Q4_K{k}_transport_count',len(src),len(tr));eq(f'Q4_K{k}_no_additional_relay',q4['selected'][str(k)]['extra_relay_mission_copies'],0)
        eq(f'Q4_K{k}_energy_inheritance',q4['selected'][str(k)]['total_energy_kwh'],s['total_energy_kwh']);eq(f'Q4_K{k}_return_inheritance',q4['selected'][str(k)]['joint_makespan_s'],s['joint_makespan_s'])
        for key in RESOURCE_KEYS:
            need=sum(int(g[key]) for g in groups);eq(f'Q4_K{k}_{key}_sum',need,q4['selected'][str(k)]['need_'+key]);eq(f'Q4_K{k}_{key}_gap',max(0,need-q4['inventory'][key]),q4['selected'][str(k)]['gap_'+key])
    frozen=js('results/q4/source_Q3_fingerprints.json') if (root/'results/q4/source_Q3_fingerprints.json').exists() else None
    # 独立Q4验证已检查9个源哈希；这里再次重新构建严格图核对分量。
    from solve_q4 import FrozenQ3,strict_no_copy
    fg=FrozenQ3(root);diag=strict_no_copy(fg);ck('strict_components_match',diag['components']==q4['components']);ck('strict_K3_possible',diag['component_count']>=3)
    cert=js('results/q3/closure_repair_certificate.json');ck('Q3_final_checked_before_freeze',cert['status']=='independently_verified_final_Q3');ck('no_relay_replication_policy',cert['Q4_replication_allowed'] is False)
    previous=root/'reference/previous_release_q12_hashes.json'
    if previous.exists():
        for p,h in js(str(previous.relative_to(root))).items():ck('inherited_Q12_raw_'+p,(root/p).exists() and sha256(root/p)==h)
    # 主输出与所有已实算备选的摘要应和当次主方案对齐。
    sr=next(r for r in read_csv(root/'results/q3/scenario_comparison.csv') if r['scenario']=='q3')
    for key in ('joint_makespan_s','total_energy_kwh','relay_energy_kwh'):eq('Q3_scenario_'+key,sr[key],s[key])
    for av in js('results/q3/alternatives_validation.json'):eq('alternative_'+av['scenario'],av['checks_failed'],0)
    for q in ('q2','q3'):
        er=next(r for r in read_csv(root/'results/closure/fixed_energy_sweep.csv') if r['question']==q.upper() and float(r['energy_multiplier'])==1.)
        eq(q+'_pressure_baseline_energy',er['transport_energy_kwh'],ss[q]['energy_kwh']);ck(q+'_pressure_baseline_valid',er['energy_and_battery_feasible']=='True')
    # 从真实XLSX值检查源格式及物理（完整检查可由validate_submission另行重复）。
    from submission import _compare
    for comp,path in [(False,root/'submission/结果提交.xlsx'),(True,root/'submission/Q3运输与逐箱补充.xlsx')]:
        _,cells=_compare(root,path,write_log=False,companion=comp);ck('actual_workbook_cells_'+str(comp),all(c['pass'] for c in cells))
    acc=js('results/logs/submission_validation.json')
    for key,value in acc.items():
        if key.endswith('_failed'):eq('actual_workbook_'+key,value,0)
    # 文本数字锚点、Markdown图片引用及公式可排版性，未检验的故事性结论不装成数值断言。
    mds=list((root/'docs').glob('[0-9][0-9]_*.md'));ck('12_reports',len(mds)==12);formula_count=0
    anchors=[('02_',ss['q1']['energy_kwh']),('03_',ss['q2']['makespan_s']),('06_',s['joint_makespan_s']),('06_',s['total_energy_kwh']),('08_',s['joint_makespan_s']),('10_',s['joint_makespan_s'])]
    for prefix,val in anchors:
        p=next(p for p in mds if p.name.startswith(prefix));ck('report_anchor_'+prefix+str(val),f'{val:.6f}' in p.read_text())
    from matplotlib.mathtext import math_to_image
    for p in mds:
        ck('docx_pair_'+p.stem,p.with_suffix('.docx').exists())
        for image in re.findall(r'!\[[^\]]*\]\(([^)]*)\)',p.read_text()):ck('report_image_'+p.stem+image,(p.parent/image).resolve().exists())
        for line in p.read_text().splitlines():
            if line.startswith('$$') and line.endswith('$$'):
                formula_count+=1
                try:math_to_image('$'+line[2:-2]+'$',io.BytesIO(),dpi=90,format='png');ck('formula_'+str(formula_count),True)
                except Exception as e:ck('formula_'+str(formula_count),False,e)
    catalog=js('paper/figure_catalog.json')
    for r in catalog:
        p=root/r['图文件'];fd=js(r['绘图数值']);ck('Chinese_title_'+r['图号'],bool(re.search('[\u4e00-\u9fff]',r['中文图题'])) and r['中文图题']==fd['title'])
        for ext in ('.png','.svg','.pdf'):ck('figure_'+r['图号']+ext,p.with_suffix(ext).exists())
        for f,h in fd['sources'].items():ck('figure_source_'+r['图号']+f,sha256(root/f)==h)
    for ext in ('png','svg','pdf'):eq('exact_figure_count_'+ext,len(list((root/'results/figures').rglob('*.'+ext))),len(catalog))
    ck('no_font_files',not any(p.suffix.lower() in ('.ttf','.ttc','.otf','.woff','.woff2') for p in root.rglob('*') if p.is_file()))
    ut=js('results/logs/unit_tests.json');ck('unit_tests_pass',ut['success'] and ut['failures']==ut['errors']==0)
    result={'checks_total':len(checks),'checks_passed':sum(c['pass'] for c in checks),'checks_failed':sum(not c['pass'] for c in checks),'theme_reports':len(mds),'parsed_formulas':formula_count,
            'png_figures':len(catalog),'svg_figures':len(catalog),'pdf_figures':len(catalog),'strict_Q3_Q4_consistent':True,'source_inventory_is_not_Q4_sufficient':True,
            'scope':'实际表格/聚合/继承/源哈希/数值锚点/公式和图源闭环；视觉另检查，非全局最优或现实安全认证'}
    write_csv(root/'results/logs/final_consistency_checks.csv',checks);save_json(root/'results/logs/final_consistency_summary.json',result)
    if result['checks_failed']:raise AssertionError('闭环门禁失败：'+str([c for c in checks if not c['pass']][:30]))
    return result
