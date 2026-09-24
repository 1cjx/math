"""核心通信模块：双向预算、逐像元视线、连续运动的地形阴影区间。
Python 3.13.5 / numpy2.3.5 / numba0.65.1 / pyproj3.7.2。
几何内核用Numba编译；不是按稀疏时刻推断全程通信。
射线扇面参数(u,v)的凸多边形裁剪枚举每个可能遮挡像元，
将其投影到运动参数s=v/(u+v)，得到连续遮挡区间（含接触）。
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import math,json
import numpy as np
import rasterio
from numba import njit
from physics import GEOD
from q3_config import Q3CFG
from config import CFG

@njit(cache=True)
def _ray_blocked(a,b,dem):
    """A,B=(栅格列坐标,栅格行坐标,海拔)；连续DDA访问全部穿越像元。
    沿像元内视线最低高度与该像元高程比较；不能只查像元中心。
    """
    dx=b[0]-a[0];dy=b[1]-a[1];dz=b[2]-a[2]
    cuts=[0.0,1.0]
    for axis in range(2):
        da=b[axis]-a[axis]
        if abs(da)>1e-13:
            low=int(math.ceil(min(a[axis],b[axis])));high=int(math.floor(max(a[axis],b[axis])))
            for k in range(low,high+1):
                t=(k-a[axis])/da
                if 0<t<1:cuts.append(t)
    cuts.sort()
    for k in range(len(cuts)-1):
        t0=cuts[k];t1=cuts[k+1];tm=(t0+t1)*0.5
        x=a[0]+tm*dx;y=a[1]+tm*dy
        c=int(math.floor(x));r=int(math.floor(y))
        c0=c-1 if abs(x-round(x))<1e-10 else c
        r0=r-1 if abs(y-round(y))<1e-10 else r
        zmin=min(a[2]+t0*dz,a[2]+t1*dz)
        for rr in range(r0,r+1):
            for cc in range(c0,c+1):
                if rr<0 or cc<0 or rr>=dem.shape[0] or cc>=dem.shape[1]:return True
                if dem[rr,cc]<-1000:return True
                if zmin<=dem[rr,cc]+1e-8:return True
    # 显式处理孤立角点接触（DDA区间两侧未必含另外两个像元）。
    for t in cuts:
        x=a[0]+t*dx;y=a[1]+t*dy;z=a[2]+t*dz
        c=int(math.floor(x));r=int(math.floor(y))
        c0=int(round(x))-1 if abs(x-round(x))<1e-10 else c
        c1=int(round(x)) if abs(x-round(x))<1e-10 else c
        r0=int(round(y))-1 if abs(y-round(y))<1e-10 else r
        r1=int(round(y)) if abs(y-round(y))<1e-10 else r
        for rr in range(r0,r1+1):
            for cc in range(c0,c1+1):
                if rr<0 or cc<0 or rr>=dem.shape[0] or cc>=dem.shape[1]:return True
                if z<=dem[rr,cc]+1e-8:return True
    return False

@njit(cache=True)
def _line_peak(a,b,dem):
    dx=b[0]-a[0];dy=b[1]-a[1];cuts=[0.0,1.0]
    for axis in range(2):
        d=b[axis]-a[axis]
        if abs(d)>1e-13:
            for k in range(int(math.ceil(min(a[axis],b[axis]))),int(math.floor(max(a[axis],b[axis])))+1):
                t=(k-a[axis])/d
                if 0<t<1:cuts.append(t)
    cuts.sort();peak=-1e30
    for k in range(len(cuts)*2-1):
        t=cuts[k//2] if k%2==0 else (cuts[k//2]+cuts[k//2+1])*0.5
        x=a[0]+t*dx;y=a[1]+t*dy;c=int(math.floor(x));r=int(math.floor(y))
        c0=int(round(x))-1 if abs(x-round(x))<1e-10 else c
        c1=int(round(x)) if abs(x-round(x))<1e-10 else c
        r0=int(round(y))-1 if abs(y-round(y))<1e-10 else r
        r1=int(round(y)) if abs(y-round(y))<1e-10 else r
        for rr in range(r0,r1+1):
            for cc in range(c0,c1+1):
                if rr<0 or cc<0 or rr>=dem.shape[0] or cc>=dem.shape[1]:return math.nan
                z=dem[rr,cc]
                if z<-1000:return math.nan
                peak=max(peak,z)
    return peak

@njit(cache=True)
def _clip(poly,n,A,B,C):
    """Sutherland-Hodgman裁剪凸多边形 Au+Bv<=C。"""
    out=np.empty((12,2),np.float64);nn=0
    if n==0:return out,0
    px=poly[n-1,0];py=poly[n-1,1];fp=A*px+B*py-C
    for k in range(n):
        x=poly[k,0];y=poly[k,1];f=A*x+B*y-C
        if (f<=0)!=(fp<=0):
            t=fp/(fp-f)
            out[nn,0]=px+t*(x-px);out[nn,1]=py+t*(y-py);nn+=1
        if f<=0:
            out[nn,0]=x;out[nn,1]=y;nn+=1
        px=x;py=y;fp=f
    return out,nn

@njit(cache=True)
def _shadow_intervals(a,b0,b1,dem):
    """返回每个地形像元在s∈[0,1]造成的阴影闭区间及其行列号。
    XY投影退化（竖直升降/静止）时，在(u,v)空间依然可正确处理。
    """
    xmin=int(math.floor(min(a[0],b0[0],b1[0])))-1;xmax=int(math.floor(max(a[0],b0[0],b1[0])))+1
    ymin=int(math.floor(min(a[1],b0[1],b1[1])))-1;ymax=int(math.floor(max(a[1],b0[1],b1[1])))+1
    xmin=max(0,xmin);xmax=min(dem.shape[1]-1,xmax);ymin=max(0,ymin);ymax=min(dem.shape[0]-1,ymax)
    out=[]
    ax=b0[0]-a[0];bx=b1[0]-a[0];ay=b0[1]-a[1];by=b1[1]-a[1];az=b0[2]-a[2];bz=b1[2]-a[2]
    minz=min(a[2],b0[2],b1[2]);tested=0
    for rr in range(ymin,ymax+1):
        for cc in range(xmin,xmax+1):
            z=dem[rr,cc]
            if z+1e-8<minz:continue
            poly=np.empty((12,2),np.float64)
            poly[0,0]=0.;poly[0,1]=0.;poly[1,0]=1.;poly[1,1]=0.;poly[2,0]=0.;poly[2,1]=1.;n=3
            poly,n=_clip(poly,n,ax,bx,cc+1-a[0])
            if n==0:continue
            poly,n=_clip(poly,n,-ax,-bx,a[0]-cc)
            if n==0:continue
            poly,n=_clip(poly,n,ay,by,rr+1-a[1])
            if n==0:continue
            poly,n=_clip(poly,n,-ay,-by,a[1]-rr)
            if n==0:continue
            tested+=1
            poly,n=_clip(poly,n,az,bz,z+1e-8-a[2])
            if n==0:continue
            lower=1.;upper=0.;valid=False
            for k in range(n):
                den=poly[k,0]+poly[k,1]
                if den>1e-13:
                    s=poly[k,1]/den
                    lower=min(lower,s);upper=max(upper,s);valid=True
            if valid:out.append((max(0.,lower),min(1.,upper),rr,cc))
    return out,tested

@njit(cache=True)
def _batch_cover(anchor,points,dem,kx,ky,range_los,range_obs,eps=0.):
    """搜索用近似水平距离；正式验证改用局部三维直线距离及连续阴影。"""
    ans=np.empty(points.shape[0],np.bool_)
    for i in range(points.shape[0]):
        b=points[i];dd=math.sqrt(((b[0]-anchor[0])*kx)**2+((b[1]-anchor[1])*ky)**2+(b[2]-anchor[2])**2)
        if dd<=range_obs:ans[i]=True
        elif dd>range_los:ans[i]=False
        else:ans[i]=not _ray_blocked(anchor,b,dem)
    return ans


def union_intervals(intervals,eps=Q3CFG.interval_eps):
    out=[]
    for a,b in sorted(intervals):
        a=max(0.,float(a));b=min(1.,float(b))
        if a>b+eps:continue
        if out and a<=out[-1][1]+eps:out[-1]=(out[-1][0],max(b,out[-1][1]))
        else:out.append((a,b))
    return out


def intersection_intervals(aa,bb):
    out=[]
    for a,b in aa:
        for c,d in bb:
            lo=max(a,c);hi=min(b,d)
            if lo<=hi+1e-14:out.append((lo,max(lo,hi)))
    return union_intervals(out)


def contains(intervals,s,tol=1e-12):
    return any(a-tol<=s<=b+tol for a,b in intervals)


class Radio:
    def __init__(self,root,data):
        self.root=Path(root);self.data=data
        with rasterio.open(self.root/'data/cleaned/geospatial/dem_clean.tif') as ds:
            self.dem=ds.read(1);self.transform=ds.transform;self.bounds=ds.bounds
        self.inv=~self.transform
        self.nodes={n['node_id']:n for n in data['depots']+data['services']}
        pars={(r['category'],r['symbol']):r['value'] for r in data['communication']}
        self.frequency=pars['传播参数','f'];self.system_loss=pars['传播参数','Lsys'];self.obs_loss=pars['传播参数','Lobs']
        self.threshold=pars['接收参数','Psens']+pars['接收参数','M']
        self.endpoints={key:{'power':pars[cat,'Pt'],'gain':pars[cat,'G'],'threshold':self.threshold} for key,cat in [('T','运输无人机'),('RA','中继接入端'),('RB','中继回传端'),('G','固定网关 G01')]}
        self.budgets={};self.directions=[]
        for name,a,b in [('direct','T','G'),('access','T','RA'),('backhaul','RB','G')]:
            pa=self.endpoints[a];pb=self.endpoints[b]
            ab=pa['power']+pa['gain']+pb['gain']-self.system_loss-pb['threshold']
            ba=pb['power']+pb['gain']+pa['gain']-self.system_loss-pa['threshold']
            self.budgets[name]=min(ab,ba)
            self.directions.append({'link_type':name,'forward_loss_limit_db':ab,'reverse_loss_limit_db':ba,'bidirectional_limit_db':min(ab,ba),'receiver_threshold_dbm':self.threshold})
        origin=self.nodes['O01'];self.gateway=(origin['lon_deg'],origin['lat_deg'],origin['ground_elevation_m']+pars['固定网关 G01','hG'])
        lon=origin['lon_deg'];lat=origin['lat_deg']
        # 无线三维直线距离采用统一局部平面坐标；DEM与视线都在同一仿射网格。
        # WGS84原点处卯酉圈/子午圈半径校准米/度。此为公开的坐标近似，不把弧长冒充直线。
        aa=Q3CFG.wgs84_a_m;ee=Q3CFG.wgs84_e2;phi=math.radians(lat)
        N=aa/math.sqrt(1-ee*math.sin(phi)**2);M=aa*(1-ee)/(1-ee*math.sin(phi)**2)**1.5
        self.lon_m_per_deg=N*math.cos(phi)*math.pi/180;self.lat_m_per_deg=M*math.pi/180
        self.kx=abs(self.transform.a)*self.lon_m_per_deg
        self.ky=abs(self.transform.e)*self.lat_m_per_deg
        self.constant=Q3CFG.fspl_constant+20*math.log10(self.frequency)
        self.shadow_cache={};self.link_cache={}

    def grid_point(self,p):
        x,y=self.inv*(p[0],p[1]);return np.array([x,y,p[2]],np.float64)

    def geo_point(self,p):
        x,y=self.transform*(p[0],p[1]);return (x,y,p[2])

    def workpoint(self,sid):
        n=self.nodes[sid];return (n['lon_deg'],n['lat_deg'],n['ground_elevation_m']+(0 if sid=='O01' else CFG.service_work_height_m))

    def max_range(self,kind,blocked=False,buffer_db=0.):
        return Q3CFG.meters_per_km*10**((self.budgets[kind]-self.constant-(self.obs_loss if blocked else 0)-buffer_db)/20)

    def distance(self,a,b):
        return math.sqrt(((a[0]-b[0])*self.lon_m_per_deg)**2+((a[1]-b[1])*self.lat_m_per_deg)**2+(a[2]-b[2])**2)

    def link(self,a,b,kind):
        d=self.distance(a,b);obs=bool(_ray_blocked(self.grid_point(a),self.grid_point(b),self.dem))
        loss=-math.inf if d==0 else self.constant+20*math.log10(d/1000)+self.obs_loss*obs
        margin=self.budgets[kind]-loss
        return {'distance_m':d,'blocked':obs,'path_loss_db':loss,'margin_db':margin,'available':margin>=-Q3CFG.budget_tolerance_db}

    def shadows(self,a,b0,b1):
        key=(tuple(a),tuple(b0),tuple(b1))
        if key not in self.shadow_cache:
            raw,tested=_shadow_intervals(self.grid_point(a),self.grid_point(b0),self.grid_point(b1),self.dem)
            self.shadow_cache[key]=(union_intervals([(v[0],v[1]) for v in raw]),len(raw),tested)
        return self.shadow_cache[key]

    def distance_roots(self,a,b0,b1,limit):
        """固定局部米坐标中距离平方为二次函数，精确求阈值根。"""
        scale=np.array([self.lon_m_per_deg,self.lat_m_per_deg,1.])
        v=(np.asarray(b0)-np.asarray(a))*scale;w=(np.asarray(b1)-np.asarray(b0))*scale
        A=float(w@w);B=float(2*v@w);C=float(v@v-limit**2)
        if A<1e-20:return []
        disc=B*B-4*A*C
        if disc<0:return []
        d=math.sqrt(max(0.,disc));roots=[(-B-d)/(2*A),(-B+d)/(2*A)]
        return [float(s) for s in roots if 0.<s<1.]

    def profile(self,a,b0,b1,kind,buffer_db=0.):
        """所有阴影边界+双向预算距离根的精确分段；包含垂直和静止阶段。"""
        key=(tuple(a),tuple(b0),tuple(b1),kind,float(buffer_db))
        if key in self.link_cache:return self.link_cache[key]
        shadows,nshadow,ntested=self.shadows(a,b0,b1)
        cuts=[0.,1.]+[s for seg in shadows for s in seg]
        for obs in [False,True]:cuts+=self.distance_roots(a,b0,b1,self.max_range(kind,obs,buffer_db))
        cuts=sorted(set(cuts));rows=[];a=np.asarray(a);b0=np.asarray(b0);b1=np.asarray(b1)
        for lo,hi in zip(cuts,cuts[1:]):
            if hi-lo<1e-14:continue
            mid=(lo+hi)/2;obs=contains(shadows,mid,tol=0.0)
            d=self.distance(a,b0+(b1-b0)*mid)
            loss=-math.inf if d==0 else self.constant+20*math.log10(d/1000)+self.obs_loss*obs
            rows.append({'s0':lo,'s1':hi,'blocked':obs,'available':loss<=self.budgets[kind]-buffer_db+1e-10})
        result={'pieces':rows,'boundaries':cuts,'shadows':shadows,'occluding_cells':nshadow,'terrain_cells_tested':ntested}
        self.link_cache[key]=result;return result
