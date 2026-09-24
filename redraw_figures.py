#!/usr/bin/env python3
"""重画论文图（不重排求解方案）。
环境：Python3.13.5, numpy2.3.5, matplotlib3.10.8, rasterio1.5.0,
scipy1.17.0, cairosvg2.8.2, PyMuPDF1.26.7。根目录相对路径；无需网络。
"""
from pathlib import Path
import argparse,sys,time
from viz.core import Publisher,ROOT
from viz.redraw import make_originals

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',nargs='*');p.add_argument('--skip-extras',action='store_true');args=p.parse_args()
    start=time.time();pub=Publisher();make_originals(pub,set(args.only) if args.only else None)
    if not args.skip_extras and not args.only:
        from viz.extras import make_extras
        make_extras(pub)
    pub.finish();print(f'已生成 {len(pub.records)} 幅原生数据图，用时 {time.time()-start:.1f}s')
if __name__=='__main__':main()
