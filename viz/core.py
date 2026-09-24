"""共享数据读取、逐图数据追溯和原生矢量输出。图表不读取任何旧PNG/PDF。"""
from pathlib import Path
import csv,json,hashlib,io
import numpy as np
import matplotlib as _native_pdf_backend  # D_NATIVE_PDF_PATCH_V1
from matplotlib import pyplot as plt
from matplotlib.text import Text
from matplotlib.transforms import Bbox
from .style import setup, INK

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiment'
OUT=ROOT/'figures'
DATA=ROOT/'plot_data'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,np.ndarray)):return [clean(v) for v in value]
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    if isinstance(value,(int,np.integer)):return int(value)
    if isinstance(value,np.bool_):return bool(value)
    return value

def csvwrite(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:raise ValueError('Cannot export empty table')
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

class Source:
    def __init__(self):
        self.used=set();self._csv={};self._json={}
    def csv(self,path):
        self.used.add(path)
        if path not in self._csv:
            with (EXP/path).open(encoding='utf-8-sig',newline='') as f:self._csv[path]=list(csv.DictReader(f))
        return self._csv[path]
    def json(self,path):
        self.used.add(path)
        if path not in self._json:self._json[path]=json.loads((EXP/path).read_text(encoding='utf-8'))
        return self._json[path]
    def use(self,path):self.used.add(path);return EXP/path
    def start(self,extra=()):self.used=set(extra)

class Publisher:
    def __init__(self):
        setup();OUT.mkdir(exist_ok=True);DATA.mkdir(exist_ok=True);self.records=[]
    def save(self,fig,code,title,src,values,note='',short_title=None):
        ax=fig.axes[0]
        titlepad=10
        leg=ax.get_legend()
        if leg is not None:
            anchor=leg.get_bbox_to_anchor().transformed(ax.transAxes.inverted())
            if anchor.y1>1.001:
                # 将图例放在轴外的一行，图题在其上，不覆盖数据与图题。
                leg.set_bbox_to_anchor((0,1.01),transform=ax.transAxes)
                leg.set_loc('lower left')
                titlepad=29
        ax.set_title(short_title if short_title is not None else title,loc='left',pad=titlepad,color=INK)
        # 标題由绘图轴原生生成；无卡片、徽章、渐变背景、旧图截图或外包装。
        if getattr(fig,'_shared_state_frame',False):
            fig.subplots_adjust(left=.13,right=.99,bottom=.23,top=.73)
        else:fig.tight_layout(pad=.9)
        fig.canvas.draw()
        bbox=Bbox.from_bounds(0,0,*fig.get_size_inches()) if getattr(fig,'_shared_state_frame',False) else fig.get_tightbbox(fig.canvas.get_renderer()).padded(.05)
        p=OUT/code
        fig.savefig(p.with_suffix('.png'),dpi=260,bbox_inches=bbox,pad_inches=0)
        buf=io.BytesIO()
        fig.savefig(buf,format='svg',bbox_inches=bbox,pad_inches=0,metadata={'Date':None,'Creator':'D题数值图原生重绘'})
        svg=buf.getvalue();p.with_suffix('.svg').write_bytes(svg)
        # SVG保留中文字形路径；PDF用原生后端嵌入所需字形，无需系统Cairo动态库。
        # PDF由当前Figure直接导出；不调用Cairo或SVG转换器。
        with _native_pdf_backend.rc_context({"pdf.fonttype": 3, "pdf.use14corefonts": False}):
            fig.savefig(
                str(p.with_suffix('.pdf')),
                format="pdf", backend="pdf",
                bbox_inches=bbox, pad_inches=0,
                metadata={"CreationDate": None, "ModDate": None,
                          "Creator": "D scientific figures / native Matplotlib PDF"},
            )
        prov={s:sha(EXP/s) for s in sorted(src.used)}
        # 导出每张图真实绘图变量；统计或插值的含义单独记录。
        payload={'figure_id':code,'title':title,'sources':prov,'note':note,'values':clean(values),
                 'visible_text':[t.get_text() for t in fig.findobj(match=Text) if t.get_visible() and t.get_text()]}
        write_json(DATA/f'{code}.json',payload)
        row={'图号':code,'中文图题':title,'PDF':f'figures/{code}.pdf','PNG':f'figures/{code}.png','SVG':f'figures/{code}.svg',
             '数据源':';'.join(prov),'绘图数据':f'plot_data/{code}.json','解释':note,'PDF_SHA256':sha(p.with_suffix('.pdf'))}
        self.records.append(row);plt.close(fig)
        print(f'{code} {title}',flush=True)
    def finish(self):
        # 增量--only模式保留未重画图的索引，避免覆盖为不完整图集。
        previous=ROOT/'audit/render_manifest.json'
        if len(self.records)<163 and previous.exists():
            merged={r['图号']:r for r in json.loads(previous.read_text(encoding='utf-8'))}
            merged.update({r['图号']:r for r in self.records})
            self.records=[merged[k] for k in sorted(merged)]
        csvwrite(ROOT/'figure_catalog.csv',self.records)
        write_json(ROOT/'audit/render_manifest.json',self.records)
