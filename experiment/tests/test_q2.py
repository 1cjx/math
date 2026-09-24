"""Q2端点/衔接测试及独立验收器的错误注入测试。Python 3.13.5。"""
from pathlib import Path
import sys,json,unittest,copy,math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from q2_physics import Problem,charge_duration
from q2_validation import independent_arcs,validate_rows
from io_utils import read_csv
from config import CFG

class Q2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/cleaned/model_inputs.json').read_text('utf-8'))
        geo={(r['from_id'],r['to_id']):{k:(v if k in ('from_id','to_id') else float(v)) for k,v in r.items()} for r in read_csv(ROOT/'results/q2/arc_geometry.csv')}
        cls.pb=Problem(ROOT,cls.data,geo);cls.arc=independent_arcs(ROOT,cls.data)
        cls.tr=read_csv(ROOT/'results/q2/Q2_运输架次.csv');cls.bx=read_csv(ROOT/'results/q2/Q2_逐箱交付.csv')
    def test_charge_endpoints(self):
        for full in (1800,2400,3000):
            self.assertAlmostEqual(charge_duration(0,full),full)
            self.assertAlmostEqual(charge_duration(.9,full),.35*full)
            self.assertAlmostEqual(charge_duration(1,full),0)
            self.assertAlmostEqual(charge_duration(.2,full),full*(.65*.7/.9+.35))
    def test_charge_continuity(self):
        self.assertLess(abs(charge_duration(.9-1e-10,3000)-charge_duration(.9+1e-10,3000)),1e-5)
    def test_bad_soc_rejected(self):
        with self.assertRaises(ValueError):charge_duration(-.01,3000)
        with self.assertRaises(ValueError):charge_duration(1.01,3000)
    def test_medical_and_first_deadlines_intersection(self):
        for i,b in enumerate(self.pb.boxes):
            hard=[]
            if b['material_type']=='医疗物资':hard.append(b['expected_s'])
            if b['is_first_batch']:hard.append(b['first_deadline_s'])
            self.assertEqual(self.pb.hard[i],min(hard,default=math.inf))
    def test_source_floor_all_formal_scenarios(self):
        self.assertTrue(all(r>=max(m['reserve_fraction'] for m in self.data['transport_models']) for r in CFG.reserve_scenarios))
    def test_singlepoint_inherits_q1_energy_and_time(self):
        routes={r['service_id']:{k:(v if k=='service_id' else float(v)) for k,v in r.items()} for r in read_csv(ROOT/'results/q1/route_geometry.csv')}
        for r in read_csv(ROOT/'results/q1/batches_NET.csv'):
            ids=[self.pb.box_index[x] for x in r['box_ids'].split(';')];g=r['model_id'];sid=r['service_id']
            ev=self.pb.evaluate(self.pb.trip(g,(sid,),ids));self.assertIsNotNone(ev)
            self.assertAlmostEqual(ev['energy'],float(r['energy_kwh']),places=10)
            self.assertAlmostEqual(ev['duration'],float(r['operation_time_s']),places=8)
    def test_duplicate_in_trip_rejected(self):
        self.assertIsNone(self.pb.evaluate(('A',(self.pb.sid[0],),(0,0))))
    def test_overload_rejected(self):
        self.assertIsNone(self.pb.evaluate(('A',tuple(sorted(set(self.pb.sid))),tuple(range(len(self.pb.boxes))))))
    def test_main_independent_acceptance(self):
        s,*_=validate_rows(self.data,self.arc,self.tr,self.bx);self.assertEqual(s['checks_failed'],0)
    def _reject(self,ts,bs,fragment):
        s,cs,*_=validate_rows(self.data,self.arc,ts,bs)
        self.assertGreater(s['checks_failed'],0);self.assertTrue(any(not c['pass'] and fragment in c['check'] for c in cs))
    def test_mutation_wrong_energy_detected(self):
        ts=copy.deepcopy(self.tr);ts[0]['架次能耗（kWh）']=str(float(ts[0]['架次能耗（kWh）'])+.1)
        self._reject(ts,self.bx,'energy_recalculation')
    def test_mutation_wrong_return_detected(self):
        ts=copy.deepcopy(self.tr);ts[0]['返回O01时刻（s）']=str(float(ts[0]['返回O01时刻（s）'])+20)
        self._reject(ts,self.bx,'return_time_recalculation')
    def test_mutation_duplicate_box_detected(self):
        bs=copy.deepcopy(self.bx);bs.append(copy.deepcopy(bs[0]));self._reject(self.tr,bs,'exact_once_box_coverage')
    def test_mutation_wrong_model_battery_detected(self):
        ts=copy.deepcopy(self.tr);ts[0]['电池编号']='C-BAT-01' if ts[0]['机型编号']!='C' else 'A-BAT-01'
        self._reject(ts,self.bx,'compatible_battery')
    def test_mutation_drone_double_booking_detected(self):
        ts=copy.deepcopy(self.tr)
        for i in range(1,len(ts)):
            if ts[i]['机型编号']==ts[0]['机型编号'] and float(ts[i]['开始时刻（s）'])==0:
                ts[i]['无人机编号']=ts[0]['无人机编号'];break
        self._reject(ts,self.bx,'no_overlap_and_full_recharge')
    def test_mutation_battery_double_booking_detected(self):
        ts=copy.deepcopy(self.tr)
        for i in range(1,len(ts)):
            if ts[i]['机型编号']==ts[0]['机型编号'] and float(ts[i]['开始时刻（s）'])==0:
                ts[i]['电池编号']=ts[0]['电池编号'];break
        self._reject(ts,self.bx,'no_overlap_and_full_recharge')
    def test_mutation_delivery_arrival_not_completion_detected(self):
        bs=copy.deepcopy(self.bx);bs[0]['交付完成时刻（s）']=str(float(bs[0]['交付完成时刻（s）'])-30)
        self._reject(self.tr,bs,'handoff_completed_time')
    def test_mutation_late_start_detected(self):
        ts=copy.deepcopy(self.tr);bs=copy.deepcopy(self.bx)
        for r in ts:
            r['开始时刻（s）']=str(float(r['开始时刻（s）'])+600);r['返回O01时刻（s）']=str(float(r['返回O01时刻（s）'])+600)
        for b in bs:b['交付完成时刻（s）']=str(float(b['交付完成时刻（s）'])+600)
        self._reject(ts,bs,'hard_deadline')

if __name__=='__main__':unittest.main()
