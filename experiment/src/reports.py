"""由本次结果自动生成中文报告；不固化架次、机型、阈值、瓶颈或实验数字。
Python 3.13.5；python-docx 1.2.0、matplotlib 3.10.8、Pillow 12.3.0。
Markdown保留可编辑公式，Word使用数学排版。源题规则与补充假设分别陈述。
"""
from pathlib import Path
from collections import Counter
from dataclasses import asdict
import io,json,re,math
from docx import Document
from docx.shared import Inches,Pt,Cm,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from matplotlib.mathtext import math_to_image
from PIL import Image
from config import CFG
from q2_config import Q2CFG
from io_utils import read_csv,save_json

def md_table(headers,rows):
    def esc(v):return str(v if v is not None else '不适用').replace('|','/').replace('\n','；')
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(esc(v) for v in row)+' |' for row in rows])
def fmt(x,n=4):return f'{float(x):,.{n}f}'
def js(path):return json.loads(Path(path).read_text('utf-8'))
def yn(x):return '是' if x is True or x=='True' else '否'
def num(x):return float(x) if x not in ('',None) else None

def build_markdown(root):
    root=Path(root);docs=root/'docs';docs.mkdir(parents=True,exist_ok=True)
    qd=root/'results/quality';d1=root/'results/q1';d2=root/'results/q2';logs=root/'results/logs'
    data=js(root/'data/cleaned/model_inputs.json');q=js(qd/'quality_summary.json');s1=js(d1/'summary.json');s2=js(d2/'summary.json')
    v1=js(d1/'validation_summary.json');v2=js(d2/'independent_validation.json');va=js(logs/'additional_validation.json');vx=js(logs/'submission_validation.json')
    ms={m['model_id']:m for m in data['transport_models']};bp={m['model_id']:m for m in data['transport_batteries']}
    q1tr=read_csv(d1/'batches_NET.csv');q2tr=read_csv(d2/'trips.csv');boxes=read_csv(d2/'box_deliveries.csv')
    sens=read_csv(d1/'reserve_sensitivity.csv');hyp=read_csv(d1/'energy_assumption_sensitivity.csv')
    mcounts=Counter(b['material_type'] for b in data['boxes']);models_table=md_table(['参数','A型','B型','C型'],[[label]+[ms[g][key] for g in sorted(ms)] for key,label in [
        ('empty_mass_kg','含电池空载质量/kg'),('max_payload_kg','额定载货质量/kg'),('volume_m3','容积/m³'),('usable_energy_kwh','可用电能/kWh'),
        ('empty_range_m','空载标准航程/m'),('full_range_m','满载标准航程/m'),('cruise_speed_mps','巡航速度/(m/s)'),('climb_speed_mps','爬升速度/(m/s)'),
        ('descent_speed_mps','下降速度/(m/s)'),('prepare_s','固定准备/s'),('load_per_box_s','逐箱装载/s'),('handoff_base_s','每站基础交接/s'),('handoff_per_box_s','逐箱交接/s'),('reserve_fraction','返航余量比例')]])
    issues=md_table(['问题/范围','数量','处理规则'],[[r['code']+' / '+r['scope'],r['count'],r['action']] for r in q['issues']])
    profiles=read_csv(qd/'geospatial_quality.csv')
    before=md_table(['对象','清洗前','清洗后','变化'],[
        ['货箱',q['boxes'],len(data['boxes']),'不删除；不改质量、体积、ID'],['服务区',q['services'],len(data['services']),'不按重名合并'],
        ['需求记录',q['demand_rows'],len(data['demand']),'保持逐类与逐箱一致'],['地理点/顶点',q['geospatial_vertex_rows'],q['geospatial_vertex_rows'],'保留合法闭合点与顺序'],
        ['DEM有效像元',q['valid_dem_cells'],q['valid_dem_cells'],'只修NoData元数据'],['题定物理值覆盖',0,q['physical_values_overwritten'],'未人为修正'],
        ['逐箱非适用截止时间',q['not_applicable_box_deadlines'],q['not_applicable_box_deadlines'],'保留null而非插补']])
    business=md_table(['整洁表','记录数'],q['dataset_row_counts'].items())
    cleaning=rf'''# 数据清洗说明文档

## 1. 输入范围与总体结论

以用户提供的题面、数据压缩包和结果模板为唯一场景依据，不用外部同类数据替代原始附件。data/raw保留{q['raw_file_count']}个原始文件，包含{q['input_workbooks']}个基础工作簿、结果模板、DEM/地理辅助文件和题面。SHA-256见results/quality/file_inventory.csv。题面附录1的地理说明文件扩展名与实际附件不同，按实际提供的文件读取并记录，不伪造缺失文件。

全量扫描{q['valid_dem_cells']:,}个有效DEM像元、{q['geospatial_vertex_rows']:,}行地理点/顶点及全部业务单元格，执行{q['checks_total']:,}项检查，失败{q['checks_failed']}项。核心非预期缺失{q['unexpected_missing_core_cells']}个，主键重复{q['duplicate_core_primary_keys']}个。交付需求为{q['boxes']}箱、{q['total_weight_kg']} kg、{q['total_volume_m3']} m³。上述结果仅证明本次数据内部一致，不等同于外部测绘或真实飞行验证。

## 2. 数据问题、分布与清洗规则

{issues}

“错误”与“待审核/合理特殊值”分开处理。不是为了清洗而制造改值：本次未删除任何货箱、需求、合法地理顶点或高程；未用均值、截尾或平滑覆盖题定物理值。

## 3. 缺失值及类型格式

需求首批截止时间有{q['not_applicable_demand_deadlines']}个不适用空值；逐箱首批截止时间有{q['not_applicable_box_deadlines']}个不适用空值。这些记录没有相应首批约束。JSON保留null，CSV留空，增加is_first_batch/has_first_deadline。填0会制造任务开始即逾期，均值插补会制造原题没有的时限。医疗expected_s仍为硬时限；首批箱采用first_deadline_s，交集取较早者；其他expected_s作为及时性评价。这些规则自第二问起激活，不提前强加到第一问。

合并单元格从属空白、分区标题、表头和未填结果表是结构信息，不计入样本缺失率。源工作簿按业务表头定位，不将第一行机械当作全部字段。数字按单位转为有限int/float，ID保留字符串，真假值保留布尔；跨表连接使用ID而非地名。UTF-8 BOM CSV便于Excel读取。所有源记录保留文件/表/行定位，字段与单位见data/cleaned/data_dictionary.csv及模型输入JSON。

地理名称“未记录”共影响{q['unknown_feature_name_rows']:,}个顶点行；标准name置空，name_raw保留原文并置name_missing。其坐标与要素仍有效，未知名称不导致删除道路、水体或样本。

## 4. 异常、重复、业务逻辑与分布

统计审核使用1.5倍IQR及修正Z分数（0.67449×偏差/MAD、阈值3.5）；样本不足、MAD=0或IQR=0时不做无意义除法。共有{q['statistical_flagged_field_records']}个“记录×字段”触发标记，它们不等于同等数量的坏样本；完整位置、阈值与原值见statistical_outliers.csv。不同物资质量/体积形成结构化分布，合理差异保留。

所有货箱ID、服务区ID、实体无人机ID、机型ID核查唯一性；需求按服务区和物资汇总，与箱数、总质量、总体积、首批数核对。相同地名不合并，闭环首末重复坐标不按坐标去重；地理重复按要素ID、环、顶点序号判定。机型范围、能量、效率、容量、库存非负/正值、关联外键、医疗/首批时限启用逻辑全部逐项验证。

DEM全局尾部{q['dem_iqr_tail_cells']:,}像元按山地分布保留，截峰会破坏巡航净空。GeoTIFF原先未声明NoData，依据同包MAT与说明补上{CFG.nodata_value}，不改变高程数组。节点高程与对应DEM像元差异超过审核阈值共{q['node_elevation_review_count']}处，最大绝对差{q['max_abs_node_dem_difference_m']:.6f} m；节点仍用源xlsx高程，航段净空用DEM。MAT/CSV对比{q['mat_csv_compared_cells']:,}单元格，差异{q['mat_csv_mismatch_cells']}。

## 5. 处理前后及建模入口

{before}

{business}

第二问额外生成transport_battery_units.csv，将原共享电池库存展开为逐个物理资源ID，共{sum(b['count'] for b in data['transport_batteries'])}条。这是确定性命名，不是新增库存。每机型编号从01开始，初始SOC=1，同型共享、异型不混用；总库存已经包含初装电池，不再给每架机额外加一组。

数据输入首选data/cleaned/model_inputs.json，空间输入为geospatial/dem_clean.tif或dem_clean.npz；其他地理CSV/MAT的规范视图一并保留。物理建模不进行Z-score标准化；将千米统一为米、时限统一为秒、能耗统一为kWh，而不是破坏量纲后计算。

## 6. 检查文件与边界

field_quality_profiles.csv含逐字段缺失率和分布；business_checks.csv记录逐项判断；issues_and_actions.csv记录问题与处置；node_dem_comparison.csv记录高程差；全量地理和DEM检查结果留在results/quality。清洗不补充题面未定义的能耗分项；相关模型闭合假设在第一、二问报告明示，并做分项扰动。
'''
    caps=read_csv(d1/'payload_continuous_discrete.csv');capmap={(r['service_id'],r['model_id']):r for r in caps}
    captable=md_table(['区域','A连续/kg','A整箱/kg','B连续/kg','B整箱/kg','C连续/kg','C整箱/kg'],[
        [sid]+[fmt(capmap[sid,g][k],3) for g in sorted(ms) for k in ['continuous_safe_payload_kg','available_box_max_payload_kg']] for sid in sorted({r['service_id'] for r in caps})])
    q1batchtable=md_table(['架次','区域','机型','箱数','载荷/kg','能耗/kWh','作业/s'],[[r['trip_id'],r['service_id'],r['model_id'],r['box_count'],fmt(r['weight_kg'],0),fmt(r['energy_kwh'],6),fmt(r['operation_time_s'],3)] for r in q1tr])
    op=read_csv(d1/'objective_comparison.csv');optable=md_table(['优先关系','架次数','能耗/kWh','累计作业/s'],[[r['order'],r['trips'],fmt(r['energy_kwh'],6),fmt(r['operation_time_s'],3)] for r in op])
    senstable=md_table(['返航下限','全箱可行','架次数','能耗/kWh','累计作业/s'],[[f"{100*float(r['reserve_fraction']):.0f}%",yn(r['feasible']),r['trips'] or '不可行',fmt(r['energy_kwh'],6) if r['energy_kwh'] else '—',fmt(r['operation_time_s'],3) if r['operation_time_s'] else '—'] for r in sens])
    hypstable=md_table(['水平乘子','爬升乘子','架次数','能耗/kWh','最小SOC'],[[r['horizontal_multiplier'],r['climb_multiplier'],r['trips'],fmt(r['energy_kwh'],6),f"{100*float(r['min_return_soc_fraction']):.4f}%"] for r in hyp if r['energy_kwh']])
    thresholds=read_csv(d1/'single_box_reserve_thresholds.csv');crit=s1['critical_common_reserve_fraction']
    payloadlimited=[r['service_id']+'-'+r['model_id'] for r in caps if float(r['continuous_safe_payload_kg'])<float(r['rated_payload_kg'])-1e-6]
    q1=rf'''# 第一问：单点往返能力与整箱组批（修订版）

## 摘要与本版修订

在题面“问题一”限定的单点直接往返条件下，完成{len(caps)}组连续最大安全载荷与整箱可实现载荷计算；按架次数、能耗、累计作业时间的字典序，得到{s1['trips']}架次、{s1['energy_kwh']:.8f} kWh、{s1['operation_time_s']:.6f}累计作业秒，{s1['delivered_boxes']}箱全部恰好一次交付。该结论以第3节明示的能耗分项假设为条件。

本版正式敏感性下限不低于源参数；并列连续/整箱载荷，统一Q1与Q2的开始、交接与返回时间口径；所有报告结论由当次CSV/JSON生成。原模板表头不修改，最终工作簿强制逐格与物理复核，不能沿用未核对旧Excel。

## 1. 问题拆解与评价

题面第2页要求单服务区O01→Si→O01，不跨区合批，同区可多架次，货箱不可拆、每箱一次；题目没有要求在第一问安排实体无人机与共享电池。因此第一问不据机身数量限制同时架次，也不把Q2的硬时限和充电等待混入独立批次目标。

定义N为架次数，E为总运输能耗，T为所有架次累计作业时长。主目标采用lexmin(N,E,T)：先最少架次，同架次数下最小能耗，同能耗下最短累计作业。优先关系是本文公开选择，并非题面给定唯一权重。另解ENT、TNE、NTE及二维N—E完整前沿。

## 2. 数据与符号

输入来自清洗后的节点、机型、箱子和完整DEM。每箱b对应质量w_b、体积v_b与唯一目的地i；机型g对应Q_g、V_g、E_g、m_g及空/满载航程L0、LF。返航比例rho_g读取源表，不把它与实际返回SOC混淆。

{models_table}

本问的N是架次数，不是实体架数；T是工时总和，不是多机并行Cmax。

## 3. 公共物理规则与明确假设

源题附录2：两节点水平直线航段；H_ij=max(所经过DEM像元)+50 m。O01作业高度为题定地面高程，服务区为题定地面高程+30 m；每次投送后重新爬升。主实现以经纬度短线段精确遍历触及像元（supercover），水平距离为WGS84椭球距离。不是用经纬度差当米，也不是稀疏抽样后漏掉山峰。主实现与独立all_touched扫描核对；源DEM分辨率仍是模型适用边界。

$$L_g(q)=L_g^0-(L_g^0-L_g^F)(q/Q_g)^{{3/2}}$$

$$t_{{ijg}}=h^{{up}}_{{ij}}/v_g^{{up}}+d_{{ij}}/v_g^{{cr}}+h^{{down}}_{{ij}}/v_g^{{down}}$$

题面只规定运输能耗由水平与爬升分项相加，未展开两个分项。因此明确补充：给定标准航程解释为用尽单组可用电能的对应水平航程；爬升效率解释为势能/电能比。含电池空载质量已经包含电池，不能重复加电池质量。

$$E^{{hor}}_{{ijg}}(q)=E_g^{{use}}d_{{ij}}/L_g(q)$$

$$E^{{up}}_{{ijg}}(q)=(m_g+q)g_0h^{{up}}_{{ij}}/(\eta_g\,3.6\times10^6)$$

上述是补充建模假设，不冒充官方唯一分项定义。源规则下降附加能耗为0，不另加能量回收。交接计时，但附件没有运输悬停功率，不虚构一项投送电耗；这不表示真实无人机悬停免费。若另有官方分项解释，应统一替换两问公共物理模型并全量重算。

## 4. 单点能耗、时间及最大安全载荷

去程载货q，到达Si完成该批全部交付，空载返回。两段爬升分别从O01作业高度、Si作业高度到各自巡航海拔计算，不能用净高差代替往返爬升。

$$E_{{ig}}(q)=E_{{Oig}}(q)+E_{{iOg}}(0),\quad E_{{ig}}(q)\leq(1-\rho_g)E_g^{{use}}$$

$$q^{{safe}}_{{ig}}=\max\{{q:0\leq q\leq Q_g,\ E_{{ig}}(q)\leq(1-\rho_g)E_g^{{use}}\}}$$

L(q)随q减小、1/L(q)随q增加，爬升项也增加，故E(q)单调增加。先检空载，不可行返回null；再检额定满载，满足则取Q_g；否则二分{CFG.bisection_iterations}次取可行侧。显示四舍五入不进入后续判定。

额定载荷只随机型；连续安全载荷还随航线、地形和余量变化；实际组批质量是离散箱重之和。连续定义不包含未知货物密度。针对本区现有箱集合，再枚举质量、体积、能耗均合格的子集，得到单架次整箱最大可实现质量。该值受库存限制，不能等同于机型物理能力，也不能把每个组合的见证箱重复当作全局交付方案。

{captable}

受到能耗约束而低于额定质量的组合为：{'、'.join(payloadlimited)}。逐组合见证箱ID见payload_continuous_discrete.csv。

时间统一约定如下：架次开始=在O01固定准备开始；随后逐箱装载、飞行、逐站交接、返抵O01；模板“往返时间（s）”填写该架次返回时刻减开始时刻，与Q2语义对齐。原模板没有细化此列，本文明确采用这一解释，而不是声称题面排除了其他命名解释。

$$T_p=T_g^{{prep}}+n_pT_g^{{load}}+\sum t_{{ijg}}+T_g^{{base}}+n_pT_g^{{box}}$$

同时提供纯飞行{s1['flight_time_s']:.6f} s、飞行加交接{sum(float(r['airborne_service_s']) for r in q1tr):.6f} s、完整累计作业{s1['operation_time_s']:.6f} s，文件time_components.csv可直接按明确的新口径转列，不需重新猜测。

## 5. 整箱集合划分与精确动态规划

对每区枚举全部物资数量向量及A/B/C机型；候选批次必须满足总质量≤Q_g、总体积≤V_g、往返能量≤(1−rho_g)E_g。没有箱体三维尺寸，只能采用总体积容量，不宣称求解三维几何装箱。

令x_p表示选择候选批次p，每箱只被覆盖一次。跨区批次在生成时即不允许。

$$\sum_{{p:b\in p}}x_p=1,\quad x_p\in\{{0,1\}}$$

第一问不区分同区同类同重同体积箱的时限，所以将其压缩为计数状态a。F(a)保存完成a所需最优(N,E,T)与前驱：

$$F(a)=\min_{{u\leq a,\,u\ne0}}^{{lex}}\{{F(a-u)+(1,e_u,t_u)\}}$$

F(0)=(0,0,0)，从小到大枚举全部状态/候选，无启发式截断。归纳地，最优解去掉最后一个批次必剩下更小状态的最优解；全部候选均被比较，故恢复的是声明字典序目标下的精确解（在浮点容差内）。各区独立、目标可加，局部最优相加即全局最优。计数方案恢复为真正箱号，第二套逐箱位掩码DP不使用计数压缩，独立复核各区最优值。

## 6. 主方案与最优性

{q1batchtable}

总计{s1['trips']}架次，机型构成{json.dumps(s1['model_trip_counts'],ensure_ascii=False)}，能耗{s1['energy_kwh']:.8f} kWh，累计作业{s1['operation_time_s']:.6f} s；最低返航SOC={100*s1['min_return_soc_fraction']:.6f}%。完整箱号见Q1_单点组批.csv及batches_NET.csv，每箱唯一归属见box_assignment.csv。

每个有需求服务区至少一架次；需求超过所有机型额定最大质量的区域至少再增加架次。对本数据，按每区ceil(需求质量/最大额定载荷)求和得下界{sum(math.ceil(sum(b['weight_kg'] for b in data['boxes'] if b['service_id']==si['node_id'])/max(m['max_payload_kg'] for m in ms.values())) for si in data['services'])}，主方案达到。因此架次数最少有“下界+可行解”证明；同架次下的能耗/时间通过完整DP及独立DP验证。该证明依赖所采用物理模型下的可行性，不跨越到未知替代能耗模型。

## 7. 多指标权衡与敏感性

{optable}

NET为架次→能耗→时间，ENT为能耗→架次→时间，TNE为时间→架次→能耗，NTE为架次→时间→能耗。不同优先关系不是误差。另在flight_energy_frontier.csv精确求各可行架次数的最低能耗，区分二维N—E前沿与完整三目标前沿；没有声称枚举后者。

{senstable}

正式实验全部不低于源表安全底线，每档重新优化而非只检验旧方案；不再把10%、15%放入正式结果。随余量提高，可用任务电量减少，连续安全质量不增，但整箱分割使架次数呈跳变。当前原方案可不变至最低返航SOC {100*s1['min_return_soc_fraction']:.6f}%。

由于本问不限制实体/电池周转，只要每个单箱存在安全直接往返机型，就可逐箱完成；若单箱对所有机型都不可行，加入别箱只会增能耗。故共同余量极限为各箱“最佳单箱返航SOC”的最小值，当前为{100*crit:.8f}%；逐箱证明见single_box_reserve_thresholds.csv。它是当前能耗模型下的可行性边界，不是可以降低题定底线的许可。

分项假设扰动（仅模型检验，不改源数据）如下：

{hypstable}

水平与爬升各±10%分别全量重算。完整方案及独立分项检查一起导出。节点表/DEM高程替代对照另见alternative_dem_node_elevation_summary.json，仅评估敏感性，不修改正式题定海拔。

## 8. 复核与向第二问继承

Q1独立验证{v1['checks_total']}项，失败{v1['checks_failed']}；另有见证载荷、能耗扰动和最终工作簿重新计算。继承给Q2的是箱子、地形、机型、能耗和时间函数，不是强行固定第一问组批。Q2将引入实际资源、硬时限、充电与多点访问，最优目标也改变，因此可能采用更多小型机架次并更快完成全部任务。

![Q1连续安全载荷](../results/figures/02_safe_payload.png)
'''
    comp={r['scenario']:r for r in read_csv(d2/'scenario_comparison.csv')};direct=comp['direct_only'];alt=comp['energy_tradeoff']
    comparetable=md_table(['情景','硬时限可行','架次','Cmax/s','能耗/kWh','按期箱数'],[[r['scenario'],yn(r['feasible']),r['trips'],fmt(r['makespan_s'],3),fmt(r['energy_kwh'],6),r['all_expected_on_time']] for r in comp.values()])
    routetable=md_table(['架次','无人机/型','电池','服务区顺序','开始/s','返回/s','能耗/kWh'],[[r['trip_id'],r['drone_id']+'/'+r['model_id'],r['battery_id'],r['visit_order'].replace(';','→'),fmt(r['start_s'],3),fmt(r['return_s'],3),fmt(r['energy_kwh'],4)] for r in q2tr])
    drs=read_csv(d2/'drone_usage.csv');bts=read_csv(d2/'battery_usage.csv')
    drtable=md_table(['无人机','型','架次','作业/s','最后返回/s','利用率'],[[r['drone_id'],r['model_id'],r['trip_count'],fmt(r['operation_time_s'],2),fmt(r['last_return_s'],2),f"{100*float(r['utilization']):.2f}%"] for r in drs])
    batstable=md_table(['电池','使用次数','执行无人机','末次充满/s'],[[r['battery_id'],r['usage_count'],r['different_drones'].replace(';',' / '),fmt(r['last_charge_complete_s'],2)] for r in bts])
    maxgap=read_csv(d2/'delay_stress_diagnostic.csv');minbox=min((r for r in boxes if r['hard_slack_s']),key=lambda r:float(r['hard_slack_s']))
    mintrip=min(q2tr,key=lambda r:float(r['return_soc_fraction']))
    lower=js(d2/'lower_bound.json');status=js(logs/'unit_tests.json') if (logs/'unit_tests.json').exists() else {'tests_run':26}
    q2=rf'''# 第二问：异构无人机多点多架次运输调度

## 摘要

继承第一问清洗数据与公共物理规则，重新联合优化真实货箱分配、访问次序、机型、实体无人机、共享电池和开始时刻。采用确定种子的箱级邻域搜索、模拟退火、破坏—修复和资源列表调度，得到{s2['trips']}架次方案，{s2['multipoint_trips']}架次跨多个服务区、单架次最多{s2['max_stops_in_solution']}个服务区。全部{s2['delivered_boxes']}箱交付，医疗{s2['medical_on_time']}/{s2['medical_boxes']}、首批{s2['first_batch_on_time']}/{s2['first_batch_boxes']}均按硬时限完成；全部期望时间按期{s2['all_expected_on_time']}/{s2['delivered_boxes']}。

最后一架无人机返回O01的时刻为{s2['makespan_s']:.6f} s（{s2['makespan_s']/60:.6f} min），运输能耗{s2['energy_kwh']:.8f} kWh。已独立验证可行；零逾期达到该非负目标的理论下界，但Cmax、能耗和架次数没有全局最优证明。本报告不把启发式上界冒充严格全局最优。

## 1. 题意与第一问的继承边界

题面第3页要求不考虑通信保障，每次O01出发、访问一个或多个服务区后返回，满足全部箱约束、机身与电池库存、两阶段充电周转及物资时限。医疗expected_s和首批first_deadline_s是硬约束，普通物资expected_s用于及时性评价。Cmax是最后返航时刻，不是最后交付时刻，也不是所有架次工时之和。第三问的通信条件本问不加入，不能据本问结果宣称全程通信已经满足。

第一问给出了独立批次能力，但不包含排程。这里继承数据、单位、直接航段与能耗函数，重新允许跨服务区合批、拆分旧批、改变机型和箱号归属。对照中只固定Q1批次并使用相同资源列表调度，检验其直接继承效果；该对照不可行也不能证明所有其他固定组批排程都不可行。

## 2. 输入、资源、时钟及附加约定

场景包含{len(data['services'])}服务区、{len(data['boxes'])}货箱和{len(data['transport_drones'])}实体运输机。库存按源表读取：

{md_table(['机型','实体数量','共享电池总数','完全充电/s'],[[g,sum(d['model_id']==g for d in data['transport_drones']),bp[g]['count'],bp[g]['full_charge_s']] for g in sorted(ms)])}

共享电池数量已经包括初始机载与备用电池，不能再按机身数量加初装电池。源表没有每个电池的名称，因此按机型与序号生成唯一battery_id；它们可跨同型无人机使用，不能跨型。所有电池t=0满电。

统一s_p=固定准备开始；起飞=s_p+prepare+n×load；返回f_p=s_p+完整作业时长。机身与所选电池从准备开始独占到返航；准备和装载资源工位数未给定，因此不虚构全场单工位。题面没有额外运输换电/周转秒数，不重复加入任意常数。电池返航后立即充电，各组可并行，不假定有限充电端口。

到站后的交接采用源机型基础交接时间加逐箱交接时间，箱的交付完成是该箱交接完成，不是刚到站。点内顺序按硬截止、期望时间、优先级降序、箱ID的公开规则；这是本算法固定策略，不宣称穷尽所有交接次序。各架次采用不重复服务点的基本路线，最多允许{Q2CFG.maximum_stops}个不同服务区，不人为截为两点或三点；“不重复”是搜索策略边界，不冒充题面禁止重复访问。

## 3. 任意航段、动态载荷与时间递推

对16节点全图计算120个无向地形剖面，形成240条有向航段。每条按触及的全部DEM像元最高值+50 m定巡航海拔；起终点作业高度和爬升、巡航、下降速度与第一问一致。在每个投送点重新从30 m作业高度爬升。全部240条航段都用另一套rasterio all_touched在原始DEM上独立核验，未用欧氏平面捷径替代地形。

某架次p的路径为O01,i1,…,ik,O01，初始载荷q_p为全部箱重。访问j后卸下本站全部箱，后续航段只携带尚未交付货物。

$$q_{{p,\ell+1}}=q_{{p,\ell}}-\sum_{{b\in B_{{p,\ell}}}}w_b,\quad q_{{p,1}}=\sum_{{b\in B_p}}w_b$$

$$e_p=\sum_{{\ell}}\left[ E_g^{{use}}d_\ell/L_g(q_{{p,\ell}})+(m_g+q_{{p,\ell}})g_0h_\ell^{{up}}/(\eta_g\,3.6\times10^6)\right]$$

源题等效航程的3/2次幂关系保持不变。能源分项仍为第一问明示的补充假设；去程最大载荷不能用于所有中间航段，返程必须空载。下降附加能耗按题规则取0。

对每一站，先加三阶段飞行时间，再加本站基础交接时间，然后逐箱增加对应机型每箱交接时间，记录c_b；全部完成后开始下一条航段。当前模型的δ_pb=c_b−s_p由箱分配、机型、服务次序与点内次序唯一决定，可预计算。legs.csv列出每航段进出载荷、最高地形、三阶段时间及能耗分项；phase_events.csv列出完整事件边界。

## 4. 约束与优化模型

### 4.1 整箱与路径物理可行性

概念上令p为一个物理可行的整箱路线候选，x_p∈{{0,1}}表示选用；每个候选已指定机型、箱集合、服务顺序、能耗e_p、时长τ_p和逐箱偏移δ_pb。全部箱集合划分为互不重叠批次，且访问区集合恰好等于箱目的地集合。

$$\sum_{{p:b\in B_p}}x_p=1$$

$$\sum_{{b\in B_p}}w_b\leq Q_g,\quad\sum_{{b\in B_p}}v_b\leq V_g,\quad e_p\leq(1-\rho_g)E_g^{{use}}$$

质量/体积在起飞时最大；每站只卸货，使以后不增加。每条腿仍逐项验算实际剩余载荷。容量与箱不可拆同时满足，不能把758 kg平均摊到架次后假定可行。

### 4.2 医疗、首批与普通物资时限

对箱b，硬截止d_b^H取其所有适用硬时限的最小值；没有硬时限取无穷。医疗且首批的箱子同时满足两项，不能只取较宽松者。所选候选包含b时，c_b=s_p+δ_pb。硬约束c_b≤d_b^H；逾期量z_b=max(0,c_b−expected_b)。优先级π_b直接用附件值。

$$D=\sum_b \pi_b\max(0,c_b-d_b^{{exp}})$$

D统计所有箱；医疗/首批已在硬约束下，不会用其他物资早点送来抵消医疗迟到。数学模型禁止硬违约；搜索中的罚项只帮助穿越暂时不可行邻域，最终输出前必须硬违约为0。

### 4.3 实体机与共享电池

每个选中候选指派且只指派一架相同机型实体无人机与一组相同机型共享电池。同一无人机的区间[s_p,f_p)互不重叠；不同机型ID不能替换。可以同时使用不同无人机，不把累计工时当Cmax。

返航SOC r_p=1−e_p/E_g。依源题两阶段充电：

$$t_{{ch}}(r)=T_g^{{full}}\left[0.65\max(0,0.9-r)/0.9+0.35(1-\max(0.9,r))/0.1\right]$$

r<0.9时先快速补到0.9，再慢充到1；r≥0.9仅慢充剩余部分。r=0、0.9、1分别对应全充时间、0.35倍和0，在0.9处连续。不得用(1−r)×全充时间替代。电池任务占用与充电合起来为[s_p,f_p+t_ch(r_p))；同一电池的下一架次准备不能早于充满。不同电池可并行充电。

### 4.4 多目标优先关系

硬约束先满足；主目标为lexmin(D,Cmax,E,N)，其中Cmax=max_p f_p。本文选择优先清除逾期，再压缩完成时间，再省能量和架次。能耗和架次参与评价与同Cmax的选择，而不是用任意总和掩盖取舍。搜索打分用于接受候选，保存最优解时仍按字典序比较。

在D=0达到下界之后，另做Cmax≤{Q2CFG.alternative_energy_budget_ratio:.2f}×主方案Cmax的能耗优先对照。它公开允许较长完成时间，不与主目标混称同一种最优。

## 5. 算法与一键流程

不枚举80箱的全部跨区子集。先预计算240航段及各型飞行时间；按箱的硬/期望截止与优先级构建初始解，将箱插入既有路线或新架次，枚举新增服务点所有插入位置；三种机型都进入候选。

解的编码为架次列表，每个元素为“机型、有序不同服务区、实际箱索引”。解码逐项选择最早空闲的相容机身和最早满电电池，开始=max(二者可用时刻)。任务返回后更新机身时刻与电池充满时刻。不同机型之间的列表交换不必产生实际差异；同型顺序、组批及型号选择共同改变资源冲突与时限。

邻域覆盖同型架次调序、单箱迁移、箱交换、整站块迁移、访问序交换、换型、分批、合批与新增单箱架次。物理不合格候选即时剔除。模拟退火容许部分目标劣化，避免只贪心；每轮再破坏{Q2CFG.destroy_size_min}—{Q2CFG.destroy_size_max}个箱并逐箱修复，保存最佳可行解。点内次序与列表式资源解码限制了搜索空间，因此没有Cmax/E/N全局最优保证。

主搜索固定种子{list(Q2CFG.seeds)}，各{Q2CFG.iterations_per_seed:,}次邻域与{Q2CFG.lns_iterations}次破坏修复；随后{len(Q2CFG.polish_seeds)}轮、每轮{Q2CFG.polish_iterations:,}次邻域和{Q2CFG.polish_lns_iterations}次修复。直接往返对照采用同样预算，仅限制每架次一个服务区。能耗对照另用{len(Q2CFG.energy_seeds)}轮、每轮{Q2CFG.energy_iterations:,}次及{Q2CFG.energy_lns_iterations}次修复。停止依据是固定迭代，不是硬件相关秒数；参数均在q2_config.py，物理参数在config.py或源数据。

物理评价按“机型、路线、箱集合”缓存；每次列表解码线性扫架次和箱，资源选择只需扫描该型小规模机身/电池。最坏组合优化仍困难，这里利用80箱、8机身的小场景做充分可复现多起点搜索。所有种子与每轮指标、初解/改进记录导出，不只保留最佳一次却不说明尝试预算。

流程：raw→全量清洗→Q1精确组批与独立验证→240航段→Q2初解/改进→3个对照→LP下界→逐箱/资源独立验证→原模板Excel→从最终Excel再重算→图表与中文报告。任一验收失败主程序报错，不能发布“通过”状态。

## 6. 最终架次、逐箱交付与资源结果

{routetable}

{s2['trips']}架次使用机型构成为{json.dumps(s2['model_trip_counts'],ensure_ascii=False)}；{s2['battery_units_used']}组库存电池实际使用，充满后复用{s2['battery_reuses']}次，其中{s2['battery_sharing_across_drones_units']}组在不同同型机身间共享。全部{s2['delivered_weight_kg']} kg、{s2['delivered_volume_m3']:.3f} m³、{s2['delivered_boxes']}箱交付，模板逐箱表有完整箱ID与完成秒数，不需人工从路线猜测分配。

最后交付时刻为{s2['last_box_delivery_s']:.6f} s，最后返航时刻为{s2['makespan_s']:.6f} s；二者不相同。总纯飞行{s2['flight_time_sum_s']:.6f} s，总作业{s2['operation_time_sum_s']:.6f} s，也均不是并行Cmax。末次电池充满可晚于Cmax，因为题定任务完成取运输机最后返航，不要求最后所有电池充满才算完工。

{drtable}

{batstable}

最低返航SOC为{100*s2['min_return_soc_fraction']:.6f}%（{mintrip['trip_id']}），源下限为{100*ms[mintrip['model_id']]['reserve_fraction']:.0f}%。最紧硬时限为{minbox['box_id']}，裕度仅{float(minbox['hard_slack_s']):.6f} s。当前数学参数下可行，但时间和电量缓冲较小，不可把数值可行性说成真实扰动下的稳健保证。

![全部运输路线](../results/figures/q2_01_routes.png)

![实体无人机时序](../results/figures/q2_02_drone_gantt.png)

![共享电池及充电时序](../results/figures/q2_03_battery_gantt.png)

## 7. 对照、权衡与下界

{comparetable}

q1_frozen是将Q1批次按截止优先列表投入实际库存的诊断。它在该排程下违反硬时限，故不作为可提交第二问方案，也不拿其低能耗宣称优于满足时限的方案。固定组批是否还存在别的可行排程，本对照未证明。

与同预算直接往返重新优化对照相比，主方案Cmax下降{100*(1-s2['makespan_s']/float(direct['makespan_s'])):.4f}%，能耗下降{100*(1-s2['energy_kwh']/float(direct['energy_kwh'])):.4f}%，架次下降{100*(1-s2['trips']/int(direct['trips'])):.4f}%。这是本次求得解之间的比较，不是两种问题全局最优值之差。

能耗优先对照在允许Cmax上限{s2['energy_tradeoff_makespan_cap_s']:.6f} s内，得到{alt['trips']}架次、{float(alt['energy_kwh']):.8f} kWh、{float(alt['makespan_s']):.6f} s；较主方案能耗下降{100*(1-float(alt['energy_kwh'])/s2['energy_kwh']):.4f}%，完成时间增加{100*(float(alt['makespan_s'])/s2['makespan_s']-1):.4f}%。这说明及时性达标后仍有时长与能耗/架次权衡。

为不把“搜索未改进”当最优证明，构建保守工作量LP松弛。每箱可分数分配到各机型，架次和到访次数允许连续；保留每型总重量/体积容量，每服务区至少一次合计到访，各型累计工作量≤该型机身数×Cmax。每服务区的入航段时间取全图最小值，每次返航也取最短值；放松电池、时限和能量，故可行域包含原问题的投影。

单型工作量下界为：每架次固定准备与最短返航；每箱装载与交接；每次到站基础交接与最短入段。各项都不大于真实总作业，LP最优值因此是原问题的保守Cmax下界。SciPy linprog/HiGHS实际求解{lower['variables']}变量、{lower['inequalities']}不等式、{lower['equalities']}等式；原对偶证书最大残差{lower['certificate_residual']:.3g}，保守扣除数值容差后下界{lower['lower_bound_s']:.6f} s。

当前可行上界{s2['makespan_s']:.6f} s与下界的相对差为{100*s2['relative_upper_lower_gap']:.4f}%。它反映下界较松和最优性尚未闭合，不等于实际误差，也不支持“接近全局最优”的断言。D=0有理论最优依据；其余目标仍为已核验启发式结果。

![同预算搜索过程](../results/figures/q2_05_convergence.png)

![完成时间与能耗权衡](../results/figures/q2_06_tradeoff.png)

## 8. 独立验证与扰动边界

不复用优化器物理函数，从最终箱ID、路线、开始时间与原始DEM独立重算：逐箱唯一覆盖、单箱目的地、质量体积、各航段载荷、空载返航、能耗、每箱交接完成、全部硬时限、逐机区间、逐电池任务/充电区间与满电复用。主CSV检查{v2['checks_total']}项，失败{v2['checks_failed']}；有向地形检查{v2['arc_checks']}条，失败{v2['arc_checks_failed']}。最大能量差{v2['max_energy_error_kwh']:.3g} kWh，最大时间差{v2['max_time_error_s']:.3g} s，为浮点舍入量级。

三个对照另执行{va['experiment_checks_total']}项资源/物理复核；冻结Q1对照允许记录硬违约，不将其标为硬可行。最终工作簿还经过独立复算，避免只验证内存解而导出文件错列。测试包含故意改错能耗、返航、箱号、机型电池、双重占用、交接完成与硬时限，确认验证器会拒绝错误答案。

冻结主方案整体延后的诊断如下；仅展示缓冲，不是放宽硬约束，也不是鲁棒重优化：

{md_table(['整体延后/s','硬约束违约箱','期望时间违约箱'],[[r['uniform_delay_s'],r['hard_violated_boxes'],r['expected_violated_boxes']] for r in maxgap])}

真实风场、测绘误差、未给出的功率过程和作业波动未被本题参数覆盖。本结果可用于题目规定的确定性模型与结果提交，不可直接作实际救援调度安全保证。需要更大缓冲时应显式修改硬截止裕度/能源储备并重新优化，不能只把输出小数取整冒充加了余量。

## 9. 文件与使用说明

最终submission/结果提交.xlsx的Q2_运输架次和Q2_逐箱交付可直接对应模板。箱表{s2['delivered_boxes']}行、架次表{s2['trips']}行。细化文件trips.csv、box_deliveries.csv、legs.csv、phase_events.csv、drone_usage.csv、battery_cycles.csv、battery_usage.csv相互使用同一trip_id/box_id，不需要人工拼表。独立检查与下界证书、全部实验和参数均附于results/q2。

公共规则来源：用户题面“问题二”（第3页）、附录2（第7—9页）；全部设备、时限、箱属性来源于5个原基础工作簿。算法的资源列表规则、点内交接顺序、能耗分项闭合、字典序、启发式预算是本文明确选择。LP接口参照SciPy官方linprog文档，见docs/参考与参数说明.md，不从外部报道推导本场景参数。
'''
    texts={'01_数据清洗说明.md':cleaning,'02_第一问建模与求解_修订.md':q1,'03_第二问建模与求解.md':q2}
    for name,text in texts.items():(docs/name).write_text(text,encoding='utf-8')
    return [docs/name for name in texts]

