"""核心算法模块1：逐像元地形净空、载荷-能耗与单调二分安全载荷。
实测 Python 3.13.5；numpy 2.3.5，rasterio 1.5.0，pyproj 3.7.2。
能耗两分项采用config中明确记录的补充假设；下降附加能耗为0。
"""
import math
import numpy as np
from pyproj import Geod
from config import CFG

GEOD=Geod(ellps='WGS84')

def segment_cells(lon0,lat0,lon1,lat1,transform):
    """Supercover：枚举线段穿越的全部像元，含恰好接触边界的相邻像元。
    在像元连续坐标中计算所有整数网格线交点参数t，区间中点确定像元。
    不使用固定步长抽样估计最大值，因此不会跳过窄峰像元。
    """
    x0,y0=(~transform)*(lon0,lat0);x1,y1=(~transform)*(lon1,lat1)
    dx,dy=x1-x0,y1-y0; ts=[0.0,1.0]
    for a,b in [(x0,x1),(y0,y1)]:
        if abs(b-a)>CFG.geometry_tolerance:
            for k in range(math.ceil(min(a,b)),math.floor(max(a,b))+1):
                t=(k-a)/(b-a)
                if 0.0<t<1.0:ts.append(t)
    ts=sorted(set(ts)); cells={}
    def add(t):
        x,y=x0+dx*t,y0+dy*t
        cs=[math.floor(x)];rs=[math.floor(y)]
        if abs(x-round(x))<CFG.geometry_tolerance:cs=[round(x)-1,round(x)]
        if abs(y-round(y))<CFG.geometry_tolerance:rs=[round(y)-1,round(y)]
        for r in rs:
            for c in cs:cells[(r,c)]=min(t,cells.get((r,c),t))
    for a,b in zip(ts,ts[1:]):add((a+b)/2)
    for t in ts:add(t)
    return [(r,c,t) for (r,c),t in sorted(cells.items(),key=lambda x:(x[1],x[0]))]

def route_info(depot,node,arr,transform):
    lon0,lat0=depot['lon_deg'],depot['lat_deg'];lon1,lat1=node['lon_deg'],node['lat_deg']
    distance=GEOD.inv(lon0,lat0,lon1,lat1)[2]
    cells=segment_cells(lon0,lat0,lon1,lat1,transform)
    profile=[]
    for r,c,t in cells:
        if not(0<=r<arr.shape[0] and 0<=c<arr.shape[1]):raise ValueError('航线越出DEM')
        z=float(arr[r,c])
        if not math.isfinite(z) or z==CFG.nodata_value:raise ValueError('航线经过无效DEM，拒绝自动插值低估山峰')
        lon,lat=transform*(c+0.5,r+0.5)
        profile.append({'service_id':node['node_id'],'row':r,'col':c,'fraction':t,'along_m':distance*t,
                        'lon_center_deg':lon,'lat_center_deg':lat,'dem_m':z})
    maximum=max(r['dem_m'] for r in profile); cruise=maximum+CFG.terrain_clearance_m
    z0=depot['ground_elevation_m']+CFG.depot_work_height_m
    zi=node['ground_elevation_m']+CFG.service_work_height_m
    if cruise<max(z0,zi):raise ValueError('题定作业高度超过规则巡航海拔，应审核而非静默修改')
    # 将WGS84测地线分段后再次逐像元遍历，检查经纬度直线近似的影响。
    intermediate=GEOD.npts(lon0,lat0,lon1,lat1,max(1,math.ceil(distance/CFG.route_check_step_m)-1))
    pts=[(lon0,lat0)]+intermediate+[(lon1,lat1)]; gc=set()
    for a,b in zip(pts,pts[1:]):gc.update((r,c) for r,c,_ in segment_cells(*a,*b,transform))
    gcmax=max(float(arr[r,c]) for r,c in gc)
    # 对照30m等距点采样；仅用于显示潜在漏峰，不作为主算法。
    tt=np.linspace(0,1,max(2,math.ceil(distance/CFG.diagnostic_coarse_step_m)+1))
    inv=~transform
    samplemax=max(float(arr[math.floor((inv*(lon0+(lon1-lon0)*t,lat0+(lat1-lat0)*t))[1]),
                                    math.floor((inv*(lon0+(lon1-lon0)*t,lat0+(lat1-lat0)*t))[0])]) for t in tt)
    info={'service_id':node['node_id'],'distance_m':distance,'terrain_max_m':maximum,'cruise_altitude_m':cruise,
          'depot_work_altitude_m':z0,'service_work_altitude_m':zi,'outbound_climb_m':cruise-z0,
          'outbound_descent_m':cruise-zi,'inbound_climb_m':cruise-zi,'inbound_descent_m':cruise-z0,
          'crossed_cells':len(cells),'geodesic_terrain_max_m':gcmax,'geodesic_max_difference_m':gcmax-maximum,
          'coarse_sample_max_m':samplemax,'coarse_sampling_underestimate_m':maximum-samplemax}
    return info,profile

