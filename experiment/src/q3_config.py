"""第三问集中配置。Python 3.13.5；Numba 0.65.1；其余版本见requirements.txt。
无线预算/机型/库存均读原附件；此处仅包含数值精度、搜索及可视化参数。
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Q3Config:
    wgs84_a_m: float = 6378137.0
    wgs84_e2: float = 0.0066943799901413165
    fspl_constant: float = 32.45                 # 原题附录3；不是32.44
    meters_per_km: float = 1000.0
    seconds_per_hour: float = 3600.0
    geometry_eps: float = 1e-10
    los_height_eps_m: float = 1e-8              # 接触按遮挡侧处理
    interval_eps: float = 1e-12
    time_tolerance_s: float = 1e-6
    budget_tolerance_db: float = 1e-8
    candidate_grid_stride_pixels: int = 4
    candidate_refine_stride_pixels: int = 4
    candidate_refine_radius_pixels: int = 24
    search_sample_spacing_m: float = 60.0
    independent_sample_seconds: float = 1.0
    independent_sample_spacing_m: float = 8.0
    candidate_min_agl_m: float = 50.0
    search_budget_buffer_db: float = 0.20
    service_time_buffer_s: float = 1.0
    relay_height_mode: str = 'strict_given_cruise_ceiling'
    max_simultaneous_relay_bodies: int = 2
    relay_sorties_in_search_family: int = 4
    max_candidate_finalists: int = 30
    candidate_geographic_search: str = 'full_valid_DEM'
    transport_candidate_seeds: tuple = (20261011,20261012,20261013)
    transport_candidate_iterations: int = 30000
    transport_candidate_lns: int = 80
    energy_tradeoff_seeds: tuple = (20261031,20261032)
    energy_tradeoff_iterations: int = 30000
    energy_tradeoff_lns: int = 80
    energy_tradeoff_cap_multiplier: float = 1.1
    extra_common_delays_s: tuple = (60.,90.,120.)
    outer_polish_rounds: int = 2
    outer_polish_seed: int = 20261021
    outer_polish_iterations: int = 40000
    outer_polish_lns: int = 100
    early_service_end_s: tuple = (1450.,4000.)
    late_service_end_s: float = 9600.
    milp_node_limit: int = 100000
    milp_relative_gap: float = 1e-9
    milp_cmax_tolerance_s: float = 1e-6
    search_invalid_window_penalty_s: float = 1000000.
    maximum_late_pairs: int = 100
    numerical_distance_tolerance_m: float = 1e-5
    plot_dpi: int = 240
    perturbation_delays_s: tuple = (0.0,1.0,2.0,3.0,5.0,10.0,30.0)
    propagation_extra_losses_db: tuple = (0.0,0.05,0.1,0.2,0.5,1.0,2.0)

Q3CFG=Q3Config()
