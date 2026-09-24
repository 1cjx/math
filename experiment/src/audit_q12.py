"""Q1/Q2逐条题意审查与输入回溯：原XLSX逐单元格对照，不使用清洗器转换函数。
Python3.13.5；源题数学公式已人工核对OMML，自动核对其关键指数和不等式常数。
"""
from pathlib import Path
from collections import defaultdict
import math,json,zipfile
import xml.etree.ElementTree as etree
from io_utils import xlsx_read,write_csv,save_json,sha256
from data_quality import SCHEMAS,TABLE_SOURCES
from config import CFG
from q2_config import Q2CFG


def run_audit_q12(root):
    root=Path(root);out=root/'results/audit';out.mkdir(parents=True,exist_ok=True);data=json.loads((root/'data/cleaned/model_inputs.json').read_text());books={};checks=[]
    for f in (root/'data/raw').rglob('*.xlsx'):books[f.name]=xlsx_read(f)[0]
    for tab,(book,sheet) in TABLE_SOURCES.items():
        headers,keys,types=SCHEMAS[tab];mat=books[book][sheet]
        # 原表的列位置由其自身标题定位，行位置由追溯字段定位。
        headerrow=next(row for row in mat if all(h in row for h in headers));columns=[headerrow.index(h) for h in headers]
        for r in data[tab]:
            row=mat[r['source_excel_row']-1]
            for col,h,k,typ in zip(columns,headers,keys,types):
                raw=row[col] if col<len(row) else None;clean=r[k]
                if raw is None:ok=clean is None
                elif typ==str:ok=str(raw).strip()==clean
                else:ok=math.isfinite(float(clean)) and float(raw)==float(clean)
                checks.append({'check':f'{tab}/source_row{r["source_excel_row"]}/{k}','raw_header':h,'raw_value':raw,'clean_value':clean,'pass':ok})
    for r in data['communication']:
        raw=books[r['source_workbook']][r['source_sheet']][r['source_excel_row']-1]
        for col,k in [(0,'category'),(1,'parameter'),(3,'symbol'),(4,'value')]:
            v=raw[col];ok=float(v)==float(r[k]) if k=='value' else str(v).strip()==r[k]
            checks.append({'check':f'communication/row{r["source_excel_row"]}/{k}','raw_header':k,'raw_value':v,'clean_value':r[k],'pass':ok})
    with zipfile.ZipFile(root/'data/raw/题面.docx') as z:
        xml=etree.fromstring(z.read('word/document.xml'))
        maths=[''.join(n.itertext()) for n in xml.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath')]
    txt='\n'.join(maths);(out/'source_formula_text.txt').write_text(txt,encoding='utf-8')
    for key,ok in [('load_exponent_matches_1.5',CFG.range_load_exponent==3/2 and '3/2' in txt),('source_32.45_FSPL_constant','32.45' in txt),('all_models_source_reserve_20percent',all(m['reserve_percent']==20 for m in data['transport_models'])),('official_sensitive_grid_not_below_floor',min(CFG.reserve_scenarios)>=.2)]:
        checks.append({'check':key,'raw_header':'题面/参数核对','raw_value':None,'clean_value':None,'pass':ok})
    # 非自动判断部分以明确证据矩阵列出，不能伪装成每项都是数值测试。
    rules=[
      ('Q1','不分配实体/电池；只O01-Si-O01，不跨区','题面第2页','optimizer.py候选按service_id分区；validation.py逐箱DP','已核验；Q1不强加Q2时限'),
      ('Q1','45组最大安全载荷；整箱不可拆且只送一次','题面第2页','max_safe_payload.csv；payload_continuous_discrete.csv；box_assignment.csv','连续能力与现有箱集合可实现值分别列出'),
      ('Q1','质量、容积、返航余量','题面第2页','independent_optimality.csv；validation_checks.csv','逐批质量/体积/完整往返电耗而非只看去程'),
      ('Q1','三个目标及余量变化','题面第2页','objective_comparison.csv；reserve_sensitivity.csv','优先关系公开，20%起，不把单项最优称综合全优'),
      ('Q2','联合组批、访问次序、机型、实体、电池、开始时刻','题面第3页','q2_search.py；q2_physics.py；trips.csv','均在搜索/解码中决定；无通信要求'),
      ('Q2','医疗期望时限硬约束，首批截止硬约束','题面第3页','q2_validation.py逐箱重算','其余期望时限仅作加权逾期评价'),
      ('Q2','全部任务完工为所有运输机最后返回O01','题面第3页','summary.json；Q2_运输架次.csv','非最后交付或累计工时'),
      ('Q2','8机、初装已包含的14组电池、同型共享','题面第9页','independent_resources.csv；transport_battery_units.csv','未凭空增加初装电池、并行充电可行'),
      ('Q2','90%拐点，65%/35%分段充满才可再次使用','题面第9页','independent_charge；battery_usage.csv','不按全程线性充电，也不带未充满电池出发'),
      ('Q1/Q2','航段最高DEM像元+50；每站30米作业后再爬升','题面第7页','240条有向arc_geometry；独立rasterio核验','去返分开，载荷逐站递减，返程为零'),
      ('Q1/Q2','航程1.5次幂；含电池空载质量不再加电池','题面第8页/原参数','physics.py与q2_validation.py独立公式','水平/爬升两个分项是已披露闭合假设'),
      ('Q1/Q2','模板往返时间与开始时刻口径','原结果模板仅给标题','time_components.csv；提交说明','固定解释：准备开始至返回；保留其他分项；没有额外官方定义'),
      ('Q2','单点/多点、节能对照和可行性','题面第3页','scenario_comparison.csv；每对照独立复核','启发式解；不误称下界已闭合'),
      ('Q1/Q2/Q3','共同原始ID、单位、物理规则','题面第4至5页','本回溯表；共用config与独立重算','Q3新运输方案另表，绝不覆盖Q2答案'),
      ('Q3','全阶段连续通信、单中继双向接入与回传','题面第10至11页','q3_validation.py连续顶点枚举和独立点审查','不只查服务点，不以遮挡直接代替断链'),
      ('Q3','两中继/六组件/300m AGL/建链/周转/返航','题面第8至9页及原表','independent_relay_details.csv','计划总质量23.5kg，建链期额外保守计能耗'),
      ('Q3','联合完工含中继返回','题面第3至4页','Q3_中继架次.csv；summary.json','运输与中继能耗合计，两类架次分别列出'),
    ]
    write_csv(out/'source_cell_trace.csv',checks);write_csv(out/'requirements_traceability.csv',[dict(zip(['question','requirement','source_location','implementation_or_evidence','audit_interpretation'],r)) for r in rules])
    changes=[
       {'item':'Q1/Q2数值与时序','finding':'未发现使原可提交方案失效的计算错误；须以本次独立重跑为准','action':'保留原方案并执行逐单元格源数据回溯和独立物理重算','impact':'不把未考虑Q3通信的Q2方案当成Q3可行方案'},
       {'item':'原模板缺少Q3运输与逐箱工作表','finding':'若覆盖Q2运输表，将造成Q2结论与Q3通信编号前后矛盾','action':'主模板保留Q2；另交Q3运输与逐箱补充.xlsx及两张CSV，Q3-T专属编号','impact':'两问答案分开；检查器联读主模板和补充文件'},
       {'item':'Q3视距与DEM坐标口径','finding':'新问题需要三维直线；不直接以经纬度差作为米或把遮挡等同断链','action':'建立统一局部仿射米坐标；视线与距离同空间；公开坐标近似并报告椭球对照误差','impact':'不修改运输椭球水平航程；通信规则在声明坐标模型内连续验证'},
       {'item':'通信区间边界瞬时','finding':'正长度采样或区间中点不能证明瞬时接触点可通信','action':'正长度开区间及全部边界单点分别报告，单一保障者且直连优先','impact':'零时长行是边界事件，不是占位或丢失任务'},
       {'item':'文档/打包旧作用域','finding':'继承报告仍有Q3未求解与只填写三表的旧叙述','action':'生成器、README、验收、模板发布和打包作用域统一改为Q1/Q2/Q3','impact':'最终包不并置旧版本参考报告误导读者'},
    ]
    write_csv(out/'findings_and_fixes.csv',changes)
    result={'source_cells_checked':len(checks),'source_mismatches':sum(not c['pass'] for c in checks),'traceability_rows':len(rules),'findings_and_consistency_fixes':len(changes),'q1_q2_numerical_rules_changed':False,'source_rule_inventions_presented_as_official':False}
    save_json(out/'audit_summary.json',result)
    if result['source_mismatches']:raise AssertionError('原始单元格回溯失败')
    return result
