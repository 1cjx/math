"""重画全部147幅原论文图。读取CSV/JSON/DEM；不读取旧实验图片，不修改求解结果。
Python 3.13.5；NumPy 2.3.5，Matplotlib 3.10.8，Rasterio 1.5.0。
"""
import re,math
from functools import lru_cache
from collections import Counter,defaultdict
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from matplotlib import pyplot as plt, colors, ticker, cm, patheffects
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from .core import Source,Publisher,EXP,OUT,ROOT,clean
from .style import *

S=Source()
MODELS={x['model_id']:x for x in S.json('data/cleaned/model_inputs.json')['transport_models']}
INPUT=S.json('data/cleaned/model_inputs.json')
NODES={x['node_id']:x for x in INPUT['nodes']}
SERVICES=[f'S{i:03d}' for i in range(1,16)]
NAMES={'q1_frozen':'冻结Q1批次（硬时限不满足）','main':'主方案','q3':'最终闭环主方案','polish_1':'最终闭环候选','polish_2':'较快候选','uncoupled_baseline':'独立基线','energy_tradeoff':'节能对照','fixed_service_windows':'固定服务窗对照','multipoint':'多点搜索','direct_only':'单点对照','q1_fixed_batches':'冻结Q1批次'}

def C(q,f):return S.csv(f'results/{q}/{f}.csv')
def J(q):return S.json(f'results/{q}/summary.json')
def nums(rows,k,factor=1):return np.array([float(r[k])*factor if r.get(k) not in ('',None) else np.nan for r in rows])
def short(x):
    x=str(x)
    for a,b in [('型运输无人机','型运输机'),('中继能源组件','中继能源')]:x=x.replace(a,b)
    return x

def dotbars(labels,y,ylabel,title='',horizontal=False,cs=None,fmt=None):
    f,a=figure((7.4,max(3.8,len(labels)*.27)) if horizontal else (7.4,4.4))
    x=np.arange(len(labels));cs=cs if cs is not None else [BLUE]*len(labels)
    if horizontal:
        a.hlines(x,0,y,color=cs,lw=2.0,alpha=.45);a.scatter(y,x,c=cs,s=37,edgecolors='white',lw=.7,zorder=3)
        a.set_yticks(x,labels);a.invert_yaxis();a.set_xlabel(ylabel);a.grid(False,axis='y');a.grid(axis='x')
    else:
        a.vlines(x,0,y,color=cs,lw=2.5,alpha=.45);a.scatter(x,y,c=cs,s=38,edgecolors='white',lw=.7,zorder=3)
        a.set_xticks(x,labels,rotation=45 if len(labels)>10 else 0,ha='right' if len(labels)>10 else 'center');a.set_ylabel(ylabel)
    if len(y)<=18:
        delta=.018*(np.nanmax(np.abs(y)) if np.nanmax(np.abs(y)) else 1)
        for i,v in enumerate(y):
            st=(fmt.format(v) if fmt else (f'{v:.1f}' if abs(v-round(v))>1e-6 else f'{v:.0f}'))
            if horizontal:a.annotate(st,(v,i),xytext=(5,0),textcoords='offset points',ha='left',va='center',fontsize=8,color=INK)
            else:a.annotate(st,(i,v),xytext=(0,5 if v>=0 else -10),textcoords='offset points',ha='center',va='bottom',fontsize=8,color=INK)
    a.axvline(0,color=MUTED,lw=.7) if horizontal else a.axhline(0,color=MUTED,lw=.7)
    return f,a

def grouped(labels,series,ylabel):
    f,a=figure((7.8,4.65));x=np.arange(len(labels));width=.72/len(series)
    for j,(lab,yy) in enumerate(series):
        a.bar(x+(j-(len(series)-1)/2)*width,yy,width,label=lab,color=COLORS[j],edgecolor='white',linewidth=.45)
    a.set_xticks(x,[short(x).replace('无人机','\n无人机').replace('共享','\n共享') for x in labels],rotation=45 if len(labels)>10 else 0,ha='right' if len(labels)>10 else 'center')
    a.set_ylabel(ylabel);legend(a,ncol=min(3,len(series)),loc='upper left',bbox_to_anchor=(0,1.12));a.set_ylim(bottom=0)
    return f,a

def heatmap(labels,xlabels,arr,label,cmap=ENERGY,fmt=None,vmin=None,vmax=None):
    arr=np.asarray(arr,dtype=float)
    f,a=figure((5.1,5.8) if len(labels)>=12 and len(xlabels)<=4 else (7.4,max(4.3,len(labels)*.23)))
    image=a.imshow(np.ma.masked_invalid(arr),aspect='auto',interpolation='nearest',cmap=cmap,vmin=vmin,vmax=vmax)
    a.set_xticks(range(len(xlabels)),xlabels);a.set_yticks(range(len(labels)),labels);a.grid(False)
    a.tick_params(length=0)
    for sp in a.spines.values():sp.set_visible(False)
    a.set_xticks(np.arange(-.5,len(xlabels),1),minor=True);a.set_yticks(np.arange(-.5,len(labels),1),minor=True)
    a.grid(which='minor',color='white',lw=1);a.tick_params(which='minor',bottom=False,left=False)
    if fmt:
        mn=np.nanmin(arr) if vmin is None else vmin;mx=np.nanmax(arr) if vmax is None else vmax
        for i,j in np.ndindex(arr.shape):
            v=arr[i,j];norm=(v-mn)/(mx-mn) if mx>mn else .5
            a.text(j,i,fmt.format(v) if np.isfinite(v) else '不可行',ha='center',va='center',fontsize=8,color='white' if norm<.18 or norm>.84 else INK)
    cb=f.colorbar(image,ax=a,pad=.025,fraction=.03,shrink=.88);cb.set_label(label);cb.outline.set_visible(False)
    return f,a

@lru_cache(1)
def dem():
    with rasterio.open(EXP/'data/cleaned/geospatial/dem_clean.tif') as ds:
        z=ds.read(1,masked=True);bd=ds.bounds;tf=ds.transform
    return z,bd,tf

