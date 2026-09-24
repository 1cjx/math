"""原生补充诊断图：确定性模型曲面、真实横截面分布、真实候选和任务状态。
每个统计图单独绘制；compose.py 将独立矢量页组合为论文多面板图。
不随机制造样本；不把等效航程当安全往返半径。
"""
import sys,math
from collections import defaultdict
import numpy as np
from scipy.stats import gaussian_kde
from matplotlib import pyplot as plt,colors,cm,ticker,patheffects
from matplotlib.lines import Line2D
from .core import ROOT,EXP,write_json,csvwrite
from .redraw import S,C,nums,INPUT,MODELS,NODES,SERVICES,heatmap,plot_map
from .style import *

sys.path.insert(0,str(EXP/'src'))
from physics import trip_energy,effective_range
from config import CFG

# 纯绘图参数集中定义；不是新增机型参数或优化约束。
GRID_NQ=81; GRID_NH=61; EXTRA_ALTITUDE_M=500.0
RESERVE_LEVELS=(.20,.25,.30,.35)
KDE_BANDWIDTH='scott'; KDE_POINTS=301
STATE_TRIP='Q3-T-016'

def store(pub,code,title,f,values,note):
    if code in ('F160','F161','F162','F163'):f._shared_state_frame=True
    pub.save(f,code,title,S,values,note)

