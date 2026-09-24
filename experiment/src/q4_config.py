"""Q4集中配置。Python 3.13.5；依赖版本见requirements.txt。
Q4不使用新飞行/无线模型、不重排Q3；仅做确定性枚举和固定区间资源着色。
设备、货物、库存、充电参数全部读取清洗数据，禁止用配置覆盖源值。
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Q4Config:
    group_counts: tuple = (2, 3)
    time_tolerance_s: float = 1e-6
    metric_tolerance: float = 1e-12
    relay_inheritance_mode: str = 'strict_unique_mission_no_replication'
    # Q3定稿前完成闭环修复；Q4运输和中继任务各恰好一次，禁止副本。
    resource_reassignment_before_start: bool = True
    objective_order: tuple = ('shortage_units', 'resource_units', 'transport_workload_cv')
    # 件数是明确的等件计数偏好，不代表各类资源等价或等价采购费用。
    balance_sweep_caps: tuple = (0.30, 0.50, 0.70, 0.90, 1.00, 1.20, 1.30, 1.50)
    plot_dpi: int = 240
    expected_component_limit: int = 16  # 防止替换输入后无提示指数爆炸；不是裁剪候选
    source_phase_validation_dense: bool = False

Q4CFG = Q4Config()
RESOURCE_KEYS = ('transport_A','transport_B','transport_C','battery_A','battery_B','battery_C','relay_drone','relay_energy')
RESOURCE_NAMES = ('A型运输无人机','B型运输无人机','C型运输无人机','A型电池组','B型电池组','C型电池组','中继无人机','中继能源组件')
Q4_HEADERS = ['K（2或3）','任务组编号','服务区列表','A型运输无人机数','B型运输无人机数','C型运输无人机数','A型电池组数','B型电池组数','C型电池组数','中继无人机数','中继能源组件数']
SOURCE_Q3_FILES = ('trips.csv','relay_sorties.csv','box_deliveries.csv','Q3_运输架次.csv','Q3_逐箱交付.csv','Q3_中继架次.csv','Q3_通信保障.csv','summary.json','independent_validation.json')
