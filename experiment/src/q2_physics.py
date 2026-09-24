"""核心物理模块：任意两节点地形、动态剩余载荷、逐箱交接和电池两阶段充电。
Python 3.13.5；numpy 2.3.5，rasterio 1.5.0，pyproj 3.7.2。
公共能耗假设与Q1相同，详见config.py的PARAMETER_PROVENANCE。
"""
from __future__ import annotations
from collections import defaultdict
from functools import lru_cache
from itertools import permutations
from pathlib import Path
import json, math
import numpy as np
import rasterio
from config import CFG
from q2_config import Q2CFG
from physics import GEOD, segment_cells, effective_range
from io_utils import save_json, write_csv


def charge_duration(soc: float, full_s: float) -> float:
    """剩余SOC→100%；在90%处连续，90%以上仅慢充；满电需0秒。"""
    if not -Q2CFG.numeric_tolerance <= soc <= 1+Q2CFG.numeric_tolerance:
        raise ValueError('SOC必须位于[0,1]')
    soc=max(0.0,min(1.0,soc));k=Q2CFG.charge_knee_fraction
    return full_s*(Q2CFG.charge_fast_time_fraction*max(0.0,k-soc)/k+
        Q2CFG.charge_slow_time_fraction*(1-max(k,soc))/(1-k))


def all_arcs(root: Path, data: dict):
    """完整16节点有向图：120个无向逐像元剖面，240条有向三阶段航段。"""
    nodes=sorted(data['depots']+data['services'],key=lambda r:r['node_id'])
    with rasterio.open(root/'data/cleaned/geospatial/dem_clean.tif') as ds:
        arr=ds.read(1);tr=ds.transform
    rows=[];profiles=[];geom={}
    for i,a in enumerate(nodes):
        for j,b in enumerate(nodes):
            if i>=j:continue
            cells=segment_cells(a['lon_deg'],a['lat_deg'],b['lon_deg'],b['lat_deg'],tr)
            zz=[]
            for rr,cc,t in cells:
                if not(0<=rr<arr.shape[0] and 0<=cc<arr.shape[1]):raise ValueError('航段越出DEM')
                z=float(arr[rr,cc])
                if not math.isfinite(z) or z==CFG.nodata_value:raise ValueError('航段存在NoData')
                zz.append(z)
                profiles.append({'from_id':a['node_id'],'to_id':b['node_id'],'row':rr,'col':cc,'fraction':t,'dem_m':z})
            H=max(zz)+CFG.terrain_clearance_m
            d=GEOD.inv(a['lon_deg'],a['lat_deg'],b['lon_deg'],b['lat_deg'])[2]
            for fr,to in [(a,b),(b,a)]:
                zf=fr['ground_elevation_m']+(CFG.depot_work_height_m if fr['node_id']=='O01' else CFG.service_work_height_m)
                zt=to['ground_elevation_m']+(CFG.depot_work_height_m if to['node_id']=='O01' else CFG.service_work_height_m)
                if H<max(zf,zt):raise ValueError('题定作业海拔超过规则巡航海拔')
                r={'from_id':fr['node_id'],'to_id':to['node_id'],'distance_m':d,'terrain_max_m':max(zz),
                   'cruise_altitude_m':H,'origin_work_altitude_m':zf,'destination_work_altitude_m':zt,
                   'climb_m':H-zf,'descent_m':H-zt,'crossed_cells':len(cells)}
                geom[(fr['node_id'],to['node_id'])]=r;rows.append(r)
    write_csv(root/'results/q2/arc_geometry.csv',rows)
    write_csv(root/'results/q2/arc_dem_cells.csv',profiles)
    return geom


