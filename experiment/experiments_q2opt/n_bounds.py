"""回答两个问题：(1) 架次数上限：结构上限80（一箱一架次）是否可行；贪心拆分求最大可行N。
(2) 16/17架次搜索：验证多点模式下18是否真的是可达最小值。"""
import sys, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from q2_physics import Problem
from q2_search import urgency_order, mutate, rebuild, anneal_score, objective
from q2_config import Q2CFG
import math, random

data = json.loads((ROOT / 'data/cleaned/model_inputs.json').read_text('utf-8'))
pb = Problem(ROOT, data)
t0 = time.time()

def brief(m):
    return (f"hard={m['hard_late_s']:.3f} tardy={m['weighted_tardiness_s']:.3f} "
            f"N={m['trips']} Cmax={m['makespan_s']:.2f} E={m['energy_kwh']:.3f}")

# ---------- 1) 结构上限：一箱一架次 N=80 ----------
singles = []
for i in range(len(pb.boxes)):
    best = None
    for g in pb.models:
        tt = pb.trip(g, (pb.sid[i],), (i,))
        ev = pb.evaluate(tt)
        if ev is None: continue
        if best is None or ev['duration'] < best[1]:
            best = (tt, ev['duration'])
    if best is None:
        raise ValueError(f'箱 {pb.bid[i]} 无单箱可行机型')
    singles.append(best[0])
m80 = pb.schedule(urgency_order(pb, singles))
print(f"[N=80 一箱一架次] {brief(m80)} 电池占用={m80.get('battery_reuses', '?')}/{m80.get('battery_units_used','?')} ({time.time()-t0:.0f}s)")

# ---------- 2) 贪心拆分：从可行解出发，反复拆分直到不能再拆 ----------
g = json.loads((ROOT / 'results/q2/solution_genome.json').read_text(encoding='utf-8'))
trips = [(t[0], tuple(t[1]), tuple(t[2])) for t in g['trips']]  # main25

def try_split(trips):
    """尝试拆分某个架次为两个，保持零硬违约零逾期。返回新解或None。"""
    for idx, tr in enumerate(trips):
        ids = list(tr[2])
        if len(ids) < 2: continue
        # 拆分方案：按服务区分组拆（多点架次）或对半拆（单点架次）
        if len(tr[1]) >= 2:
            stops = list(tr[1])
            cut = len(stops) // 2
            groups = [stops[:cut], stops[cut:]]
        else:
            groups = [[tr[1][0]], [tr[1][0]]]
            half = len(ids) // 2
            groups_boxes = [ids[:half], ids[half:]]
            grp_tries = [(tuple(sorted(set(pb.sid[i] for i in gb))) if False else tr[1], gb) for gb in groups_boxes]
        if len(tr[1]) >= 2:
            grp_tries = []
            for grp in groups:
                gb = [i for i in ids if pb.sid[i] in grp]
                if gb: grp_tries.append((tuple(grp), gb))
            if len(grp_tries) < 2:
                half = len(ids) // 2
                grp_tries = [(tr[1], ids[:half]), (tr[1], ids[half:])]
        # 为两组各选机型（保持原机型优先，尝试全部组合）
        combos = []
        for ga in pb.models:
            ta = pb.trip(ga, grp_tries[0][0], tuple(grp_tries[0][1]))
            if pb.evaluate(ta) is None: continue
            for gb_ in pb.models:
                tb = pb.trip(gb_, grp_tries[1][0], tuple(grp_tries[1][1]))
                if pb.evaluate(tb) is None: continue
                combos.append((ta, tb))
        for ta, tb in combos:
            cand = trips[:idx] + [ta, tb] + trips[idx+1:]
            mm = pb.schedule(urgency_order(pb, cand))
            if mm['hard_late_s'] <= 1e-9 and mm['weighted_tardiness_s'] <= 1e-9:
                return cand
    return None

cur = trips
mm = pb.schedule(urgency_order(pb, cur))
print(f"[贪心拆分起点 main25] {brief(mm)}")
splits = 0
while True:
    nxt = try_split(cur)
    if nxt is None: break
    cur = nxt; splits += 1
    if splits % 5 == 0:
        mm = pb.schedule(urgency_order(pb, cur))
        print(f"  拆分{splits}次后: {brief(mm)} ({time.time()-t0:.0f}s)")
mm = pb.schedule(urgency_order(pb, cur))
print(f"[贪心最大N] {brief(mm)}  共拆分{splits}次 ({time.time()-t0:.0f}s)")
json.dump({'trips': cur, 'box_index_order': list(pb.bid)},
          open(ROOT / 'results/q2opt/nmax_greedy_genome.json', 'w', encoding='utf-8'), ensure_ascii=False)

# ---------- 3) 16/17架次搜索：多点模式下能否低于18 ----------
def search_capped(pb, initial, seed, ncap, iterations=60000, lns=150):
    rng = random.Random(seed)
    best = initial[:]; bm = pb.schedule(best); current = best[:]; cm = bm
    for it in range(1, iterations + 1):
        cand = mutate(pb, current, rng, 15)
        if cand is None or len(cand) > ncap: continue
        nm = pb.schedule(cand)
        frac = (it % Q2CFG.reheat_interval) / Q2CFG.reheat_interval
        temp = Q2CFG.temperature_start_s * (Q2CFG.temperature_end_s / Q2CFG.temperature_start_s) ** frac
        delta = anneal_score(nm, 'trips') - anneal_score(cm, 'trips')
        if delta <= 0 or (delta / temp < 700 and rng.random() < math.exp(-delta / temp)):
            current = cand; cm = nm
        if objective(nm, 'trips') < objective(bm, 'trips'):
            best = cand; bm = nm
        if it % Q2CFG.reheat_interval == 0: current = best[:]; cm = bm
    for it in range(1, lns + 1):
        cand = rebuild(pb, best, rng, 'trips', None, 15)
        if cand is None or len(cand) > ncap: continue
        m2 = pb.schedule(cand)
        if objective(m2, 'trips') < objective(bm, 'trips'):
            best = cand; bm = m2
    return best, bm

g18 = json.loads((ROOT / 'results/q2opt/trips_min_genome.json').read_text(encoding='utf-8'))
base18 = [(t[0], tuple(t[1]), tuple(t[2])) for t in g18['trips']]
for ncap in (17, 16):
    bestN = None; bmN = None
    for seed in (801, 802, 803):
        tr, m = search_capped(pb, base18, seed, ncap, iterations=40000, lns=100)
        print(f"  [Ncap={ncap} seed={seed}] {brief(m)} ({time.time()-t0:.0f}s)")
        if bestN is None or objective(m, 'trips') < objective(bmN, 'trips'):
            bestN, bmN = tr, m
    print(f"[Ncap={ncap} 最终] {brief(bmN)}  → {'找到'+str(bmN['trips'])+'架次可行解!' if bmN['trips']<=ncap else '未找到≤'+str(ncap)+'架次的零违约解'}")
print("TOTAL", f"{time.time()-t0:.0f}s")
