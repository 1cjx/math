"""绘图数据一致性核验，不替代原来的调度/连续通信物理验证。"""
from pathlib import Path
import json,csv,hashlib,sys,re
import numpy as np
import fitz
from viz.core import ROOT,EXP,OUT,sha,write_json

FAIL=[];CHECKS=[]
def check(name,predicate,details=''):
    r={'check':name,'passed':bool(predicate),'details':details};CHECKS.append(r)
    if not r['passed']:FAIL.append(r)
def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    manifests=json.loads((ROOT/'audit/render_manifest.json').read_text(encoding='utf-8'))
    check('独立图共163幅',len(manifests)==163)
    for row in manifests:
        code=row['图号'];d=json.loads((ROOT/'plot_data'/f'{code}.json').read_text(encoding='utf-8'))
        check(code+'包含中文图题',bool(re.search('[\u4e00-\u9fff]',d['title'])))
        for src,h in d['sources'].items():check(code+'源文件哈希:'+src,sha(EXP/src)==h)
        for ext in ('png','svg','pdf'):check(code+'.'+ext+'存在',(OUT/f'{code}.{ext}').exists())
        with fitz.open(OUT/f'{code}.pdf') as f:
            check(code+'矢量PDF单页',len(f)==1)
            check(code+'不是整页旧图截图',len(f[0].get_drawings())>2)
        svg=(OUT/f'{code}.svg').read_text(encoding='utf-8')
        for banned in ('科学图表美化版','Style refresh by code','no fabricated results','Data-driven result figure'):
            check(code+'无装饰性文案:'+banned,banned not in svg)
    def v(code):return json.loads((ROOT/'plot_data'/f'{code}.json').read_text(encoding='utf-8'))['values']
    boxes=readcsv(EXP/'data/cleaned/boxes.csv');check('真实货箱唯一80箱',len(boxes)==len({r['box_id'] for r in boxes})==80)
    check('堆叠需求数总计80',sum(sum(r['counts']) for r in v('F012'))==80)
    check('新增需求矩阵质量正确',abs(np.array(v('F157')['weight_kg']).sum()-sum(float(r['weight_kg']) for r in boxes))<1e-9)
    # 阶跃CDF和小提琴横截面源值逐组一致，不将KDE视为新增观测。
    cap=readcsv(EXP/'results/q1/capacity_sensitivity.csv');vp=v('F151')
    for st in vp['statistics']:
        rho=st['reserve_percent']/100;raw=np.array([float(r['max_safe_payload_kg']) for r in cap if r['model_id']=='C' and abs(float(r['reserve_fraction'])-rho)<1e-10])
        check('C型分布样本数'+str(rho),len(raw)==st['n_services']==15)
        for key,val in zip(('min','q1','median','q3','max'),np.quantile(raw,[0,.25,.5,.75,1])):check('分位统计'+str(rho)+key,abs(st[key]-val)<1e-10)
    mat=np.array(v('F152')['capacity_kg']);check('逐服务区余量增加载荷不增',np.all(np.diff(mat,axis=1)<=1e-7))
    # 独立表达式检查整个81x61能耗网格。
    d=v('F148');q=np.array(d['payload_grid_kg']);H=np.array(d['cruise_altitude_grid_m']);rt=d['route'];data=json.loads((EXP/'data/cleaned/model_inputs.json').read_text(encoding='utf-8'));g=next(x for x in data['transport_models'] if x['model_id']=='C')
    sys.path.insert(0,str(EXP/'src'));from config import CFG
    L=g['empty_range_m']-(g['empty_range_m']-g['full_range_m'])*(q/g['max_payload_kg'])**CFG.range_load_exponent
    hor=CFG.horizontal_energy_multiplier*g['usable_energy_kwh']*rt['distance_m']*(1/L+1/g['empty_range_m'])
    up=CFG.climb_energy_multiplier*CFG.gravity_m_s2/(g['climb_efficiency']*CFG.joules_per_kwh)*((g['empty_mass_kg']+q[None,:])*(H[:,None]-rt['depot_work_altitude_m'])+g['empty_mass_kg']*(H[:,None]-rt['service_work_altitude_m']))
    error=float(np.max(np.abs(hor[None,:]+up-np.array(d['energy_grid_kwh']))));check('4941个曲面网格值独立计算',error<1e-10,f'max_error_kwh={error}')
    check('曲面明示非现场观测',d['kind']=='deterministic_parameter_sweep_not_field_observations')
    points=d['actual_S008_point'];real=next(r for r in readcsv(EXP/'results/q1/batches_NET.csv') if r['service_id']=='S008')
    check('模型图中S008基准点真实',abs(points['energy_kwh']-float(real['energy_kwh']))<1e-10)
    r=v('F160');check('SOC累计能耗与源架次一致',abs(sum(x['energy_kwh'] for x in r['phase_energy'])-float(r['trip']['energy_kwh']))<1e-10)
    check('SOC返航端点一致',abs(r['soc_percent'][-1]-float(r['trip']['return_soc_fraction'])*100)<1e-9)
    check('真实候选点数量',len(v('F158')['records'])==5)
    check('Q3运输和中继任务未增造',len(readcsv(EXP/'results/q3/trips.csv'))==25 and len(readcsv(EXP/'results/q3/relay_sorties.csv'))==4)
    # 原求解成果文件在本轮前后逐字节保持。
    pin=ROOT/'audit/frozen_inputs.json'
    if pin.exists():
        expected=json.loads(pin.read_text(encoding='utf-8'))
        for rel,h in expected.items():check('冻结求解成果:'+rel,sha(EXP/rel)==h)
    result={'scope':'本轮原生绘图、数值聚合和文件继承验证；未重新求解优化器，也不替代原物理可行性证书。','checks':len(CHECKS),'failed':len(FAIL),'failures':FAIL,'source_F148_grid_points':len(q)*len(H),'max_surface_error_kwh':error}
    write_json(ROOT/'audit/figure_validation.json',result);write_json(ROOT/'audit/figure_validation_details.json',CHECKS)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if FAIL:raise SystemExit(1)
if __name__=='__main__':main()
