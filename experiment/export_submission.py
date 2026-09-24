"""Python 3.13.5；openpyxl3.1.5。由当次结果CSV重建原模板，不运行优化。"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from submission import sync_submission
if __name__=='__main__':print(sync_submission(ROOT))
