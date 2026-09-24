"""严格Q4提交说明：运行前源Q3已完成闭环修复，不再采用任务副本。"""
from pathlib import Path
import json
from io_utils import read_csv,write_csv,save_json,sha256
from q4_config import RESOURCE_KEYS,RESOURCE_NAMES

def write_submission_readme(root):
    root=Path(root);q3=json.loads((root/'results/q3/summary.json').read_text());q4=json.loads((root/'results/q4/summary.json').read_text())
    text=['D题四问闭环验证版：提交必读','',
    '1. 主工作簿结果提交.xlsx与Q3运输与逐箱补充.xlsx必须配套使用；Q3运输表不得与Q2通信外场景混合。',
    '2. 当前主版本已在Q3定稿阶段完成严格三组可分区修复。旧的较快Q3保留为独立优化对照，不属于正式Q4的输入。',
    '3. Q4严格保持最终Q3每个运输/中继任务、位置、海拔、时刻与通信源关系；任务恰好一次，不复制、不拆分、不缩短。',
    '4. Q4只在执行开始前按组重新配置同型实体/电池。@组号只是源任务归属标识，不表示第二次执行。各组物理资源不得交叉借用。',
    '5. 源库存不修改。表中资源数量为独立执行需求，超过库存的型号必须增补；不同类型不能互相抵扣。']
    for k in ('2','3'):
        s=q4['selected'][k];gap='、'.join(f'{n}{s["gap_"+key]}件' for key,n in zip(RESOURCE_KEYS,RESOURCE_NAMES) if s['gap_'+key]) or '无'
        text.append(f'   {k}组：总配置{s["resource_units"]}件，缺口{s["shortage_units"]}件；逐类为{gap}。')
    text.extend(['6. 物理检查通过是声明模型及相应库存条件下可行，不是现实飞行安全认证。Q2/Q3未证明全局最优；Q1及固定Q3后的Q4有条件精确最优。',
    f'7. 当前Q3为{q3["trips"]}运输架次、{q3["relay_trips"]}中继架次，联合最后返回{q3["joint_makespan_s"]:.6f}秒，总能耗{q3["total_energy_kwh"]:.6f}kWh。两种Q4分区均完全继承该时间和能量。',
    '8. Q1往返时间采用准备至返回的完整作业时间；Q2/Q3开始时刻为准备开始，纯飞行分项另存。Excel显示小数不会改变存储精度。',
    '9. python run_all.py --check-reference 完整复现；python validate_submission.py 从实际工作簿单元格独立复核。所有中文图仅引用同目录当次数值。'])
    (root/'submission/提交必读.txt').write_text('\n'.join(text)+'\n',encoding='utf-8')
