# D题：逐图生成位置、数据来源与修改指南

> 适用版本：`D题_科学图表原生重绘_完整交付.zip`，不是此前的PPT式美化包。本说明基于该包**实际解压后的源码、逐图JSON、图件清单与LaTeX主文件**逐项定位。只新增说明，不修改任何图、实验数据、求解代码或论文正文。

**覆盖范围：163幅独立图（F001–F163）＋6幅组合图（P01–P06）；当前主论文直接引用其中29幅F图。** 文中行号均为本次核对版本的1起始行号。修改源码后行号会移动，请同时使用“函数名＋检索键”定位。`F049`是文件编号，不是论文中自动排出的“图49”。

**建议把本MD放到解压后的 `D_scientific_redesign/` 根目录。** 以下相对文件链接即从该目录出发；编辑器可用Ctrl+G跳转源码行。Markdown内的相对链接在不同阅读器中的行为可能不同，路径文字本身仍可用于搜索。

## 目录

- [一、先区分生成脚本、数据和论文路径](#quick)
- [二、逐张修改与重生成流程](#workflow)
- [三、全局样式和共用函数位置](#shared)
- [四、当前论文29幅图的引用对照](#paper)
- [五、全部独立图快速索引](#index)
- [六、F001–F163逐图详细定位](#details)
- [七、P01–P06组合图布局位置](#panels)
- [八、修改时最容易踩到的实际问题](#pitfalls)
- [九、本说明核对范围与版本指纹](#verify)

<a id="quick"></a>
## 一、先区分生成脚本、数据和论文路径

```text
D_scientific_redesign/              ← 以下命令的工作目录
├── redraw_figures.py                原始147图入口；--only支持F001–F147
├── rebuild_publication.py           全部重绘、核验、组图、同步；会覆盖论文main.tex
├── validate_figures.py              核验绘图来源及指定诊断量
├── sync_overleaf.py                 同步图件，但也重写论文正文，见下方警告
├── viz/
│   ├── style.py                    配色、字体、全局线宽及默认画布
│   ├── core.py                     数据读取、PNG/SVG/PDF导出与索引
│   ├── redraw.py                   F001–F147分支及共用图形函数
│   ├── extras.py                   F148–F163新增诊断图
│   └── compose.py                  P01–P06的子图与布局
├── figures/                        最新图表：Fxxx / Pxx 的PNG、SVG、PDF
├── plot_data/Fxxx.json              当次绘图变量与来源哈希【输出，不是默认输入】
├── figure_catalog.csv               最新163图目录【输出，会重写】
├── audit/
│   ├── render_manifest.json         163图索引；增量绘图时合并
│   ├── panels_manifest.json         P01–P06组成与PDF哈希
│   └── original_main.tex            sync_overleaf恢复正文时使用的基准
├── overleaf/
│   ├── main.tex                    当前论文实际引用
│   ├── optional_panels.tex          P01–P06的可选插图段
│   └── figures/                    上传论文用的PDF副本【不会自动联动】
└── experiment/                     冻结求解工程
    ├── data/cleaned/               真实节点、货箱、DEM等输入
    ├── results/q1…q4/、closure/    已完成的实验数值
    ├── paper/figure_catalog.csv     F001–F147的旧路径→编号映射和原图题
    └── src/paper_figures.py         旧版绘图器，不是本次原生重绘入口
```

**最重要的路径关系：** `figures/F049.pdf` 是最新生成文件，`overleaf/figures/F049.pdf` 是论文使用的副本。修改Python并重画之后，还需要复制新PDF到后者；只改前者不会自动更新现有Overleaf文件。

`experiment/paper/figure_catalog.csv`中的`results/figures/q2_01_routes.png`等旧名称在新代码中仍用作**路由检索键**，但新图最终存为`figures/F049.*`。因此全局搜`F049`未必找到绘图分支，搜`q2_01_routes.png`才会命中。

<a id="workflow"></a>
## 二、逐张修改与重生成流程

### 2.1 先看图，再找对应分支
打开 `图表浏览.html` 或 `figures/` 确认图号；在本说明中搜索该图号。先修改逐图分支的坐标轴、颜色、线宽、标签，不改`experiment/`内的物理参数与已求解数值。

### 2.2 F001–F147：原入口已支持按图号重绘
```bash
# 在 D_scientific_redesign/ 根目录运行
python redraw_figures.py --only F049

# 一次重画几张
python redraw_figures.py --only F012 F049 F147

# 原始147图全部重画（保留已有新增图）
python redraw_figures.py --skip-extras
```
这些命令更新`figures/Fxxx.png/.svg/.pdf`、`plot_data/Fxxx.json`、根目录图件清单和`audit/render_manifest.json`；不会重新优化Q1–Q4，也不会同步Overleaf或组合图。`Publisher.finish()`合并后清单仍有163项，终端打印“163幅”不表示这次真的重画了163张。

### 2.3 F148–F163：不要直接用旧的`--only`
**当前实际代码中，`redraw_figures.py --only F151`不会生成F151。** `--only`只筛选原始147图，同时抑制extras调用；同理不支持P图。不要根据终端合并后的清单数量误判成功。
重画全部16幅新增诊断图，可以使用现有函数：
```bash
python -c "from viz.core import Publisher; from viz.extras import make_extras; p=Publisher(); make_extras(p); p.finish()"

# 只重画同架次的四张状态图F160–F163
python -c "from viz.core import Publisher; from viz.extras import make_states; p=Publisher(); make_states(p); p.finish()"
```

**逐张调新增图的可选辅助脚本：**下面是本说明提供的新脚本，不是声称原包已有该文件。复制为根目录的`redraw_selected_local.py`，即可统一选择F001–F163。新增诊断仍执行共享数据准备，但只保存指定图；不篡改求解数值。
```python
"""在D_scientific_redesign根目录运行：python redraw_selected_local.py F151 F152"""
import argparse
import re
from matplotlib import pyplot as plt
from viz.core import Publisher
from viz.redraw import make_originals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="+")
    args = parser.parse_args()
    selected = {s.upper() for s in args.ids}
    invalid = [s for s in selected if not re.fullmatch(r"F\d{3}", s)
               or not 1 <= int(s[1:]) <= 163]
    if invalid:
        parser.error("图号须为F001–F163：" + ", ".join(sorted(invalid)))

    class SelectedPublisher(Publisher):
        def save(self, fig, code, *values, **kwargs):
            if code in selected:
                return super().save(fig, code, *values, **kwargs)
            plt.close(fig)

    pub = SelectedPublisher()
    originals = {s for s in selected if int(s[1:]) <= 147}
    extras = {s for s in selected if int(s[1:]) >= 148}
    if originals:
        make_originals(pub, originals)
    if extras:
        from viz.extras import make_extras, make_states
        if all(int(s[1:]) >= 160 for s in extras):
            make_states(pub)
        else:
            make_extras(pub)
    written = {r["图号"] for r in pub.records}
    if written != selected:
        raise RuntimeError(f"请求{sorted(selected)}，实际只生成{sorted(written)}")
    pub.finish()
    print("本次实际重画：" + ", ".join(sorted(written)))


if __name__ == "__main__":
    main()
```
```bash
python redraw_selected_local.py F151
python redraw_selected_local.py F049 F151 F152
```

### 2.4 P01–P06：先重画子图，再重组
```bash
# 例：P02由F151、F152、F153、F007组成
python redraw_selected_local.py F151 F152 F153 F007
python -m viz.compose
```
`python -m viz.compose`会重组全部六幅P图，生成PNG/PDF/SVG、图册和组合清单。它读取的是最新`figures/Fxxx.pdf`，不会再次读取求解表或执行F图绘图。仅重画F图时，已有P图仍是旧版本，必须重组。

### 2.5 安全同步PDF，不覆盖你改过的论文
**当前`sync_overleaf.py`不是“仅复制图片”。第14–26行会从`audit/original_main.tex`恢复并重写`overleaf/main.tex`；第32行会重写`optional_panels.tex`。** 已自行改正文、图注、插入组图或改变宽度后，不要直接调用它，也不要无意运行含它的`rebuild_publication.py`。
最安全的方式是只将修改过的PDF复制到`overleaf/figures/`，然后上传同名PDF覆盖。跨平台Python示例（在根目录运行）：
```python
from pathlib import Path
import shutil

root = Path.cwd()
changed = ["F049", "F151", "F152", "F153", "F007", "P02"]
for code in changed:
    src = root / "figures" / f"{code}.pdf"
    dst = root / "overleaf" / "figures" / src.name
    if not src.is_file():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
print("仅更新图件；main.tex和optional_panels.tex未动。")
```
或者在文件管理器中直接复制。只复制PDF时`overleaf/figure_catalog.csv`内的哈希是旧快照；需要归档新版本时同步刷新该清单，但不要手工伪造“全部校验通过”。根目录`figure_catalog.csv`与`plot_data/`会由重绘程序更新。

### 2.6 验证与完整重建
```bash
# 绘图来源、指定数值聚合与文件格式核验
python validate_figures.py
```
此脚本会写`audit/figure_validation.json`及详细检查记录。它核验源文件哈希、80箱汇总、特定诊断量等，**不会自动证明所有坐标轴编码都没画错、不会全面检查标签重叠，也不替代原物理验证**。修改映射关系后要同时检查图和`plot_data/Fxxx.json`。
未自行编辑论文正文、接受恢复基准`main.tex`时，才使用完整链：
```bash
python rebuild_publication.py
# 或同时本地编译：
python rebuild_publication.py --compile
```
外观调整不需要`--recompute`，也不需要执行`experiment/run_all.py`。局部重绘不更新已有ZIP；修改完成后需要把新的PDF放入论文项目再重新压缩。

<a id="shared"></a>
## 三、全局样式和共用函数位置

| 要调整什么 | 文件 | 行号 | 真正起作用的位置 |
|---|---|---|---|
| 统一色彩/机型/阶段/物资 | `viz/style.py` | 8–15 | BLUE/TEAL/GOLD等、MODEL、QUESTION、PHASE、MATERIAL、TERRAIN、ENERGY；会影响所有使用这些变量的图。 |
| 中文字库选择 | `viz/style.py` | 17–22 | chinese_font()；不需要向Overleaf上传字体文件。 |
| 全局字体、坐标轴、线宽、图例 | `viz/style.py` | 24–34 | setup()中的rcParams；显式写在局部函数里的参数优先于全局值。 |
| 默认画布与空白 | `viz/style.py` | 36–42 | figure(size, projection)；修改默认值只影响未显式传size的图。 |
| 棒棒糖/点线图 | `viz/redraw.py` | 31–47 | dotbars()；横向/竖向、标记大小、数值注释偏移。 |
| 分组柱 | `viz/redraw.py` | 49–55 | grouped()；width=.72/len(series)、图例与标签。 |
| 数值热图 | `viz/redraw.py` | 57–72 | heatmap()；格子、数值、色带、范围、colorbar。 |
| DEM读取与地图 | `viz/redraw.py` | 74–132 | dem()/plot_map()；底图、范围、航段、箭头、节点标签、色条；改helper会影响多张图。 |
| 甘特时序 | `viz/redraw.py` | 134–158 | gantt()；根据资源行数确定高、条形与充电/周转斜线、任务号。 |
| 候选时间—能耗比较 | `viz/redraw.py` | 160–180 | tradeoff()；同点注释、选中标记、可行性标记、空白。 |
| 统一标题与导出 | `viz/core.py` | 53–86 | Publisher.save()；图题、图例轴外处理、tight_layout、PNG/SVG/PDF、逐图JSON。 |
| 增量索引合并 | `viz/core.py` | 87–95 | Publisher.finish()；合并旧记录并更新根目录清单，不代表全部图都重新绘制。 |
| 新增诊断参数 | `viz/extras.py` | 19–23 | GRID_NQ/GRID_NH/EXTRA_ALTITUDE_M、RESERVE_LEVELS、KDE_BANDWIDTH/KDE_POINTS、STATE_TRIP。 |
| 状态图统一边框大小 | `viz/extras.py` | 25–27 | store()对F160–F163设置_shared_state_frame；实际留白在core.py第65–70行。 |
| 组合图组成和摆位 | `viz/compose.py` | 8–21 | PANELS中每个子图的目标矩形及页尺寸；P05另有自动布局。 |
| P05特殊自动纵向布局 | `viz/compose.py` | 26–31 | 固定宽度780 pt，根据子PDF纵横比自动计算高度；仅改PANELS中的P05纵坐标不会生效。 |
| 组合图字母及预览 | `viz/compose.py` | 33–46 | show_pdf_page保留矢量、A/B/C/D的字号/位置、1.8倍预览栅格倍率。 |

**导出清晰度有一个局部覆盖：**虽然`viz/style.py`第34行设置`savefig.dpi`，实际PNG输出在`viz/core.py`第72行显式使用`dpi=260`。要改PNG导出分辨率，需改后者；PDF/SVG由矢量对象输出，改变PNG的dpi不会提升矢量线条精度。地图底图仍是原DEM栅格。

### 只改一个图而不连带其他图
很多F图共享同一个函数甚至同一个分支。局部调整可以放在`viz/redraw.py`第354行的`pub.save(...)`之前，按`code`区分。例如：
```python
    # 在 redraw_one() 内，pub.save(...)之前添加：
    if code == "F049":
        f.set_size_inches(8.6, 5.8)
        title = "多点运输航线与真实地形"
        a.tick_params(axis="both", labelsize=10)
        for line in a.lines:
            line.set_linewidth(1.3)

    pub.save(f, code, title, S, vals, note)
```
这只改变F049的表达，不改坐标或数值。若要只对F049调整地图内部节点标签/箭头，需给`plot_map()`新增视觉参数并在该图调用时传入，或者在返回的Axes里定位目标artist；直接改`plot_map()`默认值会同时影响其他地图。
`a.set_title(...)`在分支里设置后会被`Publisher.save()`覆盖；改变保存时传入的`title`或`short_title`才会保留。论文图注则另改`overleaf/main.tex`的对应调用，两者不是同一文本。

<a id="paper"></a>
## 四、当前论文29幅图的引用对照

以下顺序由当前`overleaf/main.tex`中的`\paperfig`实际调用提取；不是资产编号排序。正文宏定义位于第59–63行，宽度从每次调用的可选参数传入，最高高度固定为`.39\textheight`，可能使甘特图等高图在正文里显得偏小。这是LaTeX缩放，不是Python图片导出缺失。
| 引用顺序 | 文件编号 | 图题 | main.tex行 | LaTeX label | 所在章节 |
|---|---|---|---|---|---|
| 1 | [F012](#F012) | 数据核查：全部货箱按服务区分布 | 239 | `fig:demand` | 数据预处理与公共物理模型 |
| 2 | [F002](#F002) | 原始全分辨率地形与任务节点 | 240 | `fig:terrain` | 数据预处理与公共物理模型 |
| 3 | [F027](#F027) | 第一问：O01至S008沿线地形与净空 | 288 | `fig:profile` | 数据预处理与公共物理模型 |
| 4 | [F046](#F046) | 第一问：C型连续上限与现有整箱可实现载荷 | 410 | `fig:discretepayload` | 问题一：单点往返能力与不可拆货箱组批 |
| 5 | [F010](#F010) | 第一问：不同架次数下的最小能耗曲线 | 484 | `fig:q1frontier` | 问题一：单点往返能力与不可拆货箱组批 |
| 6 | [F007](#F007) | 第一问：安全余量与最少架次数 | 507 | `fig:reserve` | 问题一：单点往返能力与不可拆货箱组批 |
| 7 | [F049](#F049) | Q2：26架次运输航线与节点 | 648 | `fig:q2route` | 问题二：异构无人机多点多架次运输调度 |
| 8 | [F050](#F050) | Q2：运输无人机占用时序 | 649 | `fig:q2drone` | 问题二：异构无人机多点多架次运输调度 |
| 9 | [F051](#F051) | Q2：共享电池任务与充电时序 | 653 | `fig:q2battery` | 问题二：异构无人机多点多架次运输调度 |
| 10 | [F053](#F053) | Q2：实算备选方案的时间与能耗 | 676 | `fig:q2trade` | 问题二：异构无人机多点多架次运输调度 |
| 11 | [F147](#F147) | 闭环筛选：独立Q3候选的严格三分区兼容性 | 822 | `fig:compatibility` | 问题三：连续通信约束下运输与中继联合调度 |
| 12 | [F063](#F063) | Q3：25架次运输航线与节点 | 829 | `fig:q3route` | 问题三：连续通信约束下运输与中继联合调度 |
| 13 | [F064](#F064) | Q3：运输无人机占用时序 | 830 | `fig:q3drone` | 问题三：连续通信约束下运输与中继联合调度 |
| 14 | [F078](#F078) | 第三问：中继无人机任务及周转 | 862 | `fig:relaybody` | 问题三：连续通信约束下运输与中继联合调度 |
| 15 | [F109](#F109) | 第三问：直连与中继保障的完整时间区间 | 863 | `fig:commtimeline` | 问题三：连续通信约束下运输与中继联合调度 |
| 16 | [F117](#F117) | 第四问：运输与中继依赖合并后的不可拆单元 | 899 | `fig:atomic` | 问题四：严格冻结任务的分区与资源配置 |
| 17 | [F118](#F118) | 第四问：严格不复制中继的2组分区 | 966 | `fig:k2map` | 问题四：严格冻结任务的分区与资源配置 |
| 18 | [F128](#F128) | 第四问：严格不复制中继的3组分区 | 967 | `fig:k3map` | 问题四：严格冻结任务的分区与资源配置 |
| 19 | [F138](#F138) | 第四问：严格可行的全部4个分区比较 | 1011 | `fig:q4all` | 问题四：严格冻结任务的分区与资源配置 |
| 20 | [F112](#F112) | 第三问：额外传播损耗压力测试 | 1066 | `fig:losssweep` | 闭环核验与敏感性分析 |
| 21 | [F113](#F113) | 第三问：仅中继延迟的冻结分配测试 | 1070 | `fig:relaydelay` | 闭环核验与敏感性分析 |
| 22 | [F139](#F139) | 闭环压力测试：运输能耗扰动与最低返航电量 | 1099 | `fig:energystress` | 闭环核验与敏感性分析 |
| 23 | [F142](#F142) | 闭环压力测试：充电时间扰动与下一次任务准备裕度 | 1103 | `fig:chargestress` | 闭环核验与敏感性分析 |
| 24 | [F144](#F144) | 闭环压力测试：共同延迟对最紧硬时限的影响 | 1113 | `fig:delaystress` | 闭环核验与敏感性分析 |
| 25 | [F077](#F077) | 第二问：固定搜索预算下的收敛轨迹 | 1480 | `fig:suppsearch` | 补充诊断图与完整图件索引 |
| 26 | [F079](#F079) | 第三问：中继能源组件及两阶段充电 | 1481 | `fig:suppenergy` | 补充诊断图与完整图件索引 |
| 27 | [F082](#F082) | 第三问：Q3-R-003完整飞行及服务剖面 | 1482 | `fig:supprelay` | 补充诊断图与完整图件索引 |
| 28 | [F099](#F099) | 第三问：Q3-T-016逐阶段高度剖面 | 1483 | `fig:supptransport` | 补充诊断图与完整图件索引 |
| 29 | [F135](#F135) | 第四问：3组独立运输电池占用 | 1484 | `fig:suppbattery` | 补充诊断图与完整图件索引 |

论文插图宽度、最大高度或位置不满意时，先检查上述宏与调用，而不是在Python里反复加大字体。P图默认没有插进主正文；`overleaf/optional_panels.tex`提供独立`figure`环境。

<a id="index"></a>
## 五、全部独立图快速索引

`调用`列先给具体图的分支；同一函数还可能由多图共享，详细说明列出共用函数。全部独立图均输出到`figures/Fxxx.{png,pdf,svg}`，实际绘图变量存`plot_data/Fxxx.json`。
### 数据与Q1（F001–F048）
| 编号 | 中文图题 | 调用位置 | 论文/组合使用 |
|---|---|---|---|
| [F001](#F001) | 第一问：调度中心与单点往返航线 | `viz/redraw.py:187–187` | 未直接引用 |
| [F002](#F002) | 原始全分辨率地形与任务节点 | `viz/redraw.py:186–186` | 论文2 |
| [F003](#F003) | 第一问：各机型连续最大安全载荷 | `viz/redraw.py:195–197` | 未直接引用 |
| [F004](#F004) | 第一问：各服务区最少往返架次数 | `viz/redraw.py:198–199` | 未直接引用 |
| [F005](#F005) | 第一问：逐架次往返能耗分解 | `viz/redraw.py:208–219` | 未直接引用 |
| [F006](#F006) | 第一问：每一架次返航电量核验 | `viz/redraw.py:220–224` | 未直接引用 |
| [F007](#F007) | 第一问：安全余量与最少架次数 | `viz/redraw.py:225–234` | 论文6；P02-D |
| [F008](#F008) | 第一问：提高返航余量后的总能耗 | `viz/redraw.py:225–234` | 未直接引用 |
| [F009](#F009) | 第一问：S008安全载荷对余量要求的响应 | `viz/redraw.py:235–239` | 未直接引用 |
| [F010](#F010) | 第一问：不同架次数下的最小能耗曲线 | `viz/redraw.py:240–244` | 论文5 |
| [F011](#F011) | 数据核查：题定节点海拔与DEM像元差异 | `viz/redraw.py:206–207` | 未直接引用 |
| [F012](#F012) | 数据核查：全部货箱按服务区分布 | `viz/redraw.py:200–205` | 论文1；P03-B |
| [F013](#F013) | 第一问：O01至S001沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F014](#F014) | 第一问：S001载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F015](#F015) | 第一问：O01至S002沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F016](#F016) | 第一问：S002载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F017](#F017) | 第一问：O01至S003沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F018](#F018) | 第一问：S003载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F019](#F019) | 第一问：O01至S004沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F020](#F020) | 第一问：S004载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F021](#F021) | 第一问：O01至S005沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F022](#F022) | 第一问：S005载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F023](#F023) | 第一问：O01至S006沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F024](#F024) | 第一问：S006载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F025](#F025) | 第一问：O01至S007沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F026](#F026) | 第一问：S007载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F027](#F027) | 第一问：O01至S008沿线地形与净空 | `viz/redraw.py:245–251` | 论文3 |
| [F028](#F028) | 第一问：瓶颈区域S008地形剖面 | `viz/redraw.py:245–251` | 未直接引用 |
| [F029](#F029) | 第一问：S008载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F030](#F030) | 第一问：O01至S009沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F031](#F031) | 第一问：S009载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F032](#F032) | 第一问：O01至S010沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F033](#F033) | 第一问：S010载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F034](#F034) | 第一问：O01至S011沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F035](#F035) | 第一问：S011载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F036](#F036) | 第一问：O01至S012沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F037](#F037) | 第一问：S012载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F038](#F038) | 第一问：O01至S013沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F039](#F039) | 第一问：S013载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F040](#F040) | 第一问：O01至S014沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F041](#F041) | 第一问：S014载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F042](#F042) | 第一问：O01至S015沿线地形与净空 | `viz/redraw.py:245–251` | 未直接引用 |
| [F043](#F043) | 第一问：S015载荷—能量可行边界 | `viz/redraw.py:252–256` | 未直接引用 |
| [F044](#F044) | 第一问：A型连续上限与现有整箱可实现载荷 | `viz/redraw.py:257–260` | 未直接引用 |
| [F045](#F045) | 第一问：B型连续上限与现有整箱可实现载荷 | `viz/redraw.py:257–260` | 未直接引用 |
| [F046](#F046) | 第一问：C型连续上限与现有整箱可实现载荷 | `viz/redraw.py:257–260` | 论文4 |
| [F047](#F047) | 第一问：三种时间口径的组成 | `viz/redraw.py:208–219` | 未直接引用 |
| [F048](#F048) | 第一问：能耗分项假设扰动后重新优化 | `viz/redraw.py:261–262` | 未直接引用 |

### Q2及搜索日志（F049–F062、F077）
| 编号 | 中文图题 | 调用位置 | 论文/组合使用 |
|---|---|---|---|
| [F049](#F049) | Q2：26架次运输航线与节点 | `viz/redraw.py:188–191` | 论文7 |
| [F050](#F050) | Q2：运输无人机占用时序 | `viz/redraw.py:263–272` | 论文8 |
| [F051](#F051) | Q2：共享电池任务与充电时序 | `viz/redraw.py:263–272` | 论文9 |
| [F052](#F052) | Q2：医疗及首批保障货箱硬时限 | `viz/redraw.py:273–276` | 未直接引用 |
| [F053](#F053) | Q2：实算备选方案的时间与能耗 | `viz/redraw.py:277–278` | 论文10 |
| [F054](#F054) | Q2：逐架次返航安全余量 | `viz/redraw.py:220–224` | 未直接引用 |
| [F055](#F055) | Q2：全部货箱累计交付进度 | `viz/redraw.py:279–280` | 未直接引用 |
| [F056](#F056) | Q2：A型无人机运输路线 | `viz/redraw.py:188–191` | 未直接引用 |
| [F057](#F057) | Q2：B型无人机运输路线 | `viz/redraw.py:188–191` | 未直接引用 |
| [F058](#F058) | Q2：C型无人机运输路线 | `viz/redraw.py:188–191` | 未直接引用 |
| [F059](#F059) | Q2：各服务区最紧硬时限裕度 | `viz/redraw.py:281–282` | 未直接引用 |
| [F060](#F060) | Q2：载质量与装载体积利用率 | `viz/redraw.py:283–284` | 未直接引用 |
| [F061](#F061) | Q2：逐航段汇总的运输能耗分项 | `viz/redraw.py:208–219` | 未直接引用 |
| [F062](#F062) | Q2：分机型累计作业与纯飞行时间 | `viz/redraw.py:285–286` | 未直接引用 |
| [F077](#F077) | 第二问：固定搜索预算下的收敛轨迹 | `viz/redraw.py:287–291` | 论文25 |

### Q3（F063–F076、F078–F116）
| 编号 | 中文图题 | 调用位置 | 论文/组合使用 |
|---|---|---|---|
| [F063](#F063) | Q3：25架次运输航线与节点 | `viz/redraw.py:188–191` | 论文12 |
| [F064](#F064) | Q3：运输无人机占用时序 | `viz/redraw.py:263–272` | 论文13 |
| [F065](#F065) | Q3：共享电池任务与充电时序 | `viz/redraw.py:263–272` | 未直接引用 |
| [F066](#F066) | Q3：医疗及首批保障货箱硬时限 | `viz/redraw.py:273–276` | 未直接引用 |
| [F067](#F067) | Q3：实算备选方案的时间与能耗 | `viz/redraw.py:277–278` | 未直接引用 |
| [F068](#F068) | Q3：逐架次返航安全余量 | `viz/redraw.py:220–224` | 未直接引用 |
| [F069](#F069) | Q3：全部货箱累计交付进度 | `viz/redraw.py:279–280` | 未直接引用 |
| [F070](#F070) | Q3：A型无人机运输路线 | `viz/redraw.py:188–191` | 未直接引用 |
| [F071](#F071) | Q3：B型无人机运输路线 | `viz/redraw.py:188–191` | 未直接引用 |
| [F072](#F072) | Q3：C型无人机运输路线 | `viz/redraw.py:188–191` | 未直接引用 |
| [F073](#F073) | Q3：各服务区最紧硬时限裕度 | `viz/redraw.py:281–282` | 未直接引用 |
| [F074](#F074) | Q3：载质量与装载体积利用率 | `viz/redraw.py:283–284` | 未直接引用 |
| [F075](#F075) | Q3：逐航段汇总的运输能耗分项 | `viz/redraw.py:208–219` | 未直接引用 |
| [F076](#F076) | Q3：分机型累计作业与纯飞行时间 | `viz/redraw.py:285–286` | 未直接引用 |
| [F078](#F078) | 第三问：中继无人机任务及周转 | `viz/redraw.py:263–272` | 论文14 |
| [F079](#F079) | 第三问：中继能源组件及两阶段充电 | `viz/redraw.py:263–272` | 论文26 |
| [F080](#F080) | 第三问：Q3-R-001完整飞行及服务剖面 | `viz/redraw.py:292–294` | 未直接引用 |
| [F081](#F081) | 第三问：Q3-R-002完整飞行及服务剖面 | `viz/redraw.py:292–294` | 未直接引用 |
| [F082](#F082) | 第三问：Q3-R-003完整飞行及服务剖面 | `viz/redraw.py:292–294` | 论文27 |
| [F083](#F083) | 第三问：Q3-R-004完整飞行及服务剖面 | `viz/redraw.py:292–294` | 未直接引用 |
| [F084](#F084) | 第三问：Q3-T-001逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F085](#F085) | 第三问：Q3-T-002逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F086](#F086) | 第三问：Q3-T-003逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F087](#F087) | 第三问：Q3-T-004逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F088](#F088) | 第三问：Q3-T-005逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F089](#F089) | 第三问：Q3-T-006逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F090](#F090) | 第三问：Q3-T-007逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F091](#F091) | 第三问：Q3-T-008逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F092](#F092) | 第三问：Q3-T-009逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F093](#F093) | 第三问：Q3-T-010逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F094](#F094) | 第三问：Q3-T-011逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F095](#F095) | 第三问：Q3-T-012逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F096](#F096) | 第三问：Q3-T-013逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F097](#F097) | 第三问：Q3-T-014逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F098](#F098) | 第三问：Q3-T-015逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F099](#F099) | 第三问：Q3-T-016逐阶段高度剖面 | `viz/redraw.py:295–299` | 论文28 |
| [F100](#F100) | 第三问：Q3-T-017逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F101](#F101) | 第三问：Q3-T-018逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F102](#F102) | 第三问：Q3-T-019逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F103](#F103) | 第三问：Q3-T-020逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F104](#F104) | 第三问：Q3-T-021逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F105](#F105) | 第三问：Q3-T-022逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F106](#F106) | 第三问：Q3-T-023逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F107](#F107) | 第三问：Q3-T-024逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F108](#F108) | 第三问：Q3-T-025逐阶段高度剖面 | `viz/redraw.py:295–299` | 未直接引用 |
| [F109](#F109) | 第三问：直连与中继保障的完整时间区间 | `viz/redraw.py:300–308` | 论文15 |
| [F110](#F110) | 第三问：直连与中继累计保障工作量 | `viz/redraw.py:309–310` | 未直接引用 |
| [F111](#F111) | 第三问：已分割区间中点链路裕量分布 | `viz/redraw.py:311–312` | 未直接引用 |
| [F112](#F112) | 第三问：额外传播损耗压力测试 | `viz/redraw.py:313–315` | 论文20 |
| [F113](#F113) | 第三问：仅中继延迟的冻结分配测试 | `viz/redraw.py:313–315` | 论文21 |
| [F114](#F114) | 第三问：全部资源共同延后的时限裕度 | `viz/redraw.py:313–315` | 未直接引用 |
| [F115](#F115) | 第三问：每次中继任务能耗组成 | `viz/redraw.py:316–317` | 未直接引用 |
| [F116](#F116) | 第三问：中继任务返航剩余电量 | `viz/redraw.py:220–224` | 未直接引用 |

### Q4（F117–F138）
| 编号 | 中文图题 | 调用位置 | 论文/组合使用 |
|---|---|---|---|
| [F117](#F117) | 第四问：运输与中继依赖合并后的不可拆单元 | `viz/redraw.py:318–319` | 论文16；P06-B |
| [F118](#F118) | 第四问：严格不复制中继的2组分区 | `viz/redraw.py:192–194` | 论文17 |
| [F119](#F119) | 第四问：2组的运输累计作业时间 | `viz/redraw.py:320–332` | 未直接引用 |
| [F120](#F120) | 第四问：2组的货箱数量 | `viz/redraw.py:320–332` | 未直接引用 |
| [F121](#F121) | 第四问：2组的运输架次数 | `viz/redraw.py:320–332` | 未直接引用 |
| [F122](#F122) | 第四问：2组独立配置需求与原库存 | `viz/redraw.py:320–332` | 未直接引用 |
| [F123](#F123) | 第四问：2组分类型资源缺口 | `viz/redraw.py:320–332` | 未直接引用 |
| [F124](#F124) | 第四问：2组独立运输机身占用 | `viz/redraw.py:263–272` | 未直接引用 |
| [F125](#F125) | 第四问：2组独立运输电池占用 | `viz/redraw.py:263–272` | 未直接引用 |
| [F126](#F126) | 第四问：2组独立中继机身占用 | `viz/redraw.py:263–272` | 未直接引用 |
| [F127](#F127) | 第四问：2组独立中继能源组件占用 | `viz/redraw.py:263–272` | 未直接引用 |
| [F128](#F128) | 第四问：严格不复制中继的3组分区 | `viz/redraw.py:192–194` | 论文18；P06-A |
| [F129](#F129) | 第四问：3组的运输累计作业时间 | `viz/redraw.py:320–332` | 未直接引用 |
| [F130](#F130) | 第四问：3组的货箱数量 | `viz/redraw.py:320–332` | 未直接引用 |
| [F131](#F131) | 第四问：3组的运输架次数 | `viz/redraw.py:320–332` | 未直接引用 |
| [F132](#F132) | 第四问：3组独立配置需求与原库存 | `viz/redraw.py:320–332` | 未直接引用；P06-C |
| [F133](#F133) | 第四问：3组分类型资源缺口 | `viz/redraw.py:320–332` | 未直接引用 |
| [F134](#F134) | 第四问：3组独立运输机身占用 | `viz/redraw.py:263–272` | 未直接引用 |
| [F135](#F135) | 第四问：3组独立运输电池占用 | `viz/redraw.py:263–272` | 论文29 |
| [F136](#F136) | 第四问：3组独立中继机身占用 | `viz/redraw.py:263–272` | 未直接引用 |
| [F137](#F137) | 第四问：3组独立中继能源组件占用 | `viz/redraw.py:263–272` | 未直接引用 |
| [F138](#F138) | 第四问：严格可行的全部4个分区比较 | `viz/redraw.py:333–337` | 论文19；P06-D |

### 闭环压力/筛选（F139–F147）
| 编号 | 中文图题 | 调用位置 | 论文/组合使用 |
|---|---|---|---|
| [F139](#F139) | 闭环压力测试：运输能耗扰动与最低返航电量 | `viz/redraw.py:338–350` | 论文22 |
| [F140](#F140) | 闭环压力测试：运输能耗扰动导致的安全余量违约 | `viz/redraw.py:338–350` | 未直接引用 |
| [F141](#F141) | 闭环压力测试：运输能耗扰动导致的电池周转冲突 | `viz/redraw.py:338–350` | 未直接引用 |
| [F142](#F142) | 闭环压力测试：充电时间扰动与下一次任务准备裕度 | `viz/redraw.py:338–350` | 论文23 |
| [F143](#F143) | 闭环压力测试：充电变慢后的资源冲突 | `viz/redraw.py:338–350` | 未直接引用 |
| [F144](#F144) | 闭环压力测试：共同延迟对最紧硬时限的影响 | `viz/redraw.py:338–350` | 论文24 |
| [F145](#F145) | 闭环压力测试：共同延迟导致的硬时限违约货箱数 | `viz/redraw.py:338–350` | 未直接引用 |
| [F146](#F146) | 闭环压力测试：共同延迟导致的期望送达逾期 | `viz/redraw.py:338–350` | 未直接引用 |
| [F147](#F147) | 闭环筛选：独立Q3候选的严格三分区兼容性 | `viz/redraw.py:277–278` | 论文11；P04-B |

### 新增模型与统计诊断（F148–F163）
| 编号 | 中文图题 | 调用位置 | 论文/组合使用 |
|---|---|---|---|
| [F148](#F148) | C型载荷—巡航海拔能耗响应（模型扫参） | `viz/extras.py:46–55` | 未直接引用；P01-A |
| [F149](#F149) | 同一能耗曲面的可行域投影 | `viz/extras.py:56–58` | 未直接引用；P01-B |
| [F150](#F150) | 巡航海拔改变时的载荷—能耗截面 | `viz/extras.py:59–63` | 未直接引用；P01-C |
| [F151](#F151) | 返航余量下的跨服务区载荷分布 | `viz/extras.py:65–83` | 未直接引用；P02-A |
| [F152](#F152) | 15个服务区的安全载荷敏感性 | `viz/extras.py:84–87` | 未直接引用；P02-B |
| [F153](#F153) | 安全载荷的经验累计分布 | `viz/extras.py:88–92` | 未直接引用；P02-C |
| [F154](#F154) | 异构机型载荷—等效航程关系 | `viz/extras.py:93–97` | 未直接引用 |
| [F155](#F155) | 实际需求的空间位置与时间要求 | `viz/extras.py:98–113` | 未直接引用；P03-A |
| [F156](#F156) | 按期望送达时刻累计的物资需求 | `viz/extras.py:114–118` | 未直接引用；P03-D |
| [F157](#F157) | 服务区—物资类别的真实需求矩阵 | `viz/extras.py:119–121` | 未直接引用；P03-C |
| [F158](#F158) | 五个已计算Q3候选的三指标位置 | `viz/extras.py:122–133` | 未直接引用；P04-A |
| [F159](#F159) | 实际搜索日志中的时间—能耗轨迹 | `viz/extras.py:134–138` | 未直接引用；P04-C |
| [F160](#F160) | Q3-T-016：任务能耗与两阶段充电 | `viz/extras.py:158–159` | 未直接引用；P05-B |
| [F161](#F161) | Q3-T-016：完成站点交接后的剩余载荷 | `viz/extras.py:160–164` | 未直接引用；P05-C |
| [F162](#F162) | Q3-T-016：全飞行与交接区间通信切换 | `viz/extras.py:165–170` | 未直接引用；P05-D |
| [F163](#F163) | Q3-T-016：与能源、通信对齐的飞行剖面 | `viz/extras.py:171–175` | 未直接引用；P05-A |

<a id="details"></a>
## 六、F001–F163逐图详细定位

每张图的数据源列表来自**本次交付图的实际`plot_data`来源记录**；相对路径前加`experiment/`后就是实际读取位置。某些来源是构造时继承注册的辅助文件，不一定每一列都被直接画出。逐图JSON的`values`保存计算后的绘图变量，**改JSON不会让绘图器自动按你改过的JSON重画**。

<a id="F001"></a>
### F001｜第一问：调度中心与单点往返航线

**图形类型：**单点往返航线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **187** 行，函数`redraw_one()` |
| 检索键 | `01_dem_routes.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F001.png`](figures/F001.png) · [`figures/F001.pdf`](figures/F001.pdf) · [`figures/F001.svg`](figures/F001.svg) |
| 绘图变量/来源 | [`plot_data/F001.json`](plot_data/F001.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F001.pdf`](overleaf/figures/F001.pdf) |

**取数及计算位置：**读取各服务区单点往返路线，以O01为共同起终点。

**建议改动的位置：**航线颜色、线宽、箭头位置、地形透明度、标签；见plot_map。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F001
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F002"></a>
### F002｜原始全分辨率地形与任务节点

**图形类型：**DEM地形图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **186** 行，函数`redraw_one()` |
| 检索键 | `q1/q1_00_dem.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F002.png`](figures/F002.png) · [`figures/F002.pdf`](figures/F002.pdf) · [`figures/F002.svg`](figures/F002.svg) |
| 绘图变量/来源 | [`plot_data/F002.json`](plot_data/F002.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json) |
| 论文图件副本 | [`overleaf/figures/F002.pdf`](overleaf/figures/F002.pdf) |

**取数及计算位置：**整幅DEM + 16个题定节点；底图颜色对应海拔。

**建议改动的位置：**地图范围/大小、TERRAIN色带、底图alpha、标签偏移、节点面积、色条；见plot_map。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**第2个图引用；`overleaf/main.tex:240`；章节“数据预处理与公共物理模型” / “全量质量审核与标准化清洗”。
```latex
\paperfig[.88]{F002}{完整原始地形及任务节点；航线计算使用全部有效像元}{fig:terrain}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F002
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F003"></a>
### F003｜第一问：各机型连续最大安全载荷

**图形类型：**安全载荷数值热图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **195–197** 行，函数`redraw_one()` |
| 检索键 | `02_safe_payload.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **57–72** 行 `heatmap()` |
| 输出图片 | [`figures/F003.png`](figures/F003.png) · [`figures/F003.pdf`](figures/F003.pdf) · [`figures/F003.svg`](figures/F003.svg) |
| 绘图变量/来源 | [`plot_data/F003.json`](plot_data/F003.json) |
| 源文件 | [`experiment/results/q1/max_safe_payload_matrix.csv`](experiment/results/q1/max_safe_payload_matrix.csv) |
| 论文图件副本 | [`overleaf/figures/F003.pdf`](overleaf/figures/F003.pdf) |

**取数及计算位置：**max_safe_payload_matrix的A_kg、B_kg、C_kg组成15×3矩阵。

**建议改动的位置：**heatmap色带/数字字号/长宽比/色条；保持色阶语义和kg单位。

**绘图变量结构：**对象字段：`service`、`kg`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F003
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F004"></a>
### F004｜第一问：各服务区最少往返架次数

**图形类型：**架次数棒棒糖图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **198–199** 行，函数`redraw_one()` |
| 检索键 | `03_service_sorties.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F004.png`](figures/F004.png) · [`figures/F004.pdf`](figures/F004.pdf) · [`figures/F004.svg`](figures/F004.svg) |
| 绘图变量/来源 | [`plot_data/F004.json`](plot_data/F004.json) |
| 源文件 | [`experiment/results/q1/service_summary.csv`](experiment/results/q1/service_summary.csv) |
| 论文图件副本 | [`overleaf/figures/F004.pdf`](overleaf/figures/F004.pdf) |

**取数及计算位置：**按service_id展示service_summary.trips；大于1的区域单独着色。

**建议改动的位置：**dotbars竖线宽、标记大小、注释、颜色；保持离散整数刻度。

**绘图变量结构：**列表（15项），单项字段：`service_id`、`distance_m`、`terrain_max_m`、`cruise_altitude_m`、`trips`、`model_mix`、`box_count`、`weight_kg`、`volume_m3`、`energy_kwh`、`operation_time_s`、`aggregate_capacity_lower_bound`、`exact_min_trips`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F004
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F005"></a>
### F005｜第一问：逐架次往返能耗分解

**图形类型：**架次分项堆叠柱图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **208–219** 行，函数`redraw_one()` |
| 检索键 | `04_energy_components.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F005.png`](figures/F005.png) · [`figures/F005.pdf`](figures/F005.pdf) · [`figures/F005.svg`](figures/F005.svg) |
| 绘图变量/来源 | [`plot_data/F005.json`](plot_data/F005.json) |
| 源文件 | [`experiment/results/q1/batches_NET.csv`](experiment/results/q1/batches_NET.csv) |
| 论文图件副本 | [`overleaf/figures/F005.pdf`](overleaf/figures/F005.pdf) |

**取数及计算位置：**Q1直接读batches_NET分项；Q2/Q3按trip_id汇总legs水平/爬升能耗；F047为准备/飞行/交接时间。

**建议改动的位置：**分项颜色、柱宽、图例、架次标签、堆叠顺序；能量kWh与时间min不可混淆。

**同分支影响范围：**F005, F047, F061, F075。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`trip_ids`、`series`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F005
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F006"></a>
### F006｜第一问：每一架次返航电量核验

**图形类型：**返航SOC茎线/散点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **220–224** 行，函数`redraw_one()` |
| 检索键 | `05_return_soc.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F006.png`](figures/F006.png) · [`figures/F006.pdf`](figures/F006.pdf) · [`figures/F006.svg`](figures/F006.svg) |
| 绘图变量/来源 | [`plot_data/F006.json`](plot_data/F006.json) |
| 源文件 | [`experiment/results/q1/batches_NET.csv`](experiment/results/q1/batches_NET.csv) |
| 论文图件副本 | [`overleaf/figures/F006.pdf`](overleaf/figures/F006.pdf) |

**取数及计算位置：**return_soc_fraction×100；从20%基线画至每架次真实返航SOC并标注最小值。

**建议改动的位置：**机型色、标记面积、20%约束虚线与标签；不移动约束线或删最小点。

**同分支影响范围：**F006, F054, F068, F116。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（18项），单项字段：`model_id`、`box_count`、`weight_kg`、`volume_m3`、`outbound_horizontal_kwh`、`inbound_horizontal_kwh`、`outbound_climb_kwh`、`inbound_climb_kwh`、`energy_kwh`、`outbound_flight_s`、`inbound_flight_s`、`flight_time_s`、`preparation_load_s`、`handoff_s`、`airborne_service_s`、`operation_time_s`、`reserve_fraction`、`return_soc_fraction`、`energy_margin_kwh`、`payload_utilization`、`volume_utilization`、`service_id`、`box_ids`、`composition`、`trip_id`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F006
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F007"></a>
### F007｜第一问：安全余量与最少架次数

**图形类型：**安全余量敏感性折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **225–234** 行，函数`redraw_one()` |
| 检索键 | `06_reserve_sorties.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F007.png`](figures/F007.png) · [`figures/F007.pdf`](figures/F007.pdf) · [`figures/F007.svg`](figures/F007.svg) |
| 绘图变量/来源 | [`plot_data/F007.json`](plot_data/F007.json) |
| 源文件 | [`experiment/results/q1/reserve_sensitivity.csv`](experiment/results/q1/reserve_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F007.pdf`](overleaf/figures/F007.pdf) |

**取数及计算位置：**reserve_fraction×100为横轴；纵轴trips或energy_kwh；空值表示全箱交付不可行。

**建议改动的位置：**折线/点/注释/刻度/不可行标记位置；不得把空值补为0。

**同分支影响范围：**F007, F008。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（9项），单项字段：`reserve_fraction`、`feasible`、`trips`、`energy_kwh`、`operation_time_s`、`min_return_soc_fraction`、`model_mix`、`infeasible_services`。

**当前论文：**第6个图引用；`overleaf/main.tex:507`；章节“问题一：单点往返能力与不可拆货箱组批” / “目标权衡、安全余量与能耗假设敏感性”。
```latex
\paperfig[.88]{F007}{提高返航安全余量后的最少往返架次数；不可行档位不记为0}{fig:reserve}
```
**组合关系：**P02-D；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_figures.py --only F007
```
**含义边界：**各档重新优化；仅绘制全箱可交付档，不可行档详见源表，不能视为0

<a id="F008"></a>
### F008｜第一问：提高返航余量后的总能耗

**图形类型：**安全余量敏感性折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **225–234** 行，函数`redraw_one()` |
| 检索键 | `07_reserve_energy.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F008.png`](figures/F008.png) · [`figures/F008.pdf`](figures/F008.pdf) · [`figures/F008.svg`](figures/F008.svg) |
| 绘图变量/来源 | [`plot_data/F008.json`](plot_data/F008.json) |
| 源文件 | [`experiment/results/q1/reserve_sensitivity.csv`](experiment/results/q1/reserve_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F008.pdf`](overleaf/figures/F008.pdf) |

**取数及计算位置：**reserve_fraction×100为横轴；纵轴trips或energy_kwh；空值表示全箱交付不可行。

**建议改动的位置：**折线/点/注释/刻度/不可行标记位置；不得把空值补为0。

**同分支影响范围：**F007, F008。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（9项），单项字段：`reserve_fraction`、`feasible`、`trips`、`energy_kwh`、`operation_time_s`、`min_return_soc_fraction`、`model_mix`、`infeasible_services`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F008
```
**含义边界：**各档重新优化；仅绘制全箱可交付档，不可行档详见源表，不能视为0

<a id="F009"></a>
### F009｜第一问：S008安全载荷对余量要求的响应

**图形类型：**S008三机型载荷敏感性。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **235–239** 行，函数`redraw_one()` |
| 检索键 | `08_limiting_payload_sensitivity.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F009.png`](figures/F009.png) · [`figures/F009.pdf`](figures/F009.pdf) · [`figures/F009.svg`](figures/F009.svg) |
| 绘图变量/来源 | [`plot_data/F009.json`](plot_data/F009.json) |
| 源文件 | [`experiment/results/q1/capacity_sensitivity.csv`](experiment/results/q1/capacity_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F009.pdf`](overleaf/figures/F009.pdf) |

**取数及计算位置：**capacity_sensitivity按S008和机型筛选；reserve_fraction与max_safe_payload_kg。

**建议改动的位置：**MODEL颜色、机型标记、线型、图例和刻度；不重新生成实验档位。

**绘图变量结构：**列表（27项），单项字段：`service_id`、`model_id`、`reserve_fraction`、`max_safe_payload_kg`、`limiting_factor`、`empty_trip_energy_kwh`、`rated_payload_trip_energy_kwh`、`energy_budget_kwh`、`full_payload_reserve_threshold`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F009
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F010"></a>
### F010｜第一问：不同架次数下的最小能耗曲线

**图形类型：**架次数—最小能耗曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **240–244** 行，函数`redraw_one()` |
| 检索键 | `09_sortie_energy_frontier.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F010.png`](figures/F010.png) · [`figures/F010.pdf`](figures/F010.pdf) · [`figures/F010.svg`](figures/F010.svg) |
| 绘图变量/来源 | [`plot_data/F010.json`](plot_data/F010.json) |
| 源文件 | [`experiment/results/q1/flight_energy_frontier.csv`](experiment/results/q1/flight_energy_frontier.csv) |
| 论文图件副本 | [`overleaf/figures/F010.pdf`](overleaf/figures/F010.pdf) |

**取数及计算位置：**flight_energy_frontier.trips、min_energy_kwh及pareto_efficient_N_E；是真实二维非支配标记。

**建议改动的位置：**线宽、普通/非支配点样式和注释；第243行含data坐标注释位置，可移文字但不要改点值。

**绘图变量结构：**列表（63项），单项字段：`trips`、`min_energy_kwh`、`operation_time_at_min_energy_s`、`pareto_efficient_N_E`、`trip_allocation`。

**当前论文：**第5个图引用；`overleaf/main.tex:484`；章节“问题一：单点往返能力与不可拆货箱组批” / “目标权衡、安全余量与能耗假设敏感性”。
```latex
\paperfig[.88]{F010}{固定架次数下的最小运输能耗；18和19架次构成二维非支配权衡}{fig:q1frontier}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F010
```
**含义边界：**包含被支配点的逐架次数最小能耗曲线；只有18和19架次是本数据二维非支配点，非三目标全部帕累托前沿

<a id="F011"></a>
### F011｜数据核查：题定节点海拔与DEM像元差异

**图形类型：**节点高程差棒棒糖图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **206–207** 行，函数`redraw_one()` |
| 检索键 | `10_node_dem_difference.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F011.png`](figures/F011.png) · [`figures/F011.pdf`](figures/F011.pdf) · [`figures/F011.svg`](figures/F011.svg) |
| 绘图变量/来源 | [`plot_data/F011.json`](plot_data/F011.json) |
| 源文件 | [`experiment/results/quality/node_dem_comparison.csv`](experiment/results/quality/node_dem_comparison.csv) |
| 论文图件副本 | [`overleaf/figures/F011.pdf`](overleaf/figures/F011.pdf) |

**取数及计算位置：**node_dem_comparison.difference_m；符号为题定海拔−DEM像元海拔。

**建议改动的位置：**正负颜色、零线、标记和文本偏移；保留差值方向。

**绘图变量结构：**列表（16项），单项字段：`node_id`、`given_ground_m`、`dem_pixel_m`、`difference_m`、`review_gt_threshold`、`action`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F011
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F012"></a>
### F012｜数据核查：全部货箱按服务区分布

**图形类型：**物资组成堆叠柱图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **200–205** 行，函数`redraw_one()` |
| 检索键 | `11_demand_distribution.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F012.png`](figures/F012.png) · [`figures/F012.pdf`](figures/F012.pdf) · [`figures/F012.svg`](figures/F012.svg) |
| 绘图变量/来源 | [`plot_data/F012.json`](plot_data/F012.json) |
| 源文件 | [`experiment/data/cleaned/boxes.csv`](experiment/data/cleaned/boxes.csv)<br>[`experiment/results/q1/service_summary.csv`](experiment/results/q1/service_summary.csv) |
| 论文图件副本 | [`overleaf/figures/F012.pdf`](overleaf/figures/F012.pdf) |

**取数及计算位置：**boxes按service_id、material_type计数；每柱高度为该服务区总箱数。

**建议改动的位置：**柱宽、MATERIAL配色、顶端数字、图例布局、服务区标签旋转；不是质量柱。

**绘图变量结构：**列表（4项），单项字段：`material`、`counts`。

**当前论文：**第1个图引用；`overleaf/main.tex:239`；章节“数据预处理与公共物理模型” / “全量质量审核与标准化清洗”。
```latex
\paperfig[.88]{F012}{各服务区不可拆货箱数量及物资组成；堆叠总高度来自完整逐箱需求汇总}{fig:demand}
```
**组合关系：**P03-B；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_figures.py --only F012
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F013"></a>
### F013｜第一问：O01至S001沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S001.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F013.png`](figures/F013.png) · [`figures/F013.pdf`](figures/F013.pdf) · [`figures/F013.svg`](figures/F013.svg) |
| 绘图变量/来源 | [`plot_data/F013.json`](plot_data/F013.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F013.pdf`](overleaf/figures/F013.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F013
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F014"></a>
### F014｜第一问：S001载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S001.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F014.png`](figures/F014.png) · [`figures/F014.pdf`](figures/F014.pdf) · [`figures/F014.svg`](figures/F014.svg) |
| 绘图变量/来源 | [`plot_data/F014.json`](plot_data/F014.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S001.csv`](experiment/results/closure/energy_curves_S001.csv) |
| 论文图件副本 | [`overleaf/figures/F014.pdf`](overleaf/figures/F014.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F014
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F015"></a>
### F015｜第一问：O01至S002沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S002.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F015.png`](figures/F015.png) · [`figures/F015.pdf`](figures/F015.pdf) · [`figures/F015.svg`](figures/F015.svg) |
| 绘图变量/来源 | [`plot_data/F015.json`](plot_data/F015.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F015.pdf`](overleaf/figures/F015.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F015
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F016"></a>
### F016｜第一问：S002载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S002.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F016.png`](figures/F016.png) · [`figures/F016.pdf`](figures/F016.pdf) · [`figures/F016.svg`](figures/F016.svg) |
| 绘图变量/来源 | [`plot_data/F016.json`](plot_data/F016.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S002.csv`](experiment/results/closure/energy_curves_S002.csv) |
| 论文图件副本 | [`overleaf/figures/F016.pdf`](overleaf/figures/F016.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F016
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F017"></a>
### F017｜第一问：O01至S003沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S003.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F017.png`](figures/F017.png) · [`figures/F017.pdf`](figures/F017.pdf) · [`figures/F017.svg`](figures/F017.svg) |
| 绘图变量/来源 | [`plot_data/F017.json`](plot_data/F017.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F017.pdf`](overleaf/figures/F017.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F017
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F018"></a>
### F018｜第一问：S003载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S003.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F018.png`](figures/F018.png) · [`figures/F018.pdf`](figures/F018.pdf) · [`figures/F018.svg`](figures/F018.svg) |
| 绘图变量/来源 | [`plot_data/F018.json`](plot_data/F018.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S003.csv`](experiment/results/closure/energy_curves_S003.csv) |
| 论文图件副本 | [`overleaf/figures/F018.pdf`](overleaf/figures/F018.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F018
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F019"></a>
### F019｜第一问：O01至S004沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S004.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F019.png`](figures/F019.png) · [`figures/F019.pdf`](figures/F019.pdf) · [`figures/F019.svg`](figures/F019.svg) |
| 绘图变量/来源 | [`plot_data/F019.json`](plot_data/F019.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F019.pdf`](overleaf/figures/F019.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F019
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F020"></a>
### F020｜第一问：S004载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S004.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F020.png`](figures/F020.png) · [`figures/F020.pdf`](figures/F020.pdf) · [`figures/F020.svg`](figures/F020.svg) |
| 绘图变量/来源 | [`plot_data/F020.json`](plot_data/F020.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S004.csv`](experiment/results/closure/energy_curves_S004.csv) |
| 论文图件副本 | [`overleaf/figures/F020.pdf`](overleaf/figures/F020.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F020
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F021"></a>
### F021｜第一问：O01至S005沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S005.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F021.png`](figures/F021.png) · [`figures/F021.pdf`](figures/F021.pdf) · [`figures/F021.svg`](figures/F021.svg) |
| 绘图变量/来源 | [`plot_data/F021.json`](plot_data/F021.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F021.pdf`](overleaf/figures/F021.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F021
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F022"></a>
### F022｜第一问：S005载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S005.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F022.png`](figures/F022.png) · [`figures/F022.pdf`](figures/F022.pdf) · [`figures/F022.svg`](figures/F022.svg) |
| 绘图变量/来源 | [`plot_data/F022.json`](plot_data/F022.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S005.csv`](experiment/results/closure/energy_curves_S005.csv) |
| 论文图件副本 | [`overleaf/figures/F022.pdf`](overleaf/figures/F022.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F022
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F023"></a>
### F023｜第一问：O01至S006沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S006.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F023.png`](figures/F023.png) · [`figures/F023.pdf`](figures/F023.pdf) · [`figures/F023.svg`](figures/F023.svg) |
| 绘图变量/来源 | [`plot_data/F023.json`](plot_data/F023.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F023.pdf`](overleaf/figures/F023.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F023
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F024"></a>
### F024｜第一问：S006载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S006.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F024.png`](figures/F024.png) · [`figures/F024.pdf`](figures/F024.pdf) · [`figures/F024.svg`](figures/F024.svg) |
| 绘图变量/来源 | [`plot_data/F024.json`](plot_data/F024.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S006.csv`](experiment/results/closure/energy_curves_S006.csv) |
| 论文图件副本 | [`overleaf/figures/F024.pdf`](overleaf/figures/F024.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F024
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F025"></a>
### F025｜第一问：O01至S007沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S007.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F025.png`](figures/F025.png) · [`figures/F025.pdf`](figures/F025.pdf) · [`figures/F025.svg`](figures/F025.svg) |
| 绘图变量/来源 | [`plot_data/F025.json`](plot_data/F025.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F025.pdf`](overleaf/figures/F025.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F025
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F026"></a>
### F026｜第一问：S007载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S007.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F026.png`](figures/F026.png) · [`figures/F026.pdf`](figures/F026.pdf) · [`figures/F026.svg`](figures/F026.svg) |
| 绘图变量/来源 | [`plot_data/F026.json`](plot_data/F026.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S007.csv`](experiment/results/closure/energy_curves_S007.csv) |
| 论文图件副本 | [`overleaf/figures/F026.pdf`](overleaf/figures/F026.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F026
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F027"></a>
### F027｜第一问：O01至S008沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S008.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F027.png`](figures/F027.png) · [`figures/F027.pdf`](figures/F027.pdf) · [`figures/F027.svg`](figures/F027.svg) |
| 绘图变量/来源 | [`plot_data/F027.json`](plot_data/F027.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F027.pdf`](overleaf/figures/F027.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**第3个图引用；`overleaf/main.tex:288`；章节“数据预处理与公共物理模型” / “运输机参数与地形净空”。
```latex
\paperfig[.88]{F027}{O01至S008的地形与飞行净空剖面；服务区交接后需重新爬升返航}{fig:profile}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F027
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F028"></a>
### F028｜第一问：瓶颈区域S008地形剖面

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `12_route_terrain_profile.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F028.png`](figures/F028.png) · [`figures/F028.pdf`](figures/F028.pdf) · [`figures/F028.svg`](figures/F028.svg) |
| 绘图变量/来源 | [`plot_data/F028.json`](plot_data/F028.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F028.pdf`](overleaf/figures/F028.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F028
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F029"></a>
### F029｜第一问：S008载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S008.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F029.png`](figures/F029.png) · [`figures/F029.pdf`](figures/F029.pdf) · [`figures/F029.svg`](figures/F029.svg) |
| 绘图变量/来源 | [`plot_data/F029.json`](plot_data/F029.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S008.csv`](experiment/results/closure/energy_curves_S008.csv) |
| 论文图件副本 | [`overleaf/figures/F029.pdf`](overleaf/figures/F029.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F029
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F030"></a>
### F030｜第一问：O01至S009沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S009.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F030.png`](figures/F030.png) · [`figures/F030.pdf`](figures/F030.pdf) · [`figures/F030.svg`](figures/F030.svg) |
| 绘图变量/来源 | [`plot_data/F030.json`](plot_data/F030.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F030.pdf`](overleaf/figures/F030.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F030
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F031"></a>
### F031｜第一问：S009载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S009.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F031.png`](figures/F031.png) · [`figures/F031.pdf`](figures/F031.pdf) · [`figures/F031.svg`](figures/F031.svg) |
| 绘图变量/来源 | [`plot_data/F031.json`](plot_data/F031.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S009.csv`](experiment/results/closure/energy_curves_S009.csv) |
| 论文图件副本 | [`overleaf/figures/F031.pdf`](overleaf/figures/F031.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F031
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F032"></a>
### F032｜第一问：O01至S010沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S010.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F032.png`](figures/F032.png) · [`figures/F032.pdf`](figures/F032.pdf) · [`figures/F032.svg`](figures/F032.svg) |
| 绘图变量/来源 | [`plot_data/F032.json`](plot_data/F032.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F032.pdf`](overleaf/figures/F032.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F032
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F033"></a>
### F033｜第一问：S010载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S010.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F033.png`](figures/F033.png) · [`figures/F033.pdf`](figures/F033.pdf) · [`figures/F033.svg`](figures/F033.svg) |
| 绘图变量/来源 | [`plot_data/F033.json`](plot_data/F033.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S010.csv`](experiment/results/closure/energy_curves_S010.csv) |
| 论文图件副本 | [`overleaf/figures/F033.pdf`](overleaf/figures/F033.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F033
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F034"></a>
### F034｜第一问：O01至S011沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S011.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F034.png`](figures/F034.png) · [`figures/F034.pdf`](figures/F034.pdf) · [`figures/F034.svg`](figures/F034.svg) |
| 绘图变量/来源 | [`plot_data/F034.json`](plot_data/F034.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F034.pdf`](overleaf/figures/F034.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F034
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F035"></a>
### F035｜第一问：S011载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S011.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F035.png`](figures/F035.png) · [`figures/F035.pdf`](figures/F035.pdf) · [`figures/F035.svg`](figures/F035.svg) |
| 绘图变量/来源 | [`plot_data/F035.json`](plot_data/F035.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S011.csv`](experiment/results/closure/energy_curves_S011.csv) |
| 论文图件副本 | [`overleaf/figures/F035.pdf`](overleaf/figures/F035.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F035
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F036"></a>
### F036｜第一问：O01至S012沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S012.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F036.png`](figures/F036.png) · [`figures/F036.pdf`](figures/F036.pdf) · [`figures/F036.svg`](figures/F036.svg) |
| 绘图变量/来源 | [`plot_data/F036.json`](plot_data/F036.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F036.pdf`](overleaf/figures/F036.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F036
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F037"></a>
### F037｜第一问：S012载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S012.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F037.png`](figures/F037.png) · [`figures/F037.pdf`](figures/F037.pdf) · [`figures/F037.svg`](figures/F037.svg) |
| 绘图变量/来源 | [`plot_data/F037.json`](plot_data/F037.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S012.csv`](experiment/results/closure/energy_curves_S012.csv) |
| 论文图件副本 | [`overleaf/figures/F037.pdf`](overleaf/figures/F037.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F037
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F038"></a>
### F038｜第一问：O01至S013沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S013.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F038.png`](figures/F038.png) · [`figures/F038.pdf`](figures/F038.pdf) · [`figures/F038.svg`](figures/F038.svg) |
| 绘图变量/来源 | [`plot_data/F038.json`](plot_data/F038.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F038.pdf`](overleaf/figures/F038.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F038
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F039"></a>
### F039｜第一问：S013载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S013.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F039.png`](figures/F039.png) · [`figures/F039.pdf`](figures/F039.pdf) · [`figures/F039.svg`](figures/F039.svg) |
| 绘图变量/来源 | [`plot_data/F039.json`](plot_data/F039.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S013.csv`](experiment/results/closure/energy_curves_S013.csv) |
| 论文图件副本 | [`overleaf/figures/F039.pdf`](overleaf/figures/F039.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F039
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F040"></a>
### F040｜第一问：O01至S014沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S014.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F040.png`](figures/F040.png) · [`figures/F040.pdf`](figures/F040.pdf) · [`figures/F040.svg`](figures/F040.svg) |
| 绘图变量/来源 | [`plot_data/F040.json`](plot_data/F040.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F040.pdf`](overleaf/figures/F040.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F040
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F041"></a>
### F041｜第一问：S014载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S014.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F041.png`](figures/F041.png) · [`figures/F041.pdf`](figures/F041.pdf) · [`figures/F041.svg`](figures/F041.svg) |
| 绘图变量/来源 | [`plot_data/F041.json`](plot_data/F041.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S014.csv`](experiment/results/closure/energy_curves_S014.csv) |
| 论文图件副本 | [`overleaf/figures/F041.pdf`](overleaf/figures/F041.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F041
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F042"></a>
### F042｜第一问：O01至S015沿线地形与净空

**图形类型：**沿航线DEM阶梯剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **245–251** 行，函数`redraw_one()` |
| 检索键 | `q1/terrain_S015.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F042.png`](figures/F042.png) · [`figures/F042.pdf`](figures/F042.pdf) · [`figures/F042.svg`](figures/F042.svg) |
| 绘图变量/来源 | [`plot_data/F042.json`](plot_data/F042.json) |
| 源文件 | [`experiment/results/q1/route_dem_cells.csv`](experiment/results/q1/route_dem_cells.csv)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv) |
| 论文图件副本 | [`overleaf/figures/F042.pdf`](overleaf/figures/F042.pdf) |

**取数及计算位置：**route_dem_cells按service_id筛选，横轴along_m/1000；叠加route_geometry.cruise_altitude_m。

**建议改动的位置：**阶梯线、fill_between透明度、净空箭头、图例；不要平滑掉像元峰值。

**同分支影响范围：**F013, F015, F017, F019, F021, F023, F025, F027, F028, F030, F032, F034, F036, F038, F040, F042。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`profile`、`route`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F042
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；阶梯保留像元峰值，不平滑地形。

<a id="F043"></a>
### F043｜第一问：S015载荷—能量可行边界

**图形类型：**各机型载荷—能耗占比曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **252–256** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_curve_S015.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F043.png`](figures/F043.png) · [`figures/F043.pdf`](figures/F043.pdf) · [`figures/F043.svg`](figures/F043.svg) |
| 绘图变量/来源 | [`plot_data/F043.json`](plot_data/F043.json) |
| 源文件 | [`experiment/results/closure/energy_curves_S015.csv`](experiment/results/closure/energy_curves_S015.csv) |
| 论文图件副本 | [`overleaf/figures/F043.pdf`](overleaf/figures/F043.pdf) |

**取数及计算位置：**读取对应energy_curves_Sxxx，按model_id分组；payload_kg与energy_fraction_percent。

**建议改动的位置：**三机型颜色、线宽、80%任务能量线和图例；保持其与20%返航余量的关系。

**同分支影响范围：**F014, F016, F018, F020, F022, F024, F026, F029, F031, F033, F035, F037, F039, F041, F043。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（363项），单项字段：`service_id`、`model_id`、`payload_kg`、`energy_fraction_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F043
```
**含义边界：**基于明确能耗假设的确定性曲线，不是额外现场实验

<a id="F044"></a>
### F044｜第一问：A型连续上限与现有整箱可实现载荷

**图形类型：**连续/整箱载荷双端点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **257–260** 行，函数`redraw_one()` |
| 检索键 | `q1/payload_A.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F044.png`](figures/F044.png) · [`figures/F044.pdf`](figures/F044.pdf) · [`figures/F044.svg`](figures/F044.svg) |
| 绘图变量/来源 | [`plot_data/F044.json`](plot_data/F044.json) |
| 源文件 | [`experiment/results/q1/payload_continuous_discrete.csv`](experiment/results/q1/payload_continuous_discrete.csv) |
| 论文图件副本 | [`overleaf/figures/F044.pdf`](overleaf/figures/F044.pdf) |

**取数及计算位置：**按机型筛选payload_continuous_discrete；continuous_safe_payload_kg与available_box_max_payload_kg。

**建议改动的位置：**上下端点形状、连线透明度、额定上限线、图例；两个载荷含义不能对调。

**同分支影响范围：**F044, F045, F046。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（15项），单项字段：`service_id`、`model_id`、`rated_payload_kg`、`continuous_safe_payload_kg`、`available_box_max_payload_kg`、`available_total_weight_kg`、`max_payload_witness_box_ids`、`witness_volume_m3`、`witness_energy_kwh`、`reserve_fraction`、`note`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F044
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F045"></a>
### F045｜第一问：B型连续上限与现有整箱可实现载荷

**图形类型：**连续/整箱载荷双端点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **257–260** 行，函数`redraw_one()` |
| 检索键 | `q1/payload_B.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F045.png`](figures/F045.png) · [`figures/F045.pdf`](figures/F045.pdf) · [`figures/F045.svg`](figures/F045.svg) |
| 绘图变量/来源 | [`plot_data/F045.json`](plot_data/F045.json) |
| 源文件 | [`experiment/results/q1/payload_continuous_discrete.csv`](experiment/results/q1/payload_continuous_discrete.csv) |
| 论文图件副本 | [`overleaf/figures/F045.pdf`](overleaf/figures/F045.pdf) |

**取数及计算位置：**按机型筛选payload_continuous_discrete；continuous_safe_payload_kg与available_box_max_payload_kg。

**建议改动的位置：**上下端点形状、连线透明度、额定上限线、图例；两个载荷含义不能对调。

**同分支影响范围：**F044, F045, F046。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（15项），单项字段：`service_id`、`model_id`、`rated_payload_kg`、`continuous_safe_payload_kg`、`available_box_max_payload_kg`、`available_total_weight_kg`、`max_payload_witness_box_ids`、`witness_volume_m3`、`witness_energy_kwh`、`reserve_fraction`、`note`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F045
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F046"></a>
### F046｜第一问：C型连续上限与现有整箱可实现载荷

**图形类型：**连续/整箱载荷双端点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **257–260** 行，函数`redraw_one()` |
| 检索键 | `q1/payload_C.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F046.png`](figures/F046.png) · [`figures/F046.pdf`](figures/F046.pdf) · [`figures/F046.svg`](figures/F046.svg) |
| 绘图变量/来源 | [`plot_data/F046.json`](plot_data/F046.json) |
| 源文件 | [`experiment/results/q1/payload_continuous_discrete.csv`](experiment/results/q1/payload_continuous_discrete.csv) |
| 论文图件副本 | [`overleaf/figures/F046.pdf`](overleaf/figures/F046.pdf) |

**取数及计算位置：**按机型筛选payload_continuous_discrete；continuous_safe_payload_kg与available_box_max_payload_kg。

**建议改动的位置：**上下端点形状、连线透明度、额定上限线、图例；两个载荷含义不能对调。

**同分支影响范围：**F044, F045, F046。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（15项），单项字段：`service_id`、`model_id`、`rated_payload_kg`、`continuous_safe_payload_kg`、`available_box_max_payload_kg`、`available_total_weight_kg`、`max_payload_witness_box_ids`、`witness_volume_m3`、`witness_energy_kwh`、`reserve_fraction`、`note`。

**当前论文：**第4个图引用；`overleaf/main.tex:410`；章节“问题一：单点往返能力与不可拆货箱组批” / “连续安全载荷及整箱可实现载荷”。
```latex
\paperfig[.90]{F046}{C型连续最大安全载荷与现有整箱可实现载荷的区别}{fig:discretepayload}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F046
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F047"></a>
### F047｜第一问：三种时间口径的组成

**图形类型：**架次分项堆叠柱图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **208–219** 行，函数`redraw_one()` |
| 检索键 | `q1/time_components.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F047.png`](figures/F047.png) · [`figures/F047.pdf`](figures/F047.pdf) · [`figures/F047.svg`](figures/F047.svg) |
| 绘图变量/来源 | [`plot_data/F047.json`](plot_data/F047.json) |
| 源文件 | [`experiment/results/q1/batches_NET.csv`](experiment/results/q1/batches_NET.csv) |
| 论文图件副本 | [`overleaf/figures/F047.pdf`](overleaf/figures/F047.pdf) |

**取数及计算位置：**Q1直接读batches_NET分项；Q2/Q3按trip_id汇总legs水平/爬升能耗；F047为准备/飞行/交接时间。

**建议改动的位置：**分项颜色、柱宽、图例、架次标签、堆叠顺序；能量kWh与时间min不可混淆。

**同分支影响范围：**F005, F047, F061, F075。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`trip_ids`、`series`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F047
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F048"></a>
### F048｜第一问：能耗分项假设扰动后重新优化

**图形类型：**能耗假设对照横向点线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **261–262** 行，函数`redraw_one()` |
| 检索键 | `q1/energy_assumptions.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F048.png`](figures/F048.png) · [`figures/F048.pdf`](figures/F048.pdf) · [`figures/F048.svg`](figures/F048.svg) |
| 绘图变量/来源 | [`plot_data/F048.json`](plot_data/F048.json) |
| 源文件 | [`experiment/results/q1/energy_assumption_sensitivity.csv`](experiment/results/q1/energy_assumption_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F048.pdf`](overleaf/figures/F048.pdf) |

**取数及计算位置：**energy_assumption_sensitivity中每行对应一个已重新优化的水平/爬升倍率情景。

**建议改动的位置：**情景标签、横线/点大小、数值格式；不把它改写成随机重复实验。

**绘图变量结构：**列表（5项），单项字段：`horizontal_multiplier`、`climb_multiplier`、`feasible`、`trips`、`energy_kwh`、`operation_time_s`、`min_return_soc_fraction`、`type`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F048
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F049"></a>
### F049｜Q2：26架次运输航线与节点

**图形类型：**地形叠加运输路线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **188–191** 行，函数`redraw_one()` |
| 检索键 | `q2_01_routes.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F049.png`](figures/F049.png) · [`figures/F049.pdf`](figures/F049.pdf) · [`figures/F049.svg`](figures/F049.svg) |
| 绘图变量/来源 | [`plot_data/F049.json`](plot_data/F049.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F049.pdf`](overleaf/figures/F049.pdf) |

**取数及计算位置：**trips.visit_order按顺序连接O01与服务节点；可按model_id过滤；相同有向机型航段计数。

**建议改动的位置：**plot_map中的底图/航段/箭头/节点/中继点；只改一图时必须加code条件，避免所有地图一起改变。

**同分支影响范围：**F049, F056, F057, F058, F063, F070, F071, F072。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**第7个图引用；`overleaf/main.tex:648`；章节“问题二：异构无人机多点多架次运输调度” / “最终排程、资源和时限结果”。
```latex
\paperfig[.92]{F049}{问题二全部26架次路线；模型对每个有向航段独立计算地形和剩余载荷}{fig:q2route}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F049
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F050"></a>
### F050｜Q2：运输无人机占用时序

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q2_02_drone_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F050.png`](figures/F050.png) · [`figures/F050.pdf`](figures/F050.pdf) · [`figures/F050.svg`](figures/F050.svg) |
| 绘图变量/来源 | [`plot_data/F050.json`](plot_data/F050.json) |
| 源文件 | [`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F050.pdf`](overleaf/figures/F050.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（26项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**第8个图引用；`overleaf/main.tex:649`；章节“问题二：异构无人机多点多架次运输调度” / “最终排程、资源和时限结果”。
```latex
\paperfig[.97]{F050}{问题二8架实体运输无人机的准备至返回占用时序}{fig:q2drone}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F050
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F051"></a>
### F051｜Q2：共享电池任务与充电时序

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q2_03_battery_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F051.png`](figures/F051.png) · [`figures/F051.pdf`](figures/F051.pdf) · [`figures/F051.svg`](figures/F051.svg) |
| 绘图变量/来源 | [`plot_data/F051.json`](plot_data/F051.json) |
| 源文件 | [`experiment/results/q2/battery_cycles.csv`](experiment/results/q2/battery_cycles.csv) |
| 论文图件副本 | [`overleaf/figures/F051.pdf`](overleaf/figures/F051.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（26项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**第9个图引用；`overleaf/main.tex:653`；章节“问题二：异构无人机多点多架次运输调度” / “最终排程、资源和时限结果”。
```latex
\paperfig[.97]{F051}{问题二共享电池的任务占用及充电恢复；下一任务须等待对应电池满电}{fig:q2battery}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F051
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F052"></a>
### F052｜Q2：医疗及首批保障货箱硬时限

**图形类型：**硬截止与交付对比图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **273–276** 行，函数`redraw_one()` |
| 检索键 | `q2_04_hard_deadlines.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F052.png`](figures/F052.png) · [`figures/F052.pdf`](figures/F052.pdf) · [`figures/F052.svg`](figures/F052.svg) |
| 绘图变量/来源 | [`plot_data/F052.json`](plot_data/F052.json) |
| 源文件 | [`experiment/results/q2/box_deliveries.csv`](experiment/results/q2/box_deliveries.csv) |
| 论文图件副本 | [`overleaf/figures/F052.pdf`](overleaf/figures/F052.pdf) |

**取数及计算位置：**只取有hard_deadline_s的货箱，按截止时刻和箱号排序；与delivery_complete_s/60比较。

**建议改动的位置：**截止标记、交付散点、连接线、横轴编号；逐箱排序须和plot_data一致。

**同分支影响范围：**F052, F066。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（31项），单项字段：`box_id`、`trip_id`、`service_id`、`model_id`、`drone_id`、`delivery_complete_s`、`expected_s`、`hard_deadline_s`、`first_deadline_s`、`is_first_batch`、`is_medical`、`priority`、`tardiness_s`、`hard_slack_s`、`weight_kg`、`volume_m3`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F052
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；逐箱排序与完整箱号见本图数据文件。

<a id="F053"></a>
### F053｜Q2：实算备选方案的时间与能耗

**图形类型：**已计算候选时间—能耗散点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **277–278** 行，函数`redraw_one()` |
| 检索键 | `q2_06_tradeoff.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **160–180** 行 `tradeoff()` |
| 输出图片 | [`figures/F053.png`](figures/F053.png) · [`figures/F053.pdf`](figures/F053.pdf) · [`figures/F053.svg`](figures/F053.svg) |
| 绘图变量/来源 | [`plot_data/F053.json`](plot_data/F053.json) |
| 源文件 | [`experiment/results/q2/scenario_comparison.csv`](experiment/results/q2/scenario_comparison.csv) |
| 论文图件副本 | [`overleaf/figures/F053.pdf`](overleaf/figures/F053.pdf) |

**取数及计算位置：**scenario_comparison或closure_existing_candidates；相同坐标合并注释，兼容性/选中标记不同。

**建议改动的位置：**tradeoff中的点样式、注释偏移、图例与边距；不能制造更多候选或称为全局前沿。

**同分支影响范围：**F053, F067, F147。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`x`、`y`、`names`、`valid`、`chosen`。

**当前论文：**第10个图引用；`overleaf/main.tex:676`；章节“问题二：异构无人机多点多架次运输调度” / “同预算对照和多指标权衡”。
```latex
\paperfig[.89]{F053}{问题二实算可行方案的完成时间与能耗权衡}{fig:q2trade}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F053
```
**含义边界：**圆点为本问可行备选；叉号为硬时限不合格对照。同坐标标签合并，下游可分区性须另外检查；不是全局帕累托前沿

<a id="F054"></a>
### F054｜Q2：逐架次返航安全余量

**图形类型：**返航SOC茎线/散点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **220–224** 行，函数`redraw_one()` |
| 检索键 | `q2_07_return_soc.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F054.png`](figures/F054.png) · [`figures/F054.pdf`](figures/F054.pdf) · [`figures/F054.svg`](figures/F054.svg) |
| 绘图变量/来源 | [`plot_data/F054.json`](plot_data/F054.json) |
| 源文件 | [`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F054.pdf`](overleaf/figures/F054.pdf) |

**取数及计算位置：**return_soc_fraction×100；从20%基线画至每架次真实返航SOC并标注最小值。

**建议改动的位置：**机型色、标记面积、20%约束虚线与标签；不移动约束线或删最小点。

**同分支影响范围：**F006, F054, F068, F116。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（26项），单项字段：`trip_id`、`drone_id`、`model_id`、`battery_id`、`start_s`、`takeoff_s`、`visit_order`、`route`、`return_s`、`energy_kwh`、`return_soc_fraction`、`initial_soc_fraction`、`weight_kg`、`volume_m3`、`box_count`、`box_ids`、`stop_count`、`flight_time_s`、`operation_time_s`、`preparation_load_s`、`handoff_s`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F054
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F055"></a>
### F055｜Q2：全部货箱累计交付进度

**图形类型：**累计交付阶梯图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **279–280** 行，函数`redraw_one()` |
| 检索键 | `q2_08_delivery_progress.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F055.png`](figures/F055.png) · [`figures/F055.pdf`](figures/F055.pdf) · [`figures/F055.svg`](figures/F055.svg) |
| 绘图变量/来源 | [`plot_data/F055.json`](plot_data/F055.json) |
| 源文件 | [`experiment/results/q2/box_deliveries.csv`](experiment/results/q2/box_deliveries.csv) |
| 论文图件副本 | [`overleaf/figures/F055.pdf`](overleaf/figures/F055.pdf) |

**取数及计算位置：**80箱delivery_complete_s排序，where=post累计计数。

**建议改动的位置：**阶梯线、填充透明度、80箱注释和横轴；不是期望需求曲线。

**同分支影响范围：**F055, F069。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（80项），单项字段：`box_id`、`trip_id`、`service_id`、`model_id`、`drone_id`、`delivery_complete_s`、`expected_s`、`hard_deadline_s`、`first_deadline_s`、`is_first_batch`、`is_medical`、`priority`、`tardiness_s`、`hard_slack_s`、`weight_kg`、`volume_m3`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F055
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F056"></a>
### F056｜Q2：A型无人机运输路线

**图形类型：**地形叠加运输路线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **188–191** 行，函数`redraw_one()` |
| 检索键 | `q2/routes_model_A.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F056.png`](figures/F056.png) · [`figures/F056.pdf`](figures/F056.pdf) · [`figures/F056.svg`](figures/F056.svg) |
| 绘图变量/来源 | [`plot_data/F056.json`](plot_data/F056.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F056.pdf`](overleaf/figures/F056.pdf) |

**取数及计算位置：**trips.visit_order按顺序连接O01与服务节点；可按model_id过滤；相同有向机型航段计数。

**建议改动的位置：**plot_map中的底图/航段/箭头/节点/中继点；只改一图时必须加code条件，避免所有地图一起改变。

**同分支影响范围：**F049, F056, F057, F058, F063, F070, F071, F072。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F056
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F057"></a>
### F057｜Q2：B型无人机运输路线

**图形类型：**地形叠加运输路线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **188–191** 行，函数`redraw_one()` |
| 检索键 | `q2/routes_model_B.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F057.png`](figures/F057.png) · [`figures/F057.pdf`](figures/F057.pdf) · [`figures/F057.svg`](figures/F057.svg) |
| 绘图变量/来源 | [`plot_data/F057.json`](plot_data/F057.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F057.pdf`](overleaf/figures/F057.pdf) |

**取数及计算位置：**trips.visit_order按顺序连接O01与服务节点；可按model_id过滤；相同有向机型航段计数。

**建议改动的位置：**plot_map中的底图/航段/箭头/节点/中继点；只改一图时必须加code条件，避免所有地图一起改变。

**同分支影响范围：**F049, F056, F057, F058, F063, F070, F071, F072。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F057
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F058"></a>
### F058｜Q2：C型无人机运输路线

**图形类型：**地形叠加运输路线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **188–191** 行，函数`redraw_one()` |
| 检索键 | `q2/routes_model_C.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F058.png`](figures/F058.png) · [`figures/F058.pdf`](figures/F058.pdf) · [`figures/F058.svg`](figures/F058.svg) |
| 绘图变量/来源 | [`plot_data/F058.json`](plot_data/F058.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F058.pdf`](overleaf/figures/F058.pdf) |

**取数及计算位置：**trips.visit_order按顺序连接O01与服务节点；可按model_id过滤；相同有向机型航段计数。

**建议改动的位置：**plot_map中的底图/航段/箭头/节点/中继点；只改一图时必须加code条件，避免所有地图一起改变。

**同分支影响范围：**F049, F056, F057, F058, F063, F070, F071, F072。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F058
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F059"></a>
### F059｜Q2：各服务区最紧硬时限裕度

**图形类型：**逐服务区最紧硬时限裕度。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **281–282** 行，函数`redraw_one()` |
| 检索键 | `q2/box_slack.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F059.png`](figures/F059.png) · [`figures/F059.pdf`](figures/F059.pdf) · [`figures/F059.svg`](figures/F059.svg) |
| 绘图变量/来源 | [`plot_data/F059.json`](plot_data/F059.json) |
| 源文件 | [`experiment/results/q2/box_deliveries.csv`](experiment/results/q2/box_deliveries.csv) |
| 论文图件副本 | [`overleaf/figures/F059.pdf`](overleaf/figures/F059.pdf) |

**取数及计算位置：**每个service_id上取min(hard_deadline_s−delivery_complete_s)。

**建议改动的位置：**dotbars点/线/最小值强调；保留秒单位与最小值聚合。

**同分支影响范围：**F059, F073。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`services`、`minimum_hard_slack_s`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F059
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F060"></a>
### F060｜Q2：载质量与装载体积利用率

**图形类型：**架次质量/体积利用率分组柱。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **283–284** 行，函数`redraw_one()` |
| 检索键 | `q2/load_usage.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **49–55** 行 `grouped()` |
| 输出图片 | [`figures/F060.png`](figures/F060.png) · [`figures/F060.pdf`](figures/F060.pdf) · [`figures/F060.svg`](figures/F060.svg) |
| 绘图变量/来源 | [`plot_data/F060.json`](plot_data/F060.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F060.pdf`](overleaf/figures/F060.pdf) |

**取数及计算位置：**weight_kg/max_payload_kg与volume_m3/机型容积，均乘100。

**建议改动的位置：**grouped柱宽、配色、百分比刻度、图例；质量和容积的分母不能更换。

**同分支影响范围：**F060, F074。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`trip_ids`、`weight_percent`、`volume_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F060
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F061"></a>
### F061｜Q2：逐航段汇总的运输能耗分项

**图形类型：**架次分项堆叠柱图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **208–219** 行，函数`redraw_one()` |
| 检索键 | `q2/energy_components.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F061.png`](figures/F061.png) · [`figures/F061.pdf`](figures/F061.pdf) · [`figures/F061.svg`](figures/F061.svg) |
| 绘图变量/来源 | [`plot_data/F061.json`](plot_data/F061.json) |
| 源文件 | [`experiment/results/q2/legs.csv`](experiment/results/q2/legs.csv)<br>[`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F061.pdf`](overleaf/figures/F061.pdf) |

**取数及计算位置：**Q1直接读batches_NET分项；Q2/Q3按trip_id汇总legs水平/爬升能耗；F047为准备/飞行/交接时间。

**建议改动的位置：**分项颜色、柱宽、图例、架次标签、堆叠顺序；能量kWh与时间min不可混淆。

**同分支影响范围：**F005, F047, F061, F075。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`trip_ids`、`series`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F061
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F062"></a>
### F062｜Q2：分机型累计作业与纯飞行时间

**图形类型：**机型累计作业/飞行时间分组柱。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **285–286** 行，函数`redraw_one()` |
| 检索键 | `q2/model_workload.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **49–55** 行 `grouped()` |
| 输出图片 | [`figures/F062.png`](figures/F062.png) · [`figures/F062.pdf`](figures/F062.pdf) · [`figures/F062.svg`](figures/F062.svg) |
| 绘图变量/来源 | [`plot_data/F062.json`](plot_data/F062.json) |
| 源文件 | [`experiment/results/q2/trips.csv`](experiment/results/q2/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F062.pdf`](overleaf/figures/F062.pdf) |

**取数及计算位置：**按model_id聚合operation_time_s与flight_time_s，再除60。

**建议改动的位置：**grouped布局、图例、配色；累计工时不等于全体任务完工时间。

**同分支影响范围：**F062, F076。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`model_ids`、`operation_min`、`flight_min`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F062
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F063"></a>
### F063｜Q3：25架次运输航线与节点

**图形类型：**地形叠加运输路线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **188–191** 行，函数`redraw_one()` |
| 检索键 | `q3/q3_01_routes.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F063.png`](figures/F063.png) · [`figures/F063.pdf`](figures/F063.pdf) · [`figures/F063.svg`](figures/F063.svg) |
| 绘图变量/来源 | [`plot_data/F063.json`](plot_data/F063.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F063.pdf`](overleaf/figures/F063.pdf) |

**取数及计算位置：**trips.visit_order按顺序连接O01与服务节点；可按model_id过滤；相同有向机型航段计数。

**建议改动的位置：**plot_map中的底图/航段/箭头/节点/中继点；只改一图时必须加code条件，避免所有地图一起改变。

**同分支影响范围：**F049, F056, F057, F058, F063, F070, F071, F072。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**第12个图引用；`overleaf/main.tex:829`；章节“问题三：连续通信约束下运输与中继联合调度” / “最终联合调度与连续保障结果”。
```latex
\paperfig[.92]{F063}{最终问题三的25次运输航线；完整中继坐标与服务时段见表\ref{tab:relaysite}、表\ref{tab:relaytime}}{fig:q3route}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F063
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F064"></a>
### F064｜Q3：运输无人机占用时序

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q3/q3_02_drone_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F064.png`](figures/F064.png) · [`figures/F064.pdf`](figures/F064.pdf) · [`figures/F064.svg`](figures/F064.svg) |
| 绘图变量/来源 | [`plot_data/F064.json`](plot_data/F064.json) |
| 源文件 | [`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F064.pdf`](overleaf/figures/F064.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（25项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**第13个图引用；`overleaf/main.tex:830`；章节“问题三：连续通信约束下运输与中继联合调度” / “最终联合调度与连续保障结果”。
```latex
\paperfig[.97]{F064}{最终问题三运输机身的占用时序；不包含中继返航尾段}{fig:q3drone}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F064
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F065"></a>
### F065｜Q3：共享电池任务与充电时序

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q3/q3_03_battery_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F065.png`](figures/F065.png) · [`figures/F065.pdf`](figures/F065.pdf) · [`figures/F065.svg`](figures/F065.svg) |
| 绘图变量/来源 | [`plot_data/F065.json`](plot_data/F065.json) |
| 源文件 | [`experiment/results/q3/battery_cycles.csv`](experiment/results/q3/battery_cycles.csv) |
| 论文图件副本 | [`overleaf/figures/F065.pdf`](overleaf/figures/F065.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（25项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F065
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F066"></a>
### F066｜Q3：医疗及首批保障货箱硬时限

**图形类型：**硬截止与交付对比图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **273–276** 行，函数`redraw_one()` |
| 检索键 | `q3/q3_04_hard_deadlines.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F066.png`](figures/F066.png) · [`figures/F066.pdf`](figures/F066.pdf) · [`figures/F066.svg`](figures/F066.svg) |
| 绘图变量/来源 | [`plot_data/F066.json`](plot_data/F066.json) |
| 源文件 | [`experiment/results/q3/box_deliveries.csv`](experiment/results/q3/box_deliveries.csv) |
| 论文图件副本 | [`overleaf/figures/F066.pdf`](overleaf/figures/F066.pdf) |

**取数及计算位置：**只取有hard_deadline_s的货箱，按截止时刻和箱号排序；与delivery_complete_s/60比较。

**建议改动的位置：**截止标记、交付散点、连接线、横轴编号；逐箱排序须和plot_data一致。

**同分支影响范围：**F052, F066。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（31项），单项字段：`box_id`、`trip_id`、`service_id`、`model_id`、`drone_id`、`delivery_complete_s`、`expected_s`、`hard_deadline_s`、`first_deadline_s`、`is_first_batch`、`is_medical`、`priority`、`tardiness_s`、`hard_slack_s`、`weight_kg`、`volume_m3`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F066
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；逐箱排序与完整箱号见本图数据文件。

<a id="F067"></a>
### F067｜Q3：实算备选方案的时间与能耗

**图形类型：**已计算候选时间—能耗散点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **277–278** 行，函数`redraw_one()` |
| 检索键 | `q3/q3_06_tradeoff.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **160–180** 行 `tradeoff()` |
| 输出图片 | [`figures/F067.png`](figures/F067.png) · [`figures/F067.pdf`](figures/F067.pdf) · [`figures/F067.svg`](figures/F067.svg) |
| 绘图变量/来源 | [`plot_data/F067.json`](plot_data/F067.json) |
| 源文件 | [`experiment/results/q3/scenario_comparison.csv`](experiment/results/q3/scenario_comparison.csv) |
| 论文图件副本 | [`overleaf/figures/F067.pdf`](overleaf/figures/F067.pdf) |

**取数及计算位置：**scenario_comparison或closure_existing_candidates；相同坐标合并注释，兼容性/选中标记不同。

**建议改动的位置：**tradeoff中的点样式、注释偏移、图例与边距；不能制造更多候选或称为全局前沿。

**同分支影响范围：**F053, F067, F147。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`x`、`y`、`names`、`valid`、`chosen`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F067
```
**含义边界：**圆点为本问可行备选；叉号为硬时限不合格对照。同坐标标签合并，下游可分区性须另外检查；不是全局帕累托前沿

<a id="F068"></a>
### F068｜Q3：逐架次返航安全余量

**图形类型：**返航SOC茎线/散点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **220–224** 行，函数`redraw_one()` |
| 检索键 | `q3/q3_07_return_soc.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F068.png`](figures/F068.png) · [`figures/F068.pdf`](figures/F068.pdf) · [`figures/F068.svg`](figures/F068.svg) |
| 绘图变量/来源 | [`plot_data/F068.json`](plot_data/F068.json) |
| 源文件 | [`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F068.pdf`](overleaf/figures/F068.pdf) |

**取数及计算位置：**return_soc_fraction×100；从20%基线画至每架次真实返航SOC并标注最小值。

**建议改动的位置：**机型色、标记面积、20%约束虚线与标签；不移动约束线或删最小点。

**同分支影响范围：**F006, F054, F068, F116。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（25项），单项字段：`trip_id`、`drone_id`、`model_id`、`battery_id`、`start_s`、`takeoff_s`、`visit_order`、`route`、`return_s`、`energy_kwh`、`return_soc_fraction`、`initial_soc_fraction`、`weight_kg`、`volume_m3`、`box_count`、`box_ids`、`stop_count`、`flight_time_s`、`operation_time_s`、`preparation_load_s`、`handoff_s`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F068
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F069"></a>
### F069｜Q3：全部货箱累计交付进度

**图形类型：**累计交付阶梯图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **279–280** 行，函数`redraw_one()` |
| 检索键 | `q3/q3_08_delivery_progress.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F069.png`](figures/F069.png) · [`figures/F069.pdf`](figures/F069.pdf) · [`figures/F069.svg`](figures/F069.svg) |
| 绘图变量/来源 | [`plot_data/F069.json`](plot_data/F069.json) |
| 源文件 | [`experiment/results/q3/box_deliveries.csv`](experiment/results/q3/box_deliveries.csv) |
| 论文图件副本 | [`overleaf/figures/F069.pdf`](overleaf/figures/F069.pdf) |

**取数及计算位置：**80箱delivery_complete_s排序，where=post累计计数。

**建议改动的位置：**阶梯线、填充透明度、80箱注释和横轴；不是期望需求曲线。

**同分支影响范围：**F055, F069。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（80项），单项字段：`box_id`、`trip_id`、`service_id`、`model_id`、`drone_id`、`delivery_complete_s`、`expected_s`、`hard_deadline_s`、`first_deadline_s`、`is_first_batch`、`is_medical`、`priority`、`tardiness_s`、`hard_slack_s`、`weight_kg`、`volume_m3`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F069
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F070"></a>
### F070｜Q3：A型无人机运输路线

**图形类型：**地形叠加运输路线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **188–191** 行，函数`redraw_one()` |
| 检索键 | `q3/routes_model_A.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F070.png`](figures/F070.png) · [`figures/F070.pdf`](figures/F070.pdf) · [`figures/F070.svg`](figures/F070.svg) |
| 绘图变量/来源 | [`plot_data/F070.json`](plot_data/F070.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F070.pdf`](overleaf/figures/F070.pdf) |

**取数及计算位置：**trips.visit_order按顺序连接O01与服务节点；可按model_id过滤；相同有向机型航段计数。

**建议改动的位置：**plot_map中的底图/航段/箭头/节点/中继点；只改一图时必须加code条件，避免所有地图一起改变。

**同分支影响范围：**F049, F056, F057, F058, F063, F070, F071, F072。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F070
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F071"></a>
### F071｜Q3：B型无人机运输路线

**图形类型：**地形叠加运输路线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **188–191** 行，函数`redraw_one()` |
| 检索键 | `q3/routes_model_B.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F071.png`](figures/F071.png) · [`figures/F071.pdf`](figures/F071.pdf) · [`figures/F071.svg`](figures/F071.svg) |
| 绘图变量/来源 | [`plot_data/F071.json`](plot_data/F071.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F071.pdf`](overleaf/figures/F071.pdf) |

**取数及计算位置：**trips.visit_order按顺序连接O01与服务节点；可按model_id过滤；相同有向机型航段计数。

**建议改动的位置：**plot_map中的底图/航段/箭头/节点/中继点；只改一图时必须加code条件，避免所有地图一起改变。

**同分支影响范围：**F049, F056, F057, F058, F063, F070, F071, F072。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F071
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F072"></a>
### F072｜Q3：C型无人机运输路线

**图形类型：**地形叠加运输路线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **188–191** 行，函数`redraw_one()` |
| 检索键 | `q3/routes_model_C.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F072.png`](figures/F072.png) · [`figures/F072.pdf`](figures/F072.pdf) · [`figures/F072.svg`](figures/F072.svg) |
| 绘图变量/来源 | [`plot_data/F072.json`](plot_data/F072.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F072.pdf`](overleaf/figures/F072.pdf) |

**取数及计算位置：**trips.visit_order按顺序连接O01与服务节点；可按model_id过滤；相同有向机型航段计数。

**建议改动的位置：**plot_map中的底图/航段/箭头/节点/中继点；只改一图时必须加code条件，避免所有地图一起改变。

**同分支影响范围：**F049, F056, F057, F058, F063, F070, F071, F072。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F072
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F073"></a>
### F073｜Q3：各服务区最紧硬时限裕度

**图形类型：**逐服务区最紧硬时限裕度。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **281–282** 行，函数`redraw_one()` |
| 检索键 | `q3/box_slack.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F073.png`](figures/F073.png) · [`figures/F073.pdf`](figures/F073.pdf) · [`figures/F073.svg`](figures/F073.svg) |
| 绘图变量/来源 | [`plot_data/F073.json`](plot_data/F073.json) |
| 源文件 | [`experiment/results/q3/box_deliveries.csv`](experiment/results/q3/box_deliveries.csv) |
| 论文图件副本 | [`overleaf/figures/F073.pdf`](overleaf/figures/F073.pdf) |

**取数及计算位置：**每个service_id上取min(hard_deadline_s−delivery_complete_s)。

**建议改动的位置：**dotbars点/线/最小值强调；保留秒单位与最小值聚合。

**同分支影响范围：**F059, F073。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`services`、`minimum_hard_slack_s`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F073
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F074"></a>
### F074｜Q3：载质量与装载体积利用率

**图形类型：**架次质量/体积利用率分组柱。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **283–284** 行，函数`redraw_one()` |
| 检索键 | `q3/load_usage.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **49–55** 行 `grouped()` |
| 输出图片 | [`figures/F074.png`](figures/F074.png) · [`figures/F074.pdf`](figures/F074.pdf) · [`figures/F074.svg`](figures/F074.svg) |
| 绘图变量/来源 | [`plot_data/F074.json`](plot_data/F074.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F074.pdf`](overleaf/figures/F074.pdf) |

**取数及计算位置：**weight_kg/max_payload_kg与volume_m3/机型容积，均乘100。

**建议改动的位置：**grouped柱宽、配色、百分比刻度、图例；质量和容积的分母不能更换。

**同分支影响范围：**F060, F074。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`trip_ids`、`weight_percent`、`volume_percent`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F074
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F075"></a>
### F075｜Q3：逐航段汇总的运输能耗分项

**图形类型：**架次分项堆叠柱图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **208–219** 行，函数`redraw_one()` |
| 检索键 | `q3/energy_components.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F075.png`](figures/F075.png) · [`figures/F075.pdf`](figures/F075.pdf) · [`figures/F075.svg`](figures/F075.svg) |
| 绘图变量/来源 | [`plot_data/F075.json`](plot_data/F075.json) |
| 源文件 | [`experiment/results/q3/legs.csv`](experiment/results/q3/legs.csv)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F075.pdf`](overleaf/figures/F075.pdf) |

**取数及计算位置：**Q1直接读batches_NET分项；Q2/Q3按trip_id汇总legs水平/爬升能耗；F047为准备/飞行/交接时间。

**建议改动的位置：**分项颜色、柱宽、图例、架次标签、堆叠顺序；能量kWh与时间min不可混淆。

**同分支影响范围：**F005, F047, F061, F075。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`trip_ids`、`series`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F075
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F076"></a>
### F076｜Q3：分机型累计作业与纯飞行时间

**图形类型：**机型累计作业/飞行时间分组柱。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **285–286** 行，函数`redraw_one()` |
| 检索键 | `q3/model_workload.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **49–55** 行 `grouped()` |
| 输出图片 | [`figures/F076.png`](figures/F076.png) · [`figures/F076.pdf`](figures/F076.pdf) · [`figures/F076.svg`](figures/F076.svg) |
| 绘图变量/来源 | [`plot_data/F076.json`](plot_data/F076.json) |
| 源文件 | [`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F076.pdf`](overleaf/figures/F076.pdf) |

**取数及计算位置：**按model_id聚合operation_time_s与flight_time_s，再除60。

**建议改动的位置：**grouped布局、图例、配色；累计工时不等于全体任务完工时间。

**同分支影响范围：**F062, F076。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`model_ids`、`operation_min`、`flight_min`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F076
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F077"></a>
### F077｜第二问：固定搜索预算下的收敛轨迹

**图形类型：**已记录的搜索轮次曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **287–291** 行，函数`redraw_one()` |
| 检索键 | `q2_05_convergence.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F077.png`](figures/F077.png) · [`figures/F077.pdf`](figures/F077.pdf) · [`figures/F077.svg`](figures/F077.svg) |
| 绘图变量/来源 | [`plot_data/F077.json`](plot_data/F077.json) |
| 源文件 | [`experiment/results/q2/direct_only_search_rounds.csv`](experiment/results/q2/direct_only_search_rounds.csv)<br>[`experiment/results/q2/multipoint_search_rounds.csv`](experiment/results/q2/multipoint_search_rounds.csv) |
| 论文图件副本 | [`overleaf/figures/F077.pdf`](overleaf/figures/F077.pdf) |

**取数及计算位置：**multipoint/direct_only日志中仅sequential_refinement行；makespan_s/60。

**建议改动的位置：**标记、线宽、轮次刻度；记录的是轮次，不是每次候选移动或独立重复试验。

**绘图变量结构：**对象字段：`multipoint`、`direct_only`。

**当前论文：**第25个图引用；`overleaf/main.tex:1480`；章节“补充诊断图与完整图件索引”。
```latex
\paperfig[.88]{F077}{问题二搜索过程中保存的目标值轨迹；停止改进不是全局最优性证明}{fig:suppsearch}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F077
```
**含义边界：**多次轮次为同一次顺序改进，不能当作独立重复试验

<a id="F078"></a>
### F078｜第三问：中继无人机任务及周转

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_body_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F078.png`](figures/F078.png) · [`figures/F078.pdf`](figures/F078.pdf) · [`figures/F078.svg`](figures/F078.svg) |
| 绘图变量/来源 | [`plot_data/F078.json`](plot_data/F078.json) |
| 源文件 | [`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv) |
| 论文图件副本 | [`overleaf/figures/F078.pdf`](overleaf/figures/F078.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**第14个图引用；`overleaf/main.tex:862`；章节“问题三：连续通信约束下运输与中继联合调度” / “最终联合调度与连续保障结果”。
```latex
\paperfig[.96]{F078}{两架中继无人机的完整任务与300秒周转占用；服务结束不等于已返回}{fig:relaybody}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F078
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F079"></a>
### F079｜第三问：中继能源组件及两阶段充电

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_energy_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F079.png`](figures/F079.png) · [`figures/F079.pdf`](figures/F079.pdf) · [`figures/F079.svg`](figures/F079.svg) |
| 绘图变量/来源 | [`plot_data/F079.json`](plot_data/F079.json) |
| 源文件 | [`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv) |
| 论文图件副本 | [`overleaf/figures/F079.pdf`](overleaf/figures/F079.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**第26个图引用；`overleaf/main.tex:1481`；章节“补充诊断图与完整图件索引”。
```latex
\paperfig[.97]{F079}{问题三中继能源组件的任务、充电与可再次投入时序}{fig:suppenergy}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F079
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F080"></a>
### F080｜第三问：Q3-R-001完整飞行及服务剖面

**图形类型：**中继飞行高度/服务时段剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **292–294** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_profile_Q3-R-001.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F080.png`](figures/F080.png) · [`figures/F080.pdf`](figures/F080.pdf) · [`figures/F080.svg`](figures/F080.svg) |
| 绘图变量/来源 | [`plot_data/F080.json`](plot_data/F080.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv) |
| 论文图件副本 | [`overleaf/figures/F080.pdf`](overleaf/figures/F080.pdf) |

**取数及计算位置：**由relay_sorties、机型速度与准备时间展开爬升/巡航/下降及有效服务窗。

**建议改动的位置：**飞行折线、服务区间阴影、图例和时间轴；不是沿途DEM剖面。

**同分支影响范围：**F080, F081, F082, F083。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`times_min`、`altitude_m`、`relay`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F080
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F081"></a>
### F081｜第三问：Q3-R-002完整飞行及服务剖面

**图形类型：**中继飞行高度/服务时段剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **292–294** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_profile_Q3-R-002.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F081.png`](figures/F081.png) · [`figures/F081.pdf`](figures/F081.pdf) · [`figures/F081.svg`](figures/F081.svg) |
| 绘图变量/来源 | [`plot_data/F081.json`](plot_data/F081.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv) |
| 论文图件副本 | [`overleaf/figures/F081.pdf`](overleaf/figures/F081.pdf) |

**取数及计算位置：**由relay_sorties、机型速度与准备时间展开爬升/巡航/下降及有效服务窗。

**建议改动的位置：**飞行折线、服务区间阴影、图例和时间轴；不是沿途DEM剖面。

**同分支影响范围：**F080, F081, F082, F083。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`times_min`、`altitude_m`、`relay`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F081
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F082"></a>
### F082｜第三问：Q3-R-003完整飞行及服务剖面

**图形类型：**中继飞行高度/服务时段剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **292–294** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_profile_Q3-R-003.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F082.png`](figures/F082.png) · [`figures/F082.pdf`](figures/F082.pdf) · [`figures/F082.svg`](figures/F082.svg) |
| 绘图变量/来源 | [`plot_data/F082.json`](plot_data/F082.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv) |
| 论文图件副本 | [`overleaf/figures/F082.pdf`](overleaf/figures/F082.pdf) |

**取数及计算位置：**由relay_sorties、机型速度与准备时间展开爬升/巡航/下降及有效服务窗。

**建议改动的位置：**飞行折线、服务区间阴影、图例和时间轴；不是沿途DEM剖面。

**同分支影响范围：**F080, F081, F082, F083。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`times_min`、`altitude_m`、`relay`。

**当前论文：**第27个图引用；`overleaf/main.tex:1482`；章节“补充诊断图与完整图件索引”。
```latex
\paperfig[.90]{F082}{第三次中继任务的往返飞行高度及有效通信服务时段}{fig:supprelay}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F082
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F083"></a>
### F083｜第三问：Q3-R-004完整飞行及服务剖面

**图形类型：**中继飞行高度/服务时段剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **292–294** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_profile_Q3-R-004.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F083.png`](figures/F083.png) · [`figures/F083.pdf`](figures/F083.pdf) · [`figures/F083.svg`](figures/F083.svg) |
| 绘图变量/来源 | [`plot_data/F083.json`](plot_data/F083.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv) |
| 论文图件副本 | [`overleaf/figures/F083.pdf`](overleaf/figures/F083.pdf) |

**取数及计算位置：**由relay_sorties、机型速度与准备时间展开爬升/巡航/下降及有效服务窗。

**建议改动的位置：**飞行折线、服务区间阴影、图例和时间轴；不是沿途DEM剖面。

**同分支影响范围：**F080, F081, F082, F083。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`times_min`、`altitude_m`、`relay`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F083
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F084"></a>
### F084｜第三问：Q3-T-001逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-001.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F084.png`](figures/F084.png) · [`figures/F084.pdf`](figures/F084.pdf) · [`figures/F084.svg`](figures/F084.svg) |
| 绘图变量/来源 | [`plot_data/F084.json`](plot_data/F084.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F084.pdf`](overleaf/figures/F084.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F084
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F085"></a>
### F085｜第三问：Q3-T-002逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-002.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F085.png`](figures/F085.png) · [`figures/F085.pdf`](figures/F085.pdf) · [`figures/F085.svg`](figures/F085.svg) |
| 绘图变量/来源 | [`plot_data/F085.json`](plot_data/F085.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F085.pdf`](overleaf/figures/F085.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F085
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F086"></a>
### F086｜第三问：Q3-T-003逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-003.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F086.png`](figures/F086.png) · [`figures/F086.pdf`](figures/F086.pdf) · [`figures/F086.svg`](figures/F086.svg) |
| 绘图变量/来源 | [`plot_data/F086.json`](plot_data/F086.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F086.pdf`](overleaf/figures/F086.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F086
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F087"></a>
### F087｜第三问：Q3-T-004逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-004.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F087.png`](figures/F087.png) · [`figures/F087.pdf`](figures/F087.pdf) · [`figures/F087.svg`](figures/F087.svg) |
| 绘图变量/来源 | [`plot_data/F087.json`](plot_data/F087.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F087.pdf`](overleaf/figures/F087.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F087
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F088"></a>
### F088｜第三问：Q3-T-005逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-005.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F088.png`](figures/F088.png) · [`figures/F088.pdf`](figures/F088.pdf) · [`figures/F088.svg`](figures/F088.svg) |
| 绘图变量/来源 | [`plot_data/F088.json`](plot_data/F088.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F088.pdf`](overleaf/figures/F088.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F088
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F089"></a>
### F089｜第三问：Q3-T-006逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-006.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F089.png`](figures/F089.png) · [`figures/F089.pdf`](figures/F089.pdf) · [`figures/F089.svg`](figures/F089.svg) |
| 绘图变量/来源 | [`plot_data/F089.json`](plot_data/F089.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F089.pdf`](overleaf/figures/F089.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F089
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F090"></a>
### F090｜第三问：Q3-T-007逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-007.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F090.png`](figures/F090.png) · [`figures/F090.pdf`](figures/F090.pdf) · [`figures/F090.svg`](figures/F090.svg) |
| 绘图变量/来源 | [`plot_data/F090.json`](plot_data/F090.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F090.pdf`](overleaf/figures/F090.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F090
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F091"></a>
### F091｜第三问：Q3-T-008逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-008.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F091.png`](figures/F091.png) · [`figures/F091.pdf`](figures/F091.pdf) · [`figures/F091.svg`](figures/F091.svg) |
| 绘图变量/来源 | [`plot_data/F091.json`](plot_data/F091.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F091.pdf`](overleaf/figures/F091.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F091
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F092"></a>
### F092｜第三问：Q3-T-009逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-009.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F092.png`](figures/F092.png) · [`figures/F092.pdf`](figures/F092.pdf) · [`figures/F092.svg`](figures/F092.svg) |
| 绘图变量/来源 | [`plot_data/F092.json`](plot_data/F092.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F092.pdf`](overleaf/figures/F092.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F092
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F093"></a>
### F093｜第三问：Q3-T-010逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-010.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F093.png`](figures/F093.png) · [`figures/F093.pdf`](figures/F093.pdf) · [`figures/F093.svg`](figures/F093.svg) |
| 绘图变量/来源 | [`plot_data/F093.json`](plot_data/F093.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F093.pdf`](overleaf/figures/F093.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F093
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F094"></a>
### F094｜第三问：Q3-T-011逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-011.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F094.png`](figures/F094.png) · [`figures/F094.pdf`](figures/F094.pdf) · [`figures/F094.svg`](figures/F094.svg) |
| 绘图变量/来源 | [`plot_data/F094.json`](plot_data/F094.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F094.pdf`](overleaf/figures/F094.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F094
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F095"></a>
### F095｜第三问：Q3-T-012逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-012.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F095.png`](figures/F095.png) · [`figures/F095.pdf`](figures/F095.pdf) · [`figures/F095.svg`](figures/F095.svg) |
| 绘图变量/来源 | [`plot_data/F095.json`](plot_data/F095.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F095.pdf`](overleaf/figures/F095.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F095
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F096"></a>
### F096｜第三问：Q3-T-013逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-013.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F096.png`](figures/F096.png) · [`figures/F096.pdf`](figures/F096.pdf) · [`figures/F096.svg`](figures/F096.svg) |
| 绘图变量/来源 | [`plot_data/F096.json`](plot_data/F096.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F096.pdf`](overleaf/figures/F096.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F096
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F097"></a>
### F097｜第三问：Q3-T-014逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-014.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F097.png`](figures/F097.png) · [`figures/F097.pdf`](figures/F097.pdf) · [`figures/F097.svg`](figures/F097.svg) |
| 绘图变量/来源 | [`plot_data/F097.json`](plot_data/F097.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F097.pdf`](overleaf/figures/F097.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F097
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F098"></a>
### F098｜第三问：Q3-T-015逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-015.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F098.png`](figures/F098.png) · [`figures/F098.pdf`](figures/F098.pdf) · [`figures/F098.svg`](figures/F098.svg) |
| 绘图变量/来源 | [`plot_data/F098.json`](plot_data/F098.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F098.pdf`](overleaf/figures/F098.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F098
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F099"></a>
### F099｜第三问：Q3-T-016逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-016.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F099.png`](figures/F099.png) · [`figures/F099.pdf`](figures/F099.pdf) · [`figures/F099.svg`](figures/F099.svg) |
| 绘图变量/来源 | [`plot_data/F099.json`](plot_data/F099.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F099.pdf`](overleaf/figures/F099.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**第28个图引用；`overleaf/main.tex:1483`；章节“补充诊断图与完整图件索引”。
```latex
\paperfig[.90]{F099}{问题三代表性运输架次的完整高度剖面；每次投送后重新爬升}{fig:supptransport}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F099
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F100"></a>
### F100｜第三问：Q3-T-017逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-017.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F100.png`](figures/F100.png) · [`figures/F100.pdf`](figures/F100.pdf) · [`figures/F100.svg`](figures/F100.svg) |
| 绘图变量/来源 | [`plot_data/F100.json`](plot_data/F100.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F100.pdf`](overleaf/figures/F100.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F100
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F101"></a>
### F101｜第三问：Q3-T-018逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-018.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F101.png`](figures/F101.png) · [`figures/F101.pdf`](figures/F101.pdf) · [`figures/F101.svg`](figures/F101.svg) |
| 绘图变量/来源 | [`plot_data/F101.json`](plot_data/F101.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F101.pdf`](overleaf/figures/F101.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F101
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F102"></a>
### F102｜第三问：Q3-T-019逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-019.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F102.png`](figures/F102.png) · [`figures/F102.pdf`](figures/F102.pdf) · [`figures/F102.svg`](figures/F102.svg) |
| 绘图变量/来源 | [`plot_data/F102.json`](plot_data/F102.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F102.pdf`](overleaf/figures/F102.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F102
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F103"></a>
### F103｜第三问：Q3-T-020逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-020.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F103.png`](figures/F103.png) · [`figures/F103.pdf`](figures/F103.pdf) · [`figures/F103.svg`](figures/F103.svg) |
| 绘图变量/来源 | [`plot_data/F103.json`](plot_data/F103.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F103.pdf`](overleaf/figures/F103.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（11项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F103
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F104"></a>
### F104｜第三问：Q3-T-021逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-021.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F104.png`](figures/F104.png) · [`figures/F104.pdf`](figures/F104.pdf) · [`figures/F104.svg`](figures/F104.svg) |
| 绘图变量/来源 | [`plot_data/F104.json`](plot_data/F104.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F104.pdf`](overleaf/figures/F104.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F104
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F105"></a>
### F105｜第三问：Q3-T-022逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-022.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F105.png`](figures/F105.png) · [`figures/F105.pdf`](figures/F105.pdf) · [`figures/F105.svg`](figures/F105.svg) |
| 绘图变量/来源 | [`plot_data/F105.json`](plot_data/F105.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F105.pdf`](overleaf/figures/F105.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F105
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F106"></a>
### F106｜第三问：Q3-T-023逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-023.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F106.png`](figures/F106.png) · [`figures/F106.pdf`](figures/F106.pdf) · [`figures/F106.svg`](figures/F106.svg) |
| 绘图变量/来源 | [`plot_data/F106.json`](plot_data/F106.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F106.pdf`](overleaf/figures/F106.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F106
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F107"></a>
### F107｜第三问：Q3-T-024逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-024.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F107.png`](figures/F107.png) · [`figures/F107.pdf`](figures/F107.pdf) · [`figures/F107.svg`](figures/F107.svg) |
| 绘图变量/来源 | [`plot_data/F107.json`](plot_data/F107.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F107.pdf`](overleaf/figures/F107.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F107
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F108"></a>
### F108｜第三问：Q3-T-025逐阶段高度剖面

**图形类型：**运输逐阶段高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **295–299** 行，函数`redraw_one()` |
| 检索键 | `q3/transport_profile_Q3-T-025.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F108.png`](figures/F108.png) · [`figures/F108.pdf`](figures/F108.pdf) · [`figures/F108.svg`](figures/F108.svg) |
| 绘图变量/来源 | [`plot_data/F108.json`](plot_data/F108.json) |
| 源文件 | [`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv) |
| 论文图件副本 | [`overleaf/figures/F108.pdf`](overleaf/figures/F108.pdf) |

**取数及计算位置：**trajectory_phases按trip_id筛选；每段start/end与p0/p1海拔对应。

**建议改动的位置：**PHASE颜色、阶段线宽、图例；不能跨交接段平滑为虚构高度。

**同分支影响范围：**F084, F085, F086, F087, F088, F089, F090, F091, F092, F093, F094, F095, F096, F097, F098, F099, F100, F101, F102, F103, F104, F105, F106, F107, F108。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`trip_id`、`drone_id`、`leg_index`、`from_id`、`to_id`、`phase`、`start_s`、`end_s`、`phase_id`、`p0_lon_deg`、`p0_lat_deg`、`p0_altitude_m`、`p1_lon_deg`、`p1_lat_deg`、`p1_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F108
```
**含义边界：**不同颜色区分连续阶段；交接为30米作业高度，不在区域地面停留

<a id="F109"></a>
### F109｜第三问：直连与中继保障的完整时间区间

**图形类型：**全架次连续通信时间图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **300–308** 行，函数`redraw_one()` |
| 检索键 | `q3/communication_timeline.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F109.png`](figures/F109.png) · [`figures/F109.pdf`](figures/F109.pdf) · [`figures/F109.svg`](figures/F109.svg) |
| 绘图变量/来源 | [`plot_data/F109.json`](plot_data/F109.json) |
| 源文件 | [`experiment/results/q3/communication_atoms.csv`](experiment/results/q3/communication_atoms.csv)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F109.pdf`](overleaf/figures/F109.pdf) |

**取数及计算位置：**communication_atoms正长度区间按trip_id、mode绘制直连/中继条。

**建议改动的位置：**直连/中继颜色、行间距、条高、坐标与图例；边界瞬时另有验证，不在此图补宽度。

**绘图变量结构：**列表（50项），单项字段：`trip_id`、`mode`、`start_duration_min`。

**当前论文：**第15个图引用；`overleaf/main.tex:863`；章节“问题三：连续通信约束下运输与中继联合调度” / “最终联合调度与连续保障结果”。
```latex
\paperfig[.98]{F109}{最终运输阶段的直连与中继保障时序；边界瞬时另有独立证书}{fig:commtimeline}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F109
```
**含义边界：**正长度区间图；孤立边界点由独立表逐点验证，图像分辨率不构成连续性证明

<a id="F110"></a>
### F110｜第三问：直连与中继累计保障工作量

**图形类型：**通信工作量对比点线图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **309–310** 行，函数`redraw_one()` |
| 检索键 | `q3/communication_duration.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F110.png`](figures/F110.png) · [`figures/F110.pdf`](figures/F110.pdf) · [`figures/F110.svg`](figures/F110.svg) |
| 绘图变量/来源 | [`plot_data/F110.json`](plot_data/F110.json) |
| 源文件 | [`experiment/results/q3/communication_atoms.csv`](experiment/results/q3/communication_atoms.csv) |
| 论文图件副本 | [`overleaf/figures/F110.pdf`](overleaf/figures/F110.pdf) |

**取数及计算位置：**按mode求sum(end_s−start_s)/60。

**建议改动的位置：**点/线与数值标记；累计保障时长不是日历时长。

**绘图变量结构：**对象字段：`modes`、`minutes`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F110
```
**含义边界：**累计飞行及交接时间，不等于日历持续时间；边界点不重复计时

<a id="F111"></a>
### F111｜第三问：已分割区间中点链路裕量分布

**图形类型：**链路中点裕量直方图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **311–312** 行，函数`redraw_one()` |
| 检索键 | `q3/link_margin_distribution.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F111.png`](figures/F111.png) · [`figures/F111.pdf`](figures/F111.pdf) · [`figures/F111.svg`](figures/F111.svg) |
| 绘图变量/来源 | [`plot_data/F111.json`](plot_data/F111.json) |
| 源文件 | [`experiment/results/q3/communication_atoms.csv`](experiment/results/q3/communication_atoms.csv) |
| 论文图件副本 | [`overleaf/figures/F111.pdf`](overleaf/figures/F111.pdf) |

**取数及计算位置：**selected_margin_mid_db仅取正长度区间；默认30个bin。

**建议改动的位置：**bins、透明度、边线、坐标；改bins是表达变化，不能把中点裕量称为全区间最小值。

**绘图变量结构：**对象字段：`midpoint_margins_db`、`histogram_count`、`bin_edges_db`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F111
```
**含义边界：**仅中点分布诊断，不是区间内最低裕量证明，不取代完整区间核验

<a id="F112"></a>
### F112｜第三问：额外传播损耗压力测试

**图形类型：**通信或共同延迟压力曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **313–315** 行，函数`redraw_one()` |
| 检索键 | `q3/propagation_loss.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F112.png`](figures/F112.png) · [`figures/F112.pdf`](figures/F112.pdf) · [`figures/F112.svg`](figures/F112.svg) |
| 绘图变量/来源 | [`plot_data/F112.json`](plot_data/F112.json) |
| 源文件 | [`experiment/results/q3/propagation_loss_sensitivity.csv`](experiment/results/q3/propagation_loss_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F112.pdf`](overleaf/figures/F112.pdf) |

**取数及计算位置：**按具体图读取额外损耗/仅中继延迟/共同延迟源表；未重新优化排程。

**建议改动的位置：**x/y标签、点线、零边界、图例；不删除失败情景，三种扰动不能混为一类。

**同分支影响范围：**F112, F113, F114。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`extra_loss_db`、`required_airborne_service_s`、`outage_duration_sum_s`、`coverage_fraction`、`boundary_points_checked`、`uncovered_boundary_points`、`continuous_feasible`。

**当前论文：**第20个图引用；`overleaf/main.tex:1066`；章节“闭环核验与敏感性分析” / “传播损耗与仅中继延迟”。
```latex
\paperfig[.87]{F112}{冻结轨迹和任务时刻后的额外传播损耗试验；较大损耗下的断链结果未被删除}{fig:losssweep}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F112
```
**含义边界：**压力场景不重优化；负裕度或中断表示失败，不能当作正式可行方案

<a id="F113"></a>
### F113｜第三问：仅中继延迟的冻结分配测试

**图形类型：**通信或共同延迟压力曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **313–315** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_delay.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F113.png`](figures/F113.png) · [`figures/F113.pdf`](figures/F113.pdf) · [`figures/F113.svg`](figures/F113.svg) |
| 绘图变量/来源 | [`plot_data/F113.json`](plot_data/F113.json) |
| 源文件 | [`experiment/results/q3/relay_only_delay_sensitivity.csv`](experiment/results/q3/relay_only_delay_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F113.pdf`](overleaf/figures/F113.pdf) |

**取数及计算位置：**按具体图读取额外损耗/仅中继延迟/共同延迟源表；未重新优化排程。

**建议改动的位置：**x/y标签、点线、零边界、图例；不删除失败情景，三种扰动不能混为一类。

**同分支影响范围：**F112, F113, F114。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（7项），单项字段：`relay_only_shift_s`、`fixed_assignment_uncovered_duration_s`、`fixed_assignment_uncovered_points`、`fixed_assignment_feasible`、`meaning`。

**当前论文：**第21个图引用；`overleaf/main.tex:1070`；章节“闭环核验与敏感性分析” / “传播损耗与仅中继延迟”。
```latex
\paperfig[.87]{F113}{仅中继延后且保持原通信分配的压力试验；2秒情景已出现通信缺口}{fig:relaydelay}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F113
```
**含义边界：**压力场景不重优化；负裕度或中断表示失败，不能当作正式可行方案

<a id="F114"></a>
### F114｜第三问：全部资源共同延后的时限裕度

**图形类型：**通信或共同延迟压力曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **313–315** 行，函数`redraw_one()` |
| 检索键 | `q3/common_delay.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F114.png`](figures/F114.png) · [`figures/F114.pdf`](figures/F114.pdf) · [`figures/F114.svg`](figures/F114.svg) |
| 绘图变量/来源 | [`plot_data/F114.json`](plot_data/F114.json) |
| 源文件 | [`experiment/results/q3/common_start_delay_sensitivity.csv`](experiment/results/q3/common_start_delay_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F114.pdf`](overleaf/figures/F114.pdf) |

**取数及计算位置：**按具体图读取额外损耗/仅中继延迟/共同延迟源表；未重新优化排程。

**建议改动的位置：**x/y标签、点线、零边界、图例；不删除失败情景，三种扰动不能混为一类。

**同分支影响范围：**F112, F113, F114。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（10项），单项字段：`common_delay_s`、`min_hard_slack_s`、`hard_late_boxes`、`feasible`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F114
```
**含义边界：**压力场景不重优化；负裕度或中断表示失败，不能当作正式可行方案

<a id="F115"></a>
### F115｜第三问：每次中继任务能耗组成

**图形类型：**中继三类能耗分组柱。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **316–317** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_energy_components.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **49–55** 行 `grouped()` |
| 输出图片 | [`figures/F115.png`](figures/F115.png) · [`figures/F115.pdf`](figures/F115.pdf) · [`figures/F115.svg`](figures/F115.svg) |
| 绘图变量/来源 | [`plot_data/F115.json`](plot_data/F115.json) |
| 源文件 | [`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv) |
| 论文图件副本 | [`overleaf/figures/F115.pdf`](overleaf/figures/F115.pdf) |

**取数及计算位置：**flight_energy_kwh、setup_energy_kwh、service_energy_kwh。

**建议改动的位置：**分项配色、柱宽、任务标签；保持飞行/建链/服务分项意义。

**绘图变量结构：**列表（4项），单项字段：`relay_trip_id`、`relay_drone_id`、`energy_module_id`、`model_id`、`site_id`、`start_s`、`arrival_s`、`link_complete_s`、`service_end_s`、`return_s`、`turnaround_end_s`、`energy_kwh`、`return_soc_fraction`、`charge_duration_s`、`charge_end_s`、`terrain_ground_m`、`hover_agl_m`、`cruise_altitude_m`、`horizontal_distance_m`、`outbound_climb_m`、`outbound_descent_m`、`inbound_climb_m`、`inbound_descent_m`、`outbound_flight_s`、`inbound_flight_s`、`horizontal_energy_kwh`、`climb_energy_kwh`、`flight_energy_kwh`、`setup_energy_kwh`、`service_energy_kwh`、`served_communication_atoms`、`hover_lon_deg`、`hover_lat_deg`、`hover_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F115
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F116"></a>
### F116｜第三问：中继任务返航剩余电量

**图形类型：**返航SOC茎线/散点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **220–224** 行，函数`redraw_one()` |
| 检索键 | `q3/relay_return_soc.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F116.png`](figures/F116.png) · [`figures/F116.pdf`](figures/F116.pdf) · [`figures/F116.svg`](figures/F116.svg) |
| 绘图变量/来源 | [`plot_data/F116.json`](plot_data/F116.json) |
| 源文件 | [`experiment/results/q3/relay_sorties.csv`](experiment/results/q3/relay_sorties.csv) |
| 论文图件副本 | [`overleaf/figures/F116.pdf`](overleaf/figures/F116.pdf) |

**取数及计算位置：**return_soc_fraction×100；从20%基线画至每架次真实返航SOC并标注最小值。

**建议改动的位置：**机型色、标记面积、20%约束虚线与标签；不移动约束线或删最小点。

**同分支影响范围：**F006, F054, F068, F116。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`relay_trip_id`、`relay_drone_id`、`energy_module_id`、`model_id`、`site_id`、`start_s`、`arrival_s`、`link_complete_s`、`service_end_s`、`return_s`、`turnaround_end_s`、`energy_kwh`、`return_soc_fraction`、`charge_duration_s`、`charge_end_s`、`terrain_ground_m`、`hover_agl_m`、`cruise_altitude_m`、`horizontal_distance_m`、`outbound_climb_m`、`outbound_descent_m`、`inbound_climb_m`、`inbound_descent_m`、`outbound_flight_s`、`inbound_flight_s`、`horizontal_energy_kwh`、`climb_energy_kwh`、`flight_energy_kwh`、`setup_energy_kwh`、`service_energy_kwh`、`served_communication_atoms`、`hover_lon_deg`、`hover_lat_deg`、`hover_altitude_m`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F116
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F117"></a>
### F117｜第四问：运输与中继依赖合并后的不可拆单元

**图形类型：**严格依赖分量工作量。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **318–319** 行，函数`redraw_one()` |
| 检索键 | `q4/atomic_workload.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F117.png`](figures/F117.png) · [`figures/F117.pdf`](figures/F117.pdf) · [`figures/F117.svg`](figures/F117.svg) |
| 绘图变量/来源 | [`plot_data/F117.json`](plot_data/F117.json) |
| 源文件 | [`experiment/results/q4/atomic_components.csv`](experiment/results/q4/atomic_components.csv) |
| 论文图件副本 | [`overleaf/figures/F117.pdf`](overleaf/figures/F117.pdf) |

**取数及计算位置：**atomic_components.transport_workload_share×100。

**建议改动的位置：**各分量颜色、标记与百分比标签；不能拆分该图对应的依赖分量。

**绘图变量结构：**列表（3项），单项字段：`component_id`、`services`、`service_count`、`transport_trips`、`boxes`、`weight_kg`、`transport_workload_s`、`transport_workload_share`。

**当前论文：**第16个图引用；`overleaf/main.tex:899`；章节“问题四：严格冻结任务的分区与资源配置” / “运输与通信双重依赖图”。
```latex
\paperfig[.89]{F117}{运输多点依赖与中继共同依赖合并后的不可拆单元及工作量}{fig:atomic}
```
**组合关系：**P06-B；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_figures.py --only F117
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F118"></a>
### F118｜第四问：严格不复制中继的2组分区

**图形类型：**严格分组空间图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **192–194** 行，函数`redraw_one()` |
| 检索键 | `q4/partition_K2.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F118.png`](figures/F118.png) · [`figures/F118.pdf`](figures/F118.pdf) · [`figures/F118.svg`](figures/F118.svg) |
| 绘图变量/来源 | [`plot_data/F118.json`](plot_data/F118.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q4/K2/groups.csv`](experiment/results/q4/K2/groups.csv) |
| 论文图件副本 | [`overleaf/figures/F118.pdf`](overleaf/figures/F118.pdf) |

**取数及计算位置：**K2/K3的groups.services决定彩点归属；不是行政边界或连续覆盖区。

**建议改动的位置：**组颜色、点面积、坐标标签、图例位置与地图范围；不改services归属。

**同分支影响范围：**F118, F128。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**第17个图引用；`overleaf/main.tex:966`；章节“问题四：严格冻结任务的分区与资源配置” / “全部划分、主分区与分型配置”。
```latex
\paperfig[.90]{F118}{资源优先的两组分区：S006独立，其余14个服务区同组}{fig:k2map}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F118
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；彩点表示服务区归属，不将凸包画成行政区或连续覆盖区。

<a id="F119"></a>
### F119｜第四问：2组的运输累计作业时间

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_workload.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F119.png`](figures/F119.png) · [`figures/F119.pdf`](figures/F119.pdf) · [`figures/F119.svg`](figures/F119.svg) |
| 绘图变量/来源 | [`plot_data/F119.json`](plot_data/F119.json) |
| 源文件 | [`experiment/results/q4/K2/groups.csv`](experiment/results/q4/K2/groups.csv) |
| 论文图件副本 | [`overleaf/figures/F119.pdf`](overleaf/figures/F119.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（2项），单项字段：`mask`、`transport_workload_s`、`relay_workload_s`、`joint_workload_s`、`transport_trips`、`relay_copies`、`boxes`、`weight_kg`、`volume_m3`、`transport_energy_kwh`、`relay_energy_kwh`、`joint_makespan_s`、`K`、`group_id`、`services`、`trip_ids`、`relay_ids`、`transport_A`、`source_ID_locked_transport_A`、`transport_B`、`source_ID_locked_transport_B`、`transport_C`、`source_ID_locked_transport_C`、`battery_A`、`source_ID_locked_battery_A`、`battery_B`、`source_ID_locked_battery_B`、`battery_C`、`source_ID_locked_battery_C`、`relay_drone`、`source_ID_locked_relay_drone`、`relay_energy`、`source_ID_locked_relay_energy`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F119
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F120"></a>
### F120｜第四问：2组的货箱数量

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_boxes.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F120.png`](figures/F120.png) · [`figures/F120.pdf`](figures/F120.pdf) · [`figures/F120.svg`](figures/F120.svg) |
| 绘图变量/来源 | [`plot_data/F120.json`](plot_data/F120.json) |
| 源文件 | [`experiment/results/q4/K2/groups.csv`](experiment/results/q4/K2/groups.csv) |
| 论文图件副本 | [`overleaf/figures/F120.pdf`](overleaf/figures/F120.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（2项），单项字段：`mask`、`transport_workload_s`、`relay_workload_s`、`joint_workload_s`、`transport_trips`、`relay_copies`、`boxes`、`weight_kg`、`volume_m3`、`transport_energy_kwh`、`relay_energy_kwh`、`joint_makespan_s`、`K`、`group_id`、`services`、`trip_ids`、`relay_ids`、`transport_A`、`source_ID_locked_transport_A`、`transport_B`、`source_ID_locked_transport_B`、`transport_C`、`source_ID_locked_transport_C`、`battery_A`、`source_ID_locked_battery_A`、`battery_B`、`source_ID_locked_battery_B`、`battery_C`、`source_ID_locked_battery_C`、`relay_drone`、`source_ID_locked_relay_drone`、`relay_energy`、`source_ID_locked_relay_energy`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F120
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F121"></a>
### F121｜第四问：2组的运输架次数

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_sorties.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F121.png`](figures/F121.png) · [`figures/F121.pdf`](figures/F121.pdf) · [`figures/F121.svg`](figures/F121.svg) |
| 绘图变量/来源 | [`plot_data/F121.json`](plot_data/F121.json) |
| 源文件 | [`experiment/results/q4/K2/groups.csv`](experiment/results/q4/K2/groups.csv) |
| 论文图件副本 | [`overleaf/figures/F121.pdf`](overleaf/figures/F121.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（2项），单项字段：`mask`、`transport_workload_s`、`relay_workload_s`、`joint_workload_s`、`transport_trips`、`relay_copies`、`boxes`、`weight_kg`、`volume_m3`、`transport_energy_kwh`、`relay_energy_kwh`、`joint_makespan_s`、`K`、`group_id`、`services`、`trip_ids`、`relay_ids`、`transport_A`、`source_ID_locked_transport_A`、`transport_B`、`source_ID_locked_transport_B`、`transport_C`、`source_ID_locked_transport_C`、`battery_A`、`source_ID_locked_battery_A`、`battery_B`、`source_ID_locked_battery_B`、`battery_C`、`source_ID_locked_battery_C`、`relay_drone`、`source_ID_locked_relay_drone`、`relay_energy`、`source_ID_locked_relay_energy`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F121
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F122"></a>
### F122｜第四问：2组独立配置需求与原库存

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_inventory.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F122.png`](figures/F122.png) · [`figures/F122.pdf`](figures/F122.pdf) · [`figures/F122.svg`](figures/F122.svg) |
| 绘图变量/来源 | [`plot_data/F122.json`](plot_data/F122.json) |
| 源文件 | [`experiment/results/q4/inventory_gap.csv`](experiment/results/q4/inventory_gap.csv)<br>[`experiment/results/q4/summary.json`](experiment/results/q4/summary.json) |
| 论文图件副本 | [`overleaf/figures/F122.pdf`](overleaf/figures/F122.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（8项），单项字段：`K`、`resource_type`、`resource_name`、`inventory`、`required`、`shortage`、`unused_inventory`、`structural_extra_vs_Q3_minimum`、`extra_vs_Q3_used_IDs`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F122
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F123"></a>
### F123｜第四问：2组分类型资源缺口

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_gap.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F123.png`](figures/F123.png) · [`figures/F123.pdf`](figures/F123.pdf) · [`figures/F123.svg`](figures/F123.svg) |
| 绘图变量/来源 | [`plot_data/F123.json`](plot_data/F123.json) |
| 源文件 | [`experiment/results/q4/inventory_gap.csv`](experiment/results/q4/inventory_gap.csv)<br>[`experiment/results/q4/summary.json`](experiment/results/q4/summary.json) |
| 论文图件副本 | [`overleaf/figures/F123.pdf`](overleaf/figures/F123.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（8项），单项字段：`K`、`resource_type`、`resource_name`、`inventory`、`required`、`shortage`、`unused_inventory`、`structural_extra_vs_Q3_minimum`、`extra_vs_Q3_used_IDs`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F123
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F124"></a>
### F124｜第四问：2组独立运输机身占用

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_drones_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F124.png`](figures/F124.png) · [`figures/F124.pdf`](figures/F124.pdf) · [`figures/F124.svg`](figures/F124.svg) |
| 绘图变量/来源 | [`plot_data/F124.json`](plot_data/F124.json) |
| 源文件 | [`experiment/results/q4/K2/resource_allocations.csv`](experiment/results/q4/K2/resource_allocations.csv) |
| 论文图件副本 | [`overleaf/figures/F124.pdf`](overleaf/figures/F124.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（25项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F124
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F125"></a>
### F125｜第四问：2组独立运输电池占用

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_batteries_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F125.png`](figures/F125.png) · [`figures/F125.pdf`](figures/F125.pdf) · [`figures/F125.svg`](figures/F125.svg) |
| 绘图变量/来源 | [`plot_data/F125.json`](plot_data/F125.json) |
| 源文件 | [`experiment/results/q4/K2/resource_allocations.csv`](experiment/results/q4/K2/resource_allocations.csv) |
| 论文图件副本 | [`overleaf/figures/F125.pdf`](overleaf/figures/F125.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（25项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F125
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F126"></a>
### F126｜第四问：2组独立中继机身占用

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_relay_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F126.png`](figures/F126.png) · [`figures/F126.pdf`](figures/F126.pdf) · [`figures/F126.svg`](figures/F126.svg) |
| 绘图变量/来源 | [`plot_data/F126.json`](plot_data/F126.json) |
| 源文件 | [`experiment/results/q4/K2/resource_allocations.csv`](experiment/results/q4/K2/resource_allocations.csv) |
| 论文图件副本 | [`overleaf/figures/F126.pdf`](overleaf/figures/F126.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F126
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F127"></a>
### F127｜第四问：2组独立中继能源组件占用

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q4/K2_modules_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F127.png`](figures/F127.png) · [`figures/F127.pdf`](figures/F127.pdf) · [`figures/F127.svg`](figures/F127.svg) |
| 绘图变量/来源 | [`plot_data/F127.json`](plot_data/F127.json) |
| 源文件 | [`experiment/results/q4/K2/resource_allocations.csv`](experiment/results/q4/K2/resource_allocations.csv) |
| 论文图件副本 | [`overleaf/figures/F127.pdf`](overleaf/figures/F127.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F127
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F128"></a>
### F128｜第四问：严格不复制中继的3组分区

**图形类型：**严格分组空间图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **192–194** 行，函数`redraw_one()` |
| 检索键 | `q4/partition_K3.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **80–132** 行 `plot_map()` |
| 输出图片 | [`figures/F128.png`](figures/F128.png) · [`figures/F128.pdf`](figures/F128.pdf) · [`figures/F128.svg`](figures/F128.svg) |
| 绘图变量/来源 | [`plot_data/F128.json`](plot_data/F128.json) |
| 源文件 | [`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q4/K3/groups.csv`](experiment/results/q4/K3/groups.csv) |
| 论文图件副本 | [`overleaf/figures/F128.pdf`](overleaf/figures/F128.pdf) |

**取数及计算位置：**K2/K3的groups.services决定彩点归属；不是行政边界或连续覆盖区。

**建议改动的位置：**组颜色、点面积、坐标标签、图例位置与地图范围；不改services归属。

**同分支影响范围：**F118, F128。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`。

**当前论文：**第18个图引用；`overleaf/main.tex:967`；章节“问题四：严格冻结任务的分区与资源配置” / “全部划分、主分区与分型配置”。
```latex
\paperfig[.90]{F128}{严格三组分区：大分量、S006与S007分别成组，不复制任何中继任务}{fig:k3map}
```
**组合关系：**P06-A；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_figures.py --only F128
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验；彩点表示服务区归属，不将凸包画成行政区或连续覆盖区。

<a id="F129"></a>
### F129｜第四问：3组的运输累计作业时间

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_workload.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F129.png`](figures/F129.png) · [`figures/F129.pdf`](figures/F129.pdf) · [`figures/F129.svg`](figures/F129.svg) |
| 绘图变量/来源 | [`plot_data/F129.json`](plot_data/F129.json) |
| 源文件 | [`experiment/results/q4/K3/groups.csv`](experiment/results/q4/K3/groups.csv) |
| 论文图件副本 | [`overleaf/figures/F129.pdf`](overleaf/figures/F129.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（3项），单项字段：`mask`、`transport_workload_s`、`relay_workload_s`、`joint_workload_s`、`transport_trips`、`relay_copies`、`boxes`、`weight_kg`、`volume_m3`、`transport_energy_kwh`、`relay_energy_kwh`、`joint_makespan_s`、`K`、`group_id`、`services`、`trip_ids`、`relay_ids`、`transport_A`、`source_ID_locked_transport_A`、`transport_B`、`source_ID_locked_transport_B`、`transport_C`、`source_ID_locked_transport_C`、`battery_A`、`source_ID_locked_battery_A`、`battery_B`、`source_ID_locked_battery_B`、`battery_C`、`source_ID_locked_battery_C`、`relay_drone`、`source_ID_locked_relay_drone`、`relay_energy`、`source_ID_locked_relay_energy`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F129
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F130"></a>
### F130｜第四问：3组的货箱数量

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_boxes.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F130.png`](figures/F130.png) · [`figures/F130.pdf`](figures/F130.pdf) · [`figures/F130.svg`](figures/F130.svg) |
| 绘图变量/来源 | [`plot_data/F130.json`](plot_data/F130.json) |
| 源文件 | [`experiment/results/q4/K3/groups.csv`](experiment/results/q4/K3/groups.csv) |
| 论文图件副本 | [`overleaf/figures/F130.pdf`](overleaf/figures/F130.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（3项），单项字段：`mask`、`transport_workload_s`、`relay_workload_s`、`joint_workload_s`、`transport_trips`、`relay_copies`、`boxes`、`weight_kg`、`volume_m3`、`transport_energy_kwh`、`relay_energy_kwh`、`joint_makespan_s`、`K`、`group_id`、`services`、`trip_ids`、`relay_ids`、`transport_A`、`source_ID_locked_transport_A`、`transport_B`、`source_ID_locked_transport_B`、`transport_C`、`source_ID_locked_transport_C`、`battery_A`、`source_ID_locked_battery_A`、`battery_B`、`source_ID_locked_battery_B`、`battery_C`、`source_ID_locked_battery_C`、`relay_drone`、`source_ID_locked_relay_drone`、`relay_energy`、`source_ID_locked_relay_energy`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F130
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F131"></a>
### F131｜第四问：3组的运输架次数

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_sorties.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F131.png`](figures/F131.png) · [`figures/F131.pdf`](figures/F131.pdf) · [`figures/F131.svg`](figures/F131.svg) |
| 绘图变量/来源 | [`plot_data/F131.json`](plot_data/F131.json) |
| 源文件 | [`experiment/results/q4/K3/groups.csv`](experiment/results/q4/K3/groups.csv) |
| 论文图件副本 | [`overleaf/figures/F131.pdf`](overleaf/figures/F131.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（3项），单项字段：`mask`、`transport_workload_s`、`relay_workload_s`、`joint_workload_s`、`transport_trips`、`relay_copies`、`boxes`、`weight_kg`、`volume_m3`、`transport_energy_kwh`、`relay_energy_kwh`、`joint_makespan_s`、`K`、`group_id`、`services`、`trip_ids`、`relay_ids`、`transport_A`、`source_ID_locked_transport_A`、`transport_B`、`source_ID_locked_transport_B`、`transport_C`、`source_ID_locked_transport_C`、`battery_A`、`source_ID_locked_battery_A`、`battery_B`、`source_ID_locked_battery_B`、`battery_C`、`source_ID_locked_battery_C`、`relay_drone`、`source_ID_locked_relay_drone`、`relay_energy`、`source_ID_locked_relay_energy`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F131
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F132"></a>
### F132｜第四问：3组独立配置需求与原库存

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_inventory.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F132.png`](figures/F132.png) · [`figures/F132.pdf`](figures/F132.pdf) · [`figures/F132.svg`](figures/F132.svg) |
| 绘图变量/来源 | [`plot_data/F132.json`](plot_data/F132.json) |
| 源文件 | [`experiment/results/q4/inventory_gap.csv`](experiment/results/q4/inventory_gap.csv)<br>[`experiment/results/q4/summary.json`](experiment/results/q4/summary.json) |
| 论文图件副本 | [`overleaf/figures/F132.pdf`](overleaf/figures/F132.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（8项），单项字段：`K`、`resource_type`、`resource_name`、`inventory`、`required`、`shortage`、`unused_inventory`、`structural_extra_vs_Q3_minimum`、`extra_vs_Q3_used_IDs`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P06-C；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_figures.py --only F132
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F133"></a>
### F133｜第四问：3组分类型资源缺口

**图形类型：**分组工作量/库存/缺口图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **320–332** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_gap.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **31–47** 行 `dotbars()` |
| 输出图片 | [`figures/F133.png`](figures/F133.png) · [`figures/F133.pdf`](figures/F133.pdf) · [`figures/F133.svg`](figures/F133.svg) |
| 绘图变量/来源 | [`plot_data/F133.json`](plot_data/F133.json) |
| 源文件 | [`experiment/results/q4/inventory_gap.csv`](experiment/results/q4/inventory_gap.csv)<br>[`experiment/results/q4/summary.json`](experiment/results/q4/summary.json) |
| 论文图件副本 | [`overleaf/figures/F133.pdf`](overleaf/figures/F133.pdf) |

**取数及计算位置：**K2或K3 groups汇总；inventory_gap按K读取inventory、required、shortage。

**建议改动的位置：**根据分支调整点线/库存双端点/标注/颜色；不要用总库存抵消不同型号缺口。

**同分支影响范围：**F119, F120, F121, F122, F123, F129, F130, F131, F132, F133。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（8项），单项字段：`K`、`resource_type`、`resource_name`、`inventory`、`required`、`shortage`、`unused_inventory`、`structural_extra_vs_Q3_minimum`、`extra_vs_Q3_used_IDs`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F133
```
**含义边界：**当前主方案的诊断视图；柱高由源表聚合

<a id="F134"></a>
### F134｜第四问：3组独立运输机身占用

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_drones_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F134.png`](figures/F134.png) · [`figures/F134.pdf`](figures/F134.pdf) · [`figures/F134.svg`](figures/F134.svg) |
| 绘图变量/来源 | [`plot_data/F134.json`](plot_data/F134.json) |
| 源文件 | [`experiment/results/q4/K3/resource_allocations.csv`](experiment/results/q4/K3/resource_allocations.csv) |
| 论文图件副本 | [`overleaf/figures/F134.pdf`](overleaf/figures/F134.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（25项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F134
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F135"></a>
### F135｜第四问：3组独立运输电池占用

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_batteries_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F135.png`](figures/F135.png) · [`figures/F135.pdf`](figures/F135.pdf) · [`figures/F135.svg`](figures/F135.svg) |
| 绘图变量/来源 | [`plot_data/F135.json`](plot_data/F135.json) |
| 源文件 | [`experiment/results/q4/K3/resource_allocations.csv`](experiment/results/q4/K3/resource_allocations.csv) |
| 论文图件副本 | [`overleaf/figures/F135.pdf`](overleaf/figures/F135.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（25项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**第29个图引用；`overleaf/main.tex:1484`；章节“补充诊断图与完整图件索引”。
```latex
\paperfig[.98]{F135}{严格三组方案的运输电池独立配置与充电占用；组间不共用电池}{fig:suppbattery}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F135
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F136"></a>
### F136｜第四问：3组独立中继机身占用

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_relay_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F136.png`](figures/F136.png) · [`figures/F136.pdf`](figures/F136.pdf) · [`figures/F136.svg`](figures/F136.svg) |
| 绘图变量/来源 | [`plot_data/F136.json`](plot_data/F136.json) |
| 源文件 | [`experiment/results/q4/K3/resource_allocations.csv`](experiment/results/q4/K3/resource_allocations.csv) |
| 论文图件副本 | [`overleaf/figures/F136.pdf`](overleaf/figures/F136.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F136
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F137"></a>
### F137｜第四问：3组独立中继能源组件占用

**图形类型：**资源占用甘特图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **263–272** 行，函数`redraw_one()` |
| 检索键 | `q4/K3_modules_gantt.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **134–158** 行 `gantt()` |
| 输出图片 | [`figures/F137.png`](figures/F137.png) · [`figures/F137.pdf`](figures/F137.pdf) · [`figures/F137.svg`](figures/F137.svg) |
| 绘图变量/来源 | [`plot_data/F137.json`](plot_data/F137.json) |
| 源文件 | [`experiment/results/q4/K3/resource_allocations.csv`](experiment/results/q4/K3/resource_allocations.csv) |
| 论文图件副本 | [`overleaf/figures/F137.pdf`](overleaf/figures/F137.pdf) |

**取数及计算位置：**按机身/电池/组内资源筛选；start至return为任务，return至ready为充电或周转。

**建议改动的位置：**gantt中的画布行高、实色/斜线、任务号字体、资源标签和图例；不压缩充电时间。

**同分支影响范围：**F050, F051, F064, F065, F078, F079, F124, F125, F126, F127, F134, F135, F136, F137。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`resource`、`start_min`、`return_min`、`ready_min`、`trip`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F137
```
**含义边界：**当前主方案的诊断视图；不另算一次独立实验

<a id="F138"></a>
### F138｜第四问：严格可行的全部4个分区比较

**图形类型：**全部合法分区散点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **333–337** 行，函数`redraw_one()` |
| 检索键 | `q4/all_partitions.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F138.png`](figures/F138.png) · [`figures/F138.pdf`](figures/F138.pdf) · [`figures/F138.svg`](figures/F138.svg) |
| 绘图变量/来源 | [`plot_data/F138.json`](plot_data/F138.json) |
| 源文件 | [`experiment/results/q4/all_partitions.csv`](experiment/results/q4/all_partitions.csv) |
| 论文图件副本 | [`overleaf/figures/F138.pdf`](overleaf/figures/F138.pdf) |

**取数及计算位置：**all_partitions中的transport_workload_cv、resource_units、shortage_units、selected_main。

**建议改动的位置：**两/三组颜色、主方案星标与文本偏移；只显示源表真实4个合法划分。

**绘图变量结构：**列表（4项），单项字段：`K`、`partition_id`、`labels`、`group_masks`、`groups`、`shortage_units`、`resource_units`、`transport_workload_cv`、`joint_workload_cv`、`max_transport_workload_share`、`inventory_feasible`、`relay_mission_copies`、`relay_unique_execution_count`、`extra_relay_mission_copies`、`transport_energy_kwh`、`relay_energy_kwh`、`joint_makespan_s`、`structural_extra_units`、`original_ID_locked_resource_units`、`total_energy_kwh`、`need_transport_A`、`gap_transport_A`、`spare_transport_A`、`need_transport_B`、`gap_transport_B`、`spare_transport_B`、`need_transport_C`、`gap_transport_C`、`spare_transport_C`、`need_battery_A`、`gap_battery_A`、`spare_battery_A`、`need_battery_B`、`gap_battery_B`、`spare_battery_B`、`need_battery_C`、`gap_battery_C`、`spare_battery_C`、`need_relay_drone`、`gap_relay_drone`、`spare_relay_drone`、`need_relay_energy`、`gap_relay_energy`、`spare_relay_energy`、`pareto_resource_balance`、`pareto_resource_vector`、`selected_main`。

**当前论文：**第19个图引用；`overleaf/main.tex:1011`；章节“问题四：严格冻结任务的分区与资源配置” / “均衡、资源冗余及继承一致性”。
```latex
\paperfig[.90]{F138}{严格可行空间内全部4个划分的资源、缺口与均衡对照}{fig:q4all}
```
**组合关系：**P06-D；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_figures.py --only F138
```
**含义边界：**固定最终Q3的严格依赖图全部分区；不同于仅按运输依赖枚举的空间

<a id="F139"></a>
### F139｜闭环压力测试：运输能耗扰动与最低返航电量

**图形类型：**冻结排程压力折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **338–350** 行，函数`redraw_one()` |
| 检索键 | `closure/energy_soc.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F139.png`](figures/F139.png) · [`figures/F139.pdf`](figures/F139.pdf) · [`figures/F139.svg`](figures/F139.svg) |
| 绘图变量/来源 | [`plot_data/F139.json`](plot_data/F139.json) |
| 源文件 | [`experiment/results/closure/fixed_energy_sweep.csv`](experiment/results/closure/fixed_energy_sweep.csv) |
| 论文图件副本 | [`overleaf/figures/F139.pdf`](overleaf/figures/F139.pdf) |

**取数及计算位置：**fixed_energy_sweep / fixed_charging_sweep / common_delay_fine_sweep按question分组，specs选x/y与倍率。

**建议改动的位置：**QUESTION颜色、线/点、阈值线、刻度；fac是单位转换不能当作视觉缩放任意修改。

**同分支影响范围：**F139, F140, F141, F142, F143, F144, F145, F146。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（24项），单项字段：`question`、`energy_multiplier`、`transport_energy_kwh`、`minimum_soc_fraction`、`reserve_violating_sorties`、`negative_soc_sorties`、`battery_reuse_conflicts`、`minimum_reuse_slack_s`、`energy_and_battery_feasible`、`experiment_scope`。

**当前论文：**第22个图引用；`overleaf/main.tex:1099`；章节“闭环核验与敏感性分析” / “能耗和充电恢复的耦合薄弱点”。
```latex
\paperfig[.88]{F139}{运输能耗倍率对最低返航SOC的影响；SOC通过不等于电池周转仍可行}{fig:energystress}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F139
```
**含义边界：**冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率

<a id="F140"></a>
### F140｜闭环压力测试：运输能耗扰动导致的安全余量违约

**图形类型：**冻结排程压力折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **338–350** 行，函数`redraw_one()` |
| 检索键 | `closure/energy_violations.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F140.png`](figures/F140.png) · [`figures/F140.pdf`](figures/F140.pdf) · [`figures/F140.svg`](figures/F140.svg) |
| 绘图变量/来源 | [`plot_data/F140.json`](plot_data/F140.json) |
| 源文件 | [`experiment/results/closure/fixed_energy_sweep.csv`](experiment/results/closure/fixed_energy_sweep.csv) |
| 论文图件副本 | [`overleaf/figures/F140.pdf`](overleaf/figures/F140.pdf) |

**取数及计算位置：**fixed_energy_sweep / fixed_charging_sweep / common_delay_fine_sweep按question分组，specs选x/y与倍率。

**建议改动的位置：**QUESTION颜色、线/点、阈值线、刻度；fac是单位转换不能当作视觉缩放任意修改。

**同分支影响范围：**F139, F140, F141, F142, F143, F144, F145, F146。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（24项），单项字段：`question`、`energy_multiplier`、`transport_energy_kwh`、`minimum_soc_fraction`、`reserve_violating_sorties`、`negative_soc_sorties`、`battery_reuse_conflicts`、`minimum_reuse_slack_s`、`energy_and_battery_feasible`、`experiment_scope`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F140
```
**含义边界：**冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率

<a id="F141"></a>
### F141｜闭环压力测试：运输能耗扰动导致的电池周转冲突

**图形类型：**冻结排程压力折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **338–350** 行，函数`redraw_one()` |
| 检索键 | `closure/energy_charge_conflicts.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F141.png`](figures/F141.png) · [`figures/F141.pdf`](figures/F141.pdf) · [`figures/F141.svg`](figures/F141.svg) |
| 绘图变量/来源 | [`plot_data/F141.json`](plot_data/F141.json) |
| 源文件 | [`experiment/results/closure/fixed_energy_sweep.csv`](experiment/results/closure/fixed_energy_sweep.csv) |
| 论文图件副本 | [`overleaf/figures/F141.pdf`](overleaf/figures/F141.pdf) |

**取数及计算位置：**fixed_energy_sweep / fixed_charging_sweep / common_delay_fine_sweep按question分组，specs选x/y与倍率。

**建议改动的位置：**QUESTION颜色、线/点、阈值线、刻度；fac是单位转换不能当作视觉缩放任意修改。

**同分支影响范围：**F139, F140, F141, F142, F143, F144, F145, F146。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（24项），单项字段：`question`、`energy_multiplier`、`transport_energy_kwh`、`minimum_soc_fraction`、`reserve_violating_sorties`、`negative_soc_sorties`、`battery_reuse_conflicts`、`minimum_reuse_slack_s`、`energy_and_battery_feasible`、`experiment_scope`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F141
```
**含义边界：**冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率

<a id="F142"></a>
### F142｜闭环压力测试：充电时间扰动与下一次任务准备裕度

**图形类型：**冻结排程压力折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **338–350** 行，函数`redraw_one()` |
| 检索键 | `closure/charge_slack.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F142.png`](figures/F142.png) · [`figures/F142.pdf`](figures/F142.pdf) · [`figures/F142.svg`](figures/F142.svg) |
| 绘图变量/来源 | [`plot_data/F142.json`](plot_data/F142.json) |
| 源文件 | [`experiment/results/closure/fixed_charging_sweep.csv`](experiment/results/closure/fixed_charging_sweep.csv) |
| 论文图件副本 | [`overleaf/figures/F142.pdf`](overleaf/figures/F142.pdf) |

**取数及计算位置：**fixed_energy_sweep / fixed_charging_sweep / common_delay_fine_sweep按question分组，specs选x/y与倍率。

**建议改动的位置：**QUESTION颜色、线/点、阈值线、刻度；fac是单位转换不能当作视觉缩放任意修改。

**同分支影响范围：**F139, F140, F141, F142, F143, F144, F145, F146。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（20项），单项字段：`question`、`full_charge_time_multiplier`、`reused_battery_transitions`、`conflicting_transitions`、`minimum_reuse_slack_s`、`feasible`、`scope`。

**当前论文：**第23个图引用；`overleaf/main.tex:1103`；章节“闭环核验与敏感性分析” / “能耗和充电恢复的耦合薄弱点”。
```latex
\paperfig[.88]{F142}{固定任务开始时刻下的充电时间倍率与最紧电池恢复裕度}{fig:chargestress}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F142
```
**含义边界：**冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率

<a id="F143"></a>
### F143｜闭环压力测试：充电变慢后的资源冲突

**图形类型：**冻结排程压力折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **338–350** 行，函数`redraw_one()` |
| 检索键 | `closure/charge_conflicts.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F143.png`](figures/F143.png) · [`figures/F143.pdf`](figures/F143.pdf) · [`figures/F143.svg`](figures/F143.svg) |
| 绘图变量/来源 | [`plot_data/F143.json`](plot_data/F143.json) |
| 源文件 | [`experiment/results/closure/fixed_charging_sweep.csv`](experiment/results/closure/fixed_charging_sweep.csv) |
| 论文图件副本 | [`overleaf/figures/F143.pdf`](overleaf/figures/F143.pdf) |

**取数及计算位置：**fixed_energy_sweep / fixed_charging_sweep / common_delay_fine_sweep按question分组，specs选x/y与倍率。

**建议改动的位置：**QUESTION颜色、线/点、阈值线、刻度；fac是单位转换不能当作视觉缩放任意修改。

**同分支影响范围：**F139, F140, F141, F142, F143, F144, F145, F146。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（20项），单项字段：`question`、`full_charge_time_multiplier`、`reused_battery_transitions`、`conflicting_transitions`、`minimum_reuse_slack_s`、`feasible`、`scope`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F143
```
**含义边界：**冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率

<a id="F144"></a>
### F144｜闭环压力测试：共同延迟对最紧硬时限的影响

**图形类型：**冻结排程压力折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **338–350** 行，函数`redraw_one()` |
| 检索键 | `closure/delay_slack.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F144.png`](figures/F144.png) · [`figures/F144.pdf`](figures/F144.pdf) · [`figures/F144.svg`](figures/F144.svg) |
| 绘图变量/来源 | [`plot_data/F144.json`](plot_data/F144.json) |
| 源文件 | [`experiment/results/closure/common_delay_fine_sweep.csv`](experiment/results/closure/common_delay_fine_sweep.csv) |
| 论文图件副本 | [`overleaf/figures/F144.pdf`](overleaf/figures/F144.pdf) |

**取数及计算位置：**fixed_energy_sweep / fixed_charging_sweep / common_delay_fine_sweep按question分组，specs选x/y与倍率。

**建议改动的位置：**QUESTION颜色、线/点、阈值线、刻度；fac是单位转换不能当作视觉缩放任意修改。

**同分支影响范围：**F139, F140, F141, F142, F143, F144, F145, F146。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（122项），单项字段：`question`、`common_delay_s`、`minimum_hard_slack_s`、`hard_late_boxes`、`expected_late_boxes`、`hard_feasible`、`scope`。

**当前论文：**第24个图引用；`overleaf/main.tex:1113`；章节“闭环核验与敏感性分析” / “全资源共同延迟与硬时限”。
```latex
\paperfig[.88]{F144}{全部任务共同延后时的最小硬截止裕度；不适用于只延后某架中继的情形}{fig:delaystress}
```
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F144
```
**含义边界：**冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率

<a id="F145"></a>
### F145｜闭环压力测试：共同延迟导致的硬时限违约货箱数

**图形类型：**冻结排程压力折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **338–350** 行，函数`redraw_one()` |
| 检索键 | `closure/delay_violations.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F145.png`](figures/F145.png) · [`figures/F145.pdf`](figures/F145.pdf) · [`figures/F145.svg`](figures/F145.svg) |
| 绘图变量/来源 | [`plot_data/F145.json`](plot_data/F145.json) |
| 源文件 | [`experiment/results/closure/common_delay_fine_sweep.csv`](experiment/results/closure/common_delay_fine_sweep.csv) |
| 论文图件副本 | [`overleaf/figures/F145.pdf`](overleaf/figures/F145.pdf) |

**取数及计算位置：**fixed_energy_sweep / fixed_charging_sweep / common_delay_fine_sweep按question分组，specs选x/y与倍率。

**建议改动的位置：**QUESTION颜色、线/点、阈值线、刻度；fac是单位转换不能当作视觉缩放任意修改。

**同分支影响范围：**F139, F140, F141, F142, F143, F144, F145, F146。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（122项），单项字段：`question`、`common_delay_s`、`minimum_hard_slack_s`、`hard_late_boxes`、`expected_late_boxes`、`hard_feasible`、`scope`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F145
```
**含义边界：**冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率

<a id="F146"></a>
### F146｜闭环压力测试：共同延迟导致的期望送达逾期

**图形类型：**冻结排程压力折线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **338–350** 行，函数`redraw_one()` |
| 检索键 | `closure/expected_delay.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F146.png`](figures/F146.png) · [`figures/F146.pdf`](figures/F146.pdf) · [`figures/F146.svg`](figures/F146.svg) |
| 绘图变量/来源 | [`plot_data/F146.json`](plot_data/F146.json) |
| 源文件 | [`experiment/results/closure/common_delay_fine_sweep.csv`](experiment/results/closure/common_delay_fine_sweep.csv) |
| 论文图件副本 | [`overleaf/figures/F146.pdf`](overleaf/figures/F146.pdf) |

**取数及计算位置：**fixed_energy_sweep / fixed_charging_sweep / common_delay_fine_sweep按question分组，specs选x/y与倍率。

**建议改动的位置：**QUESTION颜色、线/点、阈值线、刻度；fac是单位转换不能当作视觉缩放任意修改。

**同分支影响范围：**F139, F140, F141, F142, F143, F144, F145, F146。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（122项），单项字段：`question`、`common_delay_s`、`minimum_hard_slack_s`、`hard_late_boxes`、`expected_late_boxes`、`hard_feasible`、`scope`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_figures.py --only F146
```
**含义边界：**冻结排程压力试验；仅检验图示扰动维度，不重新优化、不代表随机可靠率

<a id="F147"></a>
### F147｜闭环筛选：独立Q3候选的严格三分区兼容性

**图形类型：**已计算候选时间—能耗散点图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/redraw.py`](viz/redraw.py) 第 **277–278** 行，函数`redraw_one()` |
| 检索键 | `closure/candidate_compatibility.png`（旧路径仅用于分支，不是新图输出路径） |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **160–180** 行 `tradeoff()` |
| 输出图片 | [`figures/F147.png`](figures/F147.png) · [`figures/F147.pdf`](figures/F147.pdf) · [`figures/F147.svg`](figures/F147.svg) |
| 绘图变量/来源 | [`plot_data/F147.json`](plot_data/F147.json) |
| 源文件 | [`experiment/results/q3/closure_existing_candidates.csv`](experiment/results/q3/closure_existing_candidates.csv) |
| 论文图件副本 | [`overleaf/figures/F147.pdf`](overleaf/figures/F147.pdf) |

**取数及计算位置：**scenario_comparison或closure_existing_candidates；相同坐标合并注释，兼容性/选中标记不同。

**建议改动的位置：**tradeoff中的点样式、注释偏移、图例与边距；不能制造更多候选或称为全局前沿。

**同分支影响范围：**F053, F067, F147。不加`code`条件直接改该分支，会影响这些图；改共用函数还会影响更大范围。

**绘图变量结构：**列表（4项），单项字段：`x`、`y`、`names`、`valid`、`chosen`。

**当前论文：**第11个图引用；`overleaf/main.tex:822`；章节“问题三：连续通信约束下运输与中继联合调度” / “严格三分区资格下的候选选择”。
```latex
\paperfig[.91]{F147}{问题三实算候选的联合完工时间与严格三分区兼容性}{fig:compatibility}
```
**组合关系：**P04-B；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_figures.py --only F147
```
**含义边界：**圆点支持严格三组；叉号不支持；同坐标标签合并，选择在Q3定稿前完成，不在Q4改排任务

<a id="F148"></a>
### F148｜C型载荷—巡航海拔能耗响应（模型扫参）

**图形类型：**三维能耗曲面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **46–55** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F148'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F148.png`](figures/F148.png) · [`figures/F148.pdf`](figures/F148.pdf) · [`figures/F148.svg`](figures/F148.svg) |
| 绘图变量/来源 | [`plot_data/F148.json`](plot_data/F148.json) |
| 源文件 | [`experiment/data/cleaned/boxes.csv`](experiment/data/cleaned/boxes.csv)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv)<br>[`experiment/src/config.py`](experiment/src/config.py)<br>[`experiment/src/physics.py`](experiment/src/physics.py) |
| 论文图件副本 | [`overleaf/figures/F148.pdf`](overleaf/figures/F148.pdf) |

**取数及计算位置：**数据网格32–45行；plot_surface 47行、底部约束等值线48行、真实点50行、视角52行、色条54行。

**建议改动的位置：**ENERGY色带、view_init(elev,azim)、set_box_aspect、surface透明度、点大小与色条。

**绘图变量结构：**对象字段：`route`、`model`、`payload_grid_kg`、`cruise_altitude_grid_m`、`energy_grid_kwh`、`energy_budget_kwh`、`actual_S008_point`、`kind`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P01-A；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F148  # 先按第2.3节保存辅助脚本
```
**含义边界：**固定S008的真实距离与两端作业高度；载荷和巡航海拔为确定性模型扫参，非新增现场试验或正式排程。只基准海拔对应题定巡航规则。

<a id="F149"></a>
### F149｜同一能耗曲面的可行域投影

**图形类型：**能耗等值投影。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **56–58** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F149'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F149.png`](figures/F149.png) · [`figures/F149.pdf`](figures/F149.pdf) · [`figures/F149.svg`](figures/F149.svg) |
| 绘图变量/来源 | [`plot_data/F149.json`](plot_data/F149.json) |
| 源文件 | [`experiment/data/cleaned/boxes.csv`](experiment/data/cleaned/boxes.csv)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv)<br>[`experiment/src/config.py`](experiment/src/config.py)<br>[`experiment/src/physics.py`](experiment/src/physics.py) |
| 论文图件副本 | [`overleaf/figures/F149.pdf`](overleaf/figures/F149.pdf) |

**取数及计算位置：**与F148共享32–45行网格；contourf/contour与边界标签56行；真实点及坐标57行。

**建议改动的位置：**levels、色带、边界线宽、clabel字体和色条位置；不移动真实能量边界。

**共享数据准备：**`viz/extras.py:32–45`与F148共用；保存为不同图，不是分别独立的三次实验。

**绘图变量结构：**对象字段：`route`、`model`、`payload_grid_kg`、`cruise_altitude_grid_m`、`energy_grid_kwh`、`energy_budget_kwh`、`actual_S008_point`、`kind`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P01-B；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F149  # 先按第2.3节保存辅助脚本
```
**含义边界：**固定S008的真实距离与两端作业高度；载荷和巡航海拔为确定性模型扫参，非新增现场试验或正式排程。只基准海拔对应题定巡航规则。；红线由同一网格方程确定，不人为绘制。

<a id="F150"></a>
### F150｜巡航海拔改变时的载荷—能耗截面

**图形类型：**同网格三条能耗截面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **59–63** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F150'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F150.png`](figures/F150.png) · [`figures/F150.pdf`](figures/F150.pdf) · [`figures/F150.svg`](figures/F150.svg) |
| 绘图变量/来源 | [`plot_data/F150.json`](plot_data/F150.json) |
| 源文件 | [`experiment/data/cleaned/boxes.csv`](experiment/data/cleaned/boxes.csv)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/results/q1/route_geometry.csv`](experiment/results/q1/route_geometry.csv)<br>[`experiment/src/config.py`](experiment/src/config.py)<br>[`experiment/src/physics.py`](experiment/src/physics.py) |
| 论文图件副本 | [`overleaf/figures/F150.pdf`](overleaf/figures/F150.pdf) |

**取数及计算位置：**32–45行为共享网格；60–61行选择三条海拔截面；62行为任务能量上限。

**建议改动的位置：**截面颜色、图例、线宽；选择不同海拔会改变诊断条件，需同步说明。

**共享数据准备：**`viz/extras.py:32–45`与F148共用；保存为不同图，不是分别独立的三次实验。

**绘图变量结构：**列表（3项），单项字段：`cruise_altitude_m`、`payload_kg`、`energy_kwh`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P01-C；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F150  # 先按第2.3节保存辅助脚本
```
**含义边界：**固定S008的真实距离与两端作业高度；载荷和巡航海拔为确定性模型扫参，非新增现场试验或正式排程。只基准海拔对应题定巡航规则。

<a id="F151"></a>
### F151｜返航余量下的跨服务区载荷分布

**图形类型：**小提琴轮廓+真实点+四分位线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **65–83** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F151'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F151.png`](figures/F151.png) · [`figures/F151.pdf`](figures/F151.pdf) · [`figures/F151.svg`](figures/F151.svg) |
| 绘图变量/来源 | [`plot_data/F151.json`](plot_data/F151.json) |
| 源文件 | [`experiment/results/q1/capacity_sensitivity.csv`](experiment/results/q1/capacity_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F151.pdf`](overleaf/figures/F151.pdf) |

**取数及计算位置：**65–67行取C型4档×15服务区；69–73行KDE轮廓；74–79行实点与分位线；80行统计导出。

**建议改动的位置：**小提琴半宽、透明度、实点避让、散点面积、分位线、KDE带宽；点数量与载荷不得造假。

**绘图变量结构：**对象字段：`records`、`statistics`、`kde`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P02-A；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F151  # 先按第2.3节保存辅助脚本
```
**含义边界：**跨服务区确定性横截面，不是15次独立随机试验。Scott带宽KDE仅为轮廓，裁在实际极值；散点等距横向避让不改变载荷。

<a id="F152"></a>
### F152｜15个服务区的安全载荷敏感性

**图形类型：**15×4安全载荷热图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **84–87** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F152'` |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **57–72** 行 `heatmap()` |
| 输出图片 | [`figures/F152.png`](figures/F152.png) · [`figures/F152.pdf`](figures/F152.pdf) · [`figures/F152.svg`](figures/F152.svg) |
| 绘图变量/来源 | [`plot_data/F152.json`](plot_data/F152.json) |
| 源文件 | [`experiment/results/q1/capacity_sensitivity.csv`](experiment/results/q1/capacity_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F152.pdf`](overleaf/figures/F152.pdf) |

**取数及计算位置：**84行把同一rr构造成服务区×余量矩阵；85行断言单调不增；86行调用heatmap。

**建议改动的位置：**heatmap色阶、数字大小、颜色条；不能用插值造服务区。

**共享数据准备：**`viz/extras.py:65–67`使用C型4档×15个服务区；代码中15/4及色阶有固定写法，仅更改RESERVE_LEVELS长度会需要联动调整矩阵、刻度和验证。

**绘图变量结构：**对象字段：`services`、`reserve_levels`、`capacity_kg`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P02-B；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F152  # 先按第2.3节保存辅助脚本
```
**含义边界：**每个色块为一次已完成能力计算；不对离散服务区做二维平滑插值。

<a id="F153"></a>
### F153｜安全载荷的经验累计分布

**图形类型：**经验累计分布。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **88–92** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F153'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F153.png`](figures/F153.png) · [`figures/F153.pdf`](figures/F153.pdf) · [`figures/F153.svg`](figures/F153.svg) |
| 绘图变量/来源 | [`plot_data/F153.json`](plot_data/F153.json) |
| 源文件 | [`experiment/results/q1/capacity_sensitivity.csv`](experiment/results/q1/capacity_sensitivity.csv) |
| 论文图件副本 | [`overleaf/figures/F153.pdf`](overleaf/figures/F153.pdf) |

**取数及计算位置：**65–67行生成原始横截面；89–90行排序并按15个样本形成阶梯。

**建议改动的位置：**阶梯颜色、线型与图例；保留经验分布阶梯，不改为虚构连续概率密度。

**共享数据准备：**`viz/extras.py:65–67`使用C型4档×15个服务区；代码中15/4及色阶有固定写法，仅更改RESERVE_LEVELS长度会需要联动调整矩阵、刻度和验证。

**绘图变量结构：**对象字段：`reserve_levels`、`samples`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P02-C；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F153  # 先按第2.3节保存辅助脚本
```
**含义边界：**经验分布仅对应15个给定服务区；没有概率外推，不生成随机样本。

<a id="F154"></a>
### F154｜异构机型载荷—等效航程关系

**图形类型：**三机型等效航程曲线。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **93–97** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F154'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F154.png`](figures/F154.png) · [`figures/F154.pdf`](figures/F154.pdf) · [`figures/F154.svg`](figures/F154.svg) |
| 绘图变量/来源 | [`plot_data/F154.json`](plot_data/F154.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/src/config.py`](experiment/src/config.py)<br>[`experiment/src/physics.py`](experiment/src/physics.py) |
| 论文图件副本 | [`overleaf/figures/F154.pdf`](overleaf/figures/F154.pdf) |

**取数及计算位置：**94–95行逐机型扫描0至额定载荷，调用effective_range；源公式位于experiment/src/physics.py。

**建议改动的位置：**MODEL颜色、线宽、端点标记、图例；等效航程不是往返服务半径。

**绘图变量结构：**列表（3项），单项字段：`model`、`payload_kg`、`effective_range_km`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**当前P01–P06未使用本图。

**单图命令：**
```bash
python redraw_selected_local.py F154  # 先按第2.3节保存辅助脚本
```
**含义边界：**由源题载荷指数关系计算；不是模型非支配前沿，也不是最大安全往返距离。

<a id="F155"></a>
### F155｜实际需求的空间位置与时间要求

**图形类型：**实际需求地理气泡图。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **98–113** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F155'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F155.png`](figures/F155.png) · [`figures/F155.pdf`](figures/F155.pdf) · [`figures/F155.svg`](figures/F155.svg) |
| 绘图变量/来源 | [`plot_data/F155.json`](plot_data/F155.json) |
| 源文件 | [`experiment/data/cleaned/boxes.csv`](experiment/data/cleaned/boxes.csv)<br>[`experiment/data/cleaned/geospatial/dem_clean.tif`](experiment/data/cleaned/geospatial/dem_clean.tif)<br>[`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json) |
| 论文图件副本 | [`overleaf/figures/F155.pdf`](overleaf/figures/F155.pdf) |

**取数及计算位置：**99行按服务区聚合货重、最早期望；103行面积weights×2.7、颜色deadline；105–111行标签/图例。

**建议改动的位置：**气泡面积比例、ENERGY.reversed色带、标签偏移、图例、底图；不生成连续热区。

**绘图变量结构：**对象字段：`nodes`、`routes`、`relays`、`groups`、`dem_extent`、`display_extent`、`dem_minmax_m`、`service_id`、`weight_kg`、`earliest_expected_min`、`marker_area_points2`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P03-A；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F155  # 先按第2.3节保存辅助脚本
```
**含义边界：**只绘制真实服务节点；符号面积正比货重、颜色代表本区最早期望时间。DEM为原高程，不建立无数据支持的连续需求热力场。

<a id="F156"></a>
### F156｜按期望送达时刻累计的物资需求

**图形类型：**按期望时间的累计需求阶梯。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **114–118** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F156'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F156.png`](figures/F156.png) · [`figures/F156.pdf`](figures/F156.pdf) · [`figures/F156.svg`](figures/F156.svg) |
| 绘图变量/来源 | [`plot_data/F156.json`](plot_data/F156.json) |
| 源文件 | [`experiment/data/cleaned/boxes.csv`](experiment/data/cleaned/boxes.csv) |
| 论文图件副本 | [`overleaf/figures/F156.pdf`](overleaf/figures/F156.pdf) |

**取数及计算位置：**115–116行按物资类别与expected_s排序，累计weight_kg。

**建议改动的位置：**MATERIAL颜色、阶梯线型、图例；不是实际交付进度或需求到达过程。

**绘图变量结构：**列表（4项），单项字段：`material`、`expected_time_min`、`cumulative_weight_kg`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P03-D；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F156  # 先按第2.3节保存辅助脚本
```
**含义边界：**需求累计曲线，不是实际交付曲线、需求到达过程或一天24小时预测。

<a id="F157"></a>
### F157｜服务区—物资类别的真实需求矩阵

**图形类型：**真实质量需求矩阵。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **119–121** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F157'` |
| 共用绘图实现 | [`viz/redraw.py`](viz/redraw.py) 第 **57–72** 行 `heatmap()` |
| 输出图片 | [`figures/F157.png`](figures/F157.png) · [`figures/F157.pdf`](figures/F157.pdf) · [`figures/F157.svg`](figures/F157.svg) |
| 绘图变量/来源 | [`plot_data/F157.json`](plot_data/F157.json) |
| 源文件 | [`experiment/data/cleaned/boxes.csv`](experiment/data/cleaned/boxes.csv) |
| 论文图件副本 | [`overleaf/figures/F157.pdf`](overleaf/figures/F157.pdf) |

**取数及计算位置：**继承114行boxes；119行聚合service_id×material_type重量；120行调用heatmap。

**建议改动的位置：**色带、数字格式、标签；不得把真实0类需求插值补成非零。

**绘图变量结构：**对象字段：`service_ids`、`materials`、`weight_kg`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P03-C；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F157  # 先按第2.3节保存辅助脚本
```
**含义边界：**质量由80箱逐箱汇总，总质量758 kg。空类别为真实0，不是缺失插值。

<a id="F158"></a>
### F158｜五个已计算Q3候选的三指标位置

**图形类型：**Q3候选三维散点。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **122–133** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F158'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F158.png`](figures/F158.png) · [`figures/F158.pdf`](figures/F158.pdf) · [`figures/F158.svg`](figures/F158.svg) |
| 绘图变量/来源 | [`plot_data/F158.json`](plot_data/F158.json) |
| 源文件 | [`experiment/results/q3/closure_existing_candidates.csv`](experiment/results/q3/closure_existing_candidates.csv) |
| 论文图件副本 | [`overleaf/figures/F158.pdf`](overleaf/figures/F158.pdf) |

**取数及计算位置：**123行读取5个候选；124–130行合并同坐标编号并保留真实记录；131行视角。

**建议改动的位置：**view_init、box_aspect、星标/圆点/叉号、编号标签；不能补成密集点云。

**绘图变量结构：**对象字段：`records`、`index`、`energy_kwh`、`makespan_min`、`sorties_total`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P04-A；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F158  # 先按第2.3节保存辅助脚本
```
**含义边界：**恰好5个已计算候选；编号对应绘图数据行；部分点同坐标重合。不是全局帕累托前沿，不补造迭代点云。

<a id="F159"></a>
### F159｜实际搜索日志中的时间—能耗轨迹

**图形类型：**实算搜索时间—能耗轨迹。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **134–138** 行，函数`make_extras()` |
| 检索键 | `store(pub,'F159'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F159.png`](figures/F159.png) · [`figures/F159.pdf`](figures/F159.pdf) · [`figures/F159.svg`](figures/F159.svg) |
| 绘图变量/来源 | [`plot_data/F159.json`](plot_data/F159.json) |
| 源文件 | [`experiment/results/q2/multipoint_search_rounds.csv`](experiment/results/q2/multipoint_search_rounds.csv) |
| 论文图件副本 | [`overleaf/figures/F159.pdf`](overleaf/figures/F159.pdf) |

**取数及计算位置：**134行区分初始化与顺序改进；135–137行点、先后连线、轮次色条。

**建议改动的位置：**散点面积、轮次色带、虚线、色条；只显示已保存日志，不虚构迭代历史。

**绘图变量结构：**对象字段：`warmup`、`sequential_refinement`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P04-C；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F159  # 先按第2.3节保存辅助脚本
```
**含义边界：**仅展示日志已保存的各轮结果，不是每个候选移动的点云；折线只连接记录先后，不代表连续可行前沿。

<a id="F160"></a>
### F160｜Q3-T-016：任务能耗与两阶段充电

**图形类型：**阶段模型SOC与两阶段充电。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **158–159** 行，函数`make_states()` |
| 检索键 | `store(pub,'F160'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F160.png`](figures/F160.png) · [`figures/F160.pdf`](figures/F160.pdf) · [`figures/F160.svg`](figures/F160.svg) |
| 绘图变量/来源 | [`plot_data/F160.json`](plot_data/F160.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/data/cleaned/transport_batteries.csv`](experiment/data/cleaned/transport_batteries.csv)<br>[`experiment/results/q3/battery_cycles.csv`](experiment/results/q3/battery_cycles.csv)<br>[`experiment/results/q3/communication_atoms.csv`](experiment/results/q3/communication_atoms.csv)<br>[`experiment/results/q3/legs.csv`](experiment/results/q3/legs.csv)<br>[`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F160.pdf`](overleaf/figures/F160.pdf) |

**取数及计算位置：**141–157行共用真实架次/电池/相位数据与SOC推导；158行三段曲线。

**建议改动的位置：**任务/快充/慢充配色、返回虚线、20%线、图例；SOC是模型值非遥测。

**共享数据准备：**`viz/extras.py:141–157`；`STATE_TRIP`位于第23行。P05由这四图组合，切换展示架次时四张应一起生成，并重新核验。

**绘图变量结构：**对象字段：`trip`、`battery_cycle`、`phase_energy`、`time_s`、`soc_percent`、`charge_t90_s`、`phase_heights`、`load_phases`、`communication_atoms`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P05-B；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F160  # 先按第2.3节保存辅助脚本
```
**含义边界：**分阶段均匀能量累计由同一能耗公式推导，非电流遥测。下降/交接附加能耗按题定简化模型为0；末尾为本电池充满时间，非任务完工。

<a id="F161"></a>
### F161｜Q3-T-016：完成站点交接后的剩余载荷

**图形类型：**交接后剩余载荷阶梯。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **160–164** 行，函数`make_states()` |
| 检索键 | `store(pub,'F161'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F161.png`](figures/F161.png) · [`figures/F161.pdf`](figures/F161.pdf) · [`figures/F161.svg`](figures/F161.svg) |
| 绘图变量/来源 | [`plot_data/F161.json`](plot_data/F161.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/data/cleaned/transport_batteries.csv`](experiment/data/cleaned/transport_batteries.csv)<br>[`experiment/results/q3/battery_cycles.csv`](experiment/results/q3/battery_cycles.csv)<br>[`experiment/results/q3/communication_atoms.csv`](experiment/results/q3/communication_atoms.csv)<br>[`experiment/results/q3/legs.csv`](experiment/results/q3/legs.csv)<br>[`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F161.pdf`](overleaf/figures/F161.pdf) |

**取数及计算位置：**141–157行共享输入；160–163行按handoff_complete_s形成step。

**建议改动的位置：**阶梯线/填充、ylabel、返回时刻线；不虚构交接中间每箱释放过程。

**共享数据准备：**`viz/extras.py:141–157`；`STATE_TRIP`位于第23行。P05由这四图组合，切换展示架次时四张应一起生成，并重新核验。

**绘图变量结构：**对象字段：`time_min`、`remaining_payload_kg`、`trip`、`legs`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P05-C；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F161  # 先按第2.3节保存辅助脚本
```
**含义边界：**卸货以站点交接完成为阶跃；用于航段能耗的载荷，不推断交接期间每箱释放过程。

<a id="F162"></a>
### F162｜Q3-T-016：全飞行与交接区间通信切换

**图形类型：**同架次通信提供者时间条。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **165–170** 行，函数`make_states()` |
| 检索键 | `store(pub,'F162'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F162.png`](figures/F162.png) · [`figures/F162.pdf`](figures/F162.pdf) · [`figures/F162.svg`](figures/F162.svg) |
| 绘图变量/来源 | [`plot_data/F162.json`](plot_data/F162.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/data/cleaned/transport_batteries.csv`](experiment/data/cleaned/transport_batteries.csv)<br>[`experiment/results/q3/battery_cycles.csv`](experiment/results/q3/battery_cycles.csv)<br>[`experiment/results/q3/communication_atoms.csv`](experiment/results/q3/communication_atoms.csv)<br>[`experiment/results/q3/legs.csv`](experiment/results/q3/legs.csv)<br>[`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F162.pdf`](overleaf/figures/F162.pdf) |

**取数及计算位置：**141–157行共享输入；165–168行筛提供者并画正长度区间；169行共享时间轴。

**建议改动的位置：**通信行高、提供者标签、直连/中继色；准备和返航后空白不等于任务中断。

**共享数据准备：**`viz/extras.py:141–157`；`STATE_TRIP`位于第23行。P05由这四图组合，切换展示架次时四张应一起生成，并重新核验。

**绘图变量结构：**对象字段：`providers`、`atoms`、`horizon_min`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P05-D；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F162  # 先按第2.3节保存辅助脚本
```
**含义边界：**空白仅为准备、返回后充电等无本运输任务通信需求时段；正长度通信区间直接取最终结果，边界点另行验证。

<a id="F163"></a>
### F163｜Q3-T-016：与能源、通信对齐的飞行剖面

**图形类型：**同架次高度剖面。

| 定位项目 | 位置或说明 |
|---|---|
| 生成主位置 | [`viz/extras.py`](viz/extras.py) 第 **171–175** 行，函数`make_states()` |
| 检索键 | `store(pub,'F163'` |
| 共用绘图实现 | 图形对象直接在该分支中创建；仍使用`viz/style.py`与`Publisher.save()`。 |
| 输出图片 | [`figures/F163.png`](figures/F163.png) · [`figures/F163.pdf`](figures/F163.pdf) · [`figures/F163.svg`](figures/F163.svg) |
| 绘图变量/来源 | [`plot_data/F163.json`](plot_data/F163.json) |
| 源文件 | [`experiment/data/cleaned/model_inputs.json`](experiment/data/cleaned/model_inputs.json)<br>[`experiment/data/cleaned/transport_batteries.csv`](experiment/data/cleaned/transport_batteries.csv)<br>[`experiment/results/q3/battery_cycles.csv`](experiment/results/q3/battery_cycles.csv)<br>[`experiment/results/q3/communication_atoms.csv`](experiment/results/q3/communication_atoms.csv)<br>[`experiment/results/q3/legs.csv`](experiment/results/q3/legs.csv)<br>[`experiment/results/q3/trajectory_phases.csv`](experiment/results/q3/trajectory_phases.csv)<br>[`experiment/results/q3/trips.csv`](experiment/results/q3/trips.csv) |
| 论文图件副本 | [`overleaf/figures/F163.pdf`](overleaf/figures/F163.pdf) |

**取数及计算位置：**141–157行共享输入；172–173行按PHASE画高度；174行共享时间范围。

**建议改动的位置：**阶段配色、线宽和图例；P05要求与其他三个状态图时间轴对齐。

**共享数据准备：**`viz/extras.py:141–157`；`STATE_TRIP`位于第23行。P05由这四图组合，切换展示架次时四张应一起生成，并重新核验。

**绘图变量结构：**对象字段：`trip`、`battery_cycle`、`phase_energy`、`time_s`、`soc_percent`、`charge_t90_s`、`phase_heights`、`load_phases`、`communication_atoms`。

**当前论文：**`main.tex`未直接调用这张F图；PDF已在`overleaf/figures/`，可新增插图环境。
**组合关系：**P05-A；改本图后须运行`python -m viz.compose`再复制对应P图。

**单图命令：**
```bash
python redraw_selected_local.py F163  # 先按第2.3节保存辅助脚本
```
**含义边界：**与F160-F162共享完整时间轴；返航后不绘制虚构空中轨迹。

<a id="panels"></a>
## 七、P01–P06组合图布局位置

这六幅不是在一个Matplotlib函数内直接绘制所有统计对象，而是`viz/compose.py`用PyMuPDF把独立F图PDF**按原生矢量页面组合**。所以：改曲线/坐标/统计对象去对应F图代码，改A/B/C/D相对摆位去`PANELS`，两者不能混改。目标矩形是`(x0, y0, x1, y1)`、单位为PDF点；原点在页左上，y向下。

<a id="P01"></a>
### P01｜地形—载荷—能耗的条件响应

**布局定义：**[`viz/compose.py`](viz/compose.py) 第 **9–10** 行，`PANELS`列表。共用组合函数第23–51行；输出第43–46行；图集与组合清单第49–50行。

| 子图字母 | 来源F图 | 图题 | 配置目标矩形（pt） |
|---|---|---|---|
| A | [F148](#F148) | C型载荷—巡航海拔能耗响应（模型扫参） | (115, 12, 775, 432) |
| B | [F149](#F149) | 同一能耗曲面的可行域投影 | (35, 456, 430, 775) |
| C | [F150](#F150) | 巡航海拔改变时的载荷—能耗截面 | (455, 456, 850, 775) |

**当前页大小：**885×805 pt。子PDF会保留纵横比，并在目标矩形内顶部对齐、横向居中；不会强制拉伸填满矩形。

**论文使用位置：**默认`main.tex`未插入；可选段位于`overleaf/optional_panels.tex:3–7`，标签为`fig:P01`。组图PDF副本为`overleaf/figures/P01.pdf`。

**输出：**[`figures/P01.png`](figures/P01.png) · [`figures/P01.pdf`](figures/P01.pdf) · [`figures/P01.svg`](figures/P01.svg)；组合成员与说明见[`audit/panels_manifest.json`](audit/panels_manifest.json)。组合图无独立`plot_data/Pxx.json`，数据分别追溯到各个F图。

**重建步骤：**
```bash
# 先重画有变动的子图；需要时用第2.3节辅助脚本
python redraw_selected_local.py F148 F149 F150
python -m viz.compose
```
**解释边界：**上图与两个截面来自同一确定性模型网格。固定S008距离和端点，仅基准巡航海拔为题定任务；不是现场数据或新调度结果。

<a id="P02"></a>
### P02｜返航安全余量与运输能力

**布局定义：**[`viz/compose.py`](viz/compose.py) 第 **11–12** 行，`PANELS`列表。共用组合函数第23–51行；输出第43–46行；图集与组合清单第49–50行。

| 子图字母 | 来源F图 | 图题 | 配置目标矩形（pt） |
|---|---|---|---|
| A | [F151](#F151) | 返航余量下的跨服务区载荷分布 | (35, 12, 535, 342) |
| B | [F152](#F152) | 15个服务区的安全载荷敏感性 | (575, 12, 985, 418) |
| C | [F153](#F153) | 安全载荷的经验累计分布 | (35, 453, 535, 770) |
| D | [F007](#F007) | 第一问：安全余量与最少架次数 | (575, 453, 1075, 770) |

**当前页大小：**1110×805 pt。子PDF会保留纵横比，并在目标矩形内顶部对齐、横向居中；不会强制拉伸填满矩形。

**论文使用位置：**默认`main.tex`未插入；可选段位于`overleaf/optional_panels.tex:9–13`，标签为`fig:P02`。组图PDF副本为`overleaf/figures/P02.pdf`。

**输出：**[`figures/P02.png`](figures/P02.png) · [`figures/P02.pdf`](figures/P02.pdf) · [`figures/P02.svg`](figures/P02.svg)；组合成员与说明见[`audit/panels_manifest.json`](audit/panels_manifest.json)。组合图无独立`plot_data/Pxx.json`，数据分别追溯到各个F图。

**重建步骤：**
```bash
# 先重画有变动的子图；需要时用第2.3节辅助脚本
python redraw_selected_local.py F151 F152 F153 F007
python -m viz.compose
```
**解释边界：**小提琴为每档15个服务区的C型确定性横截面，实点与四分位线均来自结果。敏感性从20%开始；不可行档位不记为0。

<a id="P03"></a>
### P03｜需求空间分布与物资组成

**布局定义：**[`viz/compose.py`](viz/compose.py) 第 **13–14** 行，`PANELS`列表。共用组合函数第23–51行；输出第43–46行；图集与组合清单第49–50行。

| 子图字母 | 来源F图 | 图题 | 配置目标矩形（pt） |
|---|---|---|---|
| A | [F155](#F155) | 实际需求的空间位置与时间要求 | (35, 12, 450, 385) |
| B | [F012](#F012) | 数据核查：全部货箱按服务区分布 | (475, 15, 885, 298) |
| C | [F157](#F157) | 服务区—物资类别的真实需求矩阵 | (35, 412, 445, 835) |
| D | [F156](#F156) | 按期望送达时刻累计的物资需求 | (475, 422, 885, 705) |

**当前页大小：**920×860 pt。子PDF会保留纵横比，并在目标矩形内顶部对齐、横向居中；不会强制拉伸填满矩形。

**论文使用位置：**默认`main.tex`未插入；可选段位于`overleaf/optional_panels.tex:15–19`，标签为`fig:P03`。组图PDF副本为`overleaf/figures/P03.pdf`。

**输出：**[`figures/P03.png`](figures/P03.png) · [`figures/P03.pdf`](figures/P03.pdf) · [`figures/P03.svg`](figures/P03.svg)；组合成员与说明见[`audit/panels_manifest.json`](audit/panels_manifest.json)。组合图无独立`plot_data/Pxx.json`，数据分别追溯到各个F图。

**重建步骤：**
```bash
# 先重画有变动的子图；需要时用第2.3节辅助脚本
python redraw_selected_local.py F155 F012 F157 F156
python -m viz.compose
```
**解释边界：**地图仅呈现真实离散服务节点，不制造连续需求热区；矩阵由80个真实货箱汇总。累计需求按期望时刻统计，不是实际交付或到达率。

<a id="P04"></a>
### P04｜已计算方案的多指标比较

**布局定义：**[`viz/compose.py`](viz/compose.py) 第 **15–16** 行，`PANELS`列表。共用组合函数第23–51行；输出第43–46行；图集与组合清单第49–50行。

| 子图字母 | 来源F图 | 图题 | 配置目标矩形（pt） |
|---|---|---|---|
| A | [F158](#F158) | 五个已计算Q3候选的三指标位置 | (90, 10, 780, 433) |
| B | [F147](#F147) | 闭环筛选：独立Q3候选的严格三分区兼容性 | (35, 456, 430, 751) |
| C | [F159](#F159) | 实际搜索日志中的时间—能耗轨迹 | (455, 456, 850, 751) |

**当前页大小：**885×780 pt。子PDF会保留纵横比，并在目标矩形内顶部对齐、横向居中；不会强制拉伸填满矩形。

**论文使用位置：**默认`main.tex`未插入；可选段位于`overleaf/optional_panels.tex:21–25`，标签为`fig:P04`。组图PDF副本为`overleaf/figures/P04.pdf`。

**输出：**[`figures/P04.png`](figures/P04.png) · [`figures/P04.pdf`](figures/P04.pdf) · [`figures/P04.svg`](figures/P04.svg)；组合成员与说明见[`audit/panels_manifest.json`](audit/panels_manifest.json)。组合图无独立`plot_data/Pxx.json`，数据分别追溯到各个F图。

**重建步骤：**
```bash
# 先重画有变动的子图；需要时用第2.3节辅助脚本
python redraw_selected_local.py F158 F147 F159
python -m viz.compose
```
**解释边界：**上图只含5个真实Q3候选，其中有同点重合；下图为已存的候选和搜索轮次，不扩充为虚假的种群点云或全局帕累托前沿。

<a id="P05"></a>
### P05｜单架次的时空—能源—通信状态

**布局定义：**[`viz/compose.py`](viz/compose.py) 第 **17–18** 行，`PANELS`列表。共用组合函数第23–51行；输出第43–46行；图集与组合清单第49–50行。

| 子图字母 | 来源F图 | 图题 | 配置目标矩形（pt） |
|---|---|---|---|
| A | [F163](#F163) | Q3-T-016：与能源、通信对齐的飞行剖面 | (40, 10, 820, 306) |
| B | [F160](#F160) | Q3-T-016：任务能耗与两阶段充电 | (40, 329, 820, 641) |
| C | [F161](#F161) | Q3-T-016：完成站点交接后的剩余载荷 | (40, 664, 820, 944) |
| D | [F162](#F162) | Q3-T-016：全飞行与交接区间通信切换 | (40, 967, 820, 1244) |

**特殊行为：**虽然上表是PANELS中的原始配置，实际执行第26–31行会重算P05所有纵坐标和整页高度，保留每张F图纵横比。有效横向范围为40–820，宽780；从y=12开始，逐图加高度和22点间距，页宽855。要改有效宽度/间距/页高，应修改此自动布局段，而不只是修改上表的矩形。F160–F163统一时间轴与留白由`viz/extras.py:25–27`及`viz/core.py:65–70`共同控制。

**论文使用位置：**默认`main.tex`未插入；可选段位于`overleaf/optional_panels.tex:27–31`，标签为`fig:P05`。组图PDF副本为`overleaf/figures/P05.pdf`。

**输出：**[`figures/P05.png`](figures/P05.png) · [`figures/P05.pdf`](figures/P05.pdf) · [`figures/P05.svg`](figures/P05.svg)；组合成员与说明见[`audit/panels_manifest.json`](audit/panels_manifest.json)。组合图无独立`plot_data/Pxx.json`，数据分别追溯到各个F图。

**重建步骤：**
```bash
# 先重画有变动的子图；需要时用第2.3节辅助脚本
python redraw_selected_local.py F163 F160 F161 F162
python -m viz.compose
```
**解释边界：**4幅图共享同一绝对时间范围，来源为Q3-T-016。SOC按模型分阶段累计并校验返航端点；末段显示电池充满，不把充电结束当作Q3完工。

<a id="P06"></a>
### P06｜严格三分区与独立资源需求

**布局定义：**[`viz/compose.py`](viz/compose.py) 第 **19–20** 行，`PANELS`列表。共用组合函数第23–51行；输出第43–46行；图集与组合清单第49–50行。

| 子图字母 | 来源F图 | 图题 | 配置目标矩形（pt） |
|---|---|---|---|
| A | [F128](#F128) | 第四问：严格不复制中继的3组分区 | (35, 12, 455, 374) |
| B | [F117](#F117) | 第四问：运输与中继依赖合并后的不可拆单元 | (480, 15, 890, 287) |
| C | [F132](#F132) | 第四问：3组独立配置需求与原库存 | (35, 403, 455, 743) |
| D | [F138](#F138) | 第四问：严格可行的全部4个分区比较 | (480, 403, 890, 697) |

**当前页大小：**925×768 pt。子PDF会保留纵横比，并在目标矩形内顶部对齐、横向居中；不会强制拉伸填满矩形。

**论文使用位置：**默认`main.tex`未插入；可选段位于`overleaf/optional_panels.tex:33–37`，标签为`fig:P06`。组图PDF副本为`overleaf/figures/P06.pdf`。

**输出：**[`figures/P06.png`](figures/P06.png) · [`figures/P06.pdf`](figures/P06.pdf) · [`figures/P06.svg`](figures/P06.svg)；组合成员与说明见[`audit/panels_manifest.json`](audit/panels_manifest.json)。组合图无独立`plot_data/Pxx.json`，数据分别追溯到各个F图。

**重建步骤：**
```bash
# 先重画有变动的子图；需要时用第2.3节辅助脚本
python redraw_selected_local.py F128 F117 F132 F138
python -m viz.compose
```
**解释边界：**保持最终Q3任务和通信关系不变。三组需求35件、分类型缺口7件；资源总件数不是采购成本，补足型号资源才可执行。

<a id="pitfalls"></a>
## 八、修改时最容易踩到的实际问题

| 情形 | 原因与处理 |
|---|---|
| 改了旧`experiment/src/paper_figures.py`，新图不变 | 这不是此次163图的活跃绘图器。改根目录`viz/redraw.py`/`extras.py`；旧工程只留存历史。 |
| 搜F049找不到函数 | F001–F147通过旧图名路由；按逐图条目搜`q2_01_routes.png`，不是寻找不存在的`draw_F049()`。 |
| 改root figure_catalog或plot_data，重画又复原 | 它们是输出。原始147图标题取自旧映射，但为避免改冻结目录，应在新绘图分支里作title覆盖。 |
| 仅改a.set_title，保存后不是该标题 | Publisher.save在core.py第64行重新设置title。改传入save的title；论文caption仍另行维护。 |
| 运行--only F151后文件没变 | 现有CLI只遍历原始147图并跳过extras；用第2.3节新增辅助脚本或直接make_extras。 |
| 一个图的样式改动影响很多图 | 共享函数/同分支；局部override按code限定。全局色彩变化本来就应重画全部相关图。 |
| 重画F图后P图仍旧 | P图是静态矢量组合；重新python -m viz.compose。 |
| P05调PANELS的y坐标无效果 | P05运行时重算布局；改compose第26–31行。 |
| PNG已变但论文没变 | PDF副本未同步；复制到overleaf/figures并上传同名文件；不要改PNG指望PDF自动更新。 |
| 重绘后论文修改消失 | sync_overleaf从audit/original_main.tex写回基准。自改正文后只复制PDF，不运行有同步的完整入口。 |
| 图很清楚但放进论文后小 | main.tex第59–63行paperfig宏限制最大高度.39\textheight；调整LaTeX宽高/分图布局，而非改变数值。 |
| 新增或删减场景后旧验证失败 | 有163/15/4/80/5等固定数量及哈希基准；外观改动不应改场景。科学含义改变后需同步新实验、文稿和独立核验，不可仅放宽断言。 |
| 修改后仍拿旧ZIP/旧检查次数当新交付 | 原ZIP和审查文件是旧快照；保存修改图、刷新核验并重新归档。说明哪些部分只改风格、哪些改变了统计表达。 |

### 推荐逐图修改记录
```markdown
### F049 修改记录
- 修改文件/函数：viz/redraw.py，redraw_one / plot_map
- 外观调整：线宽、颜色、标签偏移、图例、画布比例
- 数值/单位/样本/过滤规则是否变化：否
- 已重画文件：figures/F049.png、F049.svg、F049.pdf
- 是否影响组合图：按本说明组合关系检查
- 已复制到overleaf/figures：是/否
- 核验与实际查看记录：……
```

<a id="verify"></a>
## 九、本说明核对范围与版本指纹

本次按当前完整ZIP解压后的文件核对：163个独立图ID唯一且连续；每图三种格式、逐图JSON与Overleaf PDF副本存在；163图源记录中的路径均存在且与记录哈希一致；147个旧图名均唯一命中实际绘图分支；16个新增图的store调用位置明确；6个组合图的成员来自有效F图；29条论文图引用均能匹配到文件和代码。**这是定位文档的核对，不是重新优化四问，也不是对所有图形科学性作新一次完整认证。**

下列源码指纹可判断你本地的行号是否还与此文一致。源码不同后优先按函数和检索键定位，不应继续照搬行号。
| 相对路径 | SHA-256 |
|---|---|
| `redraw_figures.py` | `a6afd239ceebed04cc08ca50506c48a7863cb164222c540651bd8b22feb1d9ef` |
| `rebuild_publication.py` | `fd14493f23b66b0118b5790124feab1ca862005b54b60f30268fcfa34416b2bb` |
| `viz/redraw.py` | `28b01aea1c824aa8a8dbdf1a6ef9896c723f9a4a7d575a0470deecbf1ac895bf` |
| `viz/extras.py` | `9e2f789ae31ec9d5e40f606e85d1d643287b06a91be21f43c2be0e2fa1614ece` |
| `viz/style.py` | `f570a30c10977386e358b20fa3e65040ab254ed5772bbed534206934b4af07c4` |
| `viz/core.py` | `789d477efddd3fbfdb8ced5bd5c3bd74e1bb94f49ac5e51d477919f3e3b95b9e` |
| `viz/compose.py` | `9c36d0be2181874f3aeaace25c4f39c1b3e0fa656e545d4187cc1cc01f4a7291` |
| `sync_overleaf.py` | `d4335e981e9b078d3a6d6620c92af22a7b009dd8763a161cb39142b3aab383e0` |
| `validate_figures.py` | `b061d471b420261d29318b7a698f129187845d2be3851c1b85c7d9c97e46d818` |
| `overleaf/main.tex` | `bb7134aa72c8cb96c0e5c0a86f1f8934461de946c34f906c30e307042402a4ad` |
| `overleaf/optional_panels.tex` | `d7e63a2b18671d84916636d30883654fce4766485b9464f8685dc52812e01d0e` |

单图辅助脚本已在独立解压副本中实际测试F012、F151、F160，三张指定图均成功生成；测试未改动原始交付ZIP或用户的Overleaf工程。

来源：上述实际源码、根目录`figure_catalog.csv`、`plot_data/F001.json`至`F163.json`、`audit/panels_manifest.json`、`experiment/paper/figure_catalog.csv`及当前`overleaf/main.tex`。未引用参考示例图片中的数值作为实验结果。
