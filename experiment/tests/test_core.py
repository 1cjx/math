"""便携单元测试：python -m unittest discover -s tests -v"""
import sys,json,unittest
from pathlib import Path
import numpy as np
from affine import Affine
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from config import CFG
from physics import effective_range,trip_energy,safe_payload,segment_cells
from io_utils import read_csv

class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/cleaned/model_inputs.json').read_text('utf-8'))
        cls.models=cls.data['transport_models']
        raw=read_csv(ROOT/'results/q1/route_geometry.csv')[0]
        cls.route={k:v if k=='service_id' else float(v) for k,v in raw.items()}
    def test_empty_and_full_range(self):
        for m in self.models:
            self.assertAlmostEqual(effective_range(m,0),m['empty_range_m'])
            self.assertAlmostEqual(effective_range(m,m['max_payload_kg']),m['full_range_m'])
    def test_monotonic_energy(self):
        for m in self.models:
            e=[trip_energy(m,self.route,q)['energy_kwh'] for q in np.linspace(0,m['max_payload_kg'],CFG.capacity_monotonicity_test_points)]
            self.assertTrue(np.all(np.diff(e)>0))
    def test_empty_return_not_loaded_return(self):
        for m in self.models:
            d=trip_energy(m,self.route,m['max_payload_kg'])
            self.assertLess(d['inbound_horizontal_kwh'],d['outbound_horizontal_kwh'])
    def test_no_feasible_empty_trip_is_null(self):
        for m in self.models:self.assertIsNone(safe_payload(m,self.route,1.0)['max_safe_payload_kg'])
    def test_supercover_direction_invariance(self):
        tr=Affine.identity()
        a={(r,c) for r,c,_ in segment_cells(.2,.3,4.8,3.7,tr)}
        b={(r,c) for r,c,_ in segment_cells(4.8,3.7,.2,.3,tr)}
        self.assertEqual(a,b)
    def test_supercover_corner_contacts(self):
        cells={(r,c) for r,c,_ in segment_cells(.5,.5,2.5,2.5,Affine.identity())}
        self.assertTrue({(0,1),(1,0),(1,2),(2,1)}<=cells)
    def test_required_box_ids_unique(self):
        ids=[b['box_id'] for b in self.data['boxes']]
        self.assertEqual(len(ids),len(set(ids)));self.assertEqual(len(ids),CFG.expected_boxes)
    def test_nonapplicable_deadlines_not_imputed(self):
        self.assertTrue(all((b['first_deadline_s'] is not None)==b['is_first_batch'] for b in self.data['boxes']))
    def test_full_optimality_verification(self):
        s=json.loads((ROOT/'results/q1/validation_summary.json').read_text('utf-8'))
        self.assertEqual(s['checks_failed'],0);self.assertEqual(s['independent_optimum_services'],CFG.expected_services)

if __name__=='__main__':unittest.main()
