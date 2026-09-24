"""第二问集中参数；Python 3.13.5，依赖锁定于requirements.txt。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Q2Config:
    seeds: tuple = (20260923, 20260924, 20260925)
    iterations_per_seed: int = 16000
    lns_iterations: int = 60
    polish_seeds: tuple = tuple(range(20260930, 20260942))
    polish_iterations: int = 100000
    polish_lns_iterations: int = 220
    energy_seeds: tuple = (20261001,20261002,20261003,20261004)
    energy_iterations: int = 60000
    energy_lns_iterations: int = 150
    maximum_stops: int = 15  # 15个不同服务区均可访问；不是人为限定成两点/三点
    initial_restarts: int = 12
    numeric_tolerance: float = 1e-7
    energy_tolerance_kwh: float = 1e-10
    comparator_time_decimals: int = 6
    comparator_energy_decimals: int = 9
    cache_size: int = 240000
    # 先满足硬时限，再最小化优先级加权逾期；主方案随后最小化Cmax、E、N。
    temperature_start_s: float = 120.0
    temperature_end_s: float = 0.3
    reheat_interval: int = 4000
    soft_lateness_penalty: float = 100.0
    hard_lateness_penalty: float = 10000.0
    energy_tiebreak_s_per_kwh: float = 0.02
    trip_tiebreak_s: float = 0.001
    destroy_size_min: int = 2
    destroy_size_max: int = 9
    charge_knee_fraction: float = 0.9
    charge_fast_time_fraction: float = 0.65
    charge_slow_time_fraction: float = 0.35
    weighted_time_scale_s: float = 3600.0
    alternative_energy_budget_ratio: float = 1.10
    plot_dpi: int = 180

Q2CFG=Q2Config()
