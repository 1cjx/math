"""Q2改进实验：A线=最少架次(N)优化+帕累托前沿；B线=大预算多起点Cmax优化。
只读 data/ 与既有 results/，全部新产物写入 results/q2opt/。不改任何原始文件。
"""
import sys, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from q2_physics import Problem
from q2_search import greedy_initial, search, objective, urgency_order

OUT = ROOT / 'results/q2opt'
OUT.mkdir(parents=True, exist_ok=True)

data = json.loads((ROOT / 'data/cleaned/model_inputs.json').read_text('utf-8'))
pb = Problem(ROOT, data)
LOG = open(OUT / 'experiment_log.txt', 'w', encoding='utf-8')

def log(*a):
    msg = ' '.join(str(x) for x in a)
    print(msg, flush=True)
    LOG.write(msg + '\n')
    LOG.flush()

def brief(m):
    return (f"hard={m['hard_late_s']:.3f} tardy={m['weighted_tardiness_s']:.3f} "
            f"N={m['trips']} Cmax={m['makespan_s']:.2f} E={m['energy_kwh']:.3f}")

# ---------- A线：最少架次 ----------
t0 = time.time()
bestN = None; bmN = None
for s in (101, 102, 103, 104, 105, 106):
    tr = greedy_initial(pb, s, 15)
    tr, m, h, st = search(pb, tr, s, mode='trips', maxstops=15)
    log(f"[A-warmup seed={s}] {brief(m)}  ({time.time()-t0:.0f}s)")
    if bestN is None or objective(m, 'trips') < objective(bmN, 'trips'):
        bestN, bmN = tr, m
for r, s in enumerate((201, 202, 203, 204, 205), 1):
    bestN, bmN, h, st = search(pb, bestN, s, iterations=80000, lns=300, mode='trips', maxstops=15)
    log(f"[A-polish {r}] {brief(bmN)}  ({time.time()-t0:.0f}s)")
json.dump({'trips': bestN, 'box_index_order': list(pb.bid),
           'schedule_rule': 'earliest_available_compatible_drone_and_battery'},
          open(OUT / 'trips_min_genome.json', 'w'), ensure_ascii=False)
log(f"[A-FINAL] {brief(bmN)}")

# A2：从N最少的解出发，用time模式抛光，记录(N,Cmax)帕累托前沿
pareto = {}
for s in (301, 302):
    tr, m, h, st = search(pb, bestN, s, iterations=80000, lns=200, mode='time', maxstops=15)
    for x in h:
        n = x['trips']; c = x['makespan_s']
        if n not in pareto or c < pareto[n][0]:
            pareto[n] = (c, x.get('energy_kwh'))
    log(f"[A2-time-polish seed={s}] {brief(m)}")
for n in sorted(pareto):
    c, e = pareto[n]
    log(f"[A2-PARETO] N={n} Cmax={c:.2f} E={e if e is None else round(e,3)}")

# ---------- B线：Cmax大预算多起点 ----------
bestB = None; bmB = None
for s in (401, 402, 403, 404):
    tr = greedy_initial(pb, s, 15)
    tr, m, h, st = search(pb, tr, s, mode='time', maxstops=15)
    log(f"[B-warmup seed={s}] {brief(m)}  ({time.time()-t0:.0f}s)")
    if bestB is None or objective(m) < objective(bmB):
        bestB, bmB = tr, m
# 载入本次运行已得到的主方案作为额外起点
try:
    g = json.loads((ROOT / 'results/q2/solution_genome.json').read_text('utf-8'))
    if list(g['box_index_order']) == list(pb.bid):
        m0 = pb.schedule(g['trips'])
        log(f"[B-seed0 本机main] {brief(m0)}")
        if objective(m0) < objective(bmB):
            bestB, bmB = g['trips'], m0
except Exception as ex:
    log("[B-seed0 载入失败]", ex)
for r, s in enumerate((501, 502, 503, 504, 505, 506), 1):
    bestB, bmB, h, st = search(pb, bestB, s, iterations=100000, lns=300, mode='time', maxstops=15)
    log(f"[B-polish {r}] {brief(bmB)}  ({time.time()-t0:.0f}s)")
json.dump({'trips': bestB, 'box_index_order': list(pb.bid),
           'schedule_rule': 'earliest_available_compatible_drone_and_battery'},
          open(OUT / 'cmax_best_genome.json', 'w'), ensure_ascii=False)
log(f"[B-FINAL] {brief(bmB)}")
log(f"TOTAL {time.time()-t0:.0f}s")