def plot_map(trips=None,relays=None,groups=None,full=False):
    S.use('data/cleaned/geospatial/dem_clean.tif');S.use('data/cleaned/model_inputs.json')
    z,bd,tf=dem();xs=[n['lon_deg'] for n in NODES.values()];ys=[n['lat_deg'] for n in NODES.values()]
    if relays:xs += [float(x['hover_lon_deg']) for x in relays];ys += [float(x['hover_lat_deg']) for x in relays]
    ext=(bd.left,bd.right,bd.bottom,bd.top) if full else (min(xs)-.012,max(xs)+.018,min(ys)-.013,max(ys)+.013)
    f,a=figure((7.4,5.8) if full else (7.4,5.2));a.grid(False)
    mn=float(z.min());mx=float(z.max())
    im=a.imshow(z,extent=(bd.left,bd.right,bd.bottom,bd.top),origin='upper',cmap=TERRAIN,alpha=.70,interpolation='nearest',vmin=mn,vmax=mx)
    a.set_xlim(*ext[:2]);a.set_ylim(*ext[2:]);a.set_aspect(1/math.cos(math.radians(NODES['O01']['lat_deg'])))
    edges=defaultdict(int)
    if trips:
        for r in trips:
            seq=['O01']+r['visit_order'].split(';')+['O01'];g=r.get('model_id','A')
            for u,v in zip(seq[:-1],seq[1:]):edges[(u,v,g)]+=1
        for (u,v,g),n in edges.items():
            nu,nv=NODES[u],NODES[v];xx=[nu['lon_deg'],nv['lon_deg']];yy=[nu['lat_deg'],nv['lat_deg']];col=MODEL.get(g,BLUE)
            a.plot(xx,yy,color=col,lw=.75+min(n,3)*.22,alpha=.9,zorder=3)
            p0=np.array([xx[0],yy[0]]);p1=np.array([xx[1],yy[1]]);p=(p0*.35+p1*.65);back=p*.0+p0*.43+p1*.57
            a.annotate('',xy=p,xytext=back,arrowprops=dict(arrowstyle='-|>',lw=.7,color=col),zorder=4)
    gc={}
    if groups:
        for j,(label,ids) in enumerate(groups):
            for i in ids:gc[i]=COLORS[j]
            a.scatter([NODES[i]['lon_deg'] for i in ids],[NODES[i]['lat_deg'] for i in ids],s=75,color=COLORS[j],edgecolors='white',lw=.85,zorder=5,label=label)
    for k,n in NODES.items():
        if k!='O01' and not groups:a.scatter(n['lon_deg'],n['lat_deg'],s=23,fc='white',ec=INK,lw=.55,zorder=5)
        if k=='O01':continue
        off=(4,4)
        if k in ('S008','S003'):off=(-2,7)
        if k in ('S006','S014'):off=(3,-11)
        t=a.annotate(k,(n['lon_deg'],n['lat_deg']),xytext=off,textcoords='offset points',fontsize=7.5,zorder=7)
        t.set_path_effects([patheffects.withStroke(linewidth=2,foreground='white')])
    o=NODES['O01'];a.scatter(o['lon_deg'],o['lat_deg'],s=160,marker='*',color=RED,edgecolors='white',lw=.85,zorder=7)
    a.annotate('O01 调度中心',(o['lon_deg'],o['lat_deg']),xytext=(0,-17),textcoords='offset points',ha='center',fontsize=8,zorder=8,color=INK)
    if relays:
        for j,r in enumerate(relays):
            x=float(r['hover_lon_deg']);y=float(r['hover_lat_deg']);a.scatter(x,y,s=68,marker='^',color=PURPLE,edgecolors='white',lw=.8,zorder=6)
            t=a.annotate(r['relay_trip_id'].replace('Q3-',''),(x,y),xytext=(-28,-12 if j%2 else 9),textcoords='offset points',fontsize=7,color=PURPLE,zorder=8)
            t.set_path_effects([patheffects.withStroke(linewidth=2,foreground='white')])
    a.set(xlabel='经度（°E）',ylabel='纬度（°N）')
    a.xaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'));a.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
    a.xaxis.set_major_locator(ticker.MaxNLocator(5));a.yaxis.set_major_locator(ticker.MaxNLocator(5))
    cb=f.colorbar(im,ax=a,pad=.02,fraction=.035,shrink=.82);cb.set_label('DEM海拔（m）');cb.outline.set_visible(False)
    # 指北针只表达方向，不画未经数据支持的行政边界或连续需求热区。
    a.annotate('北',xy=(.065,.90),xytext=(.065,.985),xycoords='axes fraction',ha='center',va='top',arrowprops=dict(arrowstyle='<|-',lw=.75,color=INK),fontsize=8)
    if groups:legend(a,loc='upper right')
    elif trips:
        types=sorted({r.get('model_id','A') for r in trips});h=[Line2D([0],[0],color=MODEL[g],lw=1.8,label=g+'型航段') for g in types]
        if relays:h.append(Line2D([0],[0],marker='^',ls='',color=PURPLE,label='中继悬停点'))
        a.legend(handles=h,loc='upper right',fontsize=7.7)
    val={'nodes':[{'id':k,'lon':n['lon_deg'],'lat':n['lat_deg']} for k,n in NODES.items()],
         'routes':trips or [],'relays':relays or [],'groups':groups or [],'dem_extent':[bd.left,bd.right,bd.bottom,bd.top],'display_extent':ext,'dem_minmax_m':[mn,mx]}
    return f,a,val

def gantt(rows,idfield,start,end,ready=None,q=None):
    ids=sorted({r[idfield] for r in rows});size=(8.4,max(3.4,.26*len(ids)+1.2));f,a=figure(size)
    blocks=[]
    for i,k in enumerate(ids):
        if i%2==0:a.axhspan(i-.43,i+.43,color='#F4F6F7',zorder=0)
    for r in rows:
        k=r[idfield];y=ids.index(k);l=float(r[start])/60;u=float(r[end])/60
        if 'K2' in k or 'K3' in k:
            match=re.search(r'G(\d+)',k);col=COLORS[int(match.group(1))-1] if match else BLUE
        else:
            mid=r.get('model_id','');col=MODEL.get(mid,COLORS[y%3])
            if k.startswith('R'):col=PURPLE
        a.barh(y,u-l,left=l,height=.60,color=col,edgecolor='white',lw=.5,zorder=3)
        ready_value=float(r[ready])/60 if ready else u
        if ready_value>u+1e-9:a.barh(y,ready_value-u,left=u,height=.50,fc=colors.to_rgba(col,.12),edgecolor=col,lw=.5,hatch='////',zorder=2)
        tid=r.get('trip_id',r.get('source_task_id',r.get('relay_trip_id',''))).split('-')[-1]
        if u-l>5:a.text((l+u)/2,y,tid,fontsize=6.5,ha='center',va='center',color='white',zorder=5)
        blocks.append({'resource':k,'start_min':l,'return_min':u,'ready_min':ready_value,'trip':tid})
    def label(k):
        for p,v in [('transport_','机身'),('battery_','电池'),('relay_drone','中继机'),('relay_energy','中继能源')]:k=k.replace(p,v)
        return k
    a.set_yticks(range(len(ids)),[label(k) for k in ids]);a.set_xlabel('任务相对时刻（min）');a.set_ylim(len(ids)-.6,-.6);a.set_xlim(left=0)
    a.grid(False,axis='y');a.grid(axis='x');a.tick_params(axis='y',length=0,labelsize=7.5)
    if ready:a.legend(handles=[Patch(fc=BLUE,label='准备至返回'),Patch(fc='white',ec=MUTED,hatch='////',label='充电或机身周转')],loc='upper left',bbox_to_anchor=(0,1.12),ncol=2)
    return f,a,blocks

