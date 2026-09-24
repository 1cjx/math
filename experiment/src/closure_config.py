"""闭环修订集中配置。Python 3.13.5；设备参数仍从附件读取。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ClosureConfig:
    require_strict_groups: int = 3
    allow_q4_relay_replication: bool = False
    dedicated_relay_search_family: str = 'one_single_trip_component_and_existing_valid_hover_sites'
    comparison_tolerance: float = 1e-6
    common_delay_grid_s: tuple = tuple(range(0, 601, 10))
    energy_scale_grid: tuple = (.90,.95,1.00,1.01,1.02,1.03,1.04,1.05,1.08,1.10,1.15,1.20)
    charging_scale_grid: tuple = (.70,.80,.90,1.00,1.02,1.05,1.10,1.20,1.30,1.50)
    route_curve_samples: int = 121
    paper_plot_dpi: int = 240
    chinese_font_candidates: tuple = ('Noto Sans CJK SC','Microsoft YaHei','SimHei','WenQuanYi Micro Hei','Source Han Sans SC')
CLOSURE_CFG=ClosureConfig()
