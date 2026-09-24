"""分N扫掠：对每个目标架次数N，从N=18解出发做受限搜索（架次数上限=目标N），
时间模式优化Cmax，得到(N, Cmax)完整帕累托数据。产物：results/q2opt/n_sweep.csv
"""
import sys, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from q2_physics import Problem
from q2_search import mutate, rebuild, anneal_score, objective, urgency_order
from q2_config import Q2CFG
import math, random

OUT = ROOT / 'results/q2opt'
data = json.loads((ROOT / 'data/cleaned/model_inputs.json').read_text('utf-8'))
pb = Problem(ROOT, data)

g = json.loads((OUT / 'trips_min_genome.json').read_text('utf-8'))
base18 = [(t[0], tuple(t[1]), tuple(t[2])) for t in g['trips']]

def search_capped(pb, initial, seed, ncap, iterations=60000, lns=150, mode='time'):
    rng = random.Random(seed)
    best = initial[:]; bm = pb.schedule(best); current = best[:]; cm = bm
    for it in range(1, iterations + 1):
        cand = mutate(pb, current, rng, 15)
        if cand is None or len(cand) > ncap: continue
        nm = pb.schedule(cand)
        frac = (it % Q2CFG.reheat_interval) / Q2CFG.reheat_interval
        temp = Q2CFG.temperature_start_s * (Q2CFG.temperature_end_s / Q2CFG.temperature_start_s) ** frac
        delta = anneal_score(nm, mode) - anneal_score(cm, mode)
        if delta <= 0 or (delta / temp < 700 and rng.random() < math.exp(-delta / temp)):
            current = cand; cm = nm
        if objective(nm, mode) < objective(bm, mode):
            best = cand; bm = nm
        if it % Q2CFG.reheat_interval == 0: current = best[:]; cm = bm
    for it in range(1, lns + 1):
        cand = rebuild(pb, best, rng, mode, None, 15)
        if cand is None or len(cand) > ncap: continue
        mm = pb.schedule(cand)
        if objective(mm, mode) < objective(bm, mode):
            best = cand; bm = mm
    return best, bm

rows = []
t0 = time.time()
for ncap in (19, 20, 21, 22, 23, 24):
    best = None; bm = None
    for seed in (601 + 2 * i for i in range(3)):
        tr, m = search_capped(pb, base18, seed, ncap, iterations=30000, lns=80)
        if best is None or objective(m) < objective(bm):
            best, bm = tr, m
    # 抛光一轮
    best, bm = search_capped(pb, best, 700 + ncap, ncap, iterations=60000, lns=150)
    m = bm
    rows.append({'N_cap': ncap, 'N': m['trips'], 'Cmax_s': round(m['makespan_s'], 2),
                 'energy_kwh': round(m['energy_kwh'], 3), 'tardiness_s': m['weighted_tardiness_s'],
                 'hard_late_s': m['hard_late_s']})
    print(rows[-1], f"({time.time()-t0:.0f}s)", flush=True)

from io_utils import write_csv
write_csv(OUT / 'n_sweep.csv', rows)
print("saved n_sweep.csv")
