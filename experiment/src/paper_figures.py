"""中文论文图：从当次数值生成PNG、SVG与矢量PDF，逐图导出数据来源和绘图数值。
Python3.13.5；Matplotlib3.10.8，numpy2.3.5，rasterio1.5.0。
全部参数见closure_config；默认颜色；每图独立画布；无网络底图、无模拟实验数据。
"""
from pathlib import Path
from collections import Counter,defaultdict
import json,math,re,shutil
import numpy as np
import rasterio
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt,font_manager
from matplotlib.text import Text
from matplotlib.collections import PathCollection
from io_utils import read_csv,write_csv,save_json,sha256
from closure_config import CLOSURE_CFG
from physics import trip_energy
from q4_config import RESOURCE_KEYS,RESOURCE_NAMES

SCENARIO={'q1_frozen':'冻结第一问批次（硬时限不可行）','main':'多点主方案','q3':'最终闭环主方案','polish_1':'可分区备选一','polish_2':'较快独立备选','uncoupled_baseline':'原独立主方案','energy_tradeoff':'节能对照','fixed_service_windows':'固定服务窗对照',
'multipoint':'多点主方案','direct_only':'单点对照','q1_fixed_batches':'第一问批次调度','nominal':'基准'}
def trname(s):return SCENARIO.get(s,s.replace('energy','节能').replace('direct','单点').replace('multi','多点'))
def cjk_font():
    names={f.name for f in font_manager.fontManager.ttflist}
    for name in CLOSURE_CFG.chinese_font_candidates+('Noto Sans CJK JP','Noto Serif CJK JP','AR PL UMing CN'):
        if name in names:return name
    raise RuntimeError('未找到中文字库。请在操作系统安装思源黑体/Noto Sans CJK或黑体后重跑；不输出缺字的伪中文图。')

class Publisher:
    def __init__(self,root,only=None):
        self.root=Path(root);self.out=self.root/'results/figures';self.paper=self.root/'paper';self.rows=[];self.only=set(only) if only else None
        self.previous={str(Path(r['图文件']).relative_to('results/figures')):r for r in json.loads((self.paper/'figure_catalog.json').read_text())} if self.only else {}
        if self.out.exists() and not self.only:shutil.rmtree(self.out)
        self.out.mkdir(parents=True,exist_ok=True)
        if (self.paper/'figure_data').exists() and not self.only:shutil.rmtree(self.paper/'figure_data')
        (self.paper/'figure_data').mkdir(parents=True,exist_ok=True)
        plt.rcParams.update({'font.family':[cjk_font()],'axes.unicode_minus':False,'svg.fonttype':'path','svg.hashsalt':'D_strict_closure_CN_v1','pdf.fonttype':42,'font.size':10,'axes.titlesize':13})
    def save(self,fig,name,title,sources,note='当前主方案的诊断视图；不另算一次独立实验'):
        p=self.out/name;p.parent.mkdir(parents=True,exist_ok=True)
        if not p.suffix:p=p.with_suffix('.png')
        if self.only and str(p.relative_to(self.out)) not in self.only:
            self.rows.append(self.previous[str(p.relative_to(self.out))]);plt.close(fig);return
        if not re.search('[\u4e00-\u9fff]',title):raise ValueError('图题必须含中文')
        fig.axes[0].set_title(title,pad=12)
        for ax in fig.axes:
            ax.grid(alpha=.16,axis='y');ax.set_axisbelow(True)
            if '架次序号' in ax.get_xlabel() and ax.patches:
                centers=sorted({round(float(t.get_x()+t.get_width()/2),6) for t in ax.patches if hasattr(t,'get_width')})
                ax.set_xticks(centers,[f'{i+1:03d}' for i in range(len(centers))],rotation=45 if len(centers)>20 else 0,fontsize=8)
        for t in fig.findobj(match=Text):t.set_fontfamily(cjk_font())
        fig.tight_layout(pad=1.4)
        fig.savefig(p,dpi=CLOSURE_CFG.paper_plot_dpi,bbox_inches='tight')
        fig.savefig(p.with_suffix('.svg'),bbox_inches='tight',metadata={'Date':None})
        fig.savefig(p.with_suffix('.pdf'),bbox_inches='tight',metadata={'CreationDate':None,'ModDate':None,'Creator':'D题中文实验图生成程序'})
        # 捕获实际绘图序列和文字；源表哈希记录使每张图可回溯。
        line_data=[]
        for ai,ax in enumerate(fig.axes):
            for j,line in enumerate(ax.lines):
                def finite(a):
                    return [float(x) if isinstance(x,(int,float,np.number)) and np.isfinite(x) else (None if isinstance(x,(int,float,np.number)) else str(x)) for x in np.asarray(a).ravel()]
                line_data.append({'axes':ai,'series':j,'label':line.get_label(),'x':finite(line.get_xdata()),'y':finite(line.get_ydata())})
            for j,patch in enumerate(ax.patches):
                if all(hasattr(patch,f'get_{x}') for x in ('x','y','width','height')):
                    line_data.append({'axes':ai,'bar':j,'x':float(patch.get_x()),'y':float(patch.get_y()),'width':float(patch.get_width()),'height':float(patch.get_height())})
        for ai,ax in enumerate(fig.axes):
            for j,col in enumerate(ax.collections):
                if isinstance(col,PathCollection):
                    off=np.asarray(col.get_offsets(),dtype=float)
                    line_data.append({'axes':ai,'scatter':j,'xy':[[float(x),float(y)] for x,y in off]})
        texts=[t.get_text() for t in fig.findobj(match=Text) if t.get_text()]
        stem=str(p.relative_to(self.out).with_suffix('')).replace('/','__');src=[str(x) for x in sources]
        for s in src:
            if not (self.root/s).exists():raise FileNotFoundError(f'图件来源不存在:{s}')
        save_json(self.paper/'figure_data'/f'{stem}.json',{'title':title,'sources':{s:sha256(self.root/s) for s in src},'note':note,'series_and_bars':line_data,'visible_text':texts})
        self.rows.append({'图号':f'F{len(self.rows)+1:03d}','中文图题':title,'图文件':str(p.relative_to(self.root)),
            '矢量PDF':str(p.with_suffix('.pdf').relative_to(self.root)),'数据源':';'.join(src),'绘图数值':f'paper/figure_data/{stem}.json','说明':note})
        plt.close(fig)
    def finish(self):
        write_csv(self.paper/'figure_catalog.csv',self.rows)
        save_json(self.paper/'figure_catalog.json',self.rows)
        save_json(self.root/'results/closure/chinese_figure_check.json',{'figures':len(self.rows),'png':len(list(self.out.rglob('*.png'))),'svg':len(list(self.out.rglob('*.svg'))),'pdf':len(list(self.out.rglob('*.pdf'))),'font_family':cjk_font(),'missing_chinese_font':False,'all_titles_contain_chinese':True,'source_traceability':True})
        return self.rows

