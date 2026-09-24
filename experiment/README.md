# D题：四问严格闭环验证、中文实验图与论文大纲（v2：第二问优化修订版）

> **v2 修订（本版）**：第二问主方案升级为 25 架次 / Cmax=6256.80 s / E=71.727 kWh（首版 26 架次 / 6355.09 s / 71.946 kWh，完整快照保留于 `results/q2/experiments/previous_release_main/`），并新增架次数—完工时间完整权衡前沿（N=18 为 Q1 精确 DP 容量下界且可达）。Excel、图件、报告、论文宏已全部按 v2 结果重建并重新通过全部独立复核。详见 `docs/13_Q2优化修订说明.docx`。其余三问结果不变。

本版重新审查并修复Q3→Q4的真实题意继承问题。旧Q4三组方案依赖额外中继副本，已不作为正式答案。现在在Q3定稿前筛选已实算并独立验证、支持严格三分区的候选，再将最终Q3冻结给Q4。Q4绝不复制、拆分、缩短或重排中继任务；源数据及Q1/Q2主数值保留。

## 必须明确的条件

最终Q3使用源库存即可执行。Q4表格是各组独立执行需要的资源数量，源库存并不足够，必须按类型增补，详见`results/q4/inventory_gap.csv`及`submission/提交必读.txt`。不同类型的冗余不能相互抵扣。两组和三组是两种替代配置，不是同时执行两倍任务。Q4两种分区的总能耗和最后返回均等于最终Q3，不再增加任何任务副本能耗。

Q1模型内精确，Q2/Q3是独立验证的启发式可行方案，未证明全局最优；Q4是固定最终Q3后的严格依赖图全枚举、固定区间最少资源配置。两个能耗分项、模板时间标题、局部三维坐标及DEM分片模型的补充解释明确列于报告，不当作原题唯一规则。

## 提交与论文素材

一起提交`submission/结果提交.xlsx`、`submission/Q3运输与逐箱补充.xlsx`、`submission/提交必读.txt`、解题报告及可运行程序。主模板保留原6张表名/列/单位；配套文件填原模板未提供的Q3运输与逐箱表，不覆盖Q2。原始数据19文件完整保留。

`docs/10_整体论文大纲与填充映射.docx`为整体论文大纲，`paper/论文大纲.md`是可编辑文本；收到LaTeX模板后据其章节、图表和结果映射填充。`paper/results_macros.tex`从当次JSON自动提取结果，不手工改数值。`paper/figure_catalog.csv`列出全部中文图、矢量PDF、源表及逐图绘图数据。

图件统一中文，每幅提供PNG、SVG、PDF。字库使用系统Noto Sans CJK/思源/黑体，缺字库时程序报错，不发布方框乱码；包内不分发字体文件。图多包含按区域/架次的诊断视图，不谎称每图为独立实验。失败压力场景保留，不能以删除失败点制造鲁棒性。

## 完整运行

实测Python3.13.5，依赖固定requirements.txt，首次安装需联网，计算可离线；无需GPU、商业求解器、MATLAB或Excel软件。XLSX由openpyxl每次从CSV重建，不依赖artifact_tool或旧表快照。

```bash
python -m pip install -r requirements.txt
python run_all.py --check-reference
python validate_submission.py
```

Windows运行`run_one_click.bat`，Linux/macOS运行`bash run_one_click.sh`。路径基于入口文件，不依赖当前工作目录。完整流程重建`data/cleaned`、`results`、`docs`、`paper`、`submission`，个人论文草稿勿放入这些自动目录。`data/raw`不改。参考值仅在求解结束后比对，不参与优化。

仅从本版已经冻结的Q3增量重做Q4：

```bash
python run_q4.py --check-reference
```

独立验收和打包：

```bash
python -m unittest discover -s tests -v
python package_delivery.py
```

## 目录与证据

`data/raw`原件；`data/cleaned`标准化数据；`results/quality`全量质量核查；`results/audit`源单元格/公式；`results/q1`至`q4`方案和独立检查；`results/closure`额外压力场景与35行题意追溯；`paper`大纲、结果宏与图源目录；`docs`12份Word/Markdown报告；`tests`正常与错误注入；`reference`最终结果基准与原版Q1/Q2/原数据哈希；`results/logs`复现和闭环门禁。

Q3的`alternatives`是实际已求解并核验的比较方案，不能与正式通信/分区混用。正式主方案是Q3目录根文件，源哈希由Q4记录。通信正长度行代表开区间，零时长“·边界点”代表唯一瞬时状态；两者共同满足连续约束，稠密点只是交叉检查。

Q1的累计完整作业时间不同于Q2最后运输返回和Q3最后联合返回。模板显示6位小数，但存储精确往返双精度；不能抄截图四舍五入值作为通信边界输入。验证通过只对题定确定性模型及所列资源条件有效，不构成现场安全认证。
