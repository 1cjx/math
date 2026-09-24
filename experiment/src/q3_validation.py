"""独立Q3验证器：从Q3提交CSV/Excel重建轨迹、原始DEM、二维半平面顶点枚举。
Python3.13.5 / numpy2.3.5 / rasterio1.5.0 / numba0.65.1。
不调用q3_communication/q3_joint/q3_relay_schedule的几何或时序算法。
独立连续证明：枚举每个地形柱与视线扇面的可行多边形顶点，投影遮挡区间；
局部三维直线距离平方为凸二次函数，任一闭区间最大值在端点。
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict,Counter
import math,json
import numpy as np
import rasterio
from rasterio.features import rasterize
from pyproj import Geod
from numba import njit
from io_utils import read_csv,write_csv,save_json
from config import CFG
from q3_config import Q3CFG
from q2_validation import independent_arcs,validate_rows,independent_charge

@njit(cache=True)
def independent_blocked(A,B,z):
    """Amanatides-Woo网格遍历，独立于求解器的排序交点DDA。"""
    dx=B[0]-A[0];dy=B[1]-A[1];dz=B[2]-A[2]
    c=int(math.floor(A[0]));r=int(math.floor(A[1]));sx=1 if dx>0 else -1;sy=1 if dy>0 else -1
    tx=math.inf if abs(dx)<1e-14 else ((c+1-A[0]) if dx>0 else (c-A[0]))/dx
    ty=math.inf if abs(dy)<1e-14 else ((r+1-A[1]) if dy>0 else (r-A[1]))/dy
    dtx=math.inf if abs(dx)<1e-14 else abs(1/dx);dty=math.inf if abs(dy)<1e-14 else abs(1/dy);t0=0.
    for step in range(2*(z.shape[0]+z.shape[1])+10):
        t1=min(1.,tx,ty);lo=min(A[2]+t0*dz,A[2]+t1*dz)
        cc0=c-1 if abs(dx)<1e-14 and abs(A[0]-round(A[0]))<1e-10 else c
        rr0=r-1 if abs(dy)<1e-14 and abs(A[1]-round(A[1]))<1e-10 else r
        for rr in range(rr0,r+1):
            for cc in range(cc0,c+1):
                if not (0<=rr<z.shape[0] and 0<=cc<z.shape[1]):return True
                if lo<=z[rr,cc]+1e-8:return True
        # 孤立顶点、起止端点按接触遮挡规则逐个检查。
        for t in (t0,t1):
            x=A[0]+t*dx;y=A[1]+t*dy;h=A[2]+t*dz
            cx=int(math.floor(x));ry=int(math.floor(y))
            cl=int(round(x))-1 if abs(x-round(x))<1e-10 else cx;ch=int(round(x)) if abs(x-round(x))<1e-10 else cx
            rl=int(round(y))-1 if abs(y-round(y))<1e-10 else ry;rh=int(round(y)) if abs(y-round(y))<1e-10 else ry
            for rr in range(rl,rh+1):
                for cc in range(cl,ch+1):
                    if not (0<=rr<z.shape[0] and 0<=cc<z.shape[1]):return True
                    if h<=z[rr,cc]+1e-8:return True
        if t1>=1.-1e-15:return False
        ox=tx;oy=ty
        if ox<=oy+1e-14:c+=sx;tx+=dtx
        if oy<=ox+1e-14:r+=sy;ty+=dty
        t0=t1
    return True

@njit(cache=True)
def independent_shadows(A,B,C,z):
    """8个半平面交集，枚举28组边界交点而不是裁剪多边形。"""
    vx=B-A;vy=C-A
    left=max(0,int(math.floor(min(A[0],B[0],C[0])))-1);right=min(z.shape[1]-1,int(math.floor(max(A[0],B[0],C[0])))+1)
    top=max(0,int(math.floor(min(A[1],B[1],C[1])))-1);bottom=min(z.shape[0]-1,int(math.floor(max(A[1],B[1],C[1])))+1)
    mat=np.array([[-1.,0.],[0.,-1.],[1.,1.],[vx[0],vy[0]],[-vx[0],-vy[0]],[vx[1],vy[1]],[-vx[1],-vy[1]],[vx[2],vy[2]]])
    rhs=np.zeros(8);rhs[2]=1.;ans=[];tested=0
    dets=[]
    for i in range(8):
        for j in range(i+1,8):
            d=mat[i,0]*mat[j,1]-mat[i,1]*mat[j,0]
            if abs(d)>1e-14:dets.append((i,j,d))
    minheight=min(A[2],B[2],C[2])
    for r in range(top,bottom+1):
        for c in range(left,right+1):
            zz=z[r,c]
            if zz+1e-8<minheight:continue
            rhs[3]=c+1-A[0];rhs[4]=A[0]-c;rhs[5]=r+1-A[1];rhs[6]=A[1]-r;rhs[7]=zz+1e-8-A[2]
            slo=1.;shi=0.;found=False
            for ii,jj,d in dets:
                i=int(ii);j=int(jj);u=(rhs[i]*mat[j,1]-mat[i,1]*rhs[j])/d;v=(mat[i,0]*rhs[j]-rhs[i]*mat[j,0])/d
                ok=True
                for k in range(8):
                    if mat[k,0]*u+mat[k,1]*v>rhs[k]+1e-9:ok=False;break
                if ok and u+v>1e-12:
                    s=v/(u+v)
                    if s<-1e-8 or s>1+1e-8:continue
                    slo=min(slo,s);shi=max(shi,s);found=True
            tested+=1
            if found:ans.append((max(0.,slo),min(1.,shi)))
    return ans,tested


def merge01(rows):
    out=[]
    for a,b in sorted(rows):
        if out and a<=out[-1][1]+1e-12:out[-1]=(out[-1][0],max(out[-1][1],b))
        else:out.append((a,b))
    return out

class IndependentRadio:
    def __init__(self,root,data):
        tif=next((Path(root)/'data/raw').rglob('*.tif'))
        with rasterio.open(tif) as ds:self.dem=ds.read(1);self.transform=ds.transform;self.inv=~ds.transform;self.bounds=ds.bounds
        p={(r['category'],r['symbol']):r['value'] for r in data['communication']};o=data['depots'][0]
        self.origin=(o['lon_deg'],o['lat_deg'],o['ground_elevation_m']);self.gateway=(o['lon_deg'],o['lat_deg'],o['ground_elevation_m']+p['固定网关 G01','hG'])
        self.constant=32.45+20*math.log10(p['传播参数','f']);self.obs=p['传播参数','Lobs'];threshold=p['接收参数','Psens']+p['接收参数','M']
        cats={'direct':('运输无人机','固定网关 G01'),'access':('运输无人机','中继接入端'),'backhaul':('中继回传端','固定网关 G01')};self.limits={}
        for kind,(a,b) in cats.items():self.limits[kind]=min(p[a,'Pt'],p[b,'Pt'])+p[a,'G']+p[b,'G']-p['传播参数','Lsys']-threshold
        phi=math.radians(o['lat_deg']);e2=1-(1-1/298.257223563)**2;a=6378137.;W=math.sqrt(1-e2*math.sin(phi)**2)
        self.scale=np.array([a/W*math.cos(phi)*math.pi/180,a*(1-e2)/W**3*math.pi/180,1.])
        self.cache={};self.tested_cells=0
    def grid(self,p):
        xy=self.inv*(p[0],p[1]);return np.array([xy[0],xy[1],p[2]])
    def point(self,a,b,kind):
        d=float(np.linalg.norm((np.asarray(b)-a)*self.scale));blocked=bool(independent_blocked(self.grid(a),self.grid(b),self.dem))
        loss=self.constant+20*math.log10(max(d,1e-12)/1000)+self.obs*blocked
        return {'distance_m':d,'blocked':blocked,'margin_db':self.limits[kind]-loss,'available':loss<=self.limits[kind]+1e-8}
    def shadows(self,a,b,c):
        key=(tuple(a),tuple(b),tuple(c))
        if key not in self.cache:
            intervals,n=independent_shadows(self.grid(a),self.grid(b),self.grid(c),self.dem);self.cache[key]=merge01(intervals);self.tested_cells+=n
        return self.cache[key]
    def roots(self,a,b,c,kind,blocked):
        # 独立通过np.roots求二次方程，不调用主算法解析函数。
        v=(np.array(b)-a)*self.scale;w=(np.array(c)-b)*self.scale
        R=1000*10**((self.limits[kind]-self.constant-self.obs*blocked)/20)
        if float(w@w)<1e-20:return []
        ans=np.roots([float(w@w),float(2*w@v),float(v@v)-R*R])
        return [float(x.real) for x in ans if abs(x.imag)<1e-12 and 0<x.real<1]
    def profile(self,a,b,c,kind,lo=0.,hi=1.):
        sh=self.shadows(a,b,c);cuts=sorted(set([lo,hi]+[x for rr in sh for x in rr if lo<x<hi]+[x for obs in (False,True) for x in self.roots(a,b,c,kind,obs) if lo<x<hi]));rows=[]
        for x,y in zip(cuts,cuts[1:]):
            if y-x<1e-12:continue
            mid=(x+y)/2;blocked=any(i-1e-13<=mid<=j+1e-13 for i,j in sh)
            dmax=max(np.linalg.norm((np.array(b)+(np.array(c)-b)*v-a)*self.scale) for v in (x,y))
            bound=self.limits[kind]-self.constant-20*math.log10(max(dmax,1e-12)/1000)-self.obs*blocked
            dm=np.linalg.norm((np.array(b)+(np.array(c)-b)*mid-a)*self.scale)
            margin=self.limits[kind]-self.constant-20*math.log10(max(dm,1e-12)/1000)-self.obs*blocked
            rows.append({'s0':x,'s1':y,'blocked':blocked,'max_distance_m':float(dmax),'min_margin_bound_db':float(bound),'available_interior':margin>=-1e-8})
        return rows,sh


def independent_phases(data,arc,trips,deliveries):
    """只读原始参数、独立DEM航段和提交的运输/逐箱表，不读legs.csv/trajectory.csv。"""
    nodes={n['node_id']:n for n in data['depots']+data['services']};models={m['model_id']:m for m in data['transport_models']}
    bytrip=defaultdict(list)
    for b in deliveries:bytrip[b['架次编号']].append(b)
    phases=[]
    def work(s):
        n=nodes[s];return (n['lon_deg'],n['lat_deg'],n['ground_elevation_m']+(0 if s=='O01' else CFG.service_work_height_m))
    for tr in trips:
        tid=tr['架次编号'];g=tr['机型编号'];m=models[g];bs=bytrip[tid];t=float(tr['开始时刻（s）'])+m['prepare_s']+len(bs)*m['load_per_box_s'];u='O01'
        for k,v in enumerate(tr['访问服务区顺序'].split(';')+['O01'],1):
            ar=arc[u,v];a=work(u);b=work(v);ah=(a[0],a[1],ar['H']);bh=(b[0],b[1],ar['H'])
            for label,p0,p1,dt in [('爬升',a,ah,ar['up']/m['climb_speed_mps']),('巡航',ah,bh,ar['d']/m['cruise_speed_mps']),('下降',bh,b,ar['down']/m['descent_speed_mps'])]:
                if dt>1e-12:phases.append({'trip_id':tid,'drone_id':tr['无人机编号'],'leg_index':k,'from_id':u,'to_id':v,'phase':label,'start_s':t,'end_s':t+dt,'p0':p0,'p1':p1})
                t+=dt
            if v!='O01':
                dt=m['handoff_base_s']+sum(x['服务区编号']==v for x in bs)*m['handoff_per_box_s'];phases.append({'trip_id':tid,'drone_id':tr['无人机编号'],'leg_index':k,'from_id':u,'to_id':v,'phase':'投送交接','start_s':t,'end_s':t+dt,'p0':b,'p1':b});t+=dt
            u=v
        if abs(t-float(tr['返回O01时刻（s）']))>1e-6:raise AssertionError('独立轨迹重建与提交返回时刻不一致')
    for i,p in enumerate(phases,1):p['phase_id']=f'IV-PH-{i:04d}'
    return phases


def _pos(p,t):return np.array(p['p0'])+(np.array(p['p1'])-p['p0'])*((t-p['start_s'])/(p['end_s']-p['start_s']))


def validate_relay(data,radio,rows):
    checks=[];out=[];model=data['relay_models'][0];ep=data['relay_energy'][0];fleet={d['drone_id'] for d in data['relay_drones']};components={f'R-ENG-{j+1:02d}' for j in range(ep['count'])};geod=Geod(ellps='WGS84')
    def ck(k,v,det=''):checks.append({'check':k,'pass':bool(v),'details':str(det)})
    ck('relay_unique_trip_ids',len(rows)==len({r['中继架次编号'] for r in rows}))
    for r in rows:
        tid=r['中继架次编号'];p=(float(r['悬停经度（°）']),float(r['悬停纬度（°）']),float(r['悬停海拔（m）']));origin=radio.origin
        st=float(r['开始时刻（s）']);link=float(r['建链完成时刻（s）']);end=float(r['服务结束时刻（s）']);ret=float(r['返回O01时刻（s）']);reportedE=float(r['架次能耗（kWh）'])
        ck(tid+'/finite',all(math.isfinite(x) for x in (*p,st,link,end,ret,reportedE)))
        ck(tid+'/drone_inventory',r['中继无人机编号'] in fleet);ck(tid+'/energy_inventory',r['能源组件编号'] in components);ck(tid+'/start_nonnegative',st>=-1e-8)
        g=radio.grid(p);rr=int(math.floor(g[1]));cc=int(math.floor(g[0]));inside=0<=rr<radio.dem.shape[0] and 0<=cc<radio.dem.shape[1];ck(tid+'/DEM_domain',inside)
        if not inside:continue
        ground=float(radio.dem[rr,cc]);ck(tid+'/AGL_cap',0<p[2]-ground<=model['max_hover_agl_m']+1e-8)
        shape={'type':'LineString','coordinates':[origin[:2],p[:2]]};mask=rasterize([(shape,1)],out_shape=radio.dem.shape,transform=radio.transform,all_touched=True,dtype='uint8').astype(bool);H=float(radio.dem[mask].max())+CFG.terrain_clearance_m
        ck(tid+'/strict_source_cruise',H>=max(origin[2],p[2])-1e-8);d=geod.inv(*origin[:2],*p[:2])[2];up1=H-origin[2];up2=H-p[2]
        dt1=up1/model['climb_speed_mps']+d/model['cruise_speed_mps']+up2/model['descent_speed_mps'];dt2=up2/model['climb_speed_mps']+d/model['cruise_speed_mps']+up1/model['descent_speed_mps']
        arrival=st+model['prepare_s']+dt1;expectedlink=arrival+model['link_setup_s'];expectedret=end+dt2
        eh=2*model['cruise_power_kw']*d/model['cruise_speed_mps']/3600;eu=model['takeoff_mass_kg']*CFG.gravity_m_s2*(up1+up2)/(model['climb_efficiency']*CFG.joules_per_kwh)
        es=(model['hover_power_kw']+model['communication_power_kw'])*(end-arrival)/3600;e=eh+eu+es;soc=1-e/model['usable_energy_kwh'];charge=independent_charge(soc,ep['full_charge_s'])
        ck(tid+'/build_link_time',abs(expectedlink-link)<=1e-6,expectedlink-link);ck(tid+'/return_time',abs(expectedret-ret)<=1e-6,expectedret-ret)
        ck(tid+'/service_interval',end>=link-1e-8);ck(tid+'/energy_formula',abs(e-reportedE)<=1e-8,e-reportedE);ck(tid+'/return_reserve',soc>=model['reserve_fraction']-1e-8,soc)
        back=radio.point(radio.gateway,p,'backhaul');ck(tid+'/bidirectional_backhaul',back['available'],back['margin_db'])
        out.append({'relay_trip_id':tid,'drone_id':r['中继无人机编号'],'module_id':r['能源组件编号'],'start_s':st,'arrival_s':arrival,'link_s':link,'end_s':end,'return_s':ret,
            'turnaround_end_s':ret+model['turnaround_s'],'charge_end_s':ret+charge,'charge_duration_s':charge,'energy_kwh':e,'return_soc_fraction':soc,
            'ground_m':ground,'cruise_m':H,'hover_agl_m':p[2]-ground,'point':p,'backhaul_margin_db':back['margin_db'],'backhaul_blocked':back['blocked'],'horizontal_energy_kwh':eh,'climb_energy_kwh':eu,'station_energy_kwh':es})
    for field,resource_end in [('drone_id','turnaround_end_s'),('module_id','charge_end_s')]:
        grouped=defaultdict(list)
        for x in out:grouped[x[field]].append(x)
        for rid,items in grouped.items():
            items.sort(key=lambda x:x['start_s'])
            for prev,nex in zip(items,items[1:]):ck(rid+'/reuse_'+prev['relay_trip_id']+'_'+nex['relay_trip_id'],nex['start_s']>=prev[resource_end]-1e-6,nex['start_s']-prev[resource_end])
    return checks,out


def validate_communication(data,radio,phases,relay,rows,dense=True):
    checks=[];cert=[];dense_rows=[];phaseby=defaultdict(list);comby=defaultdict(list);rel={r['relay_trip_id']:r for r in relay}
    def ck(k,v,det=''):checks.append({'check':k,'pass':bool(v),'details':str(det)})
    for p in phases:phaseby[p['trip_id']].append(p)
    for i,r in enumerate(rows):
        r=dict(r);r['index']=i+1;comby[r['运输架次编号']].append(r)
    ck('communication_trip_set',set(comby)==set(phaseby))
    def find_phase(tid,lo,hi):
        return next((p for p in phaseby[tid] if p['start_s']<=lo+1e-6 and p['end_s']>=hi-1e-6),None)
    def decide(p,t,mode,rid):
        pos=_pos(p,t);dr=radio.point(radio.gateway,pos,'direct')
        if mode=='直连':return dr['available'],dr,dr
        if rid not in rel:return False,dr,dr
        rr=rel[rid];lk=radio.point(rr['point'],pos,'access');valid=(not dr['available']) and lk['available'] and rr['link_s']-1e-6<=t<=rr['end_s']+1e-6
        return valid,lk,dr
    for tid in sorted(phaseby):
        pp=sorted(phaseby[tid],key=lambda p:p['start_s']);rr=comby.get(tid,[])
        spans=[];points={}
        for r in rr:
            lo=float(r['开始时刻（s）']);hi=float(r['结束时刻（s）']);label=r['通信阶段'];mode=r['保障方式'];rid=r.get('中继架次编号','') or '';key=f"COMrow{r['index']}"
            ck(key+'/finite_ordered',math.isfinite(lo) and math.isfinite(hi) and hi>=lo)
            ck(key+'/known_mode',mode in ('直连','中继'));ck(key+'/provider_count',not rid if mode=='直连' else rid in rel)
            p=find_phase(tid,lo,hi);ck(key+'/single_physical_phase',p is not None)
            if p is None:continue
            ck(key+'/phase_label',label.split('·')[0]==p['phase'] or (lo==hi and label.split('·')[0] in {x['phase'] for x in pp if abs(x['start_s']-lo)<1e-6 or abs(x['end_s']-lo)<1e-6}))
            if hi==lo:
                q=round(lo,9);ck(key+'/unique_point',q not in points);points[q]=r
                ok,lk,dr=decide(p,lo,mode,rid);ck(key+'/instant_link_and_priority',ok,(lk['margin_db'],dr['margin_db']))
                cert.append({'row':r['index'],'trip_id':tid,'phase':p['phase'],'start_s':lo,'end_s':hi,'is_boundary':True,'mode':mode,'relay_id':rid,'min_margin_bound_db':lk['margin_db'],'pass':ok});continue
            spans.append(r);dt=p['end_s']-p['start_s'];s0=max(0.,(lo-p['start_s'])/dt);s1=min(1.,(hi-p['start_s'])/dt)
            direct,shd=radio.profile(radio.gateway,p['p0'],p['p1'],'direct',s0,s1)
            if mode=='直连':linkparts=direct;shadow=shd
            elif rid in rel:
                linkparts,shadow=radio.profile(rel[rid]['point'],p['p0'],p['p1'],'access',s0,s1)
                ck(key+'/relay_time_coverage',lo>=rel[rid]['link_s']-1e-6 and hi<=rel[rid]['end_s']+1e-6)
                ck(key+'/direct_priority_entire_interval',all(not a['available_interior'] for a in direct))
            else:continue
            minbound=min((a['min_margin_bound_db'] for a in linkparts),default=math.inf)
            ok=minbound>=-2e-7 # 米级阈值换算后的浮点容差；非新增衰落预算
            ck(key+'/continuous_terrain_and_distance',ok,minbound)
            # 不依赖稀疏采样：内部孤立阴影接触也显式检查。
            anchor=radio.gateway if mode=='直连' else rel[rid]['point'];kind='direct' if mode=='直连' else 'access'
            for aa,bb in shadow:
                for ss in (aa,bb):
                    if s0+1e-10<ss<s1-1e-10:
                        point=np.array(p['p0'])+(np.array(p['p1'])-p['p0'])*ss
                        lk=radio.point(anchor,point,kind);ck(key+'/internal_shadow_contact',lk['available'],lk['margin_db']);ok=ok and lk['available']
            cert.append({'row':r['index'],'trip_id':tid,'phase':p['phase'],'start_s':lo,'end_s':hi,'is_boundary':False,'mode':mode,'relay_id':rid,'min_margin_bound_db':minbound,'pass':ok})
            if dense:
                dist=np.linalg.norm((_pos(p,hi)-_pos(p,lo))*radio.scale);ns=max(1,math.ceil((hi-lo)/Q3CFG.independent_sample_seconds),math.ceil(dist/Q3CFG.independent_sample_spacing_m))
                for k in range(ns):
                    t=lo+(hi-lo)*(k+.5)/ns;valid,lk,dr=decide(p,t,mode,rid)
                    dense_rows.append({'trip_id':tid,'phase':p['phase'],'time_s':t,'mode':mode,'relay_id':rid,'selected_margin_db':lk['margin_db'],'direct_margin_db':dr['margin_db'],'selected_blocked':lk['blocked'],'pass':valid})
        spans.sort(key=lambda r:float(r['开始时刻（s）']));ck(tid+'/has_communication_spans',bool(spans))
        if spans:
            ck(tid+'/takeoff_boundary',abs(float(spans[0]['开始时刻（s）'])-pp[0]['start_s'])<1e-6)
            ck(tid+'/return_boundary',abs(float(spans[-1]['结束时刻（s）'])-pp[-1]['end_s'])<1e-6)
            for a,b in zip(spans,spans[1:]):ck(tid+'/no_gap_or_overlap',abs(float(a['结束时刻（s）'])-float(b['开始时刻（s）']))<1e-6)
            ends={round(float(r[k]),9) for r in spans for k in ('开始时刻（s）','结束时刻（s）')};ck(tid+'/all_boundary_points_present',ends<=set(points),len(ends-set(points)))
            for q in points:ck(tid+'/point_inside_mission',pp[0]['start_s']-1e-6<=q<=pp[-1]['end_s']+1e-6)
    ck('dense_audit_no_outage',all(x['pass'] for x in dense_rows),sum(not x['pass'] for x in dense_rows))
    return checks,cert,dense_rows


def run_q3_validation(root,folder='results/q3',dense=True,trip_rows=None,delivery_rows=None,relay_rows=None,comm_rows=None,write=True,raise_on_fail=True):
    root=Path(root);out=root/folder;data=json.loads((root/'data/cleaned/model_inputs.json').read_text());radio=IndependentRadio(root,data);arc=independent_arcs(root,data)
    trips=trip_rows if trip_rows is not None else read_csv(out/'Q3_运输架次.csv');deliveries=delivery_rows if delivery_rows is not None else read_csv(out/'Q3_逐箱交付.csv')
    relays=relay_rows if relay_rows is not None else read_csv(out/'Q3_中继架次.csv');comms=comm_rows if comm_rows is not None else read_csv(out/'Q3_通信保障.csv')
    trans_summary,trans_checks,trans_details,boxchecks,resources=validate_rows(data,arc,trips,deliveries)
    phases=independent_phases(data,arc,trips,deliveries);relaychecks,relaydetails=validate_relay(data,radio,relays)
    commchecks,cert,dense_rows=validate_communication(data,radio,phases,relaydetails,comms,dense)
    checks=trans_checks+relaychecks+commchecks;failed=[r for r in checks if not r['pass']]
    sums={'checks_total':len(checks),'checks_passed':len(checks)-len(failed),'checks_failed':len(failed),
         'transport_checks':len(trans_checks),'relay_checks':len(relaychecks),'communication_checks':len(commchecks),
         'dense_samples':len(dense_rows),'dense_failed':sum(not r['pass'] for r in dense_rows),
         'continuous_atoms':len(cert),'continuous_atoms_failed':sum(not r['pass'] for r in cert),
         'independent_shadow_cells_tested':radio.tested_cells,'transport':trans_summary,
         'relay_energy_kwh':sum(r['energy_kwh'] for r in relaydetails),'total_energy_kwh':trans_summary['energy_kwh']+sum(r['energy_kwh'] for r in relaydetails),
         'joint_makespan_s':max(trans_summary['makespan_s'],max((r['return_s'] for r in relaydetails),default=0)),
         'relay_min_soc_fraction':min((r['return_soc_fraction'] for r in relaydetails),default=None),
         'model_scope':'原始DEM分片常高+统一局部三维坐标+给定链路预算，完整连续区间与孤立边界点；不是实地认证',
         'independent_algorithm':'半平面边界交点枚举，与主裁剪法独立；AW射线遍历与主排序交点法独立'}
    if write:
        write_csv(out/'independent_checks.csv',checks);write_csv(out/'independent_continuous_certificate.csv',cert);write_csv(out/'independent_dense_audit.csv',dense_rows)
        write_csv(out/'independent_transport_checks.csv',trans_checks);write_csv(out/'independent_transport_energy.csv',trans_details);write_csv(out/'independent_box_checks.csv',boxchecks);write_csv(out/'independent_resources.csv',resources)
        write_csv(out/'independent_relay_checks.csv',relaychecks);write_csv(out/'independent_relay_details.csv',[{k:v for k,v in r.items() if k!='point'} for r in relaydetails]);save_json(out/'independent_validation.json',sums)
    if failed and raise_on_fail:raise AssertionError(f'Q3独立验证失败{len(failed)}项；前3项{failed[:3]}')
    return sums