class Problem:
    def __init__(self, root: Path, data: dict, geom: dict | None=None):
        self.root=Path(root);self.data=data
        self.boxes=sorted(data['boxes'],key=lambda b:b['box_id'])
        self.box_index={b['box_id']:i for i,b in enumerate(self.boxes)}
        self.models={m['model_id']:m for m in data['transport_models']}
        self.geom=geom if geom is not None else all_arcs(self.root,data)
        self.fleet={g:sorted(x['drone_id'] for x in data['transport_drones'] if x['model_id']==g) for g in self.models}
        self.battery_par={b['model_id']:b for b in data['transport_batteries']}
        self.batteries={g:[f'{g}-BAT-{i+1:02d}' for i in range(self.battery_par[g]['count'])] for g in self.models}
        self.bid=tuple(b['box_id'] for b in self.boxes)
        self.sid=tuple(b['service_id'] for b in self.boxes)
        self.weight=np.array([b['weight_kg'] for b in self.boxes])
        self.volume=np.array([b['volume_m3'] for b in self.boxes])
        self.priority=np.array([b['priority'] for b in self.boxes])
        self.expected=np.array([b['expected_s'] for b in self.boxes])
        self.hard=np.array([min([b['expected_s']] if b['material_type']=='医疗物资' else [math.inf]) for b in self.boxes])
        for i,b in enumerate(self.boxes):
            if b['is_first_batch']:self.hard[i]=min(self.hard[i],b['first_deadline_s'])
        # 同一服务点内的交接顺序规则也是模型选择，公开、可核验且对硬约束优先。
        self.delivery_key=tuple((self.hard[i],self.expected[i],-self.priority[i],b['box_id']) for i,b in enumerate(self.boxes))
        self.arc_values={}
        for g,m in self.models.items():
            for (u,v),r in self.geom.items():
                t=r['climb_m']/m['climb_speed_mps']+r['distance_m']/m['cruise_speed_mps']+r['descent_m']/m['descent_speed_mps']
                self.arc_values[g,u,v]=(t,r['distance_m'],r['climb_m'])
        self.evaluate=lru_cache(maxsize=Q2CFG.cache_size)(self._evaluate)

    def _evaluate(self, trip: tuple):
        """trip=(机型,有序服务区tuple,箱索引tuple)。返回None表示物理不可行。"""
        g,stops,ids=trip
        if not ids or len(set(ids))!=len(ids) or len(stops)!=len(set(stops)):return None
        if set(stops)!={self.sid[i] for i in ids} or len(stops)>Q2CFG.maximum_stops:return None
        m=self.models[g];weight=sum(float(self.weight[i]) for i in ids);volume=sum(float(self.volume[i]) for i in ids)
        if weight>m['max_payload_kg']+CFG.capacity_tolerance_kg or volume>m['volume_m3']+CFG.geometry_tolerance:return None
        q=weight;t=m['prepare_s']+m['load_per_box_s']*len(ids);pre=t;energy=0.0;flight=0.0;offsets=[];u='O01'
        for v in stops+('O01',):
            ft,d,h=self.arc_values[g,u,v]
            energy+=CFG.horizontal_energy_multiplier*m['usable_energy_kwh']*d/effective_range(m,q)
            energy+=CFG.climb_energy_multiplier*(m['empty_mass_kg']+q)*CFG.gravity_m_s2*h/(m['climb_efficiency']*CFG.joules_per_kwh)
            t+=ft;flight+=ft
            if v!='O01':
                t+=m['handoff_base_s']
                for i in sorted((i for i in ids if self.sid[i]==v),key=lambda i:self.delivery_key[i]):
                    t+=m['handoff_per_box_s'];offsets.append((i,t));q-=float(self.weight[i])
            u=v
        if energy>(1-m['reserve_fraction'])*m['usable_energy_kwh']+Q2CFG.energy_tolerance_kwh:return None
        soc=1-energy/m['usable_energy_kwh']
        # 最晚开始时刻由每一箱的硬时限以及它的交接完成偏移共同决定。
        hard_start=min(self.hard[i]-off for i,off in offsets)
        soft_start=min(self.expected[i]-off for i,off in offsets)
        return {'duration':t,'energy':energy,'soc':soc,'charge':charge_duration(soc,self.battery_par[g]['full_charge_s']),
                'offsets':tuple(offsets),'hard_latest_start':hard_start,'soft_latest_start':soft_start,
                'weight':weight,'volume':volume,'flight':flight,'preparation':pre}

    def trip(self, g, stops, ids):
        ids=tuple(sorted(ids));used={self.sid[i] for i in ids}
        return (g,tuple(s for s in stops if s in used),ids)

    def options_insert(self,trip,indices):
        """插入新箱/新服务区时枚举全部插入位置；同一区域不重复访问。"""
        g,stops,ids=trip;new=tuple(sorted(set(ids)|set(indices)))
        newstops=sorted({self.sid[i] for i in new}-set(stops));orders=[stops]
        for sid in newstops:
            orders=[o[:k]+(sid,)+o[k:] for o in orders for k in range(len(o)+1)]
        return [(g,o,new) for o in orders]

    def schedule(self, trips, detailed=False):
        """列表调度：每个任务选最早空闲的兼容机身和满电电池；不制造额外资源。
        开始=准备开始，电池从开始至返航一直独占，返航后立即并行充满。
        """
        da={g:[0.0]*len(self.fleet[g]) for g in self.models};ba={g:[0.0]*len(self.batteries[g]) for g in self.models}
        late_h=0.0;late_s=0.0;weighted_c=0.0;cmax=0.0;energy=0.0;records=[]
        for j,tr in enumerate(trips):
            ev=self.evaluate(tr)
            if ev is None:return None
            g=tr[0];di=min(range(len(da[g])),key=da[g].__getitem__);bi=min(range(len(ba[g])),key=ba[g].__getitem__)
            start=max(da[g][di],ba[g][bi]);end=start+ev['duration']
            da[g][di]=end;ba[g][bi]=end+ev['charge'];cmax=max(cmax,end);energy+=ev['energy']
            for i,off in ev['offsets']:
                c=start+off;late_h+=max(0.0,c-self.hard[i]);late_s+=float(self.priority[i])*max(0.0,c-self.expected[i]);weighted_c+=float(self.priority[i])*c
            if detailed:records.append({'trip':tr,'eval':ev,'start':start,'end':end,'drone_id':self.fleet[g][di],
                    'battery_id':self.batteries[g][bi],'charge_start':end,'charge_end':ba[g][bi]})
        return {'hard_late_s':late_h,'weighted_tardiness_s':late_s,'makespan_s':cmax,'energy_kwh':energy,
                'trips':len(trips),'weighted_completion_s':weighted_c,'records':records}
