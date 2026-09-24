"""Q2/Q3共用运输轨迹：由已经验证的三阶段航段及交接台账构建。"""
from pathlib import Path
import numpy as np
from io_utils import read_csv
from config import CFG


def phases_from_tables(data,trip_rows,legs):
    models={m['model_id']:m for m in data['transport_models']}
    nodes={n['node_id']:n for n in data['depots']+data['services']}
    tripmap={r['trip_id']:r for r in trip_rows};out=[]
    def wp(s):
        n=nodes[s]
        return (n['lon_deg'],n['lat_deg'],n['ground_elevation_m']+(0 if s=='O01' else CFG.service_work_height_m))
    for l in legs:
        g=l['model_id'];m=models[g];p0=wp(l['from_id']);p1=wp(l['to_id']);H=float(l['cruise_altitude_m'])
        up=(p0[0],p0[1],H);dn=(p1[0],p1[1],H);t=float(l['departure_s'])
        specs=[('爬升',p0,up,float(l['climb_m'])/m['climb_speed_mps']),
               ('巡航',up,dn,float(l['distance_m'])/m['cruise_speed_mps']),
               ('下降',dn,p1,float(l['descent_m'])/m['descent_speed_mps'])]
        for phase,a,b,dt in specs:
            if dt>1e-12:
                out.append({'trip_id':l['trip_id'],'drone_id':tripmap[l['trip_id']]['drone_id'],
                    'leg_index':int(l['leg_index']),'from_id':l['from_id'],'to_id':l['to_id'],
                    'phase':phase,'start_s':t,'end_s':t+dt,'p0':tuple(a),'p1':tuple(b)})
            t+=dt
        if abs(t-float(l['arrival_s']))>1e-7:raise AssertionError('轨迹阶段时间不匹配')
        te=float(l['handoff_complete_s'])
        if te-t>1e-12:
            out.append({'trip_id':l['trip_id'],'drone_id':tripmap[l['trip_id']]['drone_id'],
                    'leg_index':int(l['leg_index']),'from_id':l['from_id'],'to_id':l['to_id'],
                    'phase':'投送交接','start_s':t,'end_s':te,'p0':p1,'p1':p1})
    for i,p in enumerate(out,1):p['phase_id']=f'PH-{i:04d}'
    return out


def load_phases(root,data,folder='results/q2'):
    root=Path(root)
    return phases_from_tables(data,read_csv(root/folder/'trips.csv'),read_csv(root/folder/'legs.csv'))


def position(p,t):
    f=(t-p['start_s'])/(p['end_s']-p['start_s'])
    return tuple(float(x) for x in np.array(p['p0'])+(np.array(p['p1'])-np.array(p['p0']))*f)


def serialize_phases(phases):
    return [{k:v for k,v in p.items() if k not in ('p0','p1')} | 
            {f'{pos}_{axis}':p[pos][i] for pos in ('p0','p1') for i,axis in enumerate(('lon_deg','lat_deg','altitude_m'))} for p in phases]
