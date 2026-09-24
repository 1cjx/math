#!/usr/bin/env python3
"""完整的相对路径重绘、逐图核验、Overleaf同步；编译为可选项。
Python3.13.5；依赖版本见requirements.txt。默认只读取冻结实算结果。
"""
from pathlib import Path
import argparse,subprocess,sys,time,json
ROOT=Path(__file__).resolve().parent

def run(args,cwd=None):
    subprocess.run(args,cwd=cwd or ROOT,check=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--recompute',action='store_true',help='先从原始数据重跑已有四问求解器');p.add_argument('--compile',action='store_true',help='本地使用latexmk/XeLaTeX编译论文');args=p.parse_args();t=time.time()
    if args.recompute:run([sys.executable,str(ROOT/'experiment/run_all.py'),'--check-reference'])
    run([sys.executable,str(ROOT/'redraw_figures.py')])
    run([sys.executable,str(ROOT/'validate_figures.py')])
    run([sys.executable,'-m','viz.compose'])
    run([sys.executable,str(ROOT/'sync_overleaf.py')])
    if args.compile:
        run(['latexmk','-xelatex','-interaction=nonstopmode','-halt-on-error','main.tex'],ROOT/'overleaf')
    print(f'重绘、核验和同步完成；用时 {time.time()-t:.1f}秒。')
if __name__=='__main__':main()
