"""核心联合调度：连续通信的可行开始时间窗与机身/电池列表解码。
Python 3.13.5。接入/回传均双向；无多跳；同一中继可服务多个运输机，
题面未给带宽/连接数上限，不虚构独占单用户限制。
"""
from __future__ import annotations
from functools import lru_cache
import math
import numpy as np
from config import CFG
from q2_config import Q2CFG
from q3_config import Q3CFG
from q2_physics import Problem,charge_duration
from q3_communication import _line_peak,contains
from physics import GEOD


def merge_time_intervals(rows):
    result=[]
    for a,b in sorted(rows):
        if b<a-1e-9:continue
        if result and a<=result[-1][1]+1e-9:result[-1]=(result[-1][0],max(b,result[-1][1]))
        else:result.append((a,b))
    return result


def intersect_time(aa,bb):
    out=[]
    for a,b in aa:
        for c,d in bb:
            lo=max(a,c);hi=min(b,d)
            if lo<=hi+1e-9:out.append((lo,max(lo,hi)))
    return merge_time_intervals(out)


def relay_geometry(radio,site,model):
    p=(site['lon'],site['lat'],site['alt']);origin=radio.workpoint('O01')
    ground=float(radio.dem[int(site['row']),int(site['col'])])
    H=float(_line_peak(radio.grid_point(origin),radio.grid_point(p),radio.dem))+CFG.terrain_clearance_m
    if not math.isfinite(H):raise ValueError('中继航线NoData')
    if not ground<p[2]<=ground+model['max_hover_agl_m']+1e-8:raise ValueError('非法悬停离地高度')
    # 采用完全符合原巡航规则的候选子空间，绝不把负下降量截成0。
    if p[2]>H+1e-8 or H<origin[2]:raise ValueError('中继悬停海拔超过题定巡航海拔，本候选域拒绝而不擅自抬高巡航高度')
    d=GEOD.inv(origin[0],origin[1],p[0],p[1])[2]
    up1=H-origin[2];dn1=H-p[2];up2=dn1;dn2=up1
    t1=up1/model['climb_speed_mps']+d/model['cruise_speed_mps']+dn1/model['descent_speed_mps']
    t2=up2/model['climb_speed_mps']+d/model['cruise_speed_mps']+dn2/model['descent_speed_mps']
    eh=2*model['cruise_power_kw']*d/model['cruise_speed_mps']/Q3CFG.seconds_per_hour
    eu=model['takeoff_mass_kg']*CFG.gravity_m_s2*(up1+up2)/(model['climb_efficiency']*CFG.joules_per_kwh)
    return {'point':p,'terrain_ground_m':ground,'hover_agl_m':p[2]-ground,'cruise_altitude_m':H,
        'horizontal_distance_m':d,'outbound_climb_m':up1,'outbound_descent_m':dn1,
        'inbound_climb_m':up2,'inbound_descent_m':dn2,'outbound_flight_s':t1,'inbound_flight_s':t2,
        'horizontal_energy_kwh':eh,'climb_energy_kwh':eu,'flight_energy_kwh':eh+eu}


def make_relay_missions(radio,sites,first_ends=Q3CFG.early_service_end_s,late_end=Q3CFG.late_service_end_s):
    """四架次、两机两轮的搜索初始模板；位置由全域候选算法求得。
    首轮R01/R02，次轮在各自返回后周转并重新准备；四个不同组件来自6组库存。
    """
    data=radio.data;m=data['relay_models'][0];ep=data['relay_energy'][0]
    drones=sorted(r['drone_id'] for r in data['relay_drones'])
    if len(drones)<2 or ep['count']<4:raise ValueError('当前四架次初始模板所需库存不满足')
    missions=[]
    for j,site in enumerate(sites):
        geo=relay_geometry(radio,site,m)
        start=0. if j<2 else missions[j-2]['return_s']+m['turnaround_s']
        arrived=start+m['prepare_s']+geo['outbound_flight_s'];linked=arrived+m['link_setup_s']
        end=first_ends[j] if j<2 else late_end
        if end<linked:raise ValueError('中继服务结束早于建链')
        energy=geo['flight_energy_kwh']+(m['hover_power_kw']+m['communication_power_kw'])*(end-arrived)/Q3CFG.seconds_per_hour
        returned=end+geo['inbound_flight_s'];soc=1-energy/m['usable_energy_kwh']
        if soc<m['reserve_fraction']-1e-9:raise ValueError('中继架次超过能源预算')
        missions.append({'relay_trip_id':f'Q3-R-{j+1:03d}','relay_drone_id':drones[j%2],
            'energy_module_id':f"R-ENG-{j+1:02d}",'model_id':m['model_id'],'site_id':site.get('site_id',f'SITE-{j+1:03d}'),
            'start_s':start,'arrival_s':arrived,'link_complete_s':linked,'service_end_s':end,'return_s':returned,
            'turnaround_end_s':returned+m['turnaround_s'],'energy_kwh':energy,'return_soc_fraction':soc,
            'charge_duration_s':charge_duration(soc,ep['full_charge_s']),
            'charge_end_s':returned+charge_duration(soc,ep['full_charge_s']),**geo})
    return missions