def effective_range(model,q):
    return model['empty_range_m']-(model['empty_range_m']-model['full_range_m'])*(q/model['max_payload_kg'])**CFG.range_load_exponent

def trip_energy(model,route,q):
    """去程满批载荷q，服务区完全卸货，返程q=0；质量均含机身及电池。"""
    d=route['distance_m'];e=model['usable_energy_kwh'];m=model['empty_mass_kg'];eta=model['climb_efficiency']
    hor_out=CFG.horizontal_energy_multiplier*e*d/effective_range(model,q);hor_back=CFG.horizontal_energy_multiplier*e*d/model['empty_range_m']
    up_out=CFG.climb_energy_multiplier*(m+q)*CFG.gravity_m_s2*route['outbound_climb_m']/(eta*CFG.joules_per_kwh)
    up_back=CFG.climb_energy_multiplier*m*CFG.gravity_m_s2*route['inbound_climb_m']/(eta*CFG.joules_per_kwh)
    return {'outbound_horizontal_kwh':hor_out,'inbound_horizontal_kwh':hor_back,
            'outbound_climb_kwh':up_out,'inbound_climb_kwh':up_back,
            'energy_kwh':hor_out+hor_back+up_out+up_back}

def trip_time(model,route,n):
    out=route['outbound_climb_m']/model['climb_speed_mps']+route['distance_m']/model['cruise_speed_mps']+route['outbound_descent_m']/model['descent_speed_mps']
    back=route['inbound_climb_m']/model['climb_speed_mps']+route['distance_m']/model['cruise_speed_mps']+route['inbound_descent_m']/model['descent_speed_mps']
    preparation=model['prepare_s']+n*model['load_per_box_s'];handoff=model['handoff_base_s']+n*model['handoff_per_box_s']
    return {'outbound_flight_s':out,'inbound_flight_s':back,'flight_time_s':out+back,
            'preparation_load_s':preparation,'handoff_s':handoff,'airborne_service_s':out+back+handoff,
            'operation_time_s':preparation+out+back+handoff}

def safe_payload(model,route,reserve=None):
    rho=model['reserve_fraction'] if reserve is None else reserve
    budget=(1-rho)*model['usable_energy_kwh'];Q=model['max_payload_kg']
    e0=trip_energy(model,route,0)['energy_kwh'];eQ=trip_energy(model,route,Q)['energy_kwh']
    if e0>budget+CFG.energy_tolerance_kwh:q=None;lim='empty_trip_infeasible'
    elif eQ<=budget:q=Q;lim='rated_payload'
    else:
        lo,hi=0.0,Q
        for _ in range(CFG.bisection_iterations):
            mid=(lo+hi)/2
            if trip_energy(model,route,mid)['energy_kwh']<=budget:lo=mid
            else:hi=mid
        q=lo;lim='energy'
    return {'service_id':route['service_id'],'model_id':model['model_id'],'reserve_fraction':rho,
            'max_safe_payload_kg':q,'limiting_factor':lim,'empty_trip_energy_kwh':e0,
            'rated_payload_trip_energy_kwh':eQ,'energy_budget_kwh':budget,
            'full_payload_reserve_threshold':1-eQ/model['usable_energy_kwh']}
