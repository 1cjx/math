"""标准库数据I/O与只读OOXML解析；不依赖Excel、MATLAB或商业优化器。
Python 3.13.5；依赖参见requirements.txt。工作簿只读，不改写原始文件。
"""
from pathlib import Path
import csv, json, hashlib, zipfile, posixpath
from xml.etree import ElementTree as ET
import numpy as np

S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def save_json(path, obj):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    def conv(x):
        if isinstance(x,np.generic):return x.item()
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,Path):return str(x)
        raise TypeError(type(x).__name__)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=conv,allow_nan=False)+'\n',encoding='utf-8')

def write_csv(path, rows, fields=None):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    rows=list(rows)
    if fields is None: fields=list(rows[0]) if rows else []
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='raise'); w.writeheader(); w.writerows(rows)

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def xlsx_read(path):
    """只读解析全部sheet及真实行号；合并区留空不盲目填充。拒绝公式缓存缺失。"""
    sheets={}; metadata=[]
    with zipfile.ZipFile(path) as z:
        bad=z.testzip()
        if bad:raise ValueError(f'XLSX CRC失败：{bad}')
        ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(S+'si'):
                ss.append(''.join(t.text or '' for t in si.iter(S+'t')))
        rels={e.attrib['Id']:e.attrib['Target'] for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).find(S+'sheets'):
            target=rels[sh.attrib[R+'id']]
            fp=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            tree=ET.fromstring(z.read(fp)); rows={}; cells=[]
            for row in tree.iter(S+'row'):
                vals={}
                for cell in row.findall(S+'c'):
                    coord=cell.attrib['r']; letters=''.join(x for x in coord if x.isalpha())
                    ci=0
                    for c in letters:ci=ci*26+ord(c)-64
                    typ=cell.attrib.get('t','n'); v=cell.find(S+'v'); f=cell.find(S+'f')
                    raw=v.text if v is not None else None
                    if typ=='inlineStr':value=''.join(t.text or '' for t in cell.iter(S+'t'))
                    elif typ=='s':value=ss[int(raw)] if raw is not None else None
                    elif typ=='b':value=bool(int(raw)) if raw is not None else None
                    elif typ in ('str','e','d'):value=raw
                    elif raw is None:value=None
                    else:
                        value=float(raw)
                        if value.is_integer():value=int(value)
                    if f is not None and raw is None:raise ValueError(f'{path.name}:{sh.attrib["name"]}!{coord}公式缺少缓存')
                    vals[ci-1]=value
                    cells.append({'cell':coord,'type':typ,'value':value,'formula':f.text if f is not None else None})
                if vals:rows[int(row.attrib['r'])]=vals
            maxr=max(rows,default=0); maxc=max((max(v,default=-1) for v in rows.values()),default=-1)+1
            matrix=[[rows.get(i,{}).get(j) for j in range(maxc)] for i in range(1,maxr+1)]
            sheets[sh.attrib['name']]=matrix
            metadata.append({'workbook':Path(path).name,'sheet':sh.attrib['name'],'physical_rows':maxr,
                             'physical_cols':maxc,'cells':cells,'merge_ranges':[e.attrib['ref'] for e in tree.iter(S+'mergeCell')]})
    return sheets,metadata

def first_file(root, suffix):
    matches=sorted(Path(root).rglob(suffix))
    if len(matches)!=1:raise ValueError(f'期望唯一文件 {suffix}，实际{len(matches)}个')
    return matches[0]

def block(matrix, header, stop_header=None):
    """按业务表头定位区块，返回带真实Excel行号的记录，不依赖美化空行。"""
    starts=[i for i,r in enumerate(matrix) if r[:len(header)]==header]
    if len(starts)!=1:raise ValueError(f'表头定位失败：{header}')
    start=starts[0]+1; out=[]
    for i in range(start,len(matrix)):
        r=matrix[i]
        if not any(v is not None for v in r):continue
        if stop_header and r[0]==stop_header:break
        # 下一分区标题的定义是除A列外全空；输入业务记录均不满足此条件。
        if r[0] is not None and all(v is None for v in r[1:]):break
        out.append((i+1,r[:len(header)]))
    return out
