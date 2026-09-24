"""闭环版统一报告、论文大纲、公式结果宏与图表索引。Python3.13.5。
所有结果由当次CSV/JSON生成；不可把先前Q3数值、假设副本或条件最优替换成新事实。
"""
from pathlib import Path
import json,math
from collections import Counter
from io_utils import read_csv,save_json,write_csv
from q4_config import RESOURCE_KEYS,RESOURCE_NAMES
from q3_config import Q3CFG

def table(headers,rows):
    def f(x):return str(x if x is not None else '不适用').replace('|','/').replace('\n','；')
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(f(v) for v in r)+' |' for r in rows])
def n(x,d=6):return f'{float(x):.{d}f}'
def build_closure_reports(root):
    root=Path(root);docs=root/'docs';paper=root/'paper'
    def js(p):return json.loads((root/p).read_text('utf-8'))
    def rows(q,s):return read_csv(root/f'results/{q}/{s}.csv')
    s1,s2,s3,s4=[js(f'results/{q}/summary.json') for q in ('q1','q2','q3','q4')]
    d=js('data/cleaned/model_inputs.json');v1=js('results/q1/validation_summary.json');v2=js('results/q2/independent_validation.json');v3=js('results/q3/independent_validation.json');v4=js('results/q4/independent_validation.json')
    ut=js('results/logs/unit_tests.json');vx=js('results/logs/submission_validation.json');aud=js('results/audit/audit_summary.json');q=js('results/quality/quality_summary.json');ex=js('results/closure/experiment_summary.json');cert=js('results/q3/closure_repair_certificate.json');re=js('results/q3/reliability_summary.json')
    tr=rows('q3','trips');rr=rows('q3','relay_sorties');sc=rows('q3','scenario_comparison');choices=rows('q3','closure_existing_candidates');figs=js('paper/figure_catalog.json');rm=d['relay_models'][0]
    candidates=js('results/q3/candidates/candidate_search_summary.json');milp=js('results/q3/relay_milp_certificate.json')
    texts={}
    texts['04_闭环验证与实质修订说明.md']=rf'''# 四问闭环验证与实质修订说明

## 1. 结论先行

本次闭环验证从题面、原始表格、清洗数据、公共物理、求解模型、CSV、最终Excel、报告及图件逐层反向核验。发现的主要问题不是Q1或Q2数值算错，而是旧Q4三组配置依赖复制Q3中继任务，不能作为“中继任务安排保持不变”的严格解释下主答案。

现已在Q3定稿阶段选择满足严格三组可分区的实算候选，并完整独立验证；之后Q4严格冻结该Q3，不复制、不拆分、不缩短、不重新安排任何运输或中继任务。资源不足按类型报告增补。旧的较快Q3只保留为独立优化对照，不再用作Q4的正式输入。

## 2. 修订前后及实际代价

{table(['指标','旧独立Q3','最终闭环Q3'],[
 ['运输架次',cert['baseline_summary']['trips'],s3['trips']],['中继架次',cert['baseline_summary']['relay_trips'],s3['relay_trips']],
 ['联合最后返回/s',n(cert['baseline_summary']['joint_makespan_s']),n(s3['joint_makespan_s'])],
 ['运输与中继能耗/kWh',n(cert['baseline_summary']['total_energy_kwh']),n(s3['total_energy_kwh'])],
 ['严格依赖图不可拆单元',len(cert['strict_components_before']),len(cert['strict_components_after'])]])}

完工时间代价为{ex['Q3_standalone_vs_closure_time_cost_s']:.6f}秒，能耗代价为{ex['Q3_standalone_vs_closure_energy_cost_kwh']:.6f}千瓦时。不是“加入限制后得到全局更优”，而是在已找到的可行方案中加入下游可分区性筛选。最终候选为{cert['selected_candidate']['candidate']}；{cert['candidate_count']}个备选经严格图检查，其中{cert['feasible_candidates']}个支持至少三个非空独立组，再按及时性、联合完工、能耗和架次数择优。候选集未覆盖所有联合排程，不能声称四问全局最优。

曾另外试验延后单架次并增加专属中继的修复族，但最终发布不采用该高代价方法。源码保留作为候选不足时的明确后备；默认原数据运行选择现有可行备选，不产生第五次中继。

![Q3候选兼容性](../results/figures/closure/candidate_compatibility.png)

## 3. 数值与序列化问题

新Excel导出使用openpyxl，主流程每次从本轮CSV重建工作簿，不复制旧快照。发现默认16有效位浮点序列化可能轻微移动通信边界：数值显示很接近，但边界遮挡判断可不同。本次改为双精度往返可恢复的repr文本写入，并从真实XLSX单元格重新构造轨迹核验；没有放宽能耗、时限或通信判断容差。Excel显示6位小数只是显示规则，不是模型精度。

源坐标仍完全按附件存储，不能靠“四舍五入统一坐标”解决边界错误。主模板的六张表及Q3配套两张表保持原定义与编号引用；严格区分Q2-T和Q3-T命名空间。

## 4. 闭环验收层次

{table(['层次','实际检查量','失败数','对象'],[
 ['原单元格及公式',aud['source_cells_checked'],aud['source_mismatches'],'原始业务表与题面数学对象'],
 ['全量数据质量',q['checks_total'],q['checks_failed'],'缺失、类型、逻辑、地理与全量DEM'],
 ['Q1独立验证',v1['checks_total'],v1['checks_failed'],'逐箱DP、能耗、时间、安全载荷'],
 ['Q2独立验证',v2['checks_total'],v2['checks_failed'],'多点运输、硬时限、机身和电池'],
 ['Q3独立验证',v3['checks_total'],v3['checks_failed'],'运输、中继、全连续区间和边界'],
 ['Q4独立验证',v4['checks_total'],v4['checks_failed'],'严格依赖图、全部划分、最少资源'],
 ['Q4物理继承',v4['physical_checks_total'],v4['physical_checks_failed'],'主方案与均衡对照的实际任务重算'],
 ['单元及错误注入',ut['tests_run'],ut['failures']+ut['errors'],'错误答案应被拒绝而非静默修正']])}

检查次数是程序断言数量，不是统计样本量、正确率置信区间或外部认证。独立程序能验证题定模型中的数学和实现一致性，不能消除DEM分辨率、未给出的飞行功率或天气不确定性。两份最终Excel还需由validate_submission.py只读重验；发布前执行ZIP CRC和逐文件SHA-256核查。

## 5. 保留的前两问

Q1仍为{s1['trips']}架次、{s1['energy_kwh']:.6f}千瓦时、{s1['operation_time_s']:.6f}累计作业秒；Q2仍为{s2['trips']}架次、{s2['energy_kwh']:.6f}千瓦时、{s2['makespan_s']:.6f}秒最后运输返回。第一问没有实体/电池调度、第二问没有通信限制，均符合各问前提。不能将Q2通信直连失败当成Q2违规，也不能把Q1累计工时当多机完工时间。

Q1三种时间分别保存在time_components.csv；安全载荷区分连续质量边界和现有整箱可实现值。正式余量敏感性从20%起，源物理值不改。以下共同模型与各问详述都使用同一套单位、对象ID和物理约束。

## 6. 题意逐项追溯

完整35行来源—要求—实现—边界矩阵为results/closure/requirement_traceability.csv。它是内容核对索引，不伪装成35项独立物理测试。对未由原文唯一确定的分项能耗、时间字段、坐标近似和逐箱交接顺序单独列为建模假设，不隐去。
'''
    texts['05_共同物理规则与假设边界.md']=r'''# 四问共同物理规则、单位与假设边界

## 1. 数据与业务对象

质量kg、体积m³、距离m、时间s、能量kWh、功率kW，坐标为经纬度、海拔为m。载荷q只指货物；含电池空载质量m0参与爬升势能，不能重复加入电池。服务区、箱号和源实体编号在四问间保持不变。不同问题的架次编号各自独立，Q3运输表不引用Q2架次。

## 2. 航段与飞行时间

两节点水平直线经过的全部DEM像元取最高高程再加50m作为计划巡航海拔。O01作业海拔为地面，服务区为题定地面加30m；每个航段完整经历爬升、巡航和下降，多站每次交接后重新爬升，不以净高差替代总爬升。

$$t_{ij,g}=h_{ij}^{+}/v_g^{+}+d_{ij}/v_g^{0}+h_{ij}^{-}/v_g^{-}.$$

距离使用WGS84椭球水平测地长度；地形穿越在源经纬格网中取两点直线。原题未指定唯一投影，差异通过独立地形与距离对照披露。所有真实弧段均全像元核验，绘图使用地形剖面不能代替模型计算。

## 3. 载荷相关航程与能量

题面等效航程的载荷指数为3/2：

$$L_g(q)=L_g^0-(L_g^0-L_g^F)(q/Q_g)^{3/2}.$$

题面给出水平与爬升能耗相加，但没有展开两个分项。本项目公开补充“标准航程对应耗尽单组可用电量”的水平等效模型以及势能/效率模型：

$$E_{ij,g}(q)=E_g^{use}d_{ij}/L_g(q)+(m_{0g}+q)g h_{ij}^{+}/(\eta_g\,3.6\times10^6).$$

下降附加能耗按题定0处理，但下降飞行时间照计。逐站卸货后剩余载荷下降，最后一段空载。每架次的全部航段能耗相加，满足：

$$\sum_{(i,j)\in r}E_{ij,g}(q_{rij})\leq (1-\rho_g)E_g^{use},\qquad SOC_r=1-E_r/E_g^{use}\geq\rho_g.$$

源余量为20%，不要求严格大于。未再从标准航程重复扣一次20%。运输交接的独立功率未提供，因此不捏造运输悬停功率；中继有相应功率则必须计入。这是模型闭合边界，不等于真实运输交接不耗电。

## 4. 交付、占用和两阶段充电

交付时刻为具体货箱交接完成，不是到达服务区。点内按硬截止/期望优先的确定性次序交接，具体次序见逐箱表。任务从准备开始占用机身及一组满电电池；机身返回后可再次准备，电池需从返回SOC按两阶段模型充至100%。中继机身另外计周转，能源组件单独充电；不同实体可并行充电。

$$T_{chg}(s)=T_{full}\left[0.65\frac{\max(0,0.9-s)}{0.9}+0.35\frac{1-\max(0.9,s)}{0.1}\right].$$

Q1“往返时间”解释为准备开始至返回的完整时长；Q2/Q3“开始时刻”解释为准备开始。原模板未进一步限定列义，故这是公开解释，不是额外官方确认。纯飞行、飞行加交接、完整作业全部分别导出。

## 5. 通信模型与未增加的限制

G01位于O01坐标和地面+网关天线高处。灵敏度与衰落裕量求有效接收门限；正、反方向取更小允许传播损耗。地形遮挡增加题定损耗，并非一遮挡就自动中断。直连可用必须直连，否则可选一架同时满足接入及回传链路的中继，不允许中继多跳。

采用O01处WGS84曲率半径构建局部三维米尺度，DEM像元内常高。几何接触按遮挡侧处理；距离与地形视线使用同一仿射几何。没有原题未给的菲涅耳区、容量/带宽上限、碰撞间隔、风速、充电桩数等约束；不将未纳入这些工程因素解释为实际运行安全保证。

## 6. 各问的额外决策范围

Q1只做单区往返，不引入实体与时间排程。Q2不考虑通信，其普通期望时限是评价而非强制。Q3增加连续通信及中继联合调度，并在最终选解时要求可严格划为3个独立任务组，以实现题目四问整体继承。Q4不改变最终Q3任何任务和通信关系；同一中继任务共同保障的运输服务区必须同组，执行前重新配置同型实体不等于重排任务。

Q4不同机型的超库存分别报告，不用闲置能源组件抵扣缺少的无人机。资源件数是明示的无量纲比较目标，不代表经济成本。Q4精确最优仅相对于冻结的Q3及已声明的分区目标。
'''
    budget=rows('q3','radio_bidirectional_budgets')
    texts['06_第三问联合调度与严格继承建模.md']=rf'''# 第三问：连续通信约束下的联合调度与下游可分区选解

## 1. 问题输入和目标

输入为清洗后的16节点、80不可拆货箱、三型8运输机和共享电池、DEM、2中继机、6能源组件与双向链路参数。运输每阶段（包括交接）必须连续可通信，不能只查服务点。联合完工为最后运输机和中继机返回O01的最晚时刻。

首先满足货箱、硬时限、载荷/体积、返航能量、机身/能源库存、充电及连续通信。联合目标按配送及时性D、联合完工、总能耗、两类架次字典序处理。D为源优先级加权的期望逾期量，医疗和首批另设硬约束。本数据D=0，达到非负下界；并不因此证明其他目标全局最优。

$$D=\sum_b\pi_b\max(0,C_b-d_b),\qquad C_{{joint}}=\max\{{\max_r t_r^T,\max_j t_j^R\}}.$$

最终选解时，先要求运输—中继依赖图至少有3个连通分量，再在实际验证的候选中比较上述目标。这是为满足第四问严格任务冻结而增加的透明选择准则，不是说题目第三问单独强制这项约束。

## 2. 双向无线预算

$$P_{{th,b}}=S_b+M_b,\quad L_{{max,a\to b}}=P_{{t,a}}+G_a+G_b-L_{{sys}}-P_{{th,b}}.$$

$$L_{{max,ab}}=\min\{{L_{{max,a\to b}},L_{{max,b\to a}}\}}.$$

{table(['链路','正向上限/dB','反向上限/dB','双向上限/dB'],[[{'direct':'直连','access':'中继接入','backhaul':'中继回传'}.get(r['link_type'],r['link_type']),r['forward_loss_limit_db'],r['reverse_loss_limit_db'],r['bidirectional_limit_db']] for r in budget])}

题定频率2400MHz，遮挡附加损耗10dB，路径损耗：

$$L_{{ab}}(t)=32.45+20\log_{{10}}(2400)+20\log_{{10}}(d_{{ab}}(t)/1000)+10B_{{ab}}(t).$$

d输入m，除1000为km。源模型常数32.45不能改为习惯的32.44。直连可用优先选直连；否则存在一架服务中的中继，接入和回传同一时刻均可用才为中继状态。每架运输机同刻只能有一个保障者，不进行中继多跳。未提供用户容量上限，不能擅自将中继限制为一次只服务一架运输机。

## 3. 连续通信判定算法

一个飞行或交接阶段的位置为仿射轨迹P(s)=P0+s(P1−P0)。连接固定锚点A与全段轨迹得到视线三角扇面：

$$X(u,v)=A+u(P_0-A)+v(P_1-A),\quad u\geq0,\ v\geq0,\ u+v\leq1.$$

对扇面经过的各DEM像元叠加平面边界及视线高度不高于地形的约束，得到凸多边形；参数s=v/(u+v)投影的顶点极值给出完整遮挡区间。汇总像元区间求并集。每个固定遮挡状态段内，距离平方为s的二次函数，解门限根，再合并阶段端点、中继建链/结束时刻和阴影边界，形成状态不变的开区间。所有孤立边界点另用静态视线检查。

独立验证不调用主裁剪函数，而是用半平面边界两两交点枚举多边形，再以独立AW格网遍历复核单点；完整区间与边界合在一起支撑连续覆盖。稠密时间/空间样本只作实现交叉检查，不能替代连续性证明。

最终共有{s3['communication_atoms']-s3['communication_boundary_points']}个正长度区间、{s3['communication_boundary_points']}个孤立边界点。模板的零时长行用“·边界点”标识；它们表示真实瞬时约束，不是缺失或重复任务。公开采用开区间加唯一端点状态的表示，避免共享边界双重指派。

## 4. 中继航程、服务与能源

悬停点须在有效DEM内，离地不超{rm['max_hover_agl_m']}m。计划总起飞质量{rm['takeoff_mass_kg']}kg已包含能源及通信载荷。中继可用能量{rm['usable_energy_kwh']}kWh，返航余量{rm['reserve_fraction']*100:.0f}%；准备{rm['prepare_s']}秒、建链{rm['link_setup_s']}秒、机身周转{rm['turnaround_s']}秒。往返净空沿用每条弧段最高地形+50m规则。

水平能耗由巡航功率与巡航时间确定，爬升由势能/效率模型确定。驻留从到达悬停点起计悬停和通信功率，包括建链过程；只有建链完成后才计通信服务可用。服务结束后返回，不把航途中的中继当已建链服务者。

$$E_j^R=P_{{cr}}(t_{{out,cr}}+t_{{in,cr}})/3600+E_{{up,out}}+E_{{up,in}}+(P_{{hov}}+P_{{com}})(b_j-t_{{arr,j}})/3600.$$

每个中继机身任务区间延长到返回+周转；能源组件延长到返回+充电至100%。二者分别排程；不同资源可同时充电。全部任务在源库存内完成，不调用Q4后来假设增补的库存。

## 5. 求解技术路线与停止规则

第一层在完整有效DEM以{candidates['grid_stride_pixels']}像元步长扫描{candidates['grid_positions_scanned']}个平面候选，用回传预算和运输候选采样点筛选。候选高度取沿途规则巡航海拔和地形+最大AGL中的较低值，额外剔除低于{Q3CFG.candidate_min_agl_m}m的候选；它是公开的有限搜索子域，不能说覆盖了所有连续高度。

第二层采用2架中继各前后2次任务的结构，联合邻域搜索货箱移动、换型、站序、合并/拆分及破坏修复。每个候选运输架次通过连续几何求可开始时间窗，在机身和满电电池可用后安排；不是只给Q2成品路线添加通信标签。所有随机种子和预算集中q2_config.py、q3_config.py，固定迭代而非超时截断。

第三层固定运输路线、位置和中继实体顺序，用MILP选择通信原子的唯一提供者及中继起止，先最小联合完工，再在最优容差内最小中继能耗。输出阶段状态、间隙和约束残差，只是该固定子问题证书。

第四层外层改进保存全部已求得可行备选。在Q3定稿前计算每个备选的运输与中继依赖连通分量，至少3个才可进入闭环主方案选择。当前候选{cert['selected_candidate']['candidate']}被选中，未改它的具体物理任务。最终再次独立核验，从最终Excel回读核验后才冻结给Q4。

{table(['实算候选','严格分量数','支持三组','联合返回/s','总能耗/kWh'],[[r['candidate'],r['component_count'],'是' if r['strict_K3_feasible']=='True' else '否',n(r['joint_makespan_s']),n(r['total_energy_kwh'])] for r in choices])}

该有限候选筛选不是全局联合最优证明。旧更快的独立Q3不支持严格三组，不能一方面沿用它的时间/能耗，一方面在Q4偷偷使用另一组中继任务。

## 6. 最终结果

{table(['指标','最终值'],[['运输架次',s3['trips']],['中继架次',s3['relay_trips']],['机型架次',str(s3['model_trip_counts'])],['多服务区架次',s3['multipoint_trips']],['运输能耗/kWh',n(s3['energy_kwh'])],['中继能耗/kWh',n(s3['relay_energy_kwh'])],['总能耗/kWh',n(s3['total_energy_kwh'])],['最后箱交付/s',n(s3['last_box_delivery_s'])],['最后运输返回/s',n(s3['transport_makespan_s'])],['最后联合返回/s',n(s3['joint_makespan_s'])],['最低运输返航SOC/%',n(100*s3['min_return_soc_fraction'])],['最低中继返航SOC/%',n(100*s3['relay_min_soc_fraction'])]])}

{table(['运输架次','机型/实体','访问顺序','准备开始/s','返航/s','能耗/kWh'],[[r['trip_id'],r['model_id']+'/'+r['drone_id'],r['visit_order'],n(r['start_s'],3),n(r['return_s'],3),n(r['energy_kwh'],5)] for r in tr])}

{table(['中继架次','实体/组件','经度','纬度','海拔/m','离地/m'],[[r['relay_trip_id'],r['relay_drone_id']+'/'+r['energy_module_id'],n(r['hover_lon_deg'],8),n(r['hover_lat_deg'],8),n(r['hover_altitude_m'],3),n(r['hover_agl_m'],3)] for r in rr])}

{table(['中继架次','准备开始/s','完成建链/s','服务结束/s','返回/s','能耗/kWh'],[[r['relay_trip_id']]+[n(r[k],3) for k in ('start_s','link_complete_s','service_end_s','return_s','energy_kwh')] for r in rr])}

显示小数不改变存储值。全部80箱恰好一次，医疗{s3['medical_on_time']}/{s3['medical_boxes']}、首批{s3['first_batch_on_time']}/{s3['first_batch_boxes']}按硬时限交付，所有{s3['all_expected_on_time']}箱均不晚于期望时间。运输电池使用{s3['battery_units_used']}组，满电复用{s3['battery_reuses']}次；中继机身{s3['relay_bodies_used']}架、能源组件{s3['relay_modules_used']}组，均在源库存内。

![第三问完整运输与中继位置](../results/figures/q3/q3_01_routes.png)

![连续通信保障时序](../results/figures/q3/communication_timeline.png)

## 7. 可行性与最优性边界

独立检查{v3['checks_total']}项失败{v3['checks_failed']}，额外稠密检查{v3['dense_samples']}点失败{v3['dense_failed']}。此结果支持源确定性场景与共同补充模型下的可行性；不支持天气、测绘或时钟任意变化下的无条件安全。条件MILP的最优性不推广到连续选址及全部货箱路径组合。Q3最终版本和Q4源哈希完全对齐；后续第四问只配置与划分，不改本节任务。
'''
    stress=rows('q3','propagation_loss_sensitivity');delay=rows('q3','relay_only_delay_sensitivity');common=rows('q3','common_start_delay_sensitivity')
    texts['07_可靠性压力测试与失败情景.md']=rf'''# 可靠性压力测试与失败情景

## 1. 不混淆三类实验

重优化实验指改变参数后重新求解，如Q1各档安全余量和能耗分项扰动；冻结排程压力测试只修改指定物理量并检查现有任务，不调路线/机身/开始时刻；纯诊断视图是对已求得结果按不同维度绘图，不构成新的优化试验。本包图件多，不能把每一张图称为一次独立随机实验。

## 2. Q3额外传播损耗

冻结运输及中继位置/时间，允许按题定直连优先规则在已部署单跳链路中重新选择。每个损耗档重解距离门限根并重建连续区间，不只是查原来中点。

{table(['额外损耗/dB','累计断链/s','断链边界点','连续可行'],[[r['extra_loss_db'],n(r['outage_duration_sum_s']),r['uncovered_boundary_points'],'是' if r['continuous_feasible']=='True' else '否'] for r in stress])}

![传播损耗压力测试](../results/figures/q3/propagation_loss.png)

最大已测试通过值{re['max_tested_extra_loss_feasible_db']:.6f}dB只说明该测试维度；不证明未测试区间或真实干扰分布的可靠率。0损耗基准应完全通过，否则不得提交。

## 3. 延迟情景不可互相替代

全部运输、中继、充电共同平移时相对通信和资源关系不变，硬截止固定。当前最紧硬时限裕度为{s3['min_hard_deadline_slack_s']:.6f}秒；这是统一平移的边界，不是某架中继单独迟到的边界。仅中继晚到、原通信分配不变的结果如下：

{table(['中继单独延迟/s','未覆盖累计区间/s','未覆盖边界点','原分配可行'],[[r['relay_only_shift_s'],n(r['fixed_assignment_uncovered_duration_s']),r['fixed_assignment_uncovered_points'],'是' if r['fixed_assignment_feasible']=='True' else '否'] for r in delay])}

![中继单独迟到诊断](../results/figures/q3/relay_delay.png)

不同运输机保障时间累加可大于日历时间，不把它误解为一个全局断网窗口。原分配失败也不自动证明允许重新选链路后仍失败；两种检验必须区别。

## 4. 运输能耗与充电速度压力测试

新增{ex['additional_energy_scenarios']}组能耗倍率场景、{ex['additional_charging_scenarios']}组充电时间倍率场景，均分别作用于Q2和最终Q3。能耗增加时重新计算返航SOC和同一电池从该SOC充满所需时间，再检查下一次任务能否开始。仅充电倍率试验不改变飞行能耗。二者均冻结任务与资源分配，不宣称是重优化后的最优方案。

新增{ex['common_delay_scenarios']}组共同延迟细网格场景，每问0至600秒、10秒一步，统计硬截止与普通期望逾期货箱数。失败点以违约数量和负裕度保存，不能删去后声称全场景可行。每个运输架次另给只针对SOC约束的能耗放大上界，不能代替含充电/通信的鲁棒上界。

![能耗倍率与SOC](../results/figures/closure/energy_soc.png)

![充电倍率与资源裕度](../results/figures/closure/charge_slack.png)

![共同延迟与硬期限](../results/figures/closure/delay_slack.png)

## 5. 结果使用限制

Q2最紧硬裕度{s2['min_hard_deadline_slack_s']:.6f}秒，明显比最终Q3小。不能将两个不同任务方案的这个差解释为通信本身提高鲁棒性的因果效应。Q3不同候选的目标与路线均可能变化，本项目只报告各自的可测裕度。无风速/随机作业时间的实测分布，不虚构蒙特卡洛可靠率、置信区间或大样本实验。

全部试验源表位于results/closure和results/q3。中文图中的扰动横轴是人为测试参数，不是原始附件观测；参考0/1倍基准与正式答案数值一致。
'''
    kk=[s4['selected'][str(k)] for k in (2,3)];ac=rows('q4','atomic_components');allp=rows('q4','all_partitions')
    texts['08_第四问严格任务冻结与资源配置.md']=rf'''# 第四问：严格保持第三问任务的分区与资源配置

## 1. 输入冻结与原错误修复

本问输入为本版最终Q3：{s3['trips']}运输架次、{s3['relay_trips']}中继架次及对应逐箱/通信表。源题要求货箱组批、访问次序、运输与中继任务安排和通信关系保持不变。因此不同组不能复制同一中继任务，也不能让一架中继在执行时同时属于两个组。

旧包三组主表采用额外中继副本解释，已退出正式答案。现在先在Q3选择可严格分为三组的实算候选，再冻结给Q4；Q4不靠更改原Q3凑出可行划分。两种分区的中继任务总数均恰好{s3['relay_trips']}，没有额外能耗或改变完工时间。

## 2. 不可拆分单元的构造与完整枚举

构建以服务区为顶点的图：同一运输架次访问的全部服务区加必须同组边；依赖同一个源中继任务的全部运输服务区也加必须同组边。连通分量是不可拆分单元。任何合法组是这些单元的并；若拆开一个分量，必然违反运输同组或通信任务唯一所有权。

{table(['单元','服务区','箱数','运输架次','运输工作量占比'],[[r['component_id'],r['services'],r['boxes'],r['transport_trips'],f"{100*float(r['transport_workload_share']):.6f}%"] for r in ac])}

共{s4['component_count']}个分量。采用限制增长串枚举无标签非空划分，K=2有{s4['partition_counts']['2']}种，K=3有{s4['partition_counts']['3']}种，共{s4['total_enumerated_partitions']}种。独立程序用DFS重建图、另一套锚定集合递归枚举，核对集合完全相同。旧版只用运输依赖得到的364种不是严格通信冻结的合法空间，不能继续引用为最终候选数。

## 3. 最少资源配置的区间模型

运输机身占用[准备开始,返回)，运输电池占用到返回后充满；中继机身占用到返回+周转，中继能源占用到返回+充满。半开区间允许在资源恰好可用时开启下一任务，数值容差只吸收浮点舍入，不省略充电。固定时序、同型资源相同条件下，最少数量等于该类区间最大同时重叠数：

$$n_{{g,r}}=\max_t\sum_{{a\in A_{{g,r}}}}\mathbf{{1}}\{{s_a\leq t<e_a^{{ready}}\}}.$$

以开始时间排序、最早可用资源复用给出达到该下界的分配。独立验证用区间相容图最大匹配/最小路径覆盖核对最少数量，而不是只重算同一个贪心公式。每类输出峰值时刻及同时占用任务作下界见证。

资源执行开始前可按组重新指派同型实体；任务时刻、载荷、通信锚点不变。源实体ID的重新配置只是本问求独立需求的操作，不是执行过程中跨组借用。源库存从原表读取，任务执行时每个物理ID只能属于一个组。标识“@K3-G1”等仅表示源任务归属，不代表复制第二次任务。

## 4. 目标与比较量

优先最小分类型库存缺口总件数，再最小资源总件数，再最小运输累计作业量变异系数。各类型库存I_r，组需求n_gr：

$$G=\sum_r\max(0,\sum_g n_{{g,r}}-I_r),\quad R=\sum_{{g,r}}n_{{g,r}}.$$

$$CV=\frac{{\sqrt{{K^{{-1}}\sum_g(W_g-\overline{{W}})^2}}}}{{\overline{{W}}}}.$$

W是运输完整作业累计时间，不是组的最后返航时刻或组内服务区个数。资源件数是公开无量纲比较标准，不能解释为采购成本。剩余中继能源不能抵扣缺少的C型无人机。另给均衡优先对照与各型库存冗余。

## 5. 全部候选与主方案

{table(['候选','组数','资源件数','缺口件数','运输工作量CV'],[[r['partition_id'],r['K'],r['resource_units'],r['shortage_units'],n(r['transport_workload_cv'])] for r in allp])}

{table(['分区','组','服务区'],[[str(k)+'组',g['group_id'],g['services']] for k in (2,3) for g in rows('q4',f'K{k}/groups')])}

{table(['资源类别','原库存','两组需求','三组需求','两组缺口','三组缺口'],[[name,s4['inventory'][key],kk[0]['need_'+key],kk[1]['need_'+key],kk[0]['gap_'+key],kk[1]['gap_'+key]] for key,name in zip(RESOURCE_KEYS,RESOURCE_NAMES)])}

两组总需{kk[0]['resource_units']}件、缺口{kk[0]['shortage_units']}件；三组总需{kk[1]['resource_units']}件、缺口{kk[1]['shortage_units']}件。全部严格候选中原库存可行数：两组{s4['inventory_feasible_partition_counts']['2']}、三组{s4['inventory_feasible_partition_counts']['3']}。这不影响本问报告“所需独立配置”，但必须说明要增补后才可执行，不能将配置需求说成现库存已够。

![两组任务划分](../results/figures/q4/partition_K2.png)

![三组任务划分](../results/figures/q4/partition_K3.png)

两组与三组总运输/中继能耗均为{s3['total_energy_kwh']:.6f}kWh，联合完工均为{s3['joint_makespan_s']:.6f}s，来自严格任务继承而非新的优化测量。分区改变资源在组间的可复用性，不改变固定任务执行时间。因此设备变多不应在本模型下自动使任务变快。

## 6. 均衡与冗余的含义

最大不可拆单元占运输工作量{100*max(float(r['transport_workload_share']) for r in ac):.6f}%，限制了任何合法均衡。资源优先两组CV为{kk[0]['transport_workload_cv']:.6f}，三组为{kk[1]['transport_workload_cv']:.6f}；不能因为任务组较多就说均衡必然改善。三组只有一种严格划分，均衡优先与资源优先重合不是搜索不足，而是合法空间只有一个元素。

未分区时按固定时序重新优化能源编号可少用中继组件，源Q3使用了{s3['relay_modules_used']}个ID，而区间下界是{s4['baseline_minimum_resources']['relay_energy']}组。因此要区分原方案实际使用ID数、同一时序最少配置数、独立分组导致的增量和原库存冗余，不能把四个量混为一谈。

## 7. 独立验证

Q4独立图与枚举、逐资源最少数量、源任务映射和主表共{v4['checks_total']}项检查，失败{v4['checks_failed']}。主方案和均衡对照另做{v4['physical_checks_total']}项运输、中继、时限及连续通信核验，失败{v4['physical_checks_failed']}。从最终工作簿回读数量并关联详细本地资源表，验证实际提交而非内存字典。

精确最优性只相对于本版冻结的Q3、同型资源可在执行前配置的规则及目标顺序。没有证明原题全部可能Q3方案中本分区最省资源，也不使用额外库存倒灌修正Q3可行性。
'''
    texts['09_模板提交与一键复现.md']=rf'''# 模板提交、数值闭环与一键复现

## 1. 提交组成

主文件submission/结果提交.xlsx保留原模板全部表名、单位、顺序和标题，已经填写Q1—Q4。Q3运输与逐箱交付不在原模板中单列，因此另附submission/Q3运输与逐箱补充.xlsx；不能用Q3运输覆盖Q2运输。两份文件和提交必读.txt应一起交付。

{table(['主模板表','数据行数'],vx['sheet_row_counts'].items())}

{table(['Q3配套表','数据行数'],vx['companion_row_counts'].items())}

全部CSV为UTF-8 BOM，JSON保留数值/布尔/null类型。NoData只用于地理栅格，不把合法负通信灵敏度当缺失。每箱唯一、时刻、能耗、百分比都从同一个当次答案导出；通信边界点的零时长语义在共同模型里明示。

## 2. 环境和入口

Python3.13.5；依赖版本固定在requirements.txt。仅CPU，第一次安装依赖需要联网，求解/验证/绘图/报告可离线。无需商业优化器、MATLAB、GPU或本机Excel。openpyxl是固定依赖，主流程每次重建XLSX，不再依赖artifact_tool或参考Excel快照发布。系统需要已有中文字体；优先Noto Sans CJK/思源/黑体，缺字体时绘图会报错而不发布乱码；包内不分发字体文件。

```bash
python -m pip install -r requirements.txt
python run_all.py --check-reference
python validate_submission.py
```

仅重算冻结Q3后的Q4：

```bash
python run_q4.py --check-reference
```

代码通过主脚本位置解析路径，与当前工作目录无关。自动生成目录data/cleaned、results、docs、submission、paper会重建；不要把个人追加文件放在其中。data/raw逐文件哈希必须保持不变。关键参数集中config.py、q2_config.py、q3_config.py、q4_config.py、closure_config.py，源装备与期限从附件读取。

## 3. 最终Excel反向验收

本次主表逐格检查{vx['cell_checks']}项、配套表{vx['companion_cell_checks']}项。重新读取后按原始DEM和机型复算Q1、Q2、Q3物理，再检查Q4源任务继承和组内资源需求。XLSX存储repr双精度字符串，显示小数不成为约束输入。validate_submission.py只读工作簿，不修改错误答案来通过校验。

--check-reference只在计算结束后与reference/expected_results.json比较，不进入优化器。原数据复现应一致；主动改变模型或源参数后参考失败是预期，不应反过来硬编码旧答案。MILP状态/间隙仅适用于所建固定子问题。

## 4. 完整复现与打包

运行日志含实际环境、阶段耗时、单元测试、原文件哈希、图表来源索引及数值快照。两次独立运行比较CSV/JSON、PNG/SVG/PDF与Markdown以及全部工作簿单元格；ZIP/DOCX/XLSX内部生成标识不作为数学一致性标准。发布包还做压缩CRC和逐文件SHA-256检查。

```bash
python -m unittest discover -s tests -v
python package_delivery.py
```

该检查仍不等于证明启发式全局最优或现场安全。Q1模型内精确、Q2/Q3验证可行、Q4固定Q3后的严格图全枚举最优；这些限定不得从摘要或结论中省略。
'''
    # 论文骨架：提供章节级论证、式/表/图/源结果定位；不预设用户未来LaTeX类文件。
    outline=f'''# 整体论文大纲与LaTeX填充映射

## 论文拟题

山区洪涝场景下基于连续通信保障与严格任务继承的无人机运输及分区资源优化

标题中的“严格任务继承”对应实际Q3—Q4闭环修复，不使用“全局最优”“完全鲁棒”等本实验未证明的表述。待收到LaTeX模板后适配标题、页边距、摘要长度、参考文献和附录；本大纲不是官方版式规定。

## 摘要与关键词

摘要按“任务背景—统一模型—四问方法与关键结果—验证与适用条件”组织。Q1写{s1['trips']}架次及{n(s1['energy_kwh'])}kWh，并说明字典序及模型内精确性；Q2写{n(s2['makespan_s'])}秒最后运输返回；Q3写{n(s3['joint_makespan_s'])}秒联合返回、{n(s3['total_energy_kwh'])}kWh与全连续通信；Q4写严格两/三组的{kk[0]['shortage_units']}/{kk[1]['shortage_units']}件分类型库存缺口。末句交代独立复核和启发式非全局最优，不只列检查数量。

关键词建议：异构无人机；不可拆货箱；连续通信；共享电池；严格任务继承；分区资源配置。

## 第一章 问题重述与四层递进关系

### 1.1 场景与统一输入

说明1调度中心、15服务区、80箱与源库存；现实背景只作动机，标准场景参数以附件为准。不得使用背景报道的受困人数替代本场景需求。

### 1.2 四问边界及输出

Q1无实体排程、单点往返；Q2多点/多架次/实体与共享电池、无通信；Q3运输与中继联合连续通信；Q4严格冻结Q3做独立分区。给一张问题—输入—新增约束—输出表。解释Q1累计工时和Q2/Q3最后返回不相同。

### 1.3 总体技术路线

数据审核→公共物理→Q1精确组批→Q2资源调度→Q3通信与可分区候选选解→Q4冻结依赖分区→CSV/Excel反向核验。文字框架后续可按模板排版；不要用未经数据支持的装饰图代替计算。

## 第二章 模型假设、符号与数据清洗

### 2.1 题定规则与补充假设分列

明确两个能耗分项闭合、总体积替代三维箱几何、点内交接次序、准备占用、局部三维坐标、DEM分片常高、源题未给的工程约束。列“假设—作用—影响—敏感性证据”四列。

### 2.2 统一符号表

服务i、箱b、机型g、运输架次r、中继架次j、实体u、能源k、任务组c。q仅货物质量、m0含电池空载质量；w_b质量与π_b优先权重不重名；C_b交付完成，T_r返回，Cjoint联合完工。

### 2.3 全量质量检查和清洗

缺失语义、重复样本/合法地理闭环点、类型、单位、逐类逐箱需求一致性、DEM NoData、节点高程差异和源字典追溯。报告处理前后变化，不删除真实困难样本。

建议主图：F对应“数据核查：全部货箱按服务区分布”“原始全分辨率地形与任务节点”“题定节点海拔与DEM像元差异”；具体F编号以paper/figure_catalog.csv为准。主表为清洗规则与前后数量。证据：results/quality、data/cleaned。

## 第三章 公共飞行、能耗、交付与能源周转模型

### 3.1 全像元净空与三阶段飞行

给水平直线、巡航高程=max DEM+50米、O01地面/服务区30米的公式与剖面；解释每次投送后重新爬升。说明主逐像元算法和独立有向弧检查。

### 3.2 负载相关航程与往返能耗

给3/2航程关系、分项假设、逐段剩余载荷、空载返程和20%余量。证明在Q1单点情形能耗随去程载荷单调，给二分求根依据。

### 3.3 逐箱交付与资源区间

逐箱交付取完成交接；准备/装载/交接分项计时；电池按90%拐点两段充电至100%。机身、能源分别占用，源库存包含初装与备用；相同时间开始下一任务的半开区间解释。

建议主图：一条瓶颈地形剖面、两阶段充电公式配资源甘特局部；完整15条剖面放附录。证据：results/q1/route_geometry.csv、results/q2/arc_geometry.csv与battery_cycles.csv。

## 第四章 问题一：安全载荷与不可拆货箱精确组批

### 4.1 连续最大安全载荷与整箱能力

定义q_safe，区分额定质量、连续边界、现有箱子组合的离散可实现值。输出15×3能力表及见证箱号；空载不可行用null而非有意义的0kg。

### 4.2 可行批次枚举与集合划分

候选均属于一个服务区，同时满足质量、体积和全往返能量。每箱覆盖等式=1。依据箱型等价压缩数量状态，说明为什么此问时限不进入等价性。

### 4.3 字典序动态规划与最优性

推导F(n)=min_lex[F(n−u)+(1,E_u,T_u)]并用最优子结构归纳；独立逐箱身份位掩码DP核验。用15个区域最低一趟加三个超80kg区域得到18架次下界，并展示达到下界。

### 4.4 结果、权衡与敏感性

报告18架次、B9/C9、{n(s1['energy_kwh'])}kWh与{n(s1['operation_time_s'])}累计秒；列能耗优先对照、精确N—E前沿。合规安全余量从20%起重新优化；说明不可拆导致跳变和S008瓶颈。能耗分项扰动另述。

建议主图4幅：45组安全载荷、连续/离散对照、N—E前沿、余量—架次数；15条载荷曲线和全批次台账入附录。证据：results/q1全部。

## 第五章 问题二：异构多点运输与共享电池联合调度

### 5.1 决策变量及硬/软约束

箱—架次—访问序—机型—实体—电池—开始时刻；逐站卸载、空返、资源不重叠、满电复用；医疗期望及首批截止硬约束，其他期望用于加权迟到。完工定义为最后运输返回。

### 5.2 固定种子邻域搜索与资源解码

解释移动、交换、换型、合并拆分和破坏修复；最早可用机身/电池解码与固定预算。给简洁伪代码和参数表，不堆源代码正文。

### 5.3 下界与方案对照

给工作量LP松弛的放松方向和对偶残差；区分可行上界、松弛下界、相对间隙，不以不再改进冒充全局证明。比较同预算单点、多点、节能以及冻结Q1的诊断；硬违约诊断不能作为候选答案。

### 5.4 主结果与资源/时限验证

{ s2['trips']}架次、{n(s2['energy_kwh'])}kWh、{n(s2['makespan_s'])}秒；列80箱完成、硬时限、最紧裕度和电池充电检查。建议主图4幅：路线、机身甘特、电池甘特、完成时间—能耗权衡；80行交付表入附录。

## 第六章 问题三：连续通信联合调度及闭环选解

### 6.1 双向预算和地形遮挡

灵敏度加衰落裕量、双向最小门限、32.45常数FSPL、遮挡附加损耗；直连优先、单中继、接入/回传同刻可用。

### 6.2 全连续区间与边界点算法

仿射轨迹、锚点三角扇面与像元半平面，阴影区间并集、距离二次根、建链/服务切换点。分别论证开区间状态不变与边界静态复核，解释独立几何方法以及稠密采样为何仅为补充。

### 6.3 中继飞行、建链、驻留和独立能源

给源参数表与功率能耗；准备、建链、服务、返回、机身周转/能源充电时序；库存内使用情况；候选空间限制公开。

### 6.4 联合算法与严格可分区候选筛选

有限DEM候选→通信时间窗→运输邻域→固定子问题MILP→外层候选库→严格三分区资格→择优独立复核。必须呈现Q3定稿前选择过程，不能在Q4复制中继后仍引用旧Q3。

### 6.5 最终结果与代价

最终{s3['trips']}运输+{s3['relay_trips']}中继，{n(s3['joint_makespan_s'])}秒联合返回，{n(s3['total_energy_kwh'])}kWh。较旧较快独立Q3多{ex["Q3_standalone_vs_closure_time_cost_s"]:.6f}秒及{ex["Q3_standalone_vs_closure_energy_cost_kwh"]:.6f}kWh，运输架次变化{s3["trips"]-cert["baseline_summary"]["trips"]:+d}，形成{s4["component_count"]}个严格分量。解释这不是相同可行域的全局最优值比较。

### 6.6 连续保障与压力试验

给区间+边界核验及Excel回读、传播损耗、仅中继迟到、共同延迟各自结果。失败情景保留；不宣传任意迟到鲁棒。建议主图5幅：联合路线、运输/中继甘特、通信时序、候选兼容性、代表性链路/延迟压力图。{s3["trips"]}架运输高度和{s3["relay_trips"]}架中继剖面入附录。

## 第七章 问题四：严格冻结任务的分区及资源需求

### 7.1 运输与中继双重依赖图

同架次服务区必须同组，同源中继任务依赖也必须同组。给3个最终连通分量和不可拆证明；没有中继副本或跨组共享。

### 7.2 全划分枚举与最少资源

限制增长串枚举3个两组、1个三组；固定任务区间最大并发下界与达到下界的分配；独立最大匹配复核。电池占用延长至充满，中继机身延长至周转。

### 7.3 资源缺口优先与均衡对照

给逐类型缺口、总件数、工作量CV定义；指出总库存件数够不等于分型够。列全部4候选，主分区地图、逐类配置表，比较原库存、未分组最小配置、实际ID数量与分区额外成本。

### 7.4 主结果与适用条件

两组{kk[0]['resource_units']}件/缺口{kk[0]['shortage_units']}件，三组{kk[1]['resource_units']}件/缺口{kk[1]['shortage_units']}件。按型号补足后独立执行可行；无原库存可行分区。两种分区任务能耗/完工与最终Q3完全相同，是冻结继承的校验恒等式，不是重排优化结果。

建议主图4幅：严格分量工作量、两/三组地图、库存缺口、全候选权衡；各组资源甘特入附录。主表包括不可拆单元、主分区、8类库存—需求—缺口。

## 第八章 四问闭环核验、灵敏度与模型评价

### 8.1 前向生成与反向复核

源表→清洗→物理→方案→CSV→Excel→独立重构→报告/图件哈希。逐问说明第二套算法和错误注入测试，检查次数不当成概率置信度。

### 8.2 严格继承一致性

Q1/Q2数值保持，Q3改选候选明确记录，Q4每任务恰好一次、时间/能量/箱归属恒等、资源不跨组。说明并修复默认XLSX16位浮点边界问题。

### 8.3 扰动试验统一矩阵

重优化余量/能耗分项与冻结能耗/充电/延迟分列；0/1倍基准与主答案相符，失败点保留，分类型上界不合并成无条件可靠率。

### 8.4 优点、局限和改进方向

优点：需求身份守恒、公共物理统一、连续通信而非采样、严格任务继承与独立核验。局限：两个能耗分项补充、地形分辨率/局部坐标、候选和启发式最优性范围、确定性时限裕度、Q4依赖选定Q3。提出后续扩展但不声称已经实验验证。

## 第九章 结论与提交说明

逐问回答而非复述背景，列最终指标及限定条件。最后说明主工作簿与Q3配套必须一起交付，Q1累计时间和Q2/Q3最后返回定义；附件包含代码、环境、测试、原始与清洁数据、完整结果及图件。

## 参考文献与附录

参考文献以题面、附件说明及真正查阅的原始方法/官方文档为主，正文提及才引用；源背景不外推为当前新闻。后续使用用户LaTeX参考文献样式。附录A单位与字段字典；B全部载荷与组批；C逐箱与资源台账；D通信区间/边界证书；E全部候选分区及并发下界；F压力试验完整表；G伪代码/核心代码及版本；H图件索引和复现记录。

## 图表选用与篇幅建议

建议正文选约18—24幅关键信息图，不把{len(figs)}幅全部塞进正文。每幅图旁写“输入/规则—观察结果—能支持和不能支持的结论”。每类15/25条细剖面放补充附录或电子附件；图号按最终模板重新连续编号。所有中文PNG/SVG/PDF同源，LaTeX优先直接使用矢量PDF。

paper/figure_catalog.csv给出逐图中文标题、路径、源表和绘图数值；paper/results_macros.tex由本轮JSON生成的结果宏，收到模板后引用而非手抄。主章节关键表优先从CSV程序化生成，避免调整正文后遗留旧的6570.184296或旧三组副本能耗。
'''
    texts['10_整体论文大纲与填充映射.md']=outline
    texts['11_中文图件索引与正确引用.md']=rf'''# 中文实验图件索引与正确引用

共{len(figs)}幅独立图，每幅提供PNG（阅读）、SVG（矢量编辑）、PDF（LaTeX直接引用）。标题、坐标轴、图例均中文；Q1、Q2、Q3、机型和源ID是标识而不是未翻译叙述。中文字体来自操作系统，不随包分发字体。每图paper/figure_data记录源表SHA-256、实际绘图系列和文字，防止图件与结果分离。

图多不等于独立实验多：逐服务区/逐架次剖面是同一已验证方案的不同诊断视图；压力场景另在results/closure和results/q3列出。对失败情景不可将曲线截掉后写“全部通过”。论文正文建议选18—24幅，其余作为附录图集。

{table(['图号','中文图题','图文件'],[[r['图号'],r['中文图题'],r['图文件']] for r in figs])}

数据源及绘图数值定位见paper/figure_catalog.csv。图中的“累计通信时间/累计作业时间”是按设备相加，不能与日历最后返回互换；区间中点链路裕量直方图不是连续最低裕量证明。图中未绘制的不可行值在源表明确标识，不默认为0。
'''
    texts['12_参考来源与参数选择说明.md']='''# 参考来源与参数选择说明

## 1. 题目与附件

[1] 用户提供《山区洪涝灾害下无人机运输与通信协同优化》，问题一至四、附录1—3。原件data/raw/题面.docx。

[2] 原始数据内五个基础工作簿：调度中心与服务区、物资需求与配送时限、运输无人机、中继无人机、通信链路参数。业务参数和库存均以源表为准。

[3] 原始地理数据及其说明：30米DEM、节点/区域等公开地理数据。使用完整有效DEM，源像元不做削峰平滑。

## 2. 实现接口参考

[4] SciPy官方scipy.optimize.milp及linprog接口文档（访问日期2026-09-23）。https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html 。返回状态与间隙仅对应传入的线性/混合整数模型，不构成全部非线性联合问题最优性证明。

[5] Matplotlib官方字体文档（访问日期2026-09-23）。https://matplotlib.org/stable/users/explain/text/fonts.html 。图件采用系统CJK字体，SVG路径化与PDF嵌入子集实现跨平台显示；不分发字体文件。

## 3. 独立推导及未验证事项

载荷单调二分、计数状态DP、不可拆分图、区间并发下界与资源分配正确性在本项目报告给出证明，不将它们写成外部论文的实验结论。通信阴影区间几何和独立检查的数值输出由本项目源码产生。题面列出的无人机规格和灾情参考资料未用于覆盖附件参数，也不作为额外实测校准。

待LaTeX写作时，仅引用确实用于论证的资料，按模板整理BibTeX。不要从本报告新增没有实验支持的准确率、随机置信区间或经济成本。所有源公式、参数、算法自选设置应分列。
'''
    (docs/'参考与参数说明.md').write_text(texts['12_参考来源与参数选择说明.md'],encoding='utf-8')
    for name,text in texts.items():(docs/name).write_text(text,encoding='utf-8')
    paper.mkdir(exist_ok=True);(paper/'论文大纲.md').write_text(outline,encoding='utf-8')
    macros={'QOneSorties':s1['trips'],'QOneEnergy':n(s1['energy_kwh']),'QOneWorkSeconds':n(s1['operation_time_s']),
        'QTwoSorties':s2['trips'],'QTwoMakespan':n(s2['makespan_s']),'QTwoEnergy':n(s2['energy_kwh']),
        'QThreeTransportSorties':s3['trips'],'QThreeRelaySorties':s3['relay_trips'],'QThreeMakespan':n(s3['joint_makespan_s']),'QThreeEnergy':n(s3['total_energy_kwh']),
        'QFourTwoGroupGap':kk[0]['shortage_units'],'QFourThreeGroupGap':kk[1]['shortage_units'],'PaperFigureCount':len(figs)}
    (paper/'results_macros.tex').write_text('% 自动生成：不得反向修改宏来伪造实验结果。\n'+'\n'.join('\\newcommand{\\'+k+'}{'+str(v)+'}' for k,v in macros.items())+'\n',encoding='utf-8')
    save_json(paper/'results_for_writing.json',{'Q1':s1,'Q2':s2,'Q3':s3,'Q4':s4,'macros':macros})
    return [docs/n for n in texts]