def make_extras(pub):
    # F148-F150: 固定实际S008距离和作业端点，扫描C型载荷与巡航海拔。
    # 巡航海拔仅为条件扰动，不把这些组合称为题目标准排程或现场试验。
    S.start(['data/cleaned/model_inputs.json','src/physics.py','src/config.py'])
    route0=next(r for r in C('q1','route_geometry') if r['service_id']=='S008')
    route={k:(v if k=='service_id' else float(v)) for k,v in route0.items()}
    g=MODELS['C'];q=np.linspace(0,g['max_payload_kg'],GRID_NQ);hh=np.linspace(route['cruise_altitude_m'],route['cruise_altitude_m']+EXTRA_ALTITUDE_M,GRID_NH)
    Q,H=np.meshgrid(q,hh);E=np.zeros_like(Q)
    for i,h in enumerate(hh):
        rt=dict(route,outbound_climb_m=h-route['depot_work_altitude_m'],inbound_climb_m=h-route['service_work_altitude_m'])
        for j,v in enumerate(q):E[i,j]=trip_energy(g,rt,float(v))['energy_kwh']
    budget=(1-g['reserve_fraction'])*g['usable_energy_kwh']
    actual_load=sum(float(r['weight_kg']) for r in S.csv('data/cleaned/boxes.csv') if r['service_id']=='S008')
    point_e=trip_energy(g,route,actual_load)['energy_kwh']
    values={'route':route,'model':'C','payload_grid_kg':q,'cruise_altitude_grid_m':hh,'energy_grid_kwh':E,'energy_budget_kwh':budget,
            'actual_S008_point':{'payload_kg':actual_load,'cruise_altitude_m':hh[0],'energy_kwh':point_e},'kind':'deterministic_parameter_sweep_not_field_observations'}
    note='固定S008的真实距离与两端作业高度；载荷和巡航海拔为确定性模型扫参，非新增现场试验或正式排程。只基准海拔对应题定巡航规则。'
    f,a=figure((7.6,5.25),projection='3d')
    surface=a.plot_surface(Q,H,E,cmap=ENERGY,linewidth=0,antialiased=True,rcount=GRID_NH,ccount=GRID_NQ,alpha=.93)
    a.contour(Q,H,E,levels=[budget],colors=[RED],offset=float(E.min())-.3,zdir='z',linewidths=1.3)
    a.computed_zorder=False
    a.scatter([actual_load],[hh[0]],[point_e],c=RED,marker='o',s=32,depthshade=False,edgecolors='white',zorder=20)
    a.set(xlabel='货物载荷（kg）',ylabel='巡航海拔（m）',zlabel='往返能耗（kWh）')
    a.view_init(elev=27,azim=-128);a.set_box_aspect((1.2,1,.72));a.set_zlim(float(E.min())-.3,float(E.max()))
    for axis in (a.xaxis,a.yaxis,a.zaxis):axis.pane.fill=False;axis._axinfo['grid']['color']=(.86,.89,.91,.65)
    cb=f.colorbar(surface,ax=a,shrink=.61,pad=.04,aspect=22);cb.set_label('往返能耗（kWh）');cb.outline.set_visible(False)
    store(pub,'F148','C型载荷—巡航海拔能耗响应（模型扫参）',f,values,note)
    f,a=figure((7,4.6));im=a.contourf(Q,H,E,levels=18,cmap=ENERGY);cs=a.contour(Q,H,E,levels=[budget],colors=[RED],linewidths=1.5);a.clabel(cs,fmt={budget:f'20%余量边界：{budget:.1f} kWh'},fontsize=8)
    a.scatter(actual_load,hh[0],c=INK,s=35,edgecolors='white',zorder=5);a.set(xlabel='C型货物载荷（kg）',ylabel='巡航海拔（m）');f.colorbar(im,ax=a,pad=.02,label='往返能耗（kWh）').outline.set_visible(False)
    store(pub,'F149','同一能耗曲面的可行域投影',f,values,note+'；红线由同一网格方程确定，不人为绘制。')
    f,a=figure();cuts=[]
    for i,col in [(0,BLUE),(GRID_NH//2,TEAL),(GRID_NH-1,GOLD)]:
        a.plot(q,E[i],color=col,label=f'巡航海拔 {hh[i]:.0f} m');cuts.append({'cruise_altitude_m':hh[i],'payload_kg':q,'energy_kwh':E[i]})
    a.axhline(budget,color=RED,ls='--',lw=1,label='任务能量上限');a.set(xlabel='C型货物载荷（kg）',ylabel='往返能耗（kWh）');legend(a,loc='upper left')
    store(pub,'F150','巡航海拔改变时的载荷—能耗截面',f,cuts,note)
    # 横截面分布：每一档恰好15个服务区；确定性重复值保留，不扩充样本。
    S.start();rr=[r for r in C('q1','capacity_sensitivity') if r['model_id']=='C' and any(abs(float(r['reserve_fraction'])-v)<1e-12 for v in RESERVE_LEVELS)]
    datasets=[nums([r for r in rr if abs(float(r['reserve_fraction'])-rho)<1e-12],'max_safe_payload_kg') for rho in RESERVE_LEVELS]
    assert all(len(v)==15 and np.isfinite(v).all() for v in datasets)
    f,a=figure((7.4,4.7));stats=[];curves=[]
    for j,(rho,v,col) in enumerate(zip(RESERVE_LEVELS,datasets,COLORS)):
        y=np.linspace(v.min(),v.max(),KDE_POINTS)
        density=gaussian_kde(v,bw_method=KDE_BANDWIDTH)(y) if np.ptp(v)>1e-10 else np.ones_like(y)
        # KDE只用于轮廓，限制在样本最小/最大值；所有真实点及分位点同时叠加。
        width=.29*density/density.max();a.fill_betweenx(y,j-width,j+width,color=col,alpha=.20,lw=0);a.plot(j-width,y,color=col,lw=.7);a.plot(j+width,y,color=col,lw=.7)
        sorted_v=np.sort(v);ux,counts=np.unique(sorted_v,return_counts=True);px=[];py=[]
        for val,n in zip(ux,counts):
            off=np.linspace(-.18,.18,n) if n>1 else [0]
            px.extend(j+np.array(off));py.extend([val]*n)
        a.scatter(px,py,s=13,color=col,alpha=.9,lw=.3,edgecolors='white',zorder=4)
        q1,med,q3=np.quantile(v,[.25,.5,.75]);a.vlines(j,q1,q3,color=INK,lw=3.2,zorder=5);a.scatter(j,med,s=25,c='white',ec=INK,lw=.6,zorder=6)
        stats.append({'reserve_percent':rho*100,'n_services':15,'min':v.min(),'q1':q1,'median':med,'q3':q3,'max':v.max()});curves.append({'reserve_percent':rho*100,'grid_kg':y,'density':density})
        a.text(j,84,f'中位数 {med:.1f}',ha='center',fontsize=8,color=col)
    a.set_xticks(range(4),[f'{v*100:.0f}%' for v in RESERVE_LEVELS]);a.set(xlabel='要求保留的返航电量',ylabel='C型连续最大安全载荷（kg）',ylim=(0,90));a.grid(axis='y');a.text(.99,.03,'每档15个服务区；点为真实计算值',transform=a.transAxes,ha='right',fontsize=7.8,color=MUTED)
    store(pub,'F151','返航余量下的跨服务区载荷分布',f,{'records':rr,'statistics':stats,'kde':curves},'跨服务区确定性横截面，不是15次独立随机试验。Scott带宽KDE仅为轮廓，裁在实际极值；散点等距横向避让不改变载荷。')
    matrix=np.array([[float(next(r for r in rr if r['service_id']==sid and abs(float(r['reserve_fraction'])-rho)<1e-12)['max_safe_payload_kg']) for rho in RESERVE_LEVELS] for sid in SERVICES])
    assert np.all(np.diff(matrix,axis=1)<=1e-7)
    f,a=heatmap(SERVICES,[f'{x*100:.0f}%' for x in RESERVE_LEVELS],matrix,'C型连续安全载荷（kg）',fmt='{:.1f}',vmin=0,vmax=80);a.set_xlabel('要求保留的返航电量')
    store(pub,'F152','15个服务区的安全载荷敏感性',f,{'services':SERVICES,'reserve_levels':RESERVE_LEVELS,'capacity_kg':matrix},'每个色块为一次已完成能力计算；不对离散服务区做二维平滑插值。')
    f,a=figure()
    for rho,v,col in zip(RESERVE_LEVELS,datasets,COLORS):
        sv=np.sort(v);a.step(np.r_[sv[0],sv],np.r_[0,np.arange(1,16)/15],where='post',color=col,label=f'{rho*100:.0f}%余量')
    a.set(xlabel='C型连续最大安全载荷（kg）',ylabel='服务区累计比例',ylim=(0,1.05));a.yaxis.set_major_formatter(ticker.PercentFormatter(1));legend(a,loc='upper left')
    store(pub,'F153','安全载荷的经验累计分布',f,{'reserve_levels':RESERVE_LEVELS,'samples':datasets},'经验分布仅对应15个给定服务区；没有概率外推，不生成随机样本。')
    S.start(['data/cleaned/model_inputs.json','src/physics.py','src/config.py']);f,a=figure();curves=[]
    for g,m in MODELS.items():
        q=np.linspace(0,m['max_payload_kg'],161);L=np.array([effective_range(m,float(x))/1000 for x in q]);a.plot(q,L,color=MODEL[g],label=g+'型',lw=1.9);a.plot(q[-1],L[-1],marker='o',c=MODEL[g],mfc='white');curves.append({'model':g,'payload_kg':q,'effective_range_km':L})
    a.set(xlabel='有效货物载荷（kg）',ylabel='等效水平航程（km）');legend(a);a.text(.02,.03,'等效航程 ≠ 含爬升与空返约束的服务半径',transform=a.transAxes,fontsize=7.8,color=MUTED)
    store(pub,'F154','异构机型载荷—等效航程关系',f,curves,'由源题载荷指数关系计算；不是模型非支配前沿，也不是最大安全往返距离。')
    # 空间需求：使用实际15个离散节点，禁止虚构行政区面和无观测的连续热区。
    S.start();boxes=S.csv('data/cleaned/boxes.csv');f,a,vals=plot_map();weights=np.array([sum(float(r['weight_kg']) for r in boxes if r['service_id']==sid) for sid in SERVICES]);deadline=np.array([min(float(r['expected_s']) for r in boxes if r['service_id']==sid)/60 for sid in SERVICES])
    xs=[NODES[s]['lon_deg'] for s in SERVICES];ys=[NODES[s]['lat_deg'] for s in SERVICES]
    for text in list(a.texts):
        if text.get_text() in SERVICES:text.remove()
    points=a.scatter(xs,ys,s=weights*2.7,c=deadline,cmap=ENERGY.reversed(),ec='white',lw=.8,zorder=6)
    # 覆盖原点标签的符号后，仍保留白边标识，全部标签使用原坐标。
    for sid,x,y,w in zip(SERVICES,xs,ys,weights):
        t=a.annotate(f'{sid} · {w:.0f} kg',(x,y),xytext=(5,6),textcoords='offset points',fontsize=7.3,zorder=8);t.set_path_effects([patheffects.withStroke(linewidth=2,foreground='white')])
    a.set_title('')
    # 复用DEM色条；需求时限用离散图例，避免第二色条挤占。
    pvals=sorted(set(deadline));norm=plt.Normalize(deadline.min(),deadline.max() if deadline.max()>deadline.min() else deadline.min()+1)
    handles=[Line2D([0],[0],marker='o',ls='',c=ENERGY.reversed()(norm(v)),label=f'最早期望 {v:.0f} min',markersize=7) for v in pvals]
    a.legend(handles=handles,loc='upper right',fontsize=7.1,title='颜色：时间要求；面积：货重',title_fontsize=7.2)
    vals.update({'service_id':SERVICES,'weight_kg':weights,'earliest_expected_min':deadline,'marker_area_points2':weights*2.7})
    store(pub,'F155','实际需求的空间位置与时间要求',f,vals,'只绘制真实服务节点；符号面积正比货重、颜色代表本区最早期望时间。DEM为原高程，不建立无数据支持的连续需求热力场。')
    S.start();boxes=S.csv('data/cleaned/boxes.csv');f,a=figure();values=[]
    for mat,col in MATERIAL.items():
        rr=sorted([r for r in boxes if r['material_type']==mat],key=lambda r:float(r['expected_s']));xx=np.array([float(r['expected_s'])/60 for r in rr]);yy=np.cumsum([float(r['weight_kg']) for r in rr]);a.step(np.r_[0,xx],np.r_[0,yy],where='post',color=col,label=mat);values.append({'material':mat,'expected_time_min':xx,'cumulative_weight_kg':yy})
    a.set(xlabel='货箱期望送达时间（min）',ylabel='截至该期望时刻的累计需求（kg）');legend(a,loc='upper left')
    store(pub,'F156','按期望送达时刻累计的物资需求',f,values,'需求累计曲线，不是实际交付曲线、需求到达过程或一天24小时预测。')
    matrix=np.array([[sum(float(r['weight_kg']) for r in boxes if r['service_id']==sid and r['material_type']==mat) for mat in MATERIAL] for sid in SERVICES])
    f,a=heatmap(SERVICES,list(MATERIAL),matrix,'需求货物质量（kg）',fmt='{:.0f}',vmin=0);a.set_xticklabels(['医疗物资','饮用水','应急食品','生活卫生'])
    store(pub,'F157','服务区—物资类别的真实需求矩阵',f,{'service_ids':SERVICES,'materials':list(MATERIAL),'weight_kg':matrix},'质量由80箱逐箱汇总，总质量758 kg。空类别为真实0，不是缺失插值。')
    # 只有五个Q3已算候选，显示五个原始点；重合坐标保留记录。
    S.start();rr=C('q3','closure_existing_candidates');f,a=figure((7.3,5.0),projection='3d');xx=nums(rr,'total_energy_kwh');yy=nums(rr,'joint_makespan_s',1/60);zz=nums(rr,'transport_sorties')+nums(rr,'relay_sorties')
    coincident={}
    for i,r in enumerate(rr):
        key=(xx[i],yy[i],zz[i]);coincident.setdefault(key,[]).append(i)
    for (x,y,z),ii in coincident.items():
        r=rr[ii[0]];valid=r['strict_K3_feasible']=='True';col=TEAL if valid else MUTED;mk='*' if r['candidate']=='polish_1' else ('o' if valid else 'x')
        a.scatter(x,y,z,marker=mk,c=RED if mk=='*' else col,s=90 if mk=='*' else 40,depthshade=False)
        a.text(x,y,z+.25,'/'.join(str(i+1) for i in ii),fontsize=8)
    a.set(xlabel='总能耗（kWh）',ylabel='联合完工（min）',zlabel='两类总架次数');a.view_init(22,-58);a.set_box_aspect((1,1,.7));a.zaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    for axis in (a.xaxis,a.yaxis,a.zaxis):axis.pane.fill=False;axis._axinfo['grid']['color']=(.87,.89,.91,.65)
    store(pub,'F158','五个已计算Q3候选的三指标位置',f,{'records':rr,'index':[1,2,3,4,5],'energy_kwh':xx,'makespan_min':yy,'sorties_total':zz},'恰好5个已计算候选；编号对应绘图数据行；部分点同坐标重合。不是全局帕累托前沿，不补造迭代点云。')
    S.start();rr=C('q2','multipoint_search_rounds');f,a=figure();seq=[r for r in rr if r['round_kind']=='sequential_refinement'];warm=[r for r in rr if r['round_kind']!='sequential_refinement']
    a.scatter(nums(warm,'energy_kwh'),nums(warm,'makespan_s',1/60),marker='x',c=MUTED,s=32,label='独立初始化')
    col=a.scatter(nums(seq,'energy_kwh'),nums(seq,'makespan_s',1/60),c=np.arange(1,len(seq)+1),cmap=ENERGY,s=48,ec='white',lw=.6,label='顺序改进',zorder=4)
    a.plot(nums(seq,'energy_kwh'),nums(seq,'makespan_s',1/60),color=MUTED,ls=':',lw=.8,zorder=2);f.colorbar(col,ax=a,pad=.02,label='记录的顺序改进轮次').outline.set_visible(False);a.set(xlabel='运输能耗（kWh）',ylabel='当轮最优完工时间（min）');legend(a)
    store(pub,'F159','实际搜索日志中的时间—能耗轨迹',f,{'warmup':warm,'sequential_refinement':seq},'仅展示日志已保存的各轮结果，不是每个候选移动的点云；折线只连接记录先后，不代表连续可行前沿。')
    make_states(pub)

def make_states(pub):
    S.start(['data/cleaned/model_inputs.json'])
    trip=next(r for r in C('q3','trips') if r['trip_id']==STATE_TRIP);cy=next(r for r in C('q3','battery_cycles') if r['trip_id']==STATE_TRIP)
    phases=[r for r in C('q3','trajectory_phases') if r['trip_id']==STATE_TRIP];legs=[r for r in C('q3','legs') if r['trip_id']==STATE_TRIP];atoms=[r for r in C('q3','communication_atoms') if r['trip_id']==STATE_TRIP]
    lm={r['leg_index']:r for r in legs};m=MODELS[trip['model_id']];E=m['usable_energy_kwh'];e=0.;time=[float(trip['start_s'])];soc=[100.];heights=[];loads=[];phase_energy=[]
    for p in phases:
        l=lm[p['leg_index']];t0=float(p['start_s']);t1=float(p['end_s']);phase=p['phase'];de=float(l['climb_energy_kwh']) if phase=='爬升' else float(l['horizontal_energy_kwh']) if phase=='巡航' else 0.
        time.extend([t0,t1]);soc.extend([100*(1-e/E),100*(1-(e+de)/E)]);e+=de
        heights.append({'phase':phase,'start_s':t0,'end_s':t1,'altitude0_m':float(p['p0_altitude_m']),'altitude1_m':float(p['p1_altitude_m'])})
        loads.append({'start_s':t0,'end_s':t1,'payload_kg':float(l['remaining_payload_at_departure_kg'])})
        phase_energy.append({'phase_id':p['phase_id'],'phase':phase,'energy_kwh':de})
    assert abs(e-float(trip['energy_kwh']))<1e-9
    assert abs(soc[-1]/100-float(trip['return_soc_fraction']))<1e-10
    full=float(next(r for r in S.csv('data/cleaned/transport_batteries.csv') if r['model_id']==trip['model_id'])['full_charge_s']);sret=float(cy['return_soc_fraction']);tr=float(cy['return_s']);t90=tr+max(0,.9-sret)/.9*.65*full;tc=float(cy['charge_end_s'])
    assert abs(tc-(t90+.35*full))<1e-6 if sret<.9 else True
    # 截止当前电池充满：超过运输任务本身，不将其算入Q3联合完工。
    horizon=(float(trip['start_s'])/60,tc/60);source_values={'trip':trip,'battery_cycle':cy,'phase_energy':phase_energy,'time_s':time,'soc_percent':soc,'charge_t90_s':t90,'phase_heights':heights,'load_phases':loads,'communication_atoms':atoms}
    f,a=figure((7.7,3.15));a.plot(np.array(time)/60,soc,color=BLUE,lw=1.8,label='飞行及作业模型SOC');a.plot([tr/60,t90/60],[sret*100,90],color=GOLD,lw=1.8,label='快速充电');a.plot([t90/60,tc/60],[90,100],color=PURPLE,lw=1.8,label='慢速充电');a.axhline(20,ls='--',lw=.8,color=RED);a.axvline(tr/60,ls=':',lw=.7,color=MUTED);a.set(xlabel='任务相对时刻（min）',ylabel='电池SOC（%）',xlim=horizon,ylim=(0,112));legend(a,ncol=3,loc='upper center',bbox_to_anchor=(.5,1.05))
    store(pub,'F160',STATE_TRIP+'：任务能耗与两阶段充电',f,source_values,'分阶段均匀能量累计由同一能耗公式推导，非电流遥测。下降/交接附加能耗按题定简化模型为0；末尾为本电池充满时间，非任务完工。')
    f,a=figure((7.7,2.8));xx=[float(trip['start_s'])/60];yy=[float(trip['weight_kg'])]
    for l in legs:
        xx.extend([float(l['handoff_complete_s'])/60]);yy.extend([float(l['remaining_payload_after_handoff_kg'])])
    a.step(xx,yy,where='post',color=TEAL,lw=1.8);a.fill_between(xx,0,yy,step='post',color=TEAL,alpha=.13);a.axvline(tr/60,ls=':',lw=.7,color=MUTED);a.set(xlabel='任务相对时刻（min）',ylabel='剩余载荷（kg）',xlim=horizon,ylim=(0,float(trip['weight_kg'])*1.22))
    store(pub,'F161',STATE_TRIP+'：完成站点交接后的剩余载荷',f,{'time_min':xx,'remaining_payload_kg':yy,'trip':trip,'legs':legs},'卸货以站点交接完成为阶跃；用于航段能耗的载荷，不推断交接期间每箱释放过程。')
    f,a=figure((7.7,2.75));providers=['G01']+sorted({r['relay_trip_id'] for r in atoms if r['relay_trip_id']})
    for j,p in enumerate(providers):
        seq=[(float(r['start_s'])/60,(float(r['end_s'])-float(r['start_s']))/60) for r in atoms if float(r['end_s'])>float(r['start_s']) and ((p=='G01' and r['mode']=='直连') or (p!='G01' and r['relay_trip_id']==p))]
        if seq:a.broken_barh(seq,(j-.26,.52),facecolors=BLUE if p=='G01' else GOLD,edgecolors='none')
    a.axvline(tr/60,ls=':',lw=.7,color=MUTED);a.set_yticks(range(len(providers)),providers);a.set(xlabel='任务相对时刻（min）',ylabel='通信提供者',xlim=horizon,ylim=(len(providers)-.6,-.6));a.grid(False,axis='y');a.grid(axis='x')
    store(pub,'F162',STATE_TRIP+'：全飞行与交接区间通信切换',f,{'providers':providers,'atoms':atoms,'horizon_min':horizon},'空白仅为准备、返回后充电等无本运输任务通信需求时段；正长度通信区间直接取最终结果，边界点另行验证。')
    f,a=figure((7.7,3.0));seen=set()
    for h in heights:
        phase=h['phase'];a.plot([h['start_s']/60,h['end_s']/60],[h['altitude0_m'],h['altitude1_m']],color=PHASE.get(phase,PURPLE),lw=2,label=phase if phase not in seen else None);seen.add(phase)
    a.axvline(tr/60,ls=':',lw=.7,color=MUTED);a.set(xlabel='任务相对时刻（min）',ylabel='海拔（m）',xlim=horizon);legend(a,ncol=4,loc='upper center',bbox_to_anchor=(.5,1.05))
    store(pub,'F163',STATE_TRIP+'：与能源、通信对齐的飞行剖面',f,source_values,'与F160-F162共享完整时间轴；返航后不绘制虚构空中轨迹。')