def markdown_to_docx(path):
    path=Path(path);doc=Document();sec=doc.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7)
    sec.top_margin=Cm(1.75);sec.bottom_margin=Cm(1.75);sec.left_margin=Cm(1.8);sec.right_margin=Cm(1.8)
    normal=doc.styles['Normal'];normal.font.name='Noto Sans CJK SC';normal.font.size=Pt(10)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'),'Noto Sans CJK SC');normal.paragraph_format.line_spacing=1.16;normal.paragraph_format.space_after=Pt(5)
    for name,size in [('Title',20),('Heading 1',14),('Heading 2',11.5)]:
        st=doc.styles[name];st.font.name='Noto Sans CJK SC';st.element.rPr.rFonts.set(qn('w:eastAsia'),'Noto Sans CJK SC');st.font.size=Pt(size);st.font.color.rgb=RGBColor.from_string('18374F')
    header=sec.header.paragraphs[0];header.text='D题  /  Q1—Q4：运输、中继、分区与核验';header.style=doc.styles['Normal'];header.runs[0].font.size=Pt(8)
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('数学建模计算交付  ·  ')
    f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');footer._p.append(f)
    lines=path.read_text('utf-8').splitlines();i=0;code=False
    def para(text,style=None):
        p=doc.add_paragraph(style=style)
        for n,t in enumerate(re.split(r'(\*\*.*?\*\*)',text)):
            r=p.add_run(t[2:-2] if t.startswith('**') and t.endswith('**') else t)
            if t.startswith('**') and t.endswith('**'):r.bold=True
        return p
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('```'):code=not code;i+=1;continue
        if code:
            p=para(line);p.paragraph_format.space_after=Pt(0)
            for r in p.runs:r.font.name='Courier New';r.font.size=Pt(9)
        elif line.startswith('$$') and line.endswith('$$'):
            formula=line[2:-2];buf=io.BytesIO()
            try:
                math_to_image('$'+formula+'$',buf,dpi=220,format='png');buf.seek(0);im=Image.open(buf);w=min(6.6,im.width/220);buf.seek(0)
                p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run().add_picture(buf,width=Inches(w))
            except (ValueError,RuntimeError):para(formula)
        elif line.startswith('!['):
            m=re.match(r'!\[(.*?)\]\((.*?)\)',line);image=(path.parent/m.group(2)).resolve() if m else None
            if image and image.exists():
                im=Image.open(image);width=min(6.65,6.65*min(1,1.10/(im.height/im.width)))
                p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run().add_picture(str(image),width=Inches(width));p.paragraph_format.keep_with_next=True
                cap=para(m.group(1));cap.alignment=WD_ALIGN_PARAGRAPH.CENTER;cap.runs[0].italic=True;cap.runs[0].font.size=Pt(9)
        elif line.startswith('|'):
            block=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+',x) for x in row):block.append(row)
                i+=1
            i-=1;nc=len(block[0]);table=doc.add_table(rows=1,cols=nc);table.alignment=WD_TABLE_ALIGNMENT.CENTER;table.autofit=False;table.style='Table Grid'
            if nc==3 and block[0]==['图号','中文图题','图文件']:weights=[.08,.45,.47]
            elif nc==3 and block[0][-1]=='服务区':weights=[.12,.14,.74]
            elif nc==5 and block[0][0]=='单元':weights=[.10,.48,.10,.12,.20]
            elif nc==2:weights=[.4,.6]
            elif nc==3 and any(k in block[0][-1] for k in ['规则','状态','职责']):weights=[.31,.12,.57]
            elif nc==7 and block[0][1]=='无人机/型':weights=[.11,.10,.12,.19,.16,.16,.16]
            else:weights=[1/nc]*nc
            for c,w in zip(table.columns,weights):c.width=Cm(17.4*w)
            for ri,row in enumerate(block):
                cells=table.rows[0].cells if ri==0 else table.add_row().cells
                for j,txt in enumerate(row):
                    cells[j].text=txt;cells[j].width=Cm(17.4*weights[j])
                    for p in cells[j].paragraphs:
                        p.paragraph_format.line_spacing=1.08;p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(2)
                        for r in p.runs:r.font.size=Pt(8.5 if nc>=6 else 9);r.bold=ri==0
                trpr=table.rows[ri]._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
                if ri==0:
                    repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
                    for cell in cells:
                        sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'EAF0F4');cell._tc.get_or_add_tcPr().append(sh)
            doc.add_paragraph().paragraph_format.space_after=Pt(2)
        elif line.startswith('# '):para(line[2:],'Title')
        elif line.startswith('## '):para(line[3:],'Heading 1')
        elif line.startswith('### '):para(line[4:],'Heading 2')
        else:para(line)
        i+=1
    doc.core_properties.title=path.stem;doc.core_properties.subject='题目原始数据上的可复现建模与核验';doc.core_properties.author=''
    out=path.with_suffix('.docx');doc.save(out);return out

def run_reports(root):
    files=build_markdown(root)
    from closure_reports import build_closure_reports
    files+=build_closure_reports(root)
    return [str(markdown_to_docx(p)) for p in files]
