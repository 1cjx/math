#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D题全流程：全量清洗→Q1精确优化→Q2联合调度→Q3连续通信联合调度→Q4冻结分区与独立配置→独立核验→原模板与配套表。
实测Python 3.13.5；numpy2.3.5 scipy1.17.0 rasterio1.5.0 pyproj3.7.2
shapely2.1.2 h5py3.15.1 matplotlib3.10.8 python-docx1.2.0 Pillow12.3.0 affine2.4.0 numba0.65.1 openpyxl3.1.5。
参数集中在src/config.py、src/q2_config.py、src/q3_config.py、src/q4_config.py、src/closure_config.py；设备/需求一律读取源数据。
用法：python run_all.py --check-reference 。全部路径相对本文件。
"""
from __future__ import annotations
import argparse,contextlib,importlib.metadata,json,math,os,platform,sys,time,traceback,unittest,shutil
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from config import CFG
from q2_config import Q2CFG
from q3_config import Q3CFG
from q4_config import Q4CFG
from closure_config import CLOSURE_CFG
from io_utils import save_json,write_csv,sha256
DIRECT_DEPENDENCIES=('numpy','scipy','rasterio','pyproj','shapely','h5py','matplotlib','python-docx','Pillow','affine','numba','openpyxl')
REFERENCE_ABS_TOLERANCE=1e-6
GENERATED_DIRS=('data/cleaned','results','docs','submission','paper')
class Tee:
    def __init__(self,*streams):self.streams=streams
    def write(self,text):
        for s in self.streams:s.write(text);s.flush()
        return len(text)
    def flush(self):
        for s in self.streams:s.flush()

def snapshot():
    def read(p):return json.loads((ROOT/p).read_text('utf-8'))
    a=read('results/quality/quality_summary.json');q=read('results/q1/summary.json');r=read('results/q2/summary.json');v1=read('results/q1/validation_summary.json');v2=read('results/q2/independent_validation.json')
    t=read('results/q3/summary.json');v3=read('results/q3/independent_validation.json');au=read('results/audit/audit_summary.json')
    q4=read('results/q4/summary.json');v4=read('results/q4/independent_validation.json')
    return {'q4':{'component_count':q4['component_count'],'partition_counts':q4['partition_counts'],'minimum_shortage_units':q4['minimum_shortage_units'],'selected':{k:{f:v[f] for f in ('partition_id','resource_units','shortage_units','transport_workload_cv','total_energy_kwh')} for k,v in q4['selected'].items()},'checks_failed':v4['checks_failed'],'physical_checks_failed':v4['physical_checks_failed']},'q3':{k:t[k] for k in ('trips','energy_kwh','transport_makespan_s','joint_makespan_s','relay_energy_kwh','total_energy_kwh','relay_trips','relay_bodies_used','relay_modules_used','delivered_boxes','medical_on_time','first_batch_on_time','all_expected_on_time','min_return_soc_fraction','min_hard_deadline_slack_s','relay_min_soc_fraction','communication_atoms','communication_boundary_points')},
            'q3_verification':{'source_mismatches':au['source_mismatches'],'checks_failed':v3['checks_failed'],'continuous_atoms_failed':v3['continuous_atoms_failed'],'dense_failed':v3['dense_failed']},
            'q1':{k:q[k] for k in ('trips','energy_kwh','operation_time_s','flight_time_s','delivered_boxes','delivered_weight_kg','delivered_volume_m3','min_return_soc_fraction','critical_common_reserve_fraction','model_trip_counts')},
            'q2':{k:r[k] for k in ('trips','energy_kwh','makespan_s','weighted_tardiness_s','hard_late_s','delivered_boxes','medical_on_time','first_batch_on_time','all_expected_on_time','model_trip_counts','multipoint_trips','min_return_soc_fraction','min_hard_deadline_slack_s','battery_reuses','makespan_lower_bound_s')},
            'quality':{k:a[k] for k in ('boxes','valid_dem_cells','geospatial_vertex_rows','checks_failed','physical_values_overwritten')},
            'validation':{'q1_failed':v1['checks_failed'],'q1_exact_services':v1['independent_optimum_services'],'q2_failed':v2['checks_failed'],'q2_arc_failed':v2['arc_checks_failed']}}

def check_reference():
    expected=json.loads((ROOT/'reference/expected_results.json').read_text('utf-8'));actual=snapshot();checks=[]
    def walk(a,b,p):
        if isinstance(b,dict):
            for k in b:walk(a[k],b[k],p+'.'+k)
        else:
            ok=math.isclose(float(a),float(b),rel_tol=0,abs_tol=REFERENCE_ABS_TOLERANCE) if isinstance(b,(int,float)) else a==b
            checks.append({'field':p,'actual':a,'reference':b,'pass':ok})
    walk(actual,expected,'result');r={'checks':checks,'checks_passed':sum(x['pass'] for x in checks),'checks_failed':sum(not x['pass'] for x in checks),'absolute_tolerance':REFERENCE_ABS_TOLERANCE}
    save_json(ROOT/'results/logs/reference_check.json',r)
    if r['checks_failed']:raise AssertionError('参考比对失败：输入/参数/依赖变化时应解释新结果，不能强迫优化器输出旧指标。')
    return r

def data_dictionary(data):
    out=[]
    suffixes=[('_kg','kg'),('_m3','m³'),('_mps','m/s'),('_kwh','kWh'),('_s','s'),('_deg','degree'),('_m','m'),('_fraction','0–1')]
    for name,records in data.items():
        if not isinstance(records,list) or not records or not isinstance(records[0],dict):continue
        for key in records[0]:
            vals=[r.get(key) for r in records];unit=next((u for end,u in suffixes if key.endswith(end)),'not_applicable_or_label')
            types=' / '.join(sorted({type(x).__name__ for x in vals if x is not None}))
            out.append({'table':name,'field':key,'data_type':types,'unit':unit,'null_count':sum(x is None for x in vals),'note':'单位由字段后缀明示；source列定位原数据。不适用值保留null。'})
    write_csv(ROOT/'data/cleaned/data_dictionary.csv',out)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check-reference',action='store_true');args=parser.parse_args()
    if not (ROOT/'data/raw/题面.docx').exists():raise FileNotFoundError('请完整解压，缺少data/raw/题面.docx')
    raw={str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/'data/raw').rglob('*')) if p.is_file()}
    for name in GENERATED_DIRS:
        path=ROOT/name
        if path.exists():shutil.rmtree(path)
        path.mkdir(parents=True,exist_ok=True)
    (ROOT/'results/logs').mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'results/logs/.matplotlib_cache'))
    env={'python':sys.version,'platform':platform.platform(),'cpu_count':os.cpu_count(),
         'dependencies':{p:importlib.metadata.version(p) for p in DIRECT_DEPENDENCIES},'config':asdict(CFG),'q2_config':asdict(Q2CFG),'q3_config':asdict(Q3CFG),'q4_config':asdict(Q4CFG),'closure_config':asdict(CLOSURE_CFG),'utc_started':datetime.now(timezone.utc).isoformat()}
    save_json(ROOT/'results/logs/environment_actual.json',env);stages=[];begin=time.perf_counter()
    with (ROOT/'results/logs/run.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(Tee(sys.stdout,log)),contextlib.redirect_stderr(Tee(sys.stderr,log)):
        def stage(name,fn):
            print(f'\n[{len(stages)+1}] {name}',flush=True);t=time.perf_counter();r=fn();elapsed=time.perf_counter()-t
            stages.append({'stage':name,'elapsed_seconds':elapsed,'status':'passed'});save_json(ROOT/'results/logs/stage_timings.json',stages)
            print(f'    完成：{elapsed:.3f} 秒',flush=True);return r
        try:
            from data_quality import run_quality
            from solve_q1 import run_q1
            from q1_enhancements import enhance_q1
            from validation import run_validation
            from solve_q2 import run_q2
            from audit_q12 import run_audit_q12
            from solve_q3 import run_q3
            from solve_q4 import run_q4
            from q4_validation import run_q4_validation
            from q3_closure import run_closure_repair
            from closure_experiments import run_closure_experiments
            from paper_figures import make_paper_figures
            from q3_validation import run_q3_validation
            from q3_experiments import run_q3_experiments
            from q2_validation import run_q2_validation
            from additional_checks import run_additional_checks
            from submission import sync_submission
            from reports import run_reports
            from final_consistency import run_final_consistency
            data,_=stage('全量质量检查与清洗',lambda:run_quality(ROOT));data_dictionary(data)
            stage('第一问精确优化、权衡与合规余量敏感性',lambda:run_q1(ROOT,data))
            stage('连续/整箱载荷、能耗分项扰动与时间分解',lambda:enhance_q1(ROOT,data))
            stage('第一问独立物理与逐箱DP最优性复核',lambda:run_validation(ROOT))
            stage('第二问联合组批、路径、机身/电池调度及全部对照',lambda:run_q2(ROOT,data))
            stage('第二问从CSV独立物理/时限/资源复核',lambda:run_q2_validation(ROOT))
            stage('新载荷/分项台账与对照实验独立复核',lambda:run_additional_checks(ROOT))
            stage('Q1/Q2题意逐条审核及原表单元格回溯',lambda:run_audit_q12(ROOT))
            stage('Q3选址、运输/中继联合搜索与连续通信分割',lambda:run_q3(ROOT,data))
            stage('Q3独立连续区间/孤立点、资源与稠密交叉复核',lambda:run_q3_validation(ROOT))
            stage('Q3对照、扰动与全部备选方案独立验证',lambda:run_q3_experiments(ROOT,data))
            stage('Q3定稿前：严格三分区候选兼容性与闭环选解',lambda:run_closure_repair(ROOT))
            def verify_final_q3():
                v=run_q3_validation(ROOT)
                p=ROOT/'results/q3/closure_repair_certificate.json';c=json.loads(p.read_text('utf-8'));c.update(status='independently_verified_final_Q3',final_independent_checks=v['checks_total'],final_checks_failed=v['checks_failed']);save_json(p,c)
                return v
            stage('最终Q3重新执行全部独立连续/资源核验',verify_final_q3)
            stage('最终Q3重新计算可靠性与备选比较，不沿用旧主指标',lambda:run_q3_experiments(ROOT,data,optimize_alternatives=False))
            stage('Q4严格冻结Q3：禁止副本、全部2/3分区与资源缺口',lambda:run_q4(ROOT))
            stage('Q4独立全枚举、最大匹配与通信物理继承复核',lambda:run_q4_validation(ROOT))
            stage('闭环新增：能耗、充电、共同延迟与源规则追溯',lambda:run_closure_experiments(ROOT))
            def tests():
                result=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
                save_json(ROOT/'results/logs/unit_tests.json',{'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'success':result.wasSuccessful()})
                if not result.wasSuccessful():raise AssertionError('测试失败')
            stage('单元测试与故意错误答案拒绝测试',tests)
            stage('强制同步原模板Excel、逐格比对并从Excel独立重算',lambda:sync_submission(ROOT))
            stage('生成全部中文论文图、矢量PDF和逐图源数据',lambda:make_paper_figures(ROOT))
            stage('自动生成四问建模、核验、题意复查与论文图件报告',lambda:run_reports(ROOT))
            stage('最终跨文件/报告/图件一致性门禁',lambda:run_final_consistency(ROOT))
            if args.check_reference:stage('与参考数值比对（不参与求解）',check_reference)
            after={str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/'data/raw').rglob('*')) if p.is_file()}
            if after!=raw:raise AssertionError('原始文件发生改动')
            save_json(ROOT/'results/logs/raw_integrity_check.json',{'files':len(raw),'unchanged':True,'sha256':raw})
            hashes={str(p.relative_to(ROOT)):sha256(p) for base in ('data/cleaned','results/quality','results/q1','results/q2','results/q3','results/q4','results/audit','results/closure','submission','paper/figure_data') for p in sorted((ROOT/base).rglob('*')) if p.is_file() and p.suffix in ('.csv','.json','.geojson')}
            save_json(ROOT/'results/logs/numeric_file_hashes.json',hashes)
            save_json(ROOT/'results/logs/execution_summary.json',{'status':'success','total_elapsed_seconds':time.perf_counter()-begin,'stages':stages,'raw_unchanged':True})
            print('\n全流程成功：');print(json.dumps(snapshot(),ensure_ascii=False,indent=2));print('最终主模板：submission/结果提交.xlsx；配套：submission/Q3运输与逐箱补充.xlsx。Q1—Q4均已回答。Q4严格继承、不复制中继；分类型配置需增补，详见提交必读。')
        except Exception:
            traceback.print_exc();save_json(ROOT/'results/logs/execution_summary.json',{'status':'failed','total_elapsed_seconds':time.perf_counter()-begin,'stages':stages})
            (ROOT/'submission/提交验收.json').unlink(missing_ok=True)
            raise
if __name__=='__main__':main()