class JointProblem(Problem):
    def __init__(self,root,data,radio,sites,missions,geom=None):
        self.radio=radio;self.sites=sites;self.missions=missions;self.pattern_cache={};self.arc_patterns={}
        super().__init__(root,data,geom)
        self.base_hard=self.hard.copy()
        self._window_violations=0
        self.fail_window_penalty_s=Q3CFG.search_invalid_window_penalty_s

    def pattern(self,b0,b1):
        key=(tuple(b0),tuple(b1))
        if key in self.pattern_cache:return self.pattern_cache[key]
        direct=self.radio.profile(self.radio.gateway,b0,b1,'direct',Q3CFG.search_budget_buffer_db)
        acc=[self.radio.profile(m['point'],b0,b1,'access',Q3CFG.search_budget_buffer_db) for m in self.missions]
        cuts=sorted(set([s for p in [direct]+acc for s in p['boundaries']]))
        out=[]
        def usable(p,s):return next((z['available'] for z in p['pieces'] if z['s0']<=s<=z['s1']),False)
        for lo,hi in zip(cuts,cuts[1:]):
            if hi-lo<1e-13:continue
            mid=(lo+hi)/2
            if usable(direct,mid):continue
            mask=tuple(j for j,p in enumerate(acc) if usable(p,mid))
            if out and mask==out[-1][2] and abs(lo-out[-1][1])<1e-12:out[-1]=(out[-1][0],hi,mask)
            else:out.append((lo,hi,mask))
        # 单点阴影接触：所有实际边界也单独校验，防止闭区间瞬时中断被忽略。
        for s in cuts:
            pos=tuple(np.array(b0)+(np.array(b1)-np.array(b0))*s)
            if self.radio.link(self.radio.gateway,pos,'direct')['margin_db']>=Q3CFG.search_budget_buffer_db-1e-8:continue
            mask=tuple(j for j,m in enumerate(self.missions) if self.radio.link(m['point'],pos,'access')['margin_db']>=Q3CFG.search_budget_buffer_db-1e-8)
            out.append((s,s,mask))
        out.sort();self.pattern_cache[key]=out;return out

    def arc_pattern(self,u,v,g):
        key=(u,v,g)
        if key in self.arc_patterns:return self.arc_patterns[key]
        ar=self.geom[u,v];m=self.models[g];a=self.radio.workpoint(u);b=self.radio.workpoint(v);H=ar['cruise_altitude_m']
        aa=(a[0],a[1],H);bb=(b[0],b[1],H)
        result=[];t=0.
        for p0,p1,dt in [(a,aa,ar['climb_m']/m['climb_speed_mps']),
                         (aa,bb,ar['distance_m']/m['cruise_speed_mps']),
                         (bb,b,ar['descent_m']/m['descent_speed_mps'])]:
            if dt>1e-12:
                for lo,hi,mask in self.pattern(p0,p1):result.append((t+lo*dt,t+hi*dt,mask))
            t+=dt
        self.arc_patterns[key]=(t,result);return t,result

    def _evaluate(self,trip):
        ev=super()._evaluate(trip)
        if ev is None:return None
        g,stops,ids=trip;m=self.models[g];t=ev['preparation'];allowed=[(0.,math.inf)];u='O01'
        # 给定一段空间中继可用集合，求覆盖整个时间段的允许准备开始区间。
        def restrict(aa,lo,hi,mask):
            if not mask:return []
            windows=merge_time_intervals([(self.missions[j]['link_complete_s']+Q3CFG.service_time_buffer_s,
                                           self.missions[j]['service_end_s']-Q3CFG.service_time_buffer_s) for j in mask])
            return intersect_time(aa,[(a-lo,b-hi) for a,b in windows if b-a>=hi-lo-1e-9])
        for v in stops+('O01',):
            dt,pieces=self.arc_pattern(u,v,g)
            for lo,hi,mask in pieces:
                allowed=restrict(allowed,t+lo,t+hi,mask)
                if not allowed:return None
            t+=dt
            if v!='O01':
                n=sum(self.sid[i]==v for i in ids);h=m['handoff_base_s']+m['handoff_per_box_s']*n
                for lo,hi,mask in self.pattern(self.radio.workpoint(v),self.radio.workpoint(v)):
                    allowed=restrict(allowed,t+lo*h,t+hi*h,mask)
                    if not allowed:return None
                t+=h
            u=v
        return {**ev,'start_windows':allowed}

    def schedule(self,trips,detailed=False):
        da={g:[0.]*len(self.fleet[g]) for g in self.models};ba={g:[0.]*len(self.batteries[g]) for g in self.models}
        late_h=0.;late_s=0.;wc=0.;cmax=0.;energy=0.;records=[];invalid=0
        for tr in trips:
            ev=self.evaluate(tr)
            if ev is None:return None
            g=tr[0];di=min(range(len(da[g])),key=da[g].__getitem__);bi=min(range(len(ba[g])),key=ba[g].__getitem__)
            ready=max(da[g][di],ba[g][bi]);start=None
            for lo,hi in ev['start_windows']:
                if max(ready,lo)<=hi+1e-8:start=max(ready,lo);break
            if start is None:
                # 搜索中以显式违约标志/大罚项引导修复；导出门禁会拒绝非零。
                invalid+=1;start=ready
            end=start+ev['duration'];da[g][di]=end;ba[g][bi]=end+ev['charge'];cmax=max(cmax,end);energy+=ev['energy']
            for i,off in ev['offsets']:
                complete=start+off;late_h+=max(0.,complete-self.hard[i]);late_s+=float(self.priority[i])*max(0.,complete-self.expected[i]);wc+=float(self.priority[i])*complete
            if detailed:records.append({'trip':tr,'eval':ev,'start':start,'end':end,'drone_id':self.fleet[g][di],
                                        'battery_id':self.batteries[g][bi],'charge_start':end,'charge_end':ba[g][bi]})
        return {'hard_late_s':late_h+self.fail_window_penalty_s*invalid,'source_hard_late_s':late_h,
                'communication_window_violations':invalid,'weighted_tardiness_s':late_s,'makespan_s':cmax,
                'energy_kwh':energy,'trips':len(trips),'weighted_completion_s':wc,'records':records}