def make_paper_figures(root,only=None):
    root=Path(root);pub=Publisher(root,only=only)
    def csv(q,name):return read_csv(root/f'results/{q}/{name}.csv')
    def js(q):return json.loads((root/f'results/{q}/summary.json').read_text())
    def fig(size=(9,5)):return plt.subplots(figsize=size)
    def wrap_label(label):
        label=str(label).replace('型运输无人机','型运输\n无人机').replace('中继无人机','中继\n无人机').replace('中继能源组件','中继能源\n组件')
        return '\n'.join(label[i:i+7] for i in range(0,len(label),7)) if '\n' not in label and len(label)>10 and re.search('[\u4e00-\u9fff]',label) else label
    def bars(name,title,labels,values,ylabel,sources,note='',rotate=0):
        labels=[wrap_label(x) for x in labels]
        f,a=fig((max(8,min(13,len(labels)*.42)),5));a.bar(range(len(labels)),values);a.set_xticks(range(len(labels)),labels,rotation=rotate);a.set_ylabel(ylabel)
        pub.save(f,name,title,sources,note or '当前主方案的诊断视图；柱高由源表聚合')
    def grouped(name,title,labels,series,ylabel,sources):
        labels=[wrap_label(x) for x in labels]
        f,a=fig((max(9,min(13,len(labels)*.55)),5));x=np.arange(len(labels));n=len(series);width=.8/n
        for j,(lab,values) in enumerate(series):a.bar(x+(j-(n-1)/2)*width,values,width,label=lab)
        a.set_xticks(x,labels,rotation=40 if len(labels)>10 else 0);a.set_ylabel(ylabel);a.legend();pub.save(f,name,title,sources)
    def routes(name,title,trips,sources,relays=None,groups=None):
        f,a=fig((9,7));nodes={n['node_id']:n for n in data['nodes']}
        if groups:
            for g,ids in groups:
                a.scatter([nodes[i]['lon_deg'] for i in ids],[nodes[i]['lat_deg'] for i in ids],s=60,label=g)
        else:
            for r in trips:
                pts=[nodes[i] for i in ['O01']+r['visit_order'].split(';')+['O01']]
                a.plot([p['lon_deg'] for p in pts],[p['lat_deg'] for p in pts],linewidth=.85,alpha=.7)
        for k,n in nodes.items():a.annotate(k,(n['lon_deg'],n['lat_deg']),xytext=(4,3),textcoords='offset points',fontsize=8)
        a.scatter([nodes['O01']['lon_deg']],[nodes['O01']['lat_deg']],marker='*',s=140,label='调度中心O01')
        if relays:
            a.scatter([float(r['hover_lon_deg']) for r in relays],[float(r['hover_lat_deg']) for r in relays],marker='^',s=80,label='中继悬停位置')
            for r in relays:a.annotate(r['relay_trip_id'],(float(r['hover_lon_deg']),float(r['hover_lat_deg'])),xytext=(-35,-12),textcoords='offset points',fontsize=8)
        a.set(xlabel='经度（°）',ylabel='纬度（°）');a.set_aspect(1/math.cos(math.radians(nodes['O01']['lat_deg'])));a.legend();a.margins(.12);pub.save(f,name,title,sources)
    def gantt(name,title,rows,idfield,start,end,sources,ready=None):
        ids=sorted({r[idfield] for r in rows});f,a=fig((12,max(4.7,len(ids)*.36)))
        for r in rows:
            y=ids.index(r[idfield]);l=float(r[start])/60;u=float(r[end])/60;a.barh(y,u-l,left=l,height=.62)
            if ready and float(r[ready])>float(r[end]):a.barh(y,(float(r[ready])-float(r[end]))/60,left=u,height=.62,fill=False,hatch='///')
            tag=r.get('trip_id',r.get('source_task_id',r.get('relay_trip_id',''))).split('-')[-1]
            if u-l>5:a.text((u+l)/2,y,tag,ha='center',va='center',fontsize=7)
        def display_id(v):
            for old,new in [('transport_A','A型运输机'),('transport_B','B型运输机'),('transport_C','C型运输机'),('battery_A','A型电池'),('battery_B','B型电池'),('battery_C','C型电池'),('relay_drone','中继机'),('relay_energy','中继能源')]:v=v.replace(old,new)
            return v
        a.set(yticks=range(len(ids)),yticklabels=[display_id(v) for v in ids],xlabel='相对开始时刻（分钟）'+('；斜线表示充电或周转' if ready else ''));a.invert_yaxis();pub.save(f,name,title,sources)
    data=json.loads((root/'data/cleaned/model_inputs.json').read_text());s1,s2,s3,s4=[js(q) for q in ('q1','q2','q3','q4')]
    r1=csv('q1','route_geometry');p1=csv('q1','route_dem_cells');b1=csv('q1','batches_NET');caps=csv('q1','max_safe_payload_matrix');models=data['transport_models']
    # 第一问原12幅图中文重建，文件名保持报告引用兼容。
    routes('01_dem_routes.png','第一问：调度中心与单点往返航线',[{'visit_order':r['service_id']} for r in r1],['results/q1/route_geometry.csv','data/cleaned/model_inputs.json'])
    # 精确DEM背景另画，不用背景抽稀结果参与计算。
    with rasterio.open(root/'data/cleaned/geospatial/dem_clean.tif') as ds:z=ds.read(1);bounds=ds.bounds
    f,a=fig((9,7));im=a.imshow(z,extent=(bounds.left,bounds.right,bounds.bottom,bounds.top),origin='upper');f.colorbar(im,ax=a,label='地面海拔（米）')
    for n in data['nodes']:a.annotate(n['node_id'],(n['lon_deg'],n['lat_deg']),fontsize=8)
    a.set(xlabel='经度（°）',ylabel='纬度（°）');pub.save(f,'q1/q1_00_dem.png','原始全分辨率地形与任务节点',['data/cleaned/geospatial/dem_clean.tif','data/cleaned/model_inputs.json'])
    grouped('02_safe_payload.png','第一问：各机型连续最大安全载荷',[r['service_id'] for r in caps],[(f'{g}型',[float(r[g+'_kg']) for r in caps]) for g in 'ABC'],'货物质量（千克）',['results/q1/max_safe_payload_matrix.csv'])
    sv=csv('q1','service_summary');bars('03_service_sorties.png','第一问：各服务区最少往返架次数',[r['service_id'] for r in sv],[int(r['trips']) for r in sv],'运输架次',['results/q1/service_summary.csv'],rotate=45)
    f,a=fig((11,5));bottom=np.zeros(len(b1));fields=[('outbound_horizontal_kwh','去程水平'),('inbound_horizontal_kwh','返程水平'),('outbound_climb_kwh','去程爬升'),('inbound_climb_kwh','返程爬升')]
    for k,label in fields:
        y=np.array([float(r[k]) for r in b1]);a.bar(range(len(b1)),y,bottom=bottom,label=label);bottom+=y
    a.set_xticks(range(len(b1)),[r['trip_id'].split('-')[-1] for r in b1]);a.set(xlabel='第一问架次编号',ylabel='能耗（千瓦时）');a.legend();pub.save(f,'04_energy_components.png','第一问：逐架次往返能耗分解',['results/q1/batches_NET.csv'])
    f,a=fig((11,5));a.bar(range(len(b1)),[100*float(r['return_soc_fraction']) for r in b1]);a.axhline(20,linestyle='--',label='题定最低剩余电量20%');a.legend();a.set(xlabel='第一问架次序号',ylabel='返航剩余电量（%）');pub.save(f,'05_return_soc.png','第一问：每一架次返航电量核验',['results/q1/batches_NET.csv'])
    ss=csv('q1','reserve_sensitivity');good=[r for r in ss if r['trips']]
    for field,path,title,ylabel in [('trips','06_reserve_sorties.png','第一问：安全余量与最少架次数','架次'),('energy_kwh','07_reserve_energy.png','第一问：提高返航余量后的总能耗','能耗（千瓦时）')]:
        f,a=fig();a.plot([float(r['reserve_fraction'])*100 for r in good],[float(r[field]) for r in good],marker='o');a.set(xlabel='要求保留的电量（%）',ylabel=ylabel);pub.save(f,path,title,['results/q1/reserve_sensitivity.csv'],'各档重新优化；仅绘制全箱可交付档，不可行档详见源表，不能视为0')
    sens=csv('q1','capacity_sensitivity');f,a=fig()
    for g in 'ABC':
        rr=[r for r in sens if r['service_id']=='S008' and r['model_id']==g];a.plot([float(r['reserve_fraction'])*100 for r in rr],[float(r['max_safe_payload_kg']) if r['max_safe_payload_kg'] else np.nan for r in rr],marker='o',label=g+'型')
    a.set(xlabel='要求保留的电量（%）',ylabel='最大安全载荷（千克）');a.legend();pub.save(f,'08_limiting_payload_sensitivity.png','第一问：S008安全载荷对余量要求的响应',['results/q1/capacity_sensitivity.csv'])
    rr=csv('q1','flight_energy_frontier');f,a=fig();a.plot([int(r['trips']) for r in rr],[float(r['min_energy_kwh']) for r in rr],marker='.');a.set(xlabel='运输总架次数',ylabel='最小运输能耗（千瓦时）');pub.save(f,'09_sortie_energy_frontier.png','第一问：不同架次数下的最小能耗曲线',['results/q1/flight_energy_frontier.csv'],'包含被支配点的逐架次数最小能耗曲线；只有18和19架次是本数据二维非支配点，非三目标全部帕累托前沿')
    ev=csv('quality','node_dem_comparison');bars('10_node_dem_difference.png','数据核查：题定节点海拔与DEM像元差异',[r['node_id'] for r in ev],[float(r['difference_m']) for r in ev],'题定海拔减DEM海拔（米）',['results/quality/node_dem_comparison.csv'],rotate=45)
    bars('11_demand_distribution.png','数据核查：全部货箱按服务区分布',[r['service_id'] for r in sv],[int(r['box_count']) for r in sv],'不可拆货箱数量',['results/q1/service_summary.csv'],rotate=45)
    for r in r1:
        sid=r['service_id'];rr=[x for x in p1 if x['service_id']==sid];f,a=fig();a.step([float(x['along_m'])/1000 for x in rr],[float(x['dem_m']) for x in rr],where='mid',label='穿越像元地形剖面');a.axhline(float(r['cruise_altitude_m']),linestyle='--',label='计划巡航海拔');a.set(xlabel='沿去程水平距离（千米）',ylabel='海拔（米）');a.legend();pub.save(f,f'q1/terrain_{sid}.png',f'第一问：O01至{sid}沿线地形与净空',['results/q1/route_dem_cells.csv','results/q1/route_geometry.csv'])
        if sid=='S008':
            f,a=fig();a.step([float(x['along_m'])/1000 for x in rr],[float(x['dem_m']) for x in rr],where='mid',label='地面海拔');a.axhline(float(r['cruise_altitude_m']),linestyle='--',label='巡航海拔');a.set(xlabel='水平距离（千米）',ylabel='海拔（米）');a.legend();pub.save(f,'12_route_terrain_profile.png','第一问：瓶颈区域S008地形剖面',['results/q1/route_dem_cells.csv','results/q1/route_geometry.csv'])
        rt={k:v if k=='service_id' else float(v) for k,v in r.items()};f,a=fig();curves=[]
        for m in models:
            x=np.linspace(0,m['max_payload_kg'],CLOSURE_CFG.route_curve_samples);y=[trip_energy(m,rt,float(xx))['energy_kwh']/m['usable_energy_kwh']*100 for xx in x];a.plot(x,y,label=m['model_id']+'型');curves.extend({'service_id':sid,'model_id':m['model_id'],'payload_kg':float(xx),'energy_fraction_percent':yy} for xx,yy in zip(x,y))
        a.axhline(80,linestyle='--',label='可用任务能量上限80%');a.set(xlabel='去程货物质量（千克）',ylabel='往返耗电占可用电量（%）');a.legend();source=f'results/closure/energy_curves_{sid}.csv';write_csv(root/source,curves);pub.save(f,f'q1/energy_curve_{sid}.png',f'第一问：{sid}载荷—能量可行边界',[source],'基于明确能耗假设的确定性曲线，不是额外现场实验')
    disc=csv('q1','payload_continuous_discrete')
    for g in 'ABC':
        rr=[r for r in disc if r['model_id']==g];grouped(f'q1/payload_{g}.png',f'第一问：{g}型连续上限与现有整箱可实现载荷',[r['service_id'] for r in rr],[('连续安全上限',[float(r['continuous_safe_payload_kg']) for r in rr]),('现有整箱最大值',[float(r['available_box_max_payload_kg']) for r in rr])],'货物质量（千克）',['results/q1/payload_continuous_discrete.csv'])
    f,a=fig((11,5));bottom=np.zeros(len(b1))
    for field,label in [('preparation_load_s','准备及装载'),('flight_time_s','纯飞行'),('handoff_s','交接')]:
        y=np.array([float(r[field])/60 for r in b1]);a.bar(range(len(b1)),y,bottom=bottom,label=label);bottom+=y
    a.set(xlabel='第一问架次序号',ylabel='累计作业时间（分钟）');a.legend();pub.save(f,'q1/time_components.png','第一问：三种时间口径的组成',['results/q1/batches_NET.csv'])
    ec=csv('q1','energy_assumption_sensitivity');bars('q1/energy_assumptions.png','第一问：能耗分项假设扰动后重新优化',[f'水平{r["horizontal_multiplier"]}\n爬升{r["climb_multiplier"]}' for r in ec],[float(r['energy_kwh']) for r in ec],'方案总能耗（千瓦时）',['results/q1/energy_assumption_sensitivity.csv'])
    # Q2/Q3共用绘图规则，数值来自各自问题，绝不混用通信ID。
    for q,s in [('q2',s2),('q3',s3)]:
        tr=csv(q,'trips');bx=csv(q,'box_deliveries');bt=csv(q,'battery_cycles');src=f'results/{q}'
        rootname=lambda k: (f'q2_{k}' if q=='q2' else f'q3/q3_{k}')
        rel=csv(q,'relay_sorties') if q=='q3' else None
        routes(rootname('01_routes.png'),f'{q.upper()}：{s["trips"]}架次运输航线与节点',tr,[src+'/trips.csv','data/cleaned/model_inputs.json']+([src+'/relay_sorties.csv'] if rel else []),rel)
        gantt(rootname('02_drone_gantt.png'),f'{q.upper()}：运输无人机占用时序',tr,'drone_id','start_s','return_s',[src+'/trips.csv'])
        gantt(rootname('03_battery_gantt.png'),f'{q.upper()}：共享电池任务与充电时序',bt,'battery_id','task_start_s','return_s',[src+'/battery_cycles.csv'],ready='charge_end_s')
        hard=sorted([r for r in bx if r['hard_deadline_s']],key=lambda r:(float(r['hard_deadline_s']),r['box_id']));f,a=fig((12,6));x=range(len(hard));a.plot(x,[float(r['hard_deadline_s'])/60 for r in hard],'s--',label='硬截止时刻');a.plot(x,[float(r['delivery_complete_s'])/60 for r in hard],'o',label='交接完成');a.set_xticks(x,[r['box_id'] for r in hard],rotation=90,fontsize=7);a.set_ylabel('相对时刻（分钟）');a.legend();pub.save(f,rootname('04_hard_deadlines.png'),f'{q.upper()}：医疗及首批保障货箱硬时限',[src+'/box_deliveries.csv'])
        sc=csv(q,'scenario_comparison');f,a=fig((11,6));points={}
        for r in sc:
            xx=float(r['joint_makespan_s'] if q=='q3' else r['makespan_s'])/60;yy=float(r['total_energy_kwh'] if q=='q3' else r['energy_kwh'])
            key=(round(xx,7),round(yy,7));points.setdefault(key,{'x':xx,'y':yy,'labels':[],'valid':True})
            points[key]['labels'].append(trname(r['scenario']));points[key]['valid'] &= r.get('feasible','True')=='True'
        for j,p in enumerate(points.values()):
            a.scatter(p['x'],p['y'],s=65,marker='o' if p['valid'] else 'x',label='\n'.join(p['labels']))
        a.legend(loc='upper left',bbox_to_anchor=(1.01,1),fontsize=9,title='实算方案（同点合并）')
        a.set(xlabel='联合完工时间（分钟）' if q=='q3' else '运输完工时间（分钟）',ylabel='运输与中继总能耗（千瓦时）' if q=='q3' else '运输能耗（千瓦时）');a.margins(.32);pub.save(f,rootname('06_tradeoff.png'),f'{q.upper()}：实算备选方案的时间与能耗',[src+'/scenario_comparison.csv'],'圆点为本问可行备选；叉号为硬时限不合格对照。同坐标标签合并，下游可分区性须另外检查；不是全局帕累托前沿')
        f,a=fig((12,5));a.bar(range(len(tr)),[100*float(r['return_soc_fraction']) for r in tr]);a.axhline(20,linestyle='--',label='题定底线20%');a.set(xlabel='运输架次序号',ylabel='返航剩余电量（%）');a.legend();pub.save(f,rootname('07_return_soc.png'),f'{q.upper()}：逐架次返航安全余量',[src+'/trips.csv'])
        f,a=fig();times=sorted(float(r['delivery_complete_s'])/60 for r in bx);a.step([0]+times,[0]+list(range(1,len(times)+1)),where='post');a.set(xlabel='交接完成时刻（分钟）',ylabel='累计交付箱数');pub.save(f,rootname('08_delivery_progress.png'),f'{q.upper()}：全部货箱累计交付进度',[src+'/box_deliveries.csv'])
        for g in 'ABC':routes(f'{q}/routes_model_{g}.png',f'{q.upper()}：{g}型无人机运输路线',[r for r in tr if r['model_id']==g],[src+'/trips.csv','data/cleaned/model_inputs.json'])
        bars(f'{q}/box_slack.png',f'{q.upper()}：各服务区最紧硬时限裕度',[n['node_id'] for n in data['services']],
            [min(float(r['hard_deadline_s'])-float(r['delivery_complete_s']) for r in hard if r['service_id']==n['node_id']) for n in data['services']],'最小剩余时间（秒）',[src+'/box_deliveries.csv'],rotate=45)
        grouped(f'{q}/load_usage.png',f'{q.upper()}：载质量与装载体积利用率',[r['trip_id'].split('-')[-1] for r in tr],
            [('质量利用率',[float(r['weight_kg'])/next(m['max_payload_kg'] for m in models if m['model_id']==r['model_id'])*100 for r in tr]),('体积利用率',[float(r['volume_m3'])/next(m['volume_m3'] for m in models if m['model_id']==r['model_id'])*100 for r in tr])],'容量利用率（%）',[src+'/trips.csv','data/cleaned/model_inputs.json'])
        legs=csv(q,'legs');f,a=fig((12,5));hor=[sum(float(l['horizontal_energy_kwh']) for l in legs if l['trip_id']==r['trip_id']) for r in tr];up=[sum(float(l['climb_energy_kwh']) for l in legs if l['trip_id']==r['trip_id']) for r in tr];a.bar(range(len(tr)),hor,label='水平航程能耗');a.bar(range(len(tr)),up,bottom=hor,label='爬升附加能耗');a.set(xlabel='运输架次序号',ylabel='能耗（千瓦时）');a.legend();pub.save(f,f'{q}/energy_components.png',f'{q.upper()}：逐航段汇总的运输能耗分项',[src+'/legs.csv'])
        grouped(f'{q}/model_workload.png',f'{q.upper()}：分机型累计作业与纯飞行时间',list('ABC'),[('累计作业',[sum(float(r['operation_time_s']) for r in tr if r['model_id']==g)/60 for g in 'ABC']),('纯飞行',[sum(float(r['flight_time_s']) for r in tr if r['model_id']==g)/60 for g in 'ABC'])],'累计时间（分钟）',[src+'/trips.csv'])
    f,a=fig()
    for name,label in [('multipoint','多点搜索'),('direct_only','单点搜索')]:
        rr=[r for r in csv('q2',name+'_search_rounds') if r['round_kind']=='sequential_refinement'];key='best_makespan_s' if rr and 'best_makespan_s' in rr[0] else 'makespan_s'
        if rr and key in rr[0]:a.plot(range(1,len(rr)+1),[float(r[key])/60 for r in rr],marker='o',label=label)
    a.set(xlabel='顺序改进轮次',ylabel='当轮最佳完工时间（分钟）');a.legend();pub.save(f,'q2_05_convergence.png','第二问：固定搜索预算下的收敛轨迹',['results/q2/multipoint_search_rounds.csv','results/q2/direct_only_search_rounds.csv'],'多次轮次为同一次顺序改进，不能当作独立重复试验')
    # Q3连续通信与中继能源的细粒度图。
    rr=csv('q3','relay_sorties');tr=csv('q3','trips');ph=csv('q3','trajectory_phases');atoms=csv('q3','communication_atoms')
    gantt('q3/relay_body_gantt.png','第三问：中继无人机任务及周转',rr,'relay_drone_id','start_s','return_s',['results/q3/relay_sorties.csv'],ready='turnaround_end_s')
    gantt('q3/relay_energy_gantt.png','第三问：中继能源组件及两阶段充电',rr,'energy_module_id','start_s','return_s',['results/q3/relay_sorties.csv'],ready='charge_end_s')
    for r in rr:
        t=[float(r['start_s']),float(r['start_s'])+data['relay_models'][0]['prepare_s'],float(r['arrival_s']),float(r['link_complete_s']),float(r['service_end_s']),float(r['return_s'])]
        # 飞行剖面中的三阶段严格按速度展开，不用端点粗线替代原阶段。
        m=data['relay_models'][0];z0=data['depots'][0]['ground_elevation_m'];cr=float(r['cruise_altitude_m']);zh=float(r['hover_altitude_m']);take=t[1]
        t1=take+float(r['outbound_climb_m'])/m['climb_speed_mps'];t2=t1+float(r['horizontal_distance_m'])/m['cruise_speed_mps'];u=t[4]+float(r['inbound_climb_m'])/m['climb_speed_mps'];v=u+float(r['horizontal_distance_m'])/m['cruise_speed_mps']
        xx=[t[0],take,t1,t2,t[2],t[3],t[4],u,v,t[5]];zz=[z0,z0,cr,cr,zh,zh,zh,cr,cr,z0];f,a=fig();a.plot(np.array(xx)/60,zz,marker='.');a.axvspan(t[3]/60,t[4]/60,alpha=.10,label='完成建链后服务时段');a.set(xlabel='相对时刻（分钟）',ylabel='海拔（米）');a.legend();pub.save(f,f'q3/relay_profile_{r["relay_trip_id"]}.png',f'第三问：{r["relay_trip_id"]}完整飞行及服务剖面',['results/q3/relay_sorties.csv','data/cleaned/model_inputs.json'])
    for r in tr:
        pp=[p for p in ph if p['trip_id']==r['trip_id']];f,a=fig();seen=set()
        for phase in dict.fromkeys(p['phase'] for p in pp):
            xx=[];yy=[]
            for p in pp:
                if p['phase']==phase:xx.extend([float(p['start_s'])/60,float(p['end_s'])/60,np.nan]);yy.extend([float(p['p0_altitude_m']),float(p['p1_altitude_m']),np.nan])
            a.plot(xx,yy,label=phase,linewidth=1.7)
        a.set(xlabel='相对时刻（分钟）',ylabel='飞行与作业海拔（米）');a.legend();pub.save(f,f'q3/transport_profile_{r["trip_id"]}.png',f'第三问：{r["trip_id"]}逐阶段高度剖面',['results/q3/trajectory_phases.csv'],'不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留')
    f,a=fig((13,9));tids=[r['trip_id'] for r in tr]
    for mode in ('直连','中继'):
        group=[x for x in atoms if x['mode']==mode and float(x['end_s'])>float(x['start_s'])]
        a.barh([tids.index(x['trip_id']) for x in group],[(float(x['end_s'])-float(x['start_s']))/60 for x in group],left=[float(x['start_s'])/60 for x in group],height=.65,fill=mode=='直连',hatch='///' if mode=='中继' else None,label=mode)
    a.set(yticks=range(len(tids)),yticklabels=tids,xlabel='连续通信时间区间（分钟）');a.legend();a.invert_yaxis();pub.save(f,'q3/communication_timeline.png','第三问：直连与中继保障的完整时间区间',['results/q3/communication_atoms.csv'],'正长度区间图；孤立边界点由独立表逐点验证，图像分辨率不构成连续性证明')
    f,a=fig();dur={mode:sum(float(x['end_s'])-float(x['start_s']) for x in atoms if x['mode']==mode) for mode in ('直连','中继')};a.bar(dur.keys(),[v/60 for v in dur.values()]);a.set_ylabel('各运输机通信需求时间累计（分钟）');pub.save(f,'q3/communication_duration.png','第三问：直连与中继累计保障工作量',['results/q3/communication_atoms.csv'],'累计飞行及交接时间，不等于日历持续时间；边界点不重复计时')
    f,a=fig();positive=[x for x in atoms if x['selected_margin_mid_db']!='' and float(x['end_s'])>float(x['start_s'])];a.hist([float(x['selected_margin_mid_db']) for x in positive],bins=30);a.set(xlabel='所选链路区间中点裕量（分贝）',ylabel='区间数量');pub.save(f,'q3/link_margin_distribution.png','第三问：已分割区间中点链路裕量分布',['results/q3/communication_atoms.csv'],'仅中点分布诊断，不是区间内最低裕量证明，不取代完整区间核验')
    for source,x,y,name,title,xlab,ylab in [
      ('propagation_loss_sensitivity','extra_loss_db','outage_duration_sum_s','propagation_loss','第三问：额外传播损耗压力测试','额外传播损耗（分贝）','通信中断累计时间（秒）'),
      ('relay_only_delay_sensitivity','relay_only_shift_s','fixed_assignment_uncovered_duration_s','relay_delay','第三问：仅中继延迟的冻结分配测试','中继单独延迟（秒）','未覆盖累计区间（秒）'),
      ('common_start_delay_sensitivity','common_delay_s','min_hard_slack_s','common_delay','第三问：全部资源共同延后的时限裕度','共同延迟（秒）','最紧硬时限裕度（秒）')]:
        datax=csv('q3',source);f,a=fig();a.plot([float(r[x]) for r in datax],[float(r[y]) for r in datax],marker='o');a.set(xlabel=xlab,ylabel=ylab);pub.save(f,f'q3/{name}.png',title,[f'results/q3/{source}.csv'],'压力场景不重优化；负裕度或中断表示失败，不能当作正式可行方案')
    grouped('q3/relay_energy_components.png','第三问：每次中继任务能耗组成',[r['relay_trip_id'] for r in rr],[(lab,[float(r[k]) for r in rr]) for k,lab in [('flight_energy_kwh','往返飞行'),('setup_energy_kwh','建链悬停'),('service_energy_kwh','通信服务')]],'能耗（千瓦时）',['results/q3/relay_sorties.csv'])
    bars('q3/relay_return_soc.png','第三问：中继任务返航剩余电量',[r['relay_trip_id'] for r in rr],[100*float(r['return_soc_fraction']) for r in rr],'返航电量（%）',['results/q3/relay_sorties.csv'])
    # Q4仅绘制严格任务继承的分区，明确缺口。
    ac=csv('q4','atomic_components');bars('q4/atomic_workload.png','第四问：运输与中继依赖合并后的不可拆单元',[r['component_id'] for r in ac],[100*float(r['transport_workload_share']) for r in ac],'占全部运输累计作业时间（%）',['results/q4/atomic_components.csv'])
    for k in (2,3):
        gg=csv('q4',f'K{k}/groups');aa=csv('q4',f'K{k}/resource_allocations')
        routes(f'q4/partition_K{k}.png',f'第四问：严格不复制中继的{k}组分区',[],[f'results/q4/K{k}/groups.csv','data/cleaned/model_inputs.json'],groups=[(r['group_id'],r['services'].split(';')) for r in gg])
        for field,label,suffix in [('transport_workload_s','运输累计作业时间（分钟）','workload'),('boxes','货箱数量','boxes'),('transport_trips','运输架次数','sorties')]:
            bars(f'q4/K{k}_{suffix}.png',f'第四问：{k}组的{label.split("（")[0]}',[r['group_id'] for r in gg],[float(r[field])/(60 if field.endswith('_s') else 1) for r in gg],label,[f'results/q4/K{k}/groups.csv'])
        grouped(f'q4/K{k}_inventory.png',f'第四问：{k}组独立配置需求与原库存',list(RESOURCE_NAMES),[('现有库存',[s4['inventory'][key] for key in RESOURCE_KEYS]),('各组合计需求',[s4['selected'][str(k)]['need_'+key] for key in RESOURCE_KEYS])],'设备或能源资源件数',['results/q4/summary.json'])
        bars(f'q4/K{k}_gap.png',f'第四问：{k}组分类型资源缺口',list(RESOURCE_NAMES),[s4['selected'][str(k)]['gap_'+key] for key in RESOURCE_KEYS],'需要增补的件数',['results/q4/summary.json'])
        for keys,title,slug in [(('transport_A','transport_B','transport_C'),'运输机身','drones'),(('battery_A','battery_B','battery_C'),'运输电池','batteries'),(('relay_drone',),'中继机身','relay'),(('relay_energy',),'中继能源组件','modules')]:
            rows=[r for r in aa if r['resource_type'] in keys]
            gantt(f'q4/K{k}_{slug}_gantt.png',f'第四问：{k}组独立{title}占用',rows,'local_resource_id','start_s','return_s',[f'results/q4/K{k}/resource_allocations.csv'],ready='ready_s')
    ap=csv('q4','all_partitions');f,a=fig()
    for k in (2,3):
        rr=[r for r in ap if int(r['K'])==k];a.scatter([float(r['transport_workload_cv']) for r in rr],[float(r['resource_units']) for r in rr],label=f'{k}组')
        for r in rr:a.annotate(r['partition_id'],(float(r['transport_workload_cv']),float(r['resource_units'])),xytext=(5,5),textcoords='offset points')
    a.set(xlabel='运输工作量变异系数（越小越均衡）',ylabel='资源配置总件数');a.legend();a.margins(.18);pub.save(f,'q4/all_partitions.png',f'第四问：严格可行的全部{len(ap)}个分区比较',['results/q4/all_partitions.csv'],'固定最终Q3的严格依赖图全部分区；不同于仅按运输依赖枚举的空间')
    # 闭环新增压力曲线：相同场景，同一排程，不混同重优化敏感性。
    specs=[('fixed_energy_sweep','energy_multiplier','minimum_soc_fraction','energy_soc','运输能耗扰动与最低返航电量','能耗乘数','最低返航电量比例'),
       ('fixed_energy_sweep','energy_multiplier','reserve_violating_sorties','energy_violations','运输能耗扰动导致的安全余量违约','能耗乘数','违反余量的架次数'),
       ('fixed_energy_sweep','energy_multiplier','battery_reuse_conflicts','energy_charge_conflicts','运输能耗扰动导致的电池周转冲突','能耗乘数','电池复用冲突次数'),
       ('fixed_charging_sweep','full_charge_time_multiplier','minimum_reuse_slack_s','charge_slack','充电时间扰动与下一次任务准备裕度','充电时间乘数','最小电池复用裕度（秒）'),
       ('fixed_charging_sweep','full_charge_time_multiplier','conflicting_transitions','charge_conflicts','充电变慢后的资源冲突','充电时间乘数','发生冲突的复用次数'),
       ('common_delay_fine_sweep','common_delay_s','minimum_hard_slack_s','delay_slack','共同延迟对最紧硬时限的影响','共同延迟（秒）','最小硬时限裕度（秒）'),
       ('common_delay_fine_sweep','common_delay_s','hard_late_boxes','delay_violations','共同延迟导致的硬时限违约货箱数','共同延迟（秒）','硬时限违约箱数'),
       ('common_delay_fine_sweep','common_delay_s','expected_late_boxes','expected_delay','共同延迟导致的期望送达逾期','共同延迟（秒）','期望逾期箱数')]
    for src,x,y,name,title,xlabel,ylabel in specs:
        rr=csv('closure',src);f,a=fig()
        for q in ('Q2','Q3'):
            rows=[r for r in rr if r['question']==q];a.plot([float(r[x]) for r in rows],[float(r[y]) for r in rows],marker='.' if len(rows)>30 else 'o',label=q)
        a.set(xlabel=xlabel,ylabel=ylabel);a.legend();pub.save(f,f'closure/{name}.png','闭环压力测试：'+title,[f'results/closure/{src}.csv'],'冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率')
    ce=csv('q3','closure_existing_candidates');f,a=fig((11,6));points={}
    for r in ce:
        xx=float(r['joint_makespan_s'])/60;yy=float(r['total_energy_kwh']);key=(round(xx,7),round(yy,7),r['component_count'])
        points.setdefault(key,{'x':xx,'y':yy,'labels':[],'valid':r['strict_K3_feasible']=='True'})['labels'].append(trname(r['candidate'])+'；最多'+r['component_count']+'组')
    for p in points.values():
        a.scatter(p['x'],p['y'],marker='o' if p['valid'] else 'x',s=80,label='\n'.join(p['labels']))
    a.legend(loc='upper left',bbox_to_anchor=(1.01,1),fontsize=9,title='严格分组能力（同点合并）')
    a.set(xlabel='联合最后返回（分钟）',ylabel='运输与中继能耗（千瓦时）');a.margins(.32);pub.save(f,'closure/candidate_compatibility.png','闭环筛选：独立Q3候选的严格三分区兼容性',['results/q3/closure_existing_candidates.csv'],'圆点支持严格三组；叉号不支持；同坐标标签合并，选择在Q3定稿前完成，不在Q4改排任务')
    return pub.finish()
