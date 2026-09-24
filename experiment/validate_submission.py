"""Python 3.13.5；锁定依赖requirements.txt。不依赖artifact_tool或优化器解对象。"""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from submission import verify_submission
if __name__=='__main__':print(json.dumps(verify_submission(ROOT),ensure_ascii=False,indent=2))