def tradeoff(rows,which,compat=False):
    f,a=figure((7.4,4.6));points=[];seen={}
    for r in rows:
        is3=which=='q3';xx=float(r['joint_makespan_s'] if is3 else r['makespan_s'])/60;yy=float(r['total_energy_kwh'] if is3 else r['energy_kwh'])
        key=(round(xx,7),round(yy,7));lab=NAMES.get(r.get('candidate',r.get('scenario','')),r.get('candidate',r.get('scenario','')))
        valid=(r['strict_K3_feasible']=='True') if compat else r.get('feasible','True')=='True'
        if key not in seen:seen[key]={'x':xx,'y':yy,'names':[],'valid':valid,'chosen':False}
        seen[key]['names'].append(lab);seen[key]['chosen'] |= r.get('candidate')=='polish_1' if compat else r.get('scenario') in ['main','q3']
    for j,p in enumerate(seen.values()):
        chosen=p['chosen'];valid=p['valid'];col=TEAL if valid else MUTED;mark='*' if chosen else ('o' if valid else 'x')
        a.scatter(p['x'],p['y'],s=125 if chosen else 50,color=RED if chosen else col,marker=mark,zorder=4,lw=1)
        text=' / '.join(p['names'])
        # 少量真实备选逐点注释；不补造帕累托点云。
        dx,dy=(7,10) if j%2==0 else (7,-15)
        if j==len(seen)-1:dx,dy=(-6,12)
        a.annotate(text,(p['x'],p['y']),xytext=(dx,dy),textcoords='offset points',ha='right' if dx<0 else 'left',fontsize=7.7,color=INK)
        points.append(p)
    a.set(xlabel='联合最后返回（min）' if which=='q3' else '运输最后返回（min）',ylabel='运输与中继能耗（kWh）' if which=='q3' else '运输能耗（kWh）')
    a.margins(x=.30,y=.30)
    if compat:a.legend(handles=[Line2D([0],[0],marker='o',ls='',color=TEAL,label='支持严格三组'),Line2D([0],[0],marker='x',ls='',color=MUTED,label='不支持严格三组'),Line2D([0],[0],marker='*',ls='',color=RED,label='最终选择')],loc='upper right',fontsize=7.5)
    return f,a,points

