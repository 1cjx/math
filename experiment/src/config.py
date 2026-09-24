"""集中配置。实测 Python 3.13.5；依赖版本见 requirements.txt。
物理设备参数全部读取原始表格；下列常量均有口径说明，不替代附件值。
"""
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Config:
    terrain_clearance_m: float = 50.0       # 题面附录2
    service_work_height_m: float = 30.0     # 题面附录2
    depot_work_height_m: float = 0.0        # 题面附录2
    horizontal_energy_multiplier: float = 1.0  # 基准；只在假设敏感性实验中变化
    climb_energy_multiplier: float = 1.0
    gravity_m_s2: float = 9.81              # 补充假设：常数重力加速度
    joules_per_kwh: float = 3_600_000.0
    range_load_exponent: float = 1.5        # 题面 L(q) 的3/2次方
    percent_base: float = 100.0
    geometry_tolerance: float = 1e-9
    energy_tolerance_kwh: float = 1e-10
    capacity_tolerance_kg: float = 1e-8
    bisection_iterations: int = 80
    iqr_multiplier: float = 1.5
    modified_z_threshold: float = 3.5
    modified_z_scale: float = 0.6744897501960817
    elevation_review_threshold_m: float = 5.0  # 仅标记，不覆盖题定海拔
    nodata_value: float = -32767.0          # 地理数据说明与DEM.mat
    route_check_step_m: float = 10.0       # 测地线折线独立核验间距，非主算法
    diagnostic_coarse_step_m: float = 30.0
    reserve_scenarios: tuple = (0.20,0.25,0.30,0.35,0.40,0.45,0.50,0.55,0.60)
    priority_orders: tuple = ("NET", "ENT", "TNE", "NTE")
    main_priority: str = "NET"             # 架次数→能耗→累计作业时间，字典序
    template_time_basis: str = "operation_time_s"  # 固定准备/逐箱装载+飞行+交接
    comparison_energy_decimals: int = 10
    comparison_time_decimals: int = 6
    capacity_monotonicity_test_points: int = 21
    plot_dpi: int = 180
    expected_services: int = 15
    expected_boxes: int = 80
    expected_transport_models: int = 3
    expected_transport_drones: int = 8
    random_seed: int = 20260923             # 只用于测试，核心算法无随机性

CFG = Config()
PARAMETER_PROVENANCE = {
 'flight_rule':'题面：附录2，运输航段、时间与能耗',
 'range_rule':'题面：L_g(q)=L0-(L0-LF)(q/Q)^(3/2)',
 'horizontal_energy_assumption':'题面未展开E_hor；补充采用 E_use*d/L(q)，将标准航程视为可用电量耗尽对应航程',
 'climb_energy_assumption':'题面未展开E_up；补充采用(m0+q)*g*h_up/(eta_up*3.6e6)，eta_up按推进效率解释',
 'transport_hover_energy':'题面无运输悬停功率；依其航段能耗口径不额外虚构交接悬停电耗',
 'route_geometry':'WGS84经纬度线段作为短距离水平直线的栅格实现；距离用WGS84椭球测地距离；测地线折线逐像元做独立交叉核验',
 'ground_elevation':'起降/作业节点保留xlsx题定海拔；DEM仅确定沿线最高表面及提供差异审核',
 'operation_time':'准备+逐箱装载+往返三阶段飞行+接收点基础交接+逐箱交接；不含电池充电等待，不是多机完工时间',
 'template_roundtrip_time':'本交付的明确约定：Q1往返时间=O01开始准备至完成交付并返抵O01的总作业历时；Q2开始时刻也是开始准备，同口径；题面未进一步定义该表头，另附全部分项',
}
