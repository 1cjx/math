"""导出q2opt两个方案并做独立复核：validate_rows用独立arc计算+逐条规则校验。"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from q2_physics import Problem
from q2_validation import independent_arcs, validate_rows
from solve_q2 import export_plan

data = json.loads((ROOT / 'data/cleaned/model_inputs.json').read_text('utf-8'))
pb = Problem(ROOT, data)
arc = independent_arcs(ROOT, data)

def tup(tr):
    return (tr[0], tuple(tr[1]), tuple(tr[2]))

for genome_file, name in (('cmax_best_genome.json', 'main25'), ('trips_min_genome.json', 'tripsmin18')):
    g = json.loads((ROOT / 'results/q2opt' / genome_file).read_text('utf-8'))
    trips = [tup(t) for t in g['trips']]
    out = ROOT / 'results/q2opt' / name
    res = export_plan(pb, trips, out, name, write_template=True)
    print(f"===== {name} =====")
    print({k: res[k] for k in ('feasible', 'trips', 'makespan_s', 'energy_kwh',
                                'weighted_tardiness_s', 'hard_late_s', 'min_return_soc_fraction',
                                'min_hard_deadline_slack_s', 'multipoint_trips', 'battery_units_used')})
    # 独立复核
    trips_csv = out / 'Q2_运输架次.csv'
    boxes_csv = out / 'Q2_逐箱交付.csv'
    from io_utils import read_csv
    summary, ck, tr, bx, rc = validate_rows(data, arc, read_csv(trips_csv), read_csv(boxes_csv))
    print("独立复核: checks_failed =", summary['checks_failed'], "/", summary['checks_total'])
    for c in ck:
        if not c['pass']:
            print("  FAIL:", c['check'], c['details'][:120])
