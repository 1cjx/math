"""把各自独立绘制的图表按A/B/C面板组合；不截图，不加卡片、标题栏、阴影或装饰。
组合PDF保留原生矢量对象，底图仍为原DEM栅格。Python3.13 / PyMuPDF1.26.7。
"""
from pathlib import Path
import fitz
from .core import ROOT,OUT,write_json,sha

PANELS=[
 ('P01','地形—载荷—能耗的条件响应', [('F148',(115,12,775,432)),('F149',(35,456,430,775)),('F150',(455,456,850,775))],(885,805),
  '上图与两个截面来自同一确定性模型网格。固定S008距离和端点，仅基准巡航海拔为题定任务；不是现场数据或新调度结果。'),
 ('P02','返航安全余量与运输能力', [('F151',(35,12,535,342)),('F152',(575,12,985,418)),('F153',(35,453,535,770)),('F007',(575,453,1075,770))],(1110,805),
  '小提琴为每档15个服务区的C型确定性横截面，实点与四分位线均来自结果。敏感性从20%开始；不可行档位不记为0。'),
 ('P03','需求空间分布与物资组成', [('F155',(35,12,450,385)),('F012',(475,15,885,298)),('F157',(35,412,445,835)),('F156',(475,422,885,705))],(920,860),
  '地图仅呈现真实离散服务节点，不制造连续需求热区；矩阵由80个真实货箱汇总。累计需求按期望时刻统计，不是实际交付或到达率。'),
 ('P04','已计算方案的多指标比较', [('F158',(90,10,780,433)),('F147',(35,456,430,751)),('F159',(455,456,850,751))],(885,780),
  '上图只含5个真实Q3候选，其中有同点重合；下图为已存的候选和搜索轮次，不扩充为虚假的种群点云或全局帕累托前沿。'),
 ('P05','单架次的时空—能源—通信状态', [('F163',(40,10,820,306)),('F160',(40,329,820,641)),('F161',(40,664,820,944)),('F162',(40,967,820,1244))],(855,1267),
  '4幅图共享同一绝对时间范围，来源为Q3-T-016。SOC按模型分阶段累计并校验返航端点；末段显示电池充满，不把充电结束当作Q3完工。'),
 ('P06','严格三分区与独立资源需求', [('F128',(35,12,455,374)),('F117',(480,15,890,287)),('F132',(35,403,455,743)),('F138',(480,403,890,697))],(925,768),
  '保持最终Q3任务和通信关系不变。三组需求35件、分类型缺口7件；资源总件数不是采购成本，补足型号资源才可执行。'),
]

def compose():
    records=[];album=fitz.open()
    for code,title,items,size,note in PANELS:
        if code=='P05':
            rebuilt=[];y=12
            for sub,_ in items:
                with fitz.open(OUT/f'{sub}.pdf') as src:height=780*src[0].rect.height/src[0].rect.width
                rebuilt.append((sub,(40,y,820,y+height)));y+=height+22
            items=rebuilt;size=(855,y+8)
        d=fitz.open();p=d.new_page(width=size[0],height=size[1])
        for j,(sub,rect) in enumerate(items):
            box=fitz.Rect(*rect)
            with fitz.open(OUT/f'{sub}.pdf') as src:
                sr=src[0].rect;scale=min(box.width/sr.width,box.height/sr.height)
                w,h=sr.width*scale,sr.height*scale
                # 图表顶端对齐，字母紧邻实际绘图区，而不是远离图的外框角。
                area=fitz.Rect(box.x0+(box.width-w)/2,box.y0,box.x0+(box.width+w)/2,box.y0+h)
                p.show_pdf_page(area,src,0,keep_proportion=True)
            p.insert_text((max(8,area.x0-22),area.y0+20),chr(65+j),fontname='hebo',fontsize=16,color=(.12,.18,.24))
        d.set_metadata({'title':title,'author':'','creator':'独立数据图的矢量组合程序'})
        target=OUT/f'{code}.pdf';d.save(target,garbage=4,deflate=True,no_new_id=True)
        p.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(OUT/f'{code}.png')
        # SVG仍用PDF矢量转换；不是嵌入整页PNG。
        (OUT/f'{code}.svg').write_text(p.get_svg_image(text_as_path=True),encoding='utf-8')
        album.insert_pdf(d);d.close()
        records.append({'图号':code,'中文图题':title,'组成图号':[x[0] for x in items],'说明':note,'PDF_SHA256':sha(target)})
    album.save(ROOT/'论文联合诊断图册.pdf',garbage=4,deflate=True,no_new_id=True);album.close()
    write_json(ROOT/'audit/panels_manifest.json',records)
    return records
if __name__=='__main__':compose()
