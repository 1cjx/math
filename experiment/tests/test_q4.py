"""Q4正常/错误注入测试。Python3.13.5；运行 python -m unittest discover -s tests -v。"""
import unittest,sys,copy,tempfile,shutil,json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from solve_q4 import Interval,interval_coloring,canonical_partitions,FrozenQ3,strict_no_copy
from q4_validation import IndependentQ4,minimum_chain_cover,anchor_partitions,validate_q4_template,verify_case,independent_charge_q4
from q2_physics import charge_duration
from io_utils import read_csv,write_csv

class Q4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v=IndependentQ4(ROOT);cls.q=FrozenQ3(ROOT);cls.rows=read_csv(ROOT/'results/q4/Q4_分区配置.csv')
    def test_exact_stirling_enumeration(self):
        self.assertEqual(len(list(canonical_partitions(7,2))),63)
        self.assertEqual(len(list(anchor_partitions(range(7),3))),301)
    def test_transitive_large_component_preserved(self):
        self.assertEqual(self.q.components[0],['S001','S002','S003','S004','S005','S008','S009','S010','S011','S012','S013','S014','S015'])
    def test_touching_intervals_share_one_resource(self):
        iv=[Interval('one','transport_A',0.,10.,10.,'u'),Interval('two','transport_A',10.,20.,20.,'u')]
        self.assertEqual(interval_coloring(iv)[0],1)
    def test_battery_must_include_charge(self):
        iv=[Interval('one','battery_A',0.,15.,10.,'u'),Interval('two','battery_A',10.,20.,18.,'u')]
        self.assertEqual(interval_coloring(iv)[0],2)
    def test_relay_must_include_turnaround(self):
        iv=[Interval('one','relay_drone',0.,310.,10.,'r'),Interval('two','relay_drone',20.,350.,50.,'r')]
        self.assertEqual(interval_coloring(iv)[0],2)
    def test_all_eight_resource_types_matching_on_random_intervals(self):
        rng=random.Random(20260923)
        for _ in range(40):
            iv=[]
            for j in range(12):
                s=rng.randrange(100);e=s+rng.randrange(1,25);iv.append(Interval(str(j),'x',s,e,e,'src'))
            self.assertEqual(interval_coloring(iv)[0],minimum_chain_cover([(i.start_s,i.ready_s,i.task_id) for i in iv]))
    def test_independent_charging_across_knee(self):
        for soc in [0.,.2,.89,.9,.91,1.]:self.assertAlmostEqual(charge_duration(soc,1800),independent_charge_q4(soc,1800),places=10)
    def test_original_module_ID_count_not_minimum(self):
        self.assertEqual(self.q.source_unique[-1],4);self.assertEqual(self.q.baseline['counts'][-1],3)
    def test_full_inventory_not_sufficient_for_any_partition(self):
        self.assertEqual(min(x['shortage_units'] for x in self.v.records[2].values()),2)
        self.assertEqual(min(x['shortage_units'] for x in self.v.records[3].values()),7)
    def test_no_copy_three_groups_now_possible(self):
        self.assertEqual(strict_no_copy(self.q)['feasible_partition_counts'],{'2':3,'3':1})
    def test_direct_only_group_needs_no_relay(self):
        self.assertEqual(self.v.group(['S006'])['counts'][-2:],[0,0])
    def test_final_template_independently_valid(self):
        self.assertTrue(all(c['pass'] for c in validate_q4_template(ROOT,self.rows,self.v)))
    def test_wrong_minimum_count_rejected(self):
        rows=copy.deepcopy(self.rows);rows[0]['C型运输无人机数']=str(int(float(rows[0]['C型运输无人机数']))+1)
        self.assertTrue(any(not c['pass'] for c in validate_q4_template(ROOT,rows,self.v)))
    def test_split_multistop_component_rejected(self):
        rows=copy.deepcopy(self.rows);rows[0]['服务区列表']=rows[0]['服务区列表'].replace('S010;','');rows[1]['服务区列表']+=';S010'
        self.assertTrue(any(not c['pass'] and 'must_link' in c['check'] for c in validate_q4_template(ROOT,rows,self.v)))
    def test_fractional_device_count_rejected(self):
        rows=copy.deepcopy(self.rows);rows[0]['A型运输无人机数']='3.5'
        self.assertTrue(any(not c['pass'] and 'integer' in c['check'] for c in validate_q4_template(ROOT,rows,self.v)))
    def reject_mutation(self,filename,mutator,needle):
        names=['groups.csv','resource_catalog.csv','resource_allocations.csv','peak_certificates.csv','运输任务_固定Q3时间.csv','逐箱交付_完全继承Q3.csv','中继任务_唯一执行.csv','通信保障_源关系映射.csv','communication_lineage.csv','summary.json','configured_inventory.json']
        with tempfile.TemporaryDirectory(prefix='q4_reject_') as tmp:
            out=Path(tmp)
            for name in names:shutil.copyfile(ROOT/'results/q4/K3'/name,out/name)
            rows=read_csv(out/filename);mutator(rows);write_csv(out/filename,rows)
            checks,_=verify_case(ROOT,out,self.v,check_physics=False)
            self.assertTrue(any(not c['pass'] and needle in c['check'] for c in checks),[c for c in checks if not c['pass']])
    def test_shared_physical_resource_across_groups_rejected(self):
        def change(rows):
            a=next(r for r in rows if r['group_id']=='K3-G1' and r['resource_type']=='transport_C')
            b=next(r for r in rows if r['group_id']=='K3-G2' and r['resource_type']=='transport_C');b['physical_resource_id']=a['physical_resource_id']
        self.reject_mutation('resource_catalog.csv',change,'no_physical_resource_across_groups')
    def test_omitting_charge_end_rejected(self):
        def change(rows):
            r=next(r for r in rows if r['resource_type']=='battery_C');r['ready_s']=r['return_s']
        self.reject_mutation('resource_allocations.csv',change,'include_charge_turnaround')
    def test_shortening_frozen_relay_rejected(self):
        self.reject_mutation('中继任务_唯一执行.csv',lambda r:r[0].update({'服务结束时刻（s）':float(r[0]['服务结束时刻（s）'])-1.}),'frozen_服务结束')
    def test_changed_communication_provider_rejected(self):
        def change(rows):
            r=next(r for r in rows if r['保障方式']=='中继');r['中继架次编号']='Q3-R-999@K3-G1'
        self.reject_mutation('通信保障_源关系映射.csv',change,'entire_communication_relation')
    def test_changed_box_delivery_rejected(self):
        self.reject_mutation('逐箱交付_完全继承Q3.csv',lambda r:r[0].update({'交付完成时刻（s）':float(r[0]['交付完成时刻（s）'])+1.}),'all_boxes_exactly_frozen')
    def test_fake_existing_resource_rejected(self):
        def change(rows):
            r=next(r for r in rows if r['supply_status']=='required_addition_not_in_source');r['supply_status']='existing_inventory'
        self.reject_mutation('resource_catalog.csv',change,'existing_vs_planned_identity')
    def test_cannot_offset_type_gap_with_spare_modules(self):
        s=json.loads((ROOT/'results/q4/summary.json').read_text('utf-8'))['selected']['2']
        self.assertEqual(s['spare_relay_energy'],3);self.assertEqual(s['shortage_units'],2);self.assertFalse(s['inventory_feasible'])

if __name__=='__main__':unittest.main()
