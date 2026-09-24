"""论文图形样式。只控制视觉参数，不修改数据；Python 3.13 / Matplotlib 3.10.8。"""
from functools import lru_cache
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt, font_manager, colors
from cycler import cycler

BLUE='#466C96'; TEAL='#509C9C'; GOLD='#D5A25A'; RED='#BB6B64'; PURPLE='#877CAA'
INK='#253342'; MUTED='#667582'; GRID='#E6EAED'
COLORS=[BLUE,TEAL,GOLD,PURPLE,RED,'#91ABA3','#7593AE','#A6907A']
MODEL={'A':BLUE,'B':TEAL,'C':GOLD}; QUESTION={'Q2':BLUE,'Q3':TEAL}
PHASE={'爬升':BLUE,'巡航':TEAL,'下降':GOLD,'交接':PURPLE,'投送':PURPLE}
MATERIAL={'医疗物资':BLUE,'饮用水':TEAL,'应急食品':GOLD,'生活卫生用品':PURPLE}
TERRAIN=colors.LinearSegmentedColormap.from_list('terrain_paper',['#E8F0F2','#B7D7D5','#88B8AE','#BED0A4','#ECE0B9','#C2A07B','#80654F'])
ENERGY=colors.LinearSegmentedColormap.from_list('energy_paper',['#355C8A','#81BCBF','#DFE8BD','#F2C977','#C3664F'])

@lru_cache(None)
def chinese_font():
    names={x.name for x in font_manager.fontManager.ttflist}
    for n in ['Noto Sans CJK SC','Source Han Sans SC','Source Han Sans CN','Microsoft YaHei','SimHei','Noto Sans CJK JP','WenQuanYi Zen Hei']:
        if n in names:return n
    raise RuntimeError('缺少中文字体。请安装思源黑体或Noto Sans CJK；本包不分发字体文件。')

def setup():
    plt.rcParams.update({'font.family':[chinese_font()], 'font.size':10,'axes.titlesize':11.5,'axes.titleweight':'medium',
        'axes.labelsize':10, 'xtick.labelsize':8.5,'ytick.labelsize':8.5,'axes.unicode_minus':False,
        'figure.facecolor':'white','savefig.facecolor':'white','axes.facecolor':'white',
        'axes.edgecolor':'#86919A','axes.labelcolor':INK,'text.color':INK,'xtick.color':MUTED,'ytick.color':MUTED,
        'axes.linewidth':.65,'axes.spines.top':False,'axes.spines.right':False,
        'xtick.major.width':.6,'ytick.major.width':.6,'xtick.major.size':3,'ytick.major.size':3,
        'grid.color':GRID,'grid.linewidth':.55,'lines.linewidth':1.6,'lines.markersize':4,
        'legend.frameon':False,'legend.fontsize':8,'legend.handlelength':1.9,'legend.columnspacing':1.1,
        'axes.prop_cycle':cycler(color=COLORS),'svg.fonttype':'path','svg.hashsalt':'D_scientific_redraw_2026',
        'pdf.fonttype':42,'path.simplify':False,'savefig.dpi':260})

def figure(size=(7.2,4.45), projection=None):
    fig=plt.figure(figsize=size)
    ax=fig.add_subplot(111,projection=projection)
    if projection!='3d':
        ax.grid(axis='y',zorder=0);ax.set_axisbelow(True)
        ax.margins(x=.04,y=.12)
    return fig,ax

def legend(ax,**kw):
    default=dict(loc='best',frameon=False)
    default.update(kw);return ax.legend(**default)
