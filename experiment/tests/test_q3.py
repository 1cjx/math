"""第三问独立算法单测与故意错误提交拒绝测试。运行 python -m unittest discover -s tests -v。"""
import sys,json,copy,unittest,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from io_utils import read_csv
from q3_communication import Radio,_ray_blocked,_shadow_intervals,union_intervals
from q3_validation import IndependentRadio,independent_blocked,independent_shadows,merge01,validate_relay,validate_communication,independent_arcs,independent_phases
from q3_config import Q3CFG

class Q3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/cleaned/model_inputs.json').read_text());cls.ir=IndependentRadio(ROOT,cls.data);cls.radio=Radio(ROOT,cls.data)
        cls.relay_rows=read_csv(ROOT/'results/q3/Q3_中继架次.csv');_,cls.relay=validate_relay(cls.data,cls.ir,cls.relay_rows)
        cls.tr=read_csv(ROOT/'results/q3/Q3_运输架次.csv');cls.bx=read_csv(ROOT/'results/q3/Q3_逐箱交付.csv');cls.comm=read_csv(ROOT/'results/q3/Q3_通信保障.csv')
        cls.phases=independent_phases(cls.data,independent_arcs(ROOT,cls.data),cls.tr,cls.bx)
        # 只选一个真实有中继的运输架次进行故意破坏，避免全场景重复计算。
        cls.tid=next(x['运输架次编号'] for x in cls.comm if x['保障方式']=='中继')
        cls.oneph=[p for p in cls.phases if p['trip_id']==cls.tid];cls.onecom=[r for r in cls.comm if r['运输架次编号']==cls.tid]
    def test_raw_budgets_are_bidirectional(self):
        self.assertEqual(self.radio.budgets,{'direct':122.,'access':116.,'backhaul':126.});self.assertEqual(self.ir.limits,self.radio.budgets)
    def test_fspl_source_constant(self):self.assertEqual(Q3CFG.fspl_constant,32.45)
    def test_declared_local_coordinate_consistency(self):
        a=self.radio.gateway;b=self.relay[0]['point'];self.assertAlmostEqual(self.radio.distance(a,b),np.linalg.norm((np.array(b)-a)*self.ir.scale),places=8)
    def test_blockage_adds_loss_not_always_outage(self):
        a=self.radio.gateway;b=self.radio.workpoint('O01');self.assertTrue(self.radio.link(a,b,'direct')['available'])
    def test_independent_ray_on_random_terrain(self):
        rng=np.random.default_rng(20260923);z=rng.uniform(0,10,(12,12))
        for _ in range(60):
            a=np.r_[rng.uniform(.1,11.9,2),rng.uniform(7,20)];b=np.r_[rng.uniform(.1,11.9,2),rng.uniform(7,20)]
            self.assertEqual(bool(_ray_blocked(a,b,z)),bool(independent_blocked(a,b,z)))
    def test_continuous_shadow_not_sparse_endpoints(self):
        z=np.zeros((10,10));z[4,6]=15;a=np.array([.5,.5,10.]);b=np.array([9.5,1.5,10.]);c=np.array([9.5,8.5,10.])
        self.assertFalse(_ray_blocked(a,b,z));self.assertFalse(_ray_blocked(a,c,z))
        main=union_intervals([(x[0],x[1]) for x in _shadow_intervals(a,b,c,z)[0]]);other=merge01(independent_shadows(a,b,c,z)[0]);self.assertTrue(main);np.testing.assert_allclose(main,other,atol=1e-10)
        q=(main[0][0]+main[0][1])/2;self.assertTrue(independent_blocked(a,b+(c-b)*q,z))
    def test_vertical_shadow_independent(self):
        z=np.zeros((10,10));z[2,4]=8;a=np.array([.5,.5,10.]);b=np.array([8.5,4.5,3.]);c=np.array([8.5,4.5,20.])
        main=union_intervals([(x[0],x[1]) for x in _shadow_intervals(a,b,c,z)[0]]);other=merge01(independent_shadows(a,b,c,z)[0]);np.testing.assert_allclose(main,other,atol=1e-9)
    def test_original_q3_independent_proof(self):
        q=json.loads((ROOT/'results/q3/independent_validation.json').read_text());self.assertEqual(q['checks_failed'],0);self.assertEqual(q['continuous_atoms_failed'],0);self.assertEqual(q['dense_failed'],0)
    def test_bad_relay_energy_rejected(self):
        x=copy.deepcopy(self.relay_rows);x[0]['架次能耗（kWh）']=float(x[0]['架次能耗（kWh）'])+.1
        ck,_=validate_relay(self.data,self.ir,x);self.assertTrue(any(not c['pass'] and c['check'].endswith('/energy_formula') for c in ck))
    def test_300m_AGL_rejected(self):
        x=copy.deepcopy(self.relay_rows);x[0]['悬停海拔（m）']=float(x[0]['悬停海拔（m）'])+400
        ck,_=validate_relay(self.data,self.ir,x);self.assertTrue(any(not c['pass'] and c['check'].endswith('/AGL_cap') for c in ck))
    def test_wrong_energy_component_rejected(self):
        x=copy.deepcopy(self.relay_rows);x[0]['能源组件编号']='R-ENG-99';ck,_=validate_relay(self.data,self.ir,x);self.assertTrue(any(not c['pass'] for c in ck))
    def test_no_relay_turnaround_rejected(self):
        x=copy.deepcopy(self.relay_rows);x[2]['开始时刻（s）']=0.;ck,_=validate_relay(self.data,self.ir,x);self.assertTrue(any(not c['pass'] and '/reuse_' in c['check'] for c in ck))
    def test_continuous_gap_rejected(self):
        x=copy.deepcopy(self.onecom);idx=next(i for i,r in enumerate(x) if float(r['结束时刻（s）'])>float(r['开始时刻（s）']));x.pop(idx)
        ck,_,_=validate_communication(self.data,self.ir,self.oneph,self.relay,x,dense=False);self.assertTrue(any(not c['pass'] and ('no_gap' in c['check'] or 'takeoff_boundary' in c['check']) for c in ck))
    def test_missing_instant_rejected(self):
        x=copy.deepcopy(self.onecom);idx=next(i for i,r in enumerate(x) if float(r['结束时刻（s）'])==float(r['开始时刻（s）']));x.pop(idx)
        ck,_,_=validate_communication(self.data,self.ir,self.oneph,self.relay,x,dense=False);self.assertTrue(any(not c['pass'] and 'all_boundary' in c['check'] for c in ck))
    def test_duplicate_provider_point_rejected(self):
        x=copy.deepcopy(self.onecom);x.append(next(copy.deepcopy(r) for r in x if r['开始时刻（s）']==r['结束时刻（s）']))
        ck,_,_=validate_communication(self.data,self.ir,self.oneph,self.relay,x,dense=False);self.assertTrue(any(not c['pass'] and 'unique_point' in c['check'] for c in ck))
    def test_missing_backhaul_readiness_rejected(self):
        rel=copy.deepcopy(self.relay)
        for x in rel:x['link_s']=1e8
        ck,_,_=validate_communication(self.data,self.ir,self.oneph,rel,self.onecom,dense=False);self.assertTrue(any(not c['pass'] and 'relay_time_coverage' in c['check'] for c in ck))
    def test_use_relay_when_direct_available_rejected(self):
        x=copy.deepcopy(self.onecom);r=next(r for r in x if r['保障方式']=='直连' and r['开始时刻（s）']==r['结束时刻（s）']);r['保障方式']='中继';r['中继架次编号']=self.relay[0]['relay_trip_id']
        ck,_,_=validate_communication(self.data,self.ir,self.oneph,self.relay,x,dense=False);self.assertTrue(any(not c['pass'] and 'instant_link_and_priority' in c['check'] for c in ck))
    def test_q2_and_q3_trip_namespaces_disjoint(self):
        q2={r['架次编号'] for r in read_csv(ROOT/'results/q2/Q2_运输架次.csv')};q3={r['架次编号'] for r in self.tr};self.assertFalse(q2&q3);self.assertTrue(all(r['运输架次编号'] in q3 for r in self.comm))

if __name__=='__main__':unittest.main()
