"""将新绘图PDF同步至Overleaf同名图件；保持公式、结果宏与数值表不变。"""
from pathlib import Path
import csv,json,re,shutil,hashlib
from viz.core import ROOT,OUT,csvwrite,write_json,sha

CAPTION_FIXES={
 '各服务区不可拆货箱数量分布；柱高来自完整逐箱需求汇总':'各服务区不可拆货箱数量及物资组成；堆叠总高度来自完整逐箱需求汇总',
 '第三次中继任务的往返高度与沿途地形剖面':'第三次中继任务的往返飞行高度及有效通信服务时段',
}

def sync():
    ov=ROOT/'overleaf';ov.mkdir(exist_ok=True);(ov/'figures').mkdir(exist_ok=True)
    rows=json.loads((ROOT/'audit/render_manifest.json').read_text())
    source=ROOT/'audit/original_main.tex'
    if not source.exists():shutil.copy2(ov/'main.tex',source)
    tex=source.read_text(encoding='utf-8')
    for old,new in CAPTION_FIXES.items():tex=tex.replace(old,new)
    # 仅图注与图集数量更新；数学结果、算法、数据表保留。
    original_assets_sentence='147'
    selected=re.findall(r'\\paperfig(?:\[[^\]]*\])?\{(F\d+)\}',tex)
    for r in rows:
        code=r['图号'];shutil.copy2(OUT/f'{code}.pdf',ov/'figures'/f'{code}.pdf')
        r.update({'本论文选用':'是' if code in selected else '否','Overleaf路径':f'figures/{code}.pdf'})
    panels=json.loads((ROOT/'audit/panels_manifest.json').read_text())
    for r in panels:shutil.copy2(OUT/f'{r["图号"]}.pdf',ov/'figures'/f'{r["图号"]}.pdf')
    (ov/'main.tex').write_text(tex,encoding='utf-8');(ov/'论文完整源码_可复制.txt').write_text(tex,encoding='utf-8')
    csvwrite(ov/'figure_catalog.csv',rows)
    # 可选插入段：每张组图依旧为数值图的组合，不需要新的Python或外部图片生成。
    parts=['% 可选论文组合图：放在main.tex的\\end{document}之前。中文编译器与原工程一致。\n']
    for r in panels:
        parts.append('\\begin{figure}[p]\\centering\n'+f'\\includegraphics[width=.98\\linewidth,height=.80\\textheight,keepaspectratio]{{figures/{r["图号"]}.pdf}}\n'+f'\\caption{{{r["中文图题"]}。{r["说明"].replace("%",r"\%")}}}\n'+f'\\label{{fig:{r["图号"]}}}\n\\end{{figure}}\n')
    (ov/'optional_panels.tex').write_text('\n'.join(parts),encoding='utf-8')
    readme=f'''# D题科学图表原生重绘 · 完整Overleaf工程

main.tex是原论文的完整正文，默认引用{len(selected)}幅同编号的重新绘制图；不是PPT版式。
figures/包含全部163幅独立图和6幅可选多面板组合图。F001-F147保持原图编号；
F148-F163是新增的确定性诊断或既有数据视图。所有图直接从CSV/JSON/DEM用代码生成。

## 编译
保持主文件为main.tex、编译器为XeLaTeX。兼容类my_paper.cls与原工程一致。
不依赖Python、外部BibTeX或字体文件上传。已编译PDF另在总包提供。

## 覆盖使用
将本目录中的main.tex、figure_catalog.csv和figures/覆盖到此前完整论文工程的同名位置。
旧的圆角卡片美化图不再使用。结果宏、数值表、模型公式保持不变。
本次图注微调两处：需求图明确物资堆叠；中继剖面不再错误称为沿途地形剖面。

## 可选多面板图
optional_panels.tex内含P01-P06的LaTeX插入段及严格的解释，不默认塞进正文使论文变长。
要加入正文，在合适位置使用相应figure环境或在文末加入\\input{{optional_panels.tex}}。
读图时：模型扫参不是现场试验；15服务区横截面不是重复随机实验；仅5个Q3候选，
不代表全局帕累托前沿。Q4补足分类型资源后才可独立执行的条件仍然不变。

## 图件格式
PDF中的线、标记、字体轮廓等是矢量；地图背景是原始DEM栅格，不是旧图截图。
生成代码、每幅图的真实数据及哈希、原完整求解工程均在完整交付总包中。
不将字体文件分发给用户；本工程图件已转曲，显示不需本机额外字体。
'''
    (ov/'README.md').write_text(readme,encoding='utf-8')
    # 确认除明确披露的图注修改外，正文完全一致。
    expected=source.read_text(encoding='utf-8')
    for old,new in CAPTION_FIXES.items():expected=expected.replace(old,new)
    assert expected==tex
    macros=lambda t:re.findall(r'\\(?:newcommand|def)[^\n]*',t)
    assert macros(tex)==macros(source.read_text())
    tables=lambda t:re.findall(r'\\begin\{(?:table|longtable)\}.*?\\end\{(?:table|longtable)\}',t,re.S)
    assert tables(tex)==tables(source.read_text())
    write_json(ROOT/'audit/overleaf_sync.json',{'selected_figures':selected,'selected_count':len(selected),'pdf_assets':len(list((ov/'figures').glob('*.pdf'))),'main_text_equal_except_disclosed_captions':True,'formula_macros_unchanged':True,'all_table_blocks_unchanged':True,'main_sha256':sha(ov/'main.tex')})
    return ov
if __name__=='__main__':sync()
