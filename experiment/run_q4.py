#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从现有Q3主方案增量求解Q4。Python3.13.5；requirements.txt锁定依赖。
python run_q4.py --check-reference；不清除或重排Q1—Q3，仅更新Q4和统一提交材料。
"""
from pathlib import Path
import argparse,sys,time,json,unittest
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from io_utils import save_json,sha256
from solve_q4 import run_q4
from q4_validation import run_q4_validation
from paper_figures import make_paper_figures
from closure_experiments import run_closure_experiments
from submission import sync_submission
from reports import run_reports
from final_consistency import run_final_consistency


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check-reference',action='store_true');args=parser.parse_args();start=time.perf_counter()
    if not (ROOT/'results/q3/Q3_通信保障.csv').exists():raise FileNotFoundError('缺少当次Q3主方案，请先运行run_all.py')
    baseline={str(p.relative_to(ROOT)):sha256(p) for parent in ('data/raw','results/q1','results/q2','results/q3') for p in (ROOT/parent).rglob('*') if p.is_file() and p.suffix in ('.csv','.json','.xlsx','.docx','.tif')}
    s=run_q4(ROOT);print('Q4全枚举完成',s['partition_counts'],flush=True)
    v=run_q4_validation(ROOT);print('独立核验通过',v['checks_total'],v['physical_checks_total'],flush=True)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
    save_json(ROOT/'results/logs/unit_tests.json',{'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'success':result.wasSuccessful()})
    if not result.wasSuccessful():raise AssertionError('测试失败，不发布')
    run_closure_experiments(ROOT);sync_submission(ROOT);make_paper_figures(ROOT);run_reports(ROOT);run_final_consistency(ROOT)
    if args.check_reference:
        from run_all import check_reference
        check_reference()
    unchanged=all(sha256(ROOT/name)==h for name,h in baseline.items())
    if not unchanged:raise AssertionError('增量执行改变了前三问输入/数值')
    save_json(ROOT/'results/logs/q4_incremental_execution.json',{'status':'success','elapsed_seconds':time.perf_counter()-start,'Q123_unchanged':unchanged,'inherited_files_checked':len(baseline),'Q4_source_inventory_feasible':s['inventory_feasible_partition_counts']})
    print('Q4完成；最终模板为submission/结果提交.xlsx。库存缺口及解释见提交必读。')
if __name__=='__main__':main()