def redraw_one(row,pub):
    code=row['图号'];name=row['图文件'].replace('results/figures/','');title=row['中文图题'];note=row.get('说明','')
    S.start(row['数据源'].split(';'))
    vals={}; f=a=None; short_title=None
    if name=='q1/q1_00_dem.png':f,a,vals=plot_map(full=True)
    elif name=='01_dem_routes.png':f,a,vals=plot_map([{'visit_order':x['service_id']} for x in C('q1','route_geometry')])
    elif name in ('q2_01_routes.png','q3/q3_01_routes.png') or re.search(r'q[23]/routes_model_[ABC].png',name):
        q='q3' if name.startswith('q3') else 'q2';tr=C(q,'trips');m=re.search('model_([ABC])',name)
        if m:tr=[r for r in tr if r['model_id']==m[1]]
        f,a,vals=plot_map(tr,C('q3','relay_sorties') if q=='q3' and not m else None)
    elif re.match(r'q4/partition_K[23].png',name):
        k=re.search('K([23])',name)[1];gg=C('q4',f'K{k}/groups');f,a,vals=plot_map(groups=[(g['group_id'],g['services'].split(';')) for g in gg])
        note+='；彩点表示服务区归属，不将凸包画成行政区或连续覆盖区。'
    elif name=='02_safe_payload.png':
        rr=C('q1','max_safe_payload_matrix');vals={'service':[r['service_id'] for r in rr],'kg':[[float(r[g+'_kg']) for g in 'ABC'] for r in rr]}
        f,a=heatmap(vals['service'],['A型','B型','C型'],vals['kg'],'连续最大安全载荷（kg）',fmt='{:.1f}',vmin=0,vmax=80)
    elif name=='03_service_sorties.png':
        rr=C('q1','service_summary');yy=nums(rr,'trips');f,a=dotbars([x['service_id'] for x in rr],yy,'最少往返架次',cs=[GOLD if v>1 else BLUE for v in yy]);a.yaxis.set_major_locator(ticker.MaxNLocator(integer=True));vals=rr
    elif name=='11_demand_distribution.png':
        rr=S.csv('data/cleaned/boxes.csv');bottom=np.zeros(15);f,a=figure((7.7,4.5));vals=[]
        for mat,col in MATERIAL.items():
            yy=np.array([sum(r['service_id']==sid and r['material_type']==mat for r in rr) for sid in SERVICES]);a.bar(SERVICES,yy,bottom=bottom,color=col,label=mat,width=.7,ec='white',lw=.5);bottom+=yy;vals.append({'material':mat,'counts':yy})
        for i,v in enumerate(bottom):a.text(i,v+.18,str(int(v)),ha='center',fontsize=8)
        a.set_ylabel('不可拆货箱数（箱）');a.set_xticks(range(15),SERVICES,rotation=45,ha='right');a.set_ylim(0,max(bottom)*1.22);a.yaxis.set_major_locator(ticker.MaxNLocator(integer=True));legend(a,ncol=4,loc='upper right')
    elif name=='10_node_dem_difference.png':
        rr=C('quality','node_dem_comparison');yy=nums(rr,'difference_m');f,a=dotbars([r['node_id'] for r in rr],yy,'题定海拔 − DEM海拔（m）',cs=[RED if v<0 else TEAL for v in yy]);vals=rr
    elif name in ('04_energy_components.png','q1/time_components.png') or name in ('q2/energy_components.png','q3/energy_components.png'):
        f,a=figure((7.7,4.4))
        if name.startswith('q2/') or name.startswith('q3/'):
            q=name[:2];tr=C(q,'trips');legs=C(q,'legs');seq=[r['trip_id'] for r in tr]
            yy=[[sum(float(l[k]) for l in legs if l['trip_id']==tid) for tid in seq] for k in ('horizontal_energy_kwh','climb_energy_kwh')];labs=['水平航程','爬升附加'];ylabel='运输能耗（kWh）'
        else:
            rr=C('q1','batches_NET');seq=[r['trip_id'] for r in rr]
            spec=[('preparation_load_s','准备及装载'),('flight_time_s','纯飞行'),('handoff_s','交接')] if name.endswith('time_components.png') else [('outbound_horizontal_kwh','去程水平'),('inbound_horizontal_kwh','返程水平'),('outbound_climb_kwh','去程爬升'),('inbound_climb_kwh','返程爬升')]
            yy=[nums(rr,k,1/60 if k.endswith('_s') else 1) for k,_ in spec];labs=[x[1] for x in spec];ylabel='累计作业时间（min）' if len(spec)==3 else '运输能耗（kWh）'
        b=np.zeros(len(seq))
        for j,(lab,y) in enumerate(zip(labs,yy)):a.bar(range(len(seq)),y,bottom=b,label=lab,color=COLORS[j],width=.75,ec='white',lw=.35);b+=y
        a.set_xticks(range(len(seq)),[x.split('-')[-1] for x in seq],rotation=45 if len(seq)>20 else 0);a.set(xlabel='架次编号',ylabel=ylabel);legend(a,ncol=len(labs),loc='upper left',bbox_to_anchor=(0,1.13));vals={'trip_ids':seq,'series':dict(zip(labs,yy))}
    elif name=='05_return_soc.png' or name.endswith('07_return_soc.png') or name=='q3/relay_return_soc.png':
        rr=C('q1','batches_NET') if name=='05_return_soc.png' else C('q3','relay_sorties') if name=='q3/relay_return_soc.png' else C('q3' if name.startswith('q3') else 'q2','trips')
        f,a=figure((7.6,4.25));y=nums(rr,'return_soc_fraction',100);x=np.arange(len(rr));cols=[MODEL.get(r.get('model_id'),PURPLE) for r in rr]
        a.axhspan(0,20,color=RED,alpha=.055);a.vlines(x,20,y,color=cols,lw=1.3,alpha=.6);a.scatter(x,y,c=cols,s=31,edgecolors='white',lw=.55,zorder=4);a.axhline(20,ls='--',lw=1,color=RED,label='题定最低返航电量20%')
        a.set_xticks(x,[r.get('trip_id',r.get('relay_trip_id','')).split('-')[-1] for r in rr],rotation=45 if len(rr)>20 else 0);a.set(xlabel='架次编号',ylabel='返航剩余电量（%）',ylim=(0,100));j=int(np.argmin(y));a.annotate(f'最低 {y[j]:.3f}%',(j,y[j]),xytext=(6,12),textcoords='offset points',fontsize=8,color=RED);legend(a,loc='upper right');vals=rr
    elif name=='06_reserve_sorties.png':
        rr=C('q1','reserve_sensitivity');good=[r for r in rr if r['trips']];bad=[r for r in rr if not r['trips']]
        xx=nums(good,'reserve_fraction',100);yy=nums(good,'trips')
        q1=J('q1');critical=100*float(q1['critical_common_reserve_fraction']);baseline_hold=100*float(good[0]['min_return_soc_fraction'])
        f=plt.figure(figsize=(7.6,4.65));gs=f.add_gridspec(2,1,height_ratios=(4.4,.72),hspace=.06)
        a=f.add_subplot(gs[0]);state=f.add_subplot(gs[1],sharex=a)
        a.vlines(xx,17.45,yy,color=BLUE,lw=1.2,alpha=.22,zorder=1)
        a.scatter(xx,yy,s=43,facecolors=['white']*len(xx),edgecolors=BLUE,lw=1.35,zorder=3)
        a.scatter([xx[0]],[yy[0]],s=47,color=BLUE,edgecolors='white',lw=.55,zorder=4)
        for x,y in zip(xx,yy):a.annotate(f'{y:.0f}',(x,y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8,color=INK)
        a.axvline(baseline_hold,color=BLUE,ls='--',lw=.9,alpha=.85)
        a.axvline(critical,color=RED,ls='--',lw=.9,alpha=.9)
        a.annotate(f'18架次方案保持至 {baseline_hold:.2f}%',(baseline_hold,18),xytext=(9,18),textcoords='offset points',fontsize=8,color=BLUE,arrowprops=dict(arrowstyle='-',color=BLUE,lw=.7))
        a.annotate(f'全任务边界 {critical:.2f}%',(critical,25.05),xytext=(8,-2),textcoords='offset points',fontsize=8,color=RED,va='top')
        a.set_xlim(18,62);a.set_ylim(17.35,25.85);a.set_ylabel('重新优化后的最少架次数');a.tick_params(axis='x',labelbottom=False)
        a.yaxis.set_major_locator(ticker.MaxNLocator(integer=True));a.grid(False,axis='x')
        state.axvspan(20,critical,color=TEAL,alpha=.18,lw=0);state.axvspan(critical,60,color=RED,alpha=.13,lw=0)
        state.scatter(xx,np.full(len(xx),.22),s=19,color=BLUE,edgecolors='white',lw=.4,zorder=3)
        if bad:state.scatter(nums(bad,'reserve_fraction',100),np.full(len(bad),.22),s=27,marker='x',color=RED,lw=1.1,zorder=3)
        state.axvline(critical,color=RED,ls='--',lw=.9);state.text((20+critical)/2,.66,'全箱可交付',ha='center',va='center',fontsize=8,color=TEAL);state.text((critical+60)/2,.66,'全箱交付不可行',ha='center',va='center',fontsize=8,color=RED)
        state.set_ylim(0,1);state.set_yticks([]);state.set_xticks(nums(rr,'reserve_fraction',100));state.set_xlabel(r'返航SOC下限 $\rho$（%）');state.grid(False)
        for sp in ('left','right','top'):state.spines[sp].set_visible(False)
        vals={'sweep':rr,'baseline_18_trip_hold_to_percent':baseline_hold,'critical_common_reserve_percent':critical}
        note+='；上图仅绘制离散重优化档位，不对档位之间作线性插值；下方状态带给出解析可行边界。';short_title=''
    elif name=='07_reserve_energy.png':
        rr=C('q1','reserve_sensitivity');good=[r for r in rr if r['energy_kwh']];bad=[r for r in rr if not r['energy_kwh']];xx=nums(good,'reserve_fraction',100);yy=nums(good,'energy_kwh')
        f,a=figure((7.2,4.4));a.plot(xx,yy,'o-',color=BLUE,markerfacecolor='white',markeredgewidth=1.2,zorder=3)
        for x,y in zip(xx,yy):a.annotate(f'{y:.2f}',(x,y),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
        if bad:
            for x in nums(bad,'reserve_fraction',100):a.plot([x],[.08],transform=a.get_xaxis_transform(),marker='x',color=RED,clip_on=False)
            a.text(.98,.14,'× 全箱交付不可行',transform=a.transAxes,ha='right',fontsize=8,color=RED)
        a.set_xlim(18,62);a.set_xticks(nums(rr,'reserve_fraction',100));a.set_xlabel('要求保留的返航电量（%）');a.set_ylabel('方案运输能耗（kWh）');vals=rr
    elif name=='08_limiting_payload_sensitivity.png':
        rr=[r for r in C('q1','capacity_sensitivity') if r['service_id']=='S008'];f,a=figure()
        for g in 'ABC':
            ar=[r for r in rr if r['model_id']==g];a.plot(nums(ar,'reserve_fraction',100),nums(ar,'max_safe_payload_kg'),marker={'A':'o','B':'s','C':'^'}[g],mfc='white',mec=MODEL[g],color=MODEL[g],label=g+'型')
        a.set(xlabel='要求保留的返航电量（%）',ylabel='连续最大安全载荷（kg）');legend(a);vals=rr
    elif name=='09_sortie_energy_frontier.png':
        rr=C('q1','flight_energy_frontier');x=nums(rr,'trips');y=nums(rr,'min_energy_kwh');mask=np.array([r['pareto_efficient_N_E']=='True' for r in rr]);focus=x<=25
        f=plt.figure(figsize=(7.8,4.25));gs=f.add_gridspec(1,2,width_ratios=(3.25,1.15),wspace=.18);a=f.add_subplot(gs[0]);overview=f.add_subplot(gs[1])
        a.plot(x[focus],y[focus],color=MUTED,lw=.9,alpha=.8,zorder=1)
        a.scatter(x[focus & ~mask],y[focus & ~mask],s=25,color='#AAB3BA',edgecolors='white',lw=.45,zorder=2)
        a.scatter([x[0]],[y[0]],s=78,color=BLUE,edgecolors='white',lw=.8,zorder=5)
        a.scatter([x[1]],[y[1]],s=78,color=GOLD,edgecolors=INK,lw=.65,zorder=5)
        a.annotate(f'18架次主方案\n{y[0]:.3f} kWh',(x[0],y[0]),xytext=(12,24),textcoords='offset points',fontsize=8,color=BLUE,arrowprops=dict(arrowstyle='-',color=BLUE,lw=.7))
        a.annotate(f'19架次节能方案\n{y[1]:.3f} kWh',(x[1],y[1]),xytext=(20,-20),textcoords='offset points',fontsize=8,color=INK,arrowprops=dict(arrowstyle='-',color=GOLD,lw=.8))
        de=y[0]-y[1];dt=float(rr[1]['operation_time_at_min_energy_s'])-float(rr[0]['operation_time_at_min_energy_s'])
        a.text(.98,.95,f'增加1架次：能耗 −{de:.3f} kWh（−{100*de/y[0]:.3f}%）\n累计作业时间 +{dt:.0f} s（+{100*dt/float(rr[0]["operation_time_at_min_energy_s"]):.2f}%）',transform=a.transAxes,ha='right',va='top',fontsize=8,color=INK)
        a.set_xlim(17.65,25.35);a.set_xticks(np.arange(18,26));a.set_ylim(min(y[focus])-.42,max(y[focus])+.48);a.set_xlabel('运输总架次数 $N$');a.set_ylabel('固定整数架次数下的最小能耗（kWh）');a.text(0,1.02,'关键区间',transform=a.transAxes,ha='left',va='bottom',fontsize=9,color=INK)
        overview.axvspan(18,25,color=BLUE,alpha=.055,lw=0);overview.plot(x,y,color=MUTED,lw=.85,alpha=.8);overview.scatter(x,y,s=9,color='#98A4AD',alpha=.75)
        overview.scatter(x[mask],y[mask],s=28,c=[BLUE,GOLD],edgecolors='white',lw=.45,zorder=4);overview.set_xlim(17,81);overview.set_xticks([20,50,80]);overview.set_ylim(min(y)-4,max(y)+5);overview.set_title('18–80架次全范围',loc='left',fontsize=9,pad=6);overview.set_xlabel('$N$');overview.tick_params(axis='y',labelleft=False);overview.grid(axis='y');overview.grid(False,axis='x')
        vals=rr;note+='；主轴显示18–25架次，右侧保留18–80架次全部整数解，不删除被支配点。';short_title=''
    elif re.match(r'q1/terrain_S\d+.png',name) or name=='12_route_terrain_profile.png':
        sid=re.search(r'S\d+',name)[0] if name.startswith('q1/') else 'S008';cells=[r for r in C('q1','route_dem_cells') if r['service_id']==sid];rt=next(r for r in C('q1','route_geometry') if r['service_id']==sid)
        x=nums(cells,'along_m',.001);z=nums(cells,'dem_m');H=float(rt['cruise_altitude_m']);f,a=figure((7.2,4.2));base=min(0,float(np.min(z)))
        a.fill_between(x,base,z,step='mid',color=TEAL,alpha=.22,lw=0);a.step(x,z,where='mid',color=TEAL,lw=1,label='穿越像元地形')
        a.plot([0,float(rt['distance_m'])/1000],[H,H],color=BLUE,lw=1.8,label='计划巡航海拔')
        j=int(np.argmax(z));a.plot(x[j],z[j],'o',mfc=GOLD,mec='white',ms=5);a.annotate('',xy=(x[j],H),xytext=(x[j],z[j]),arrowprops=dict(arrowstyle='<->',lw=.8,color=INK));a.annotate('净空50 m',(x[j],H),xytext=(8,-12),textcoords='offset points',fontsize=8)
        a.set(xlabel='去程沿线水平距离（km）',ylabel='海拔（m）',ylim=(base,H*1.20));legend(a,loc='upper left');vals={'profile':cells,'route':rt};note+='；阶梯保留像元峰值，不平滑地形。'
    elif re.match(r'q1/energy_curve_S\d+.png',name):
        sid=re.search(r'S\d+',name)[0];rr=C('closure',f'energy_curves_{sid}');f,a=figure()
        for g in 'ABC':
            ar=[r for r in rr if r['model_id']==g];a.plot(nums(ar,'payload_kg'),nums(ar,'energy_fraction_percent'),color=MODEL[g],label=g+'型',lw=1.9)
        a.axhline(80,color=RED,ls='--',lw=1,label='20%余量对应能量上限');a.set(xlabel='去程货物质量（kg）',ylabel='往返能耗 / 可用电量（%）');legend(a,loc='upper left');vals=rr
    elif re.match(r'q1/payload_[ABC].png',name):
        g=re.search('payload_([ABC])',name)[1];all_rows=C('q1','payload_continuous_discrete')
        if g=='C':
            rr=sorted([r for r in all_rows if r['service_id']=='S008'],key=lambda r:'ABC'.index(r['model_id']))
            rated=nums(rr,'rated_payload_kg');safe=nums(rr,'continuous_safe_payload_kg');boxed=nums(rr,'available_box_max_payload_kg');y=np.arange(3)
            f,a=figure((7.65,3.65));a.hlines(y,boxed,rated,color='#CAD0D5',lw=2.0,zorder=1)
            a.hlines(y,boxed,safe,color=GOLD,lw=5.5,alpha=.28,zorder=2);a.hlines(y,safe,rated,color=BLUE,lw=5.5,alpha=.18,zorder=2)
            a.scatter(rated,y,marker='|',s=230,color=MUTED,lw=2.1,label='额定载荷',zorder=4)
            a.scatter(safe,y,marker='o',s=66,facecolors='white',edgecolors=BLUE,lw=1.5,label='连续安全载荷',zorder=5)
            a.scatter(boxed,y,marker='D',s=42,color=GOLD,edgecolors='white',lw=.55,label='现有整箱可实现载荷',zorder=6)
            for j,(q0,q1,q2) in enumerate(zip(rated,safe,boxed)):
                a.annotate(f'{q1:.1f}',(q1,j),xytext=(0,-15),textcoords='offset points',ha='center',fontsize=8,color=BLUE)
                a.annotate(f'{q2:.0f}',(q2,j),xytext=(0,10),textcoords='offset points',ha='center',fontsize=8,color=INK)
            a.text((safe[2]+rated[2])/2,2-.23,'航线能量约束',ha='center',va='center',fontsize=8,color=BLUE)
            a.text((boxed[2]+safe[2])/2,2+.18,'现有库存约束',ha='center',va='center',fontsize=8,color=GOLD)
            a.set_yticks(y,[r['model_id']+'型' for r in rr]);a.set_ylim(2.48,-.42);a.set_xlim(0,86);a.set_xlabel('货物质量（kg）');a.set_ylabel('S008运输机型');a.grid(False,axis='y');a.grid(axis='x');legend(a,ncol=3,loc='lower left',bbox_to_anchor=(0,1.01))
            vals={'source_row_count':len(all_rows),'shown_row_count':len(rr),'selection_rule':'正文指定的瓶颈服务区S008，展示A/B/C三种机型','shown_rows':rr}
            note+='；从45组服务区×机型数据中选择正文明确讨论的瓶颈服务区S008三组，完整45组仍保留于表6与源数据。';short_title=''
        else:
            rr=[r for r in all_rows if r['model_id']==g];v=nums(rr,'continuous_safe_payload_kg');w=nums(rr,'available_box_max_payload_kg');f,a=figure((7.7,4.4));x=np.arange(15)
            a.vlines(x,w,v,color=MODEL[g],alpha=.42,lw=4);a.scatter(x,v,marker='o',s=43,fc='white',ec=MODEL[g],lw=1.3,label='连续安全上限',zorder=4);a.scatter(x,w,marker='D',s=23,color=MODEL[g],label='现有整箱可实现值',zorder=5)
            a.axhline(MODELS[g]['max_payload_kg'],color=MUTED,ls=':',lw=.8,label='额定载质量上限');a.set_xticks(x,SERVICES,rotation=45,ha='right');a.set_ylabel('货物质量（kg）');a.set_ylim(0,MODELS[g]['max_payload_kg']*1.22);legend(a,ncol=3,loc='upper left');vals=rr
    elif name=='q1/energy_assumptions.png':
        rr=C('q1','energy_assumption_sensitivity');labs=[f'水平×{float(r["horizontal_multiplier"]):.1f} / 爬升×{float(r["climb_multiplier"]):.1f}' for r in rr];f,a=dotbars(labs,nums(rr,'energy_kwh'),'重新优化后的总运输能耗（kWh）',horizontal=True,fmt='{:.3f}');vals=rr
    elif 'gantt.png' in name:
        ready=None
        if name.startswith('q4/'):
            k=re.search('K([23])',name)[1];slug=re.search('K[23]_(.+)_gantt',name)[1];key={'drones':('transport_A','transport_B','transport_C'),'batteries':('battery_A','battery_B','battery_C'),'relay':('relay_drone',),'modules':('relay_energy',)}[slug]
            rr=[r for r in C('q4',f'K{k}/resource_allocations') if r['resource_type'] in key];idf='local_resource_id';s='start_s';e='return_s';ready='ready_s'
        elif name in ('q3/relay_body_gantt.png','q3/relay_energy_gantt.png'):
            rr=C('q3','relay_sorties');body='body' in name;idf='relay_drone_id' if body else 'energy_module_id';s='start_s';e='return_s';ready='turnaround_end_s' if body else 'charge_end_s'
        else:
            q='q3' if name.startswith('q3') else 'q2';battery='battery' in name;rr=C(q,'battery_cycles' if battery else 'trips');idf='battery_id' if battery else 'drone_id';s='task_start_s' if battery else 'start_s';e='return_s';ready='charge_end_s' if battery else None
        f,a,vals=gantt(rr,idf,s,e,ready)
    elif name.endswith('04_hard_deadlines.png'):
        q='q3' if name.startswith('q3') else 'q2';rr=sorted([r for r in C(q,'box_deliveries') if r['hard_deadline_s']],key=lambda r:(float(r['hard_deadline_s']),r['box_id']));f,a=figure((8.2,4.4));x=np.arange(len(rr));d=nums(rr,'hard_deadline_s',1/60);t=nums(rr,'delivery_complete_s',1/60)
        a.vlines(x,t,d,color=TEAL,alpha=.40,lw=1.4);a.scatter(x,d,s=18,marker='_',color=RED,label='硬截止时刻',zorder=3);a.scatter(x,t,s=17,color=BLUE,ec='white',lw=.3,label='交接完成',zorder=4)
        a.set(xlabel='按硬截止排序的货箱序号',ylabel='相对时刻（min）');a.set_xticks(np.arange(0,len(rr),5),np.arange(1,len(rr)+1,5));legend(a,ncol=2);vals=rr;note+='；逐箱排序与完整箱号见本图数据文件。'
    elif name.endswith('06_tradeoff.png') or name=='closure/candidate_compatibility.png':
        q='q3' if name.startswith('q3') or name.startswith('closure') else 'q2';rr=C(q,'closure_existing_candidates' if name.startswith('closure') else 'scenario_comparison');f,a,vals=tradeoff(rr,q,name.startswith('closure'))
    elif name.endswith('08_delivery_progress.png'):
        q='q3' if name.startswith('q3') else 'q2';rr=C(q,'box_deliveries');xx=np.sort(nums(rr,'delivery_complete_s',1/60));f,a=figure();a.step(np.r_[0,xx],np.arange(len(xx)+1),where='post',color=BLUE,lw=1.8);a.fill_between(np.r_[0,xx],np.arange(len(xx)+1),step='post',alpha=.09,color=BLUE);a.set(xlabel='交接完成时刻（min）',ylabel='累计交付箱数',ylim=(0,84));a.annotate('80箱全部交付',(xx[-1],80),xytext=(-5,-18),textcoords='offset points',ha='right',fontsize=8);vals=rr
    elif name in ('q2/box_slack.png','q3/box_slack.png'):
        q=name[:2];rr=[r for r in C(q,'box_deliveries') if r['hard_deadline_s']];yy=[min(float(r['hard_deadline_s'])-float(r['delivery_complete_s']) for r in rr if r['service_id']==sid) for sid in SERVICES];f,a=dotbars(SERVICES,yy,'最紧硬时限裕度（s）',cs=[RED if v==min(yy) else BLUE for v in yy],fmt='{:.1f}');vals={'services':SERVICES,'minimum_hard_slack_s':yy}
    elif name in ('q2/load_usage.png','q3/load_usage.png'):
        rr=C(name[:2],'trips');labs=[r['trip_id'].split('-')[-1] for r in rr];yy=[100*float(r['weight_kg'])/MODELS[r['model_id']]['max_payload_kg'] for r in rr];vv=[100*float(r['volume_m3'])/MODELS[r['model_id']]['volume_m3'] for r in rr];f,a=grouped(labs,[('质量利用率',yy),('体积利用率',vv)],'额定容量利用率（%）');a.axhline(100,color=RED,ls='--',lw=.7);vals={'trip_ids':[r['trip_id'] for r in rr],'weight_percent':yy,'volume_percent':vv}
    elif name in ('q2/model_workload.png','q3/model_workload.png'):
        rr=C(name[:2],'trips');yy=[sum(float(r['operation_time_s']) for r in rr if r['model_id']==g)/60 for g in 'ABC'];zz=[sum(float(r['flight_time_s']) for r in rr if r['model_id']==g)/60 for g in 'ABC'];f,a=grouped([g+'型' for g in 'ABC'],[('完整作业',yy),('纯飞行',zz)],'累计时间（min）');vals={'model_ids':list('ABC'),'operation_min':yy,'flight_min':zz}
    elif name=='q2_05_convergence.png':
        f,a=figure();vals={}
        for fam,col in [('multipoint',TEAL),('direct_only',BLUE)]:
            rr=[r for r in C('q2',fam+'_search_rounds') if r['round_kind']=='sequential_refinement'];yy=nums(rr,'makespan_s',1/60);a.plot(range(1,len(rr)+1),yy,'o-',color=col,mfc='white',label=NAMES[fam]);vals[fam]=rr
        a.set(xlabel='顺序改进轮次',ylabel='当轮最优运输完工时间（min）');a.xaxis.set_major_locator(ticker.MaxNLocator(integer=True));legend(a)
    elif name.startswith('q3/relay_profile_'):
        tid=name.rsplit('/',1)[-1].replace('relay_profile_','').replace('.png','');r=next(x for x in C('q3','relay_sorties') if x['relay_trip_id']==tid);m=INPUT['relay_models'][0];z0=INPUT['depots'][0]['ground_elevation_m'];cr=float(r['cruise_altitude_m']);zh=float(r['hover_altitude_m']);t0=float(r['start_s']);take=t0+m['prepare_s'];t1=take+float(r['outbound_climb_m'])/m['climb_speed_mps'];t2=t1+float(r['horizontal_distance_m'])/m['cruise_speed_mps'];ar=float(r['arrival_s']);lk=float(r['link_complete_s']);en=float(r['service_end_s']);u=en+float(r['inbound_climb_m'])/m['climb_speed_mps'];v=u+float(r['horizontal_distance_m'])/m['cruise_speed_mps'];ret=float(r['return_s'])
        x=np.array([t0,take,t1,t2,ar,lk,en,u,v,ret])/60;y=[z0,z0,cr,cr,zh,zh,zh,cr,cr,z0];f,a=figure();a.plot(x,y,color=BLUE,lw=1.8);a.axvspan(lk/60,en/60,color=TEAL,alpha=.14,label='有效通信服务时段');a.plot([lk/60,en/60],[zh,zh],color=TEAL,lw=3);a.set(xlabel='相对时刻（min）',ylabel='飞行海拔（m）');legend(a);vals={'times_min':x,'altitude_m':y,'relay':r}
    elif name.startswith('q3/transport_profile_'):
        tid=name.rsplit('/',1)[-1].replace('transport_profile_','').replace('.png','');rr=[r for r in C('q3','trajectory_phases') if r['trip_id']==tid];f,a=figure();seen=set()
        for r in rr:
            phase=r['phase'];x=[float(r['start_s'])/60,float(r['end_s'])/60];y=[float(r['p0_altitude_m']),float(r['p1_altitude_m'])];a.plot(x,y,color=PHASE.get(phase,PURPLE),lw=2,label=phase if phase not in seen else None);seen.add(phase)
        a.set(xlabel='相对时刻（min）',ylabel='飞行与作业海拔（m）');legend(a,ncol=4,loc='upper left',bbox_to_anchor=(0,1.13));vals=rr
    elif name=='q3/communication_timeline.png':
        rr=C('q3','communication_atoms');tr=C('q3','trips');tids=[r['trip_id'] for r in tr];f,a=figure((8.2,7.1));vals=[]
        for j,tid in enumerate(tids):
            if j%2==0:a.axhspan(j-.42,j+.42,color='#F4F6F7',zorder=0)
            for mode,col in [('直连',BLUE),('中继',GOLD)]:
                ar=[(float(r['start_s'])/60,(float(r['end_s'])-float(r['start_s']))/60) for r in rr if r['trip_id']==tid and r['mode']==mode and float(r['end_s'])>float(r['start_s'])]
                if ar:a.broken_barh(ar,(j-.30,.60),facecolors=col,edgecolors='none',zorder=3)
                vals.append({'trip_id':tid,'mode':mode,'start_duration_min':ar})
        a.set_yticks(range(len(tids)),[x.replace('Q3-T-','') for x in tids]);a.set(xlabel='任务相对时刻（min）',ylabel='运输架次编号',ylim=(len(tids)-.5,-.5));a.grid(False,axis='y');a.grid(axis='x');a.tick_params(axis='y',length=0);a.legend(handles=[Patch(fc=BLUE,label='G01直连'),Patch(fc=GOLD,label='中继保障')],ncol=2,loc='upper left',bbox_to_anchor=(0,1.06))
    elif name=='q3/communication_duration.png':
        rr=C('q3','communication_atoms');yy=[sum(float(r['end_s'])-float(r['start_s']) for r in rr if r['mode']==m)/60 for m in ('直连','中继')];f,a=dotbars(['G01直连','中继保障'],yy,'累计通信保障时间（min）',cs=[BLUE,GOLD],fmt='{:.2f}');vals={'modes':['直连','中继'],'minutes':yy}
    elif name=='q3/link_margin_distribution.png':
        rr=[r for r in C('q3','communication_atoms') if r['selected_margin_mid_db'] and float(r['end_s'])>float(r['start_s'])];vv=nums(rr,'selected_margin_mid_db');f,a=figure();n,bins,_=a.hist(vv,bins=30,color=TEAL,alpha=.72,ec='white',lw=.5);a.set(xlabel='区间中点所选链路裕量（dB）',ylabel='正长度区间数量');vals={'midpoint_margins_db':vv,'histogram_count':n,'bin_edges_db':bins}
    elif name in ('q3/propagation_loss.png','q3/relay_delay.png','q3/common_delay.png'):
        specs={'propagation_loss':('propagation_loss_sensitivity','extra_loss_db','outage_duration_sum_s','额外传播损耗（dB）','通信中断累计时间（s）'),'relay_delay':('relay_only_delay_sensitivity','relay_only_shift_s','fixed_assignment_uncovered_duration_s','仅中继延迟（s）','未覆盖区间累计时间（s）'),'common_delay':('common_start_delay_sensitivity','common_delay_s','min_hard_slack_s','共同延迟（s）','最紧硬时限裕度（s）')}
        file,x,y,xl,yl=specs[name.rsplit('/',1)[-1].replace('.png','')];rr=C('q3',file);f,a=figure();a.plot(nums(rr,x),nums(rr,y),'o-',color=BLUE,mfc='white');a.axhline(0,ls='--',lw=.85,color=RED);a.set(xlabel=xl,ylabel=yl);vals=rr
    elif name=='q3/relay_energy_components.png':
        rr=C('q3','relay_sorties');f,a=grouped([r['relay_trip_id'].replace('Q3-','') for r in rr],[(lab,nums(rr,k)) for k,lab in [('flight_energy_kwh','往返飞行'),('setup_energy_kwh','建链悬停'),('service_energy_kwh','通信服务')]],'能耗（kWh）');vals=rr
    elif name=='q4/atomic_workload.png':
        rr=C('q4','atomic_components');yy=nums(rr,'transport_workload_share',100);f,a=dotbars([r['component_id'] for r in rr],yy,'占全部运输累计作业时间（%）',cs=COLORS[:len(rr)],fmt='{:.2f}%');vals=rr
    elif re.match(r'q4/K[23]_(workload|boxes|sorties|inventory|gap).png',name):
        k,slug=re.search(r'K([23])_(\w+).png',name).groups()
        if slug in ('inventory','gap'):
            rr=[r for r in C('q4','inventory_gap') if r['K']==k];labs=[short(r['resource_name']) for r in rr]
            if slug=='gap':f,a=dotbars(labs,nums(rr,'shortage'),'需要增补的分类型件数',horizontal=True,cs=[RED if float(r['shortage'])>0 else MUTED for r in rr])
            else:
                f,a=figure((7.4,4.9));i=np.arange(len(rr));inv=nums(rr,'inventory');req=nums(rr,'required');a.hlines(i,inv,req,color=MUTED,lw=1.5,alpha=.5);a.scatter(inv,i,s=40,fc='white',ec=BLUE,lw=1.3,label='现有库存',zorder=3);a.scatter(req,i,s=35,c=[RED if r>v else TEAL for r,v in zip(req,inv)],marker='D',label='独立配置需求',zorder=4)
                for j,(r,v) in enumerate(zip(req,inv)):
                    if r>v:a.annotate(f'缺{r-v:.0f}',(r,j),xytext=(7,0),textcoords='offset points',va='center',fontsize=8,color=RED)
                a.set_yticks(i,labs);a.set_ylim(len(rr)-.5,-.5);a.set_xlabel('资源数量（架或组）');a.set_xlim(0,max(inv.max(),req.max())+1.5);a.grid(False,axis='y');a.grid(axis='x');a.xaxis.set_major_locator(ticker.MaxNLocator(integer=True));legend(a,loc='upper right')
        else:
            rr=C('q4',f'K{k}/groups');key,yl={'workload':('transport_workload_s','运输累计作业时间（min）'),'boxes':('boxes','货箱数量（箱）'),'sorties':('transport_trips','运输架次数')}[slug];yy=nums(rr,key,1/60 if key.endswith('_s') else 1);f,a=dotbars([r['group_id'] for r in rr],yy,yl,cs=COLORS[:len(rr)])
        vals=rr
    elif name=='q4/all_partitions.png':
        rr=C('q4','all_partitions');f,a=figure();vals=rr
        for j,r in enumerate(rr):
            x=float(r['transport_workload_cv']);y=float(r['resource_units']);col=BLUE if r['K']=='2' else GOLD;chosen=r['selected_main']=='True';a.scatter(x,y,s=100 if chosen else 50,marker='*' if chosen else 'o',color=col,zorder=3);a.annotate(r['partition_id']+f'；缺口{r["shortage_units"]}件',(x,y),xytext=(6,9),textcoords='offset points',fontsize=8)
        a.margins(x=.3,y=.30);a.set(xlabel='组间运输工作量变异系数',ylabel='独立资源配置总件数');a.yaxis.set_major_locator(ticker.MaxNLocator(integer=True));a.legend(handles=[Line2D([0],[0],marker='o',ls='',color=BLUE,label='两组'),Line2D([0],[0],marker='o',ls='',color=GOLD,label='三组'),Line2D([0],[0],marker='*',ls='',color=MUTED,label='主方案')],ncol=3,loc='upper left')
    elif name.startswith('closure/'):
        specs={'energy_soc':('fixed_energy_sweep','energy_multiplier','minimum_soc_fraction','运输能耗倍率','最低返航电量（%）',100,.2),
            'energy_violations':('fixed_energy_sweep','energy_multiplier','reserve_violating_sorties','运输能耗倍率','返航余量违约架次数',1,0),
            'energy_charge_conflicts':('fixed_energy_sweep','energy_multiplier','battery_reuse_conflicts','运输能耗倍率','电池复用冲突数',1,0),
            'charge_slack':('fixed_charging_sweep','full_charge_time_multiplier','minimum_reuse_slack_s','充电时间倍率','最紧电池复用裕度（s）',1,0),
            'charge_conflicts':('fixed_charging_sweep','full_charge_time_multiplier','conflicting_transitions','充电时间倍率','电池复用冲突数',1,0),
            'delay_slack':('common_delay_fine_sweep','common_delay_s','minimum_hard_slack_s','全部资源共同延迟（s）','最紧硬时限裕度（s）',1,0),
            'delay_violations':('common_delay_fine_sweep','common_delay_s','hard_late_boxes','全部资源共同延迟（s）','硬时限违约箱数',1,0),
            'expected_delay':('common_delay_fine_sweep','common_delay_s','expected_late_boxes','全部资源共同延迟（s）','期望时间逾期箱数',1,0)}
        file,x,y,xl,yl,fac,baseline=specs[name.rsplit('/',1)[-1].replace('.png','')];rr=C('closure',file);f,a=figure()
        for q,col in QUESTION.items():
            ar=[r for r in rr if r['question']==q];a.plot(nums(ar,x),nums(ar,y,fac),color=col,marker='o' if len(ar)<30 else None,mfc='white',label=q)
        a.axhline(baseline*fac,color=RED,ls='--',lw=.85,label='约束边界');a.set(xlabel=xl,ylabel=yl);legend(a);vals=rr
    else:raise ValueError(f'尚未实现图: {name}')
    if f is None:raise AssertionError(name)
    # 数据源与绘图值由本轮读取记录，不复制旧图中的像素。
    pub.save(f,code,title,S,vals,note,short_title=short_title)

def make_originals(pub,selection=None):
    rows=S.csv('paper/figure_catalog.csv')
    for r in rows:
        if selection and r['图号'] not in selection:continue
        redraw_one(r,pub)
