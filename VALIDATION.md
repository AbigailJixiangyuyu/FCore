# Demo 验证记录

## 无向图读取与展示

2026-11-22 使用原始 CSV 和逐行交换 `u`、`v` 的副本，比较单快照、历史聚合、四种历史挖掘、并行核分解接口和 TCCS 窗口。两套输入返回相同的图、统计和成员集合。SLADE 排名、Zebra 与 UnderGS 的成对概率及未来社区也完全一致。正常查询与预测禁止读取 S13 数据，兼容观测接口仅在主动调用时读取并按两端计数。

EmailDept3 的 S12 返回 **89 个节点、320 条无向边、1,208 次交互**。`q=49、k=7` 的当前查询为 **30 个节点、145 条边**。S10—S12 的 TCCS 结果为 52 人。Chrome 在 Vite 开发代理和 FastAPI 构建托管下均正确渲染无向图，社区边悬停可查看交互次数，异常账户可定位。

四份模型已在 RTX 5060 Laptop GPU 的 `cuda:0` 重训，检查权重恢复与评分一致后启用：

| 数据与模型 | 当前权重版本 | 核验结果 |
| --- | --- | --- |
| EmailDept3 SLADE | `slade-d73301cecdf93996` | 10 轮，S12 评分 88 人 |
| 合成样例 SLADE | `slade-bf2fec907f9ca6f5` | 10 轮，S12 评分 26 人 |
| EmailDept3 Zebra | `zebra-a55d8f6ef5de5b56` | S11 校准，S12 Brier 0.0515、对数损失 0.1941 |
| EmailDept3 UnderGS | `undergs-ea61cb576ce05a4b` | S11 校准，S12 Brier 0.0533、对数损失 0.2032 |

Zebra 默认 `q=49、k=4、阈值 0.50` 预测 **23 个节点、65 条边**。UnderGS 的新旧权重校验和一致，`k=4` 返回空社区，`k=3` 返回 **23 个节点、52 条边**。训练和回测范围沿用 S01—S12 的既定划分。

后端完整回归 48 项（含 CUDA 和 WSL）、前端 19 项测试及 Vite 生产构建均通过。

## 工程化重构

- 重构前后实际调用两套数据集的接口。除请求 ID 和耗时外，**49 个响应完全一致**，涵盖 OpenAPI、当前查询与兼容查询、四种历史算法、两种时间证据指标、SLADE、Zebra、UnderGS 及旧份额接口。正常路径未读取 S13；旧观测接口仅在显式调用时读取。Dept3 默认 S12 查询仍为 30 人、145 条无向内部边，两个预测模型均返回 435 对概率。
- 重新在导出目录生成两套数据，**36 个文件与现用数据逐字节相同**。现用数据、模型指针、权重和依赖锁文件保持原样。
- `test.ps1 -Full` 后端 **30 项**（13.45 秒，含 CUDA 和 WSL）、前端 **15 项**通过；生产构建通过。图表运行时的 Vite 体积提示仍存在。
- Vite 开发代理和 FastAPI 构建托管均通过 1440×900、1280×900 浏览器检查。面板尺寸、节点位置和边数与重构前一致；切换历史区间没有重复挖掘，异常定位不改变查询成员，切换预测模型保持成员坐标并显示 Top-10，页面未请求旧份额接口或 S13 数据。

记录：[接口基线](exports/engineering-refactor/api-before.json)、[重构后接口](exports/engineering-refactor/api-after.json)、[开发版验收](exports/engineering-refactor/after/browser.json)、[构建版验收](exports/engineering-refactor/hosted/browser.json)。截图：[当前 1440](exports/engineering-refactor/after/present-1440.png)、[当前 1280](exports/engineering-refactor/after/present-1280.png)、[历史聚合](exports/engineering-refactor/after/history-1440.png)、[UnderGS](exports/engineering-refactor/hosted/future-undergs-1440.png)。

另记一项既有可用性问题：首屏仍等待 `/api/capabilities`，而该接口会检查数据和模型。某个本地数据包缺帧时，能力检查失败可能阻止进入其他可用数据集。本次保持原启动行为，首屏与能力检查的解耦可单独处理。

## UnderGS 接入与双模型切换

验证日期：2026-11-17。Dept3 数据版本 `email-eu-core-dept3-v2-430dde7de92f`；新增并激活 **`undergs-d00b82e22d5c3ee9`**，原 Zebra **`zebra-96c7e13c15c0d1dc`** 保留。本节取代下方历史记录中“UnderGS 尚未接入”的状态；未来可切换两种模型，初始仍为 Zebra，显示固定 Top-10。

### 训练与论文核对

实际执行 `uv run --directory demo/backend python -m scripts.train_undergs --dataset email-eu-core-dept3`。Python 3.10.11、PyTorch 2.8.0+cu128、RTX 5060 Laptop GPU，cuda:0；完成 50 轮并采用第 50 轮，训练及校准耗时 **40.020 秒**，峰值显存分配 **71.73 MiB**，温度 **0.87073922**。节点表示和邻居库均在 GPU；源变换、邻居变换、更新层和预测头梯度有限且非零。保存恢复以及继续处理 S12 的 logits 精确一致后激活。

论文图 3 的重要性示例验证为 C1≈3.91、C2≈0.24；覆盖重复交互计数、无向两跳最短路径、跨快照邻居键、衰减、Top-K 同分和历史屏蔽。保留作者 GCN 的权重归一化，修正邻居状态未写回与编码器梯度截断；差异完整记录在 [UnderGS 实现说明](backend/algorithms/link_prediction/undergs/README.md)。使用下一快照标签、全部候选 BCE、对称 logit 和温度属于项目适配。

训练标签 S02—S09，S10 选模，S11 校准，S12 仅作冻结回测，页面输入推进至 S12 后预测 S13。测试验证验证／校准标签不更新编码器，以及训练不读 S12、整个流程不读 S13。原始数据、依赖配置、两个锁文件和 Python 版本保持不变，原 Zebra 指针及权重版本保留。

### S12 独立回测

完整候选共 3,828 对，320 个正例，正例率 8.359%；88 个截至观察截止已交互账户参与评分。

| 方法 | AP ↑ | ROC-AUC ↑ | Brier ↓ | 对数损失 ↓ |
|---|---:|---:|---:|---:|
| UnderGS | 0.147312 | 0.735381 | 0.076989 | 0.288972 |
| Zebra | 0.246564 | 0.786496 | 0.070002 | 0.247585 |
| 最近 S11 是否连接 | 0.334629 | 0.696563 | 0.064263 | 1.775662 |
| 最近三快照出现频率 | 0.511911 | 0.810107 | 0.049315 | 0.878433 |

UnderGS 当前排名效果低于 Zebra 和近期频率基线，未依据 S12 结果调参。已有连接组 188 对、131 个正例，AP=0.751276；未连接组 3,640 对、189 个正例，AP=0.086110。概率接近时仍保存原始精度，页面百分比显示可能相同。邮件网络结果不代表金融检测效果，也不用于宣称原论文性能。

### 工程验收

最终全量后端 **292 项测试通过**，前端 **15 项测试通过**，生产构建成功。覆盖权重缺失与恢复、损坏及非法预热状态、数据指纹冲突、CUDA 不可用、双模型独立状态、完整候选和跨社区一致性。修正了链接预测中成员顺序的规范化，成员增删仍拒绝。原历史算法、当前查询、SLADE 与 Zebra 回归通过。

真实服务返回默认 30 人社区的 435 对概率，查看账户 49 有 29 对；固定展示其中最高的 10 对。三次并发请求与重复请求完全相同，扩大社区时同一对账户概率不变；两个模型缓存独立。一次已缓存 UnderGS 请求约 57 ms，三次并发请求约 179—214 ms，仅记录本机本次观察，不作为性能保证。

浏览器 **29 项检查通过**，无运行时错误。通过实际下拉选项切换 UnderGS，社区、查看账户和节点坐标保持稳定；账户筛选无额外请求。强制 503 后清除旧边并可重试，延迟模型和旧社区响应不能覆盖当前选择。合成数据分别显示两种模型未就绪，不回退示例。开发代理与 FastAPI 构建托管均通过，未请求旧份额、观测或 S13 数据；1440×900、1920×1080、1280×900 桌面检查通过。

记录：[训练与实际接口](exports/undergs-2026-11-17/model-validation.json)、[训练日志](exports/undergs-2026-11-17/training.log)、[依赖哈希](exports/undergs-2026-11-17/dependency-verification.json)、[浏览器验收](exports/undergs-2026-11-17/browser-validation.json)。截图：[1440 UnderGS](exports/undergs-2026-11-17/future-undergs-top10-1440.png)、[1920](exports/undergs-2026-11-17/future-top10-1920.png)、[1280](exports/undergs-2026-11-17/future-top10-1280.png)、[失败重试](exports/undergs-2026-11-17/prediction-error-1440.png)、[未训练数据集](exports/undergs-2026-11-17/untrained-dataset-1440.png)、[构建托管](exports/undergs-2026-11-17/production-future-1440.png)。

## Zebra 链接预测接入与固定 Top-10 展示（前一阶段记录）

验证日期：2026-11-17。默认 Dept3 已启用 **`zebra-96c7e13c15c0d1dc`**，数据版本为 `email-eu-core-dept3-v2-430dde7de92f`。本节取代下方历史记录中未来份额、Top-3 和异常 Top-20 的界面口径；当前 03 固定显示异常程度前 10 个账户，未来固定显示查看账户概率最高的 10 条连边，不提供数量选择，不足 10 条时全部显示。UnderGS 保留为“尚未接入”的禁用选项。

### 训练与时间隔离

已实际执行 `uv run --directory demo/backend python -m scripts.train_zebra --dataset email-eu-core-dept3`。使用现有 Python 3.10、PyTorch 2.8.0+cu128、CUDA 12.8、RTX 5060 Laptop GPU，计算设备 cuda:0。最大 50 轮，第 35 轮早停，采用第 30 轮权重；训练约 685.77 秒，峰值显存分配 130.58 MiB，校准温度 1.06303012。

训练标签来自 S02—S09，S10 选择轮次，S11 校准；各输入包含截至前一快照的全部历史。固定参数重新回放至 S11，导出预热状态；S12 仅作独立回测及页面预测的观察历史，没有用于训练、选模或校准。所有步骤均未读取 S13 记录。保存恢复后的账户记忆与 T-PPR 一致，分别继续处理 S12 得到完全相同的 logits，核验后激活模型指针。

保留 Zebra 的 GRU、时间编码、SANTA、多组 T-PPR 聚合与 MLP；本项目的窗口标签、对称 logit、全部候选 BCE 和温度校准均在 [算法适配说明](backend/algorithms/link_prediction/README.md) 中区分。标准库 SANTA 与作者实现的无截断小图逐项对照，最大误差 `1.39e-17`；指标与已安装 sklearn 在含并列分数的样本上核对至 `1e-12`，未增加运行依赖。GRU、聚合变换与成对预测层均获得有限且非零梯度。

### 独立 S12 回测

截至 S11 有 88 个已交互账户、3,828 个候选对；S12 正例 320 个，占 8.36%。全部候选参与评价，自环排除，已存在连接与未连接账户对均包括在内。

| 方法 | AP ↑ | ROC-AUC ↑ | Brier ↓ | 对数损失 ↓ |
| --- | ---: | ---: | ---: | ---: |
| Zebra＋温度校准 | 0.246564 | 0.786496 | 0.070002 | 0.247585 |
| 最近快照 S11 是否有边 | 0.334629 | 0.696563 | 0.064263 | 1.775662 |
| 最近三快照有交互的频率 | 0.511911 | 0.810107 | 0.049315 | 0.878433 |

近期频率基线的 AP、AUC、Brier 优于当前 Zebra；Zebra 的对数损失更低。二值与频率基线包含 0／1，对数损失按 `1e-12` 裁剪后计算。不能据此宣称 Zebra 优于基线，也没有利用 S12 结果继续选模或调参。报告另包含已有连接／未连接两组结果；后者 3,640 个候选、189 个正例，Zebra AP 为 0.1409。邮件数据上的效果不代表金融欺诈识别效果。

### 接口与界面

默认 q=49、k=7 社区仍为 30 人，接口返回 **435 个无序顶点对**；查看账户 49 有 29 个候选关系，页面仅绘制最高的 10 条。概率不按账户或社区归一化。全图编码与只读评分分离，候选边不进入记忆和 T-PPR。相同顶点对在不同社区得到相同概率；真实模型的重复请求及 3 个并发请求一致，已缓存请求约 236—250 毫秒。

全量后端 **275 项测试通过**；随后 Top-10 默认值调整的异常接口 **20 项复核通过**。前端 **15 项逻辑测试通过**，生产构建成功。后端覆盖时间边界、对称性、保存恢复、重复／并发一致、跨社区一致、冷启动账户、模型缺失／损坏／版本冲突／CUDA 不可用及恢复；前端覆盖固定 Top-10、原概率保留、旧响应隔离、稳定坐标及预测边悬停无箭头。保留既有大分块构建提示。

实际浏览器 **23 项检查通过**：开发代理和 FastAPI 构建托管均使用真实模型；03 恰有 10 行、02 默认 30 个节点与 10 条预测边，数量选择器已移除；切换查看账户不发预测请求、不移动节点。强制 503 时清除旧边，手动重试恢复；延迟的旧社区响应被取消或忽略。三人结构只显示两条连边。历史三方法仍返回 35／37／33 人，合成数据未训练 Zebra 时显示模型未就绪，不回退旧示例。没有旧份额／观测／S13 快照请求，没有浏览器运行时错误。1440×900、1920×1080、1280×900 桌面布局检查通过，未增加手机适配。

依赖配置与锁文件 SHA-256 和接入前完全一致：`backend/pyproject.toml`、`backend/uv.lock`、`backend/.python-version`、`frontend/package.json`、`frontend/package-lock.json` 均未改动。原始 CSV、SLADE 权重及历史算法未改动。

记录与截图：[训练及模型验证](exports/zebra-2026-11-17/model-validation.json)、[浏览器检查](exports/zebra-2026-11-17/browser-validation.json)、[当前排名](exports/zebra-2026-11-17/present-1440.png)、[Top-10 未来预测](exports/zebra-2026-11-17/future-top10-1440.png)、[1920](exports/zebra-2026-11-17/future-top10-1920.png)、[1280](exports/zebra-2026-11-17/future-top10-1280.png)、[失败状态](exports/zebra-2026-11-17/prediction-error-1440.png)、[未训练数据集](exports/zebra-2026-11-17/untrained-dataset-1440.png)、[构建托管](exports/zebra-2026-11-17/production-future-1440.png)。二进制权重、训练报告和截图按现有忽略规则保留在本地。

## 严格且非空的查询默认值

验证日期：2026-11-17。前端与 FastAPI 共用 `config/query-defaults.json`，各数据集保留原查询账户；当前局部 core、历史 k、周期相似度和密度采用经过实际计算验证的非空边界。爆发固定既定 l=3，将 δ 提高到三位小数输入精度下的最大非空值。用户明确提交的值优先，无结果时不自动放宽；最大核继续自动计算最高非空核。完整定义见 [默认配置说明](config/README.md)。

| Dept3 方法 | 当前默认条件 | 社区顶点数 |
| --- | --- | --- |
| 局部 core | q=49, k=7 | 30（原 57） |
| 最大核 | 自动 7-core | 30 |
| 密度 | ρ=1 | 6 个结构，每个 3 人 |
| 周期 | q=49, k=4, ε=1 | 35 |
| 持久 | q=49, k=15 | 37（原 73），持续 0 步 |
| 爆发 | l=3, δ=6.666 | 33（原 70） |

持久的 0 持续时间沿用已确认的有效解定义，不作隐藏或重新解释；若要求正持续时间，最高 k=13，返回 52 人、持续 1 步。局部 k=8、持久 k=16、爆发 δ=6.667 为空；周期 k=5、6 即使 ε=0 也为空，更高 k 超过逐快照 q 的 core 上界。周期边界针对当前 TD 实现，不宣称完整搜索的全局最优。合成数据局部／周期／持久仍用 k=4，周期 ε=1、爆发 l=3／δ=5，保持 5／5／6 人历史结果。

相关后端 **78 项测试通过**（9.32 秒），覆盖真实与合成数据、默认和明确参数一致、严格边界、部分参数覆盖、非法输入、成员与时间证据复核、旧宽松参数及未来数据隔离。前端 **12 项测试通过**，生产构建成功；Ruff E9/F/I 与格式检查通过。实际浏览器 **19 项检查通过**：开发与构建托管的默认查询、密度六个三人候选、三种历史结果、0 时长展示、过严条件空状态、30 人整社区悬停、固定 89 人布局、数据集切换恢复独立参数、合成未来 Top-3、现有 SLADE 就绪状态和 S13 隔离。仅检查桌面 1440px，无运行时异常。

配置调整未改交易 CSV、数据版本、快照边界、算法定义或模型权重。只更新推荐参数来源说明，不需重新训练。记录：[参数边界](exports/strict-defaults-2026-11-17/parameter-boundaries.json)、[页面检查](exports/strict-defaults-2026-11-17/checks.json)、[默认局部 core](exports/strict-defaults-2026-11-17/default-local-core-1440.png)、[整社区悬停](exports/strict-defaults-2026-11-17/default-local-core-hover-1440.png)、[密度](exports/strict-defaults-2026-11-17/default-density-1440.png)、[持久](exports/strict-defaults-2026-11-17/default-durable-1440.png)、[爆发](exports/strict-defaults-2026-11-17/default-burst-1440.png)、[构建托管](exports/strict-defaults-2026-11-17/built-default-local-core-hover-1440.png)。下方默认 57／73／70 人的描述为先前参数下的历史验收记录。

## 悬停突出整个所选社区

验证日期：2026-11-17。02 不再按悬停顶点的一跳邻居或单条边缩小强调范围。悬停当前所选社区的任一成员或内部边，统一突出该社区全部可见顶点及内部有向边，减淡背景节点、跨社区边和背景边；移开后恢复原始透明度和方向样式。历史聚合图、所选结构视图及未来预测图沿用同一成员口径。悬停不修改已提交查询、参数草稿、选中结构、节点位置或预测份额；背景元素继续提供账户／交易提示。

前端构建及 **12 项逻辑测试通过**，新增覆盖非相邻内部边、孤立成员、双向连接、跨社区边、无选中结果、恢复样式和预测 Top 份额。浏览器 **15 项检查通过**：S12 实际节点拾取后，57 个所选顶点和 417 条内部有向边全部强调，44 条其余边减淡；内部边事件强调同一完整社区。另覆盖历史 35 人社区、结构视图、无结果、合成未来 5 人／Top-3、提示内容、状态与坐标稳定，以及 FastAPI 构建托管页。未发起 S13 交易或观测份额请求，无运行时异常；仅检查桌面 1440px 界面。

记录见 [社区悬停检查](exports/community-hover-2026-11-17/checks.json)、[当前社区悬停](exports/community-hover-2026-11-17/community-node-hover-1440.png)、[历史社区悬停](exports/community-hover-2026-11-17/history-community-hover-1440.png)、[构建托管截图](exports/community-hover-2026-11-17/built-community-hover-1440.png)。下方“邻域悬停”描述为此前版本的历史行为。

## 仅保留桌面布局

验证日期：2026-11-17。按当前要求删除 700px／1100px 窄屏重排、手机字号与控件换行规则、触摸专用样式和移动端 viewport 配置。页面最小宽度固定为 1280px，01／02／03 保持三列，04 位于下方；小窗口采用横向滚动。保留 1280px 桌面紧凑间距和桌面高度调整。

前端生产构建及现有 **9 项逻辑测试通过**。浏览器验证开发页 1440px、1280px、1024px 窗口和 FastAPI 构建托管页 1440px：均保持三列，无面板重叠，S12 仍有 89 个节点、461 条有向边，默认查询仍选中 57 人；1024px 窗口保持 1280px 页面宽度并横向滚动，无运行时错误。记录见 [桌面检查](exports/desktop-layout-2026-11-17/checks.json)、[桌面截图](exports/desktop-layout-2026-11-17/desktop-1440.png)、[构建托管截图](exports/desktop-layout-2026-11-17/built-desktop-1440.png)。

下方手机宽度检查和截图均为此前版本的历史验收记录，当前版本仅维护桌面界面。

## 稳定力导向布局与结构聚焦

验证日期：2026-11-17。02 已替换按账户 ID 排圆周的呈现，采用固定历史参考图的 ForceAtlas2＋Noverlap。默认显示完整网络，支持“全图／所选结构”切换、节点与标签避让、邻域悬停、方向提示和键盘选择。参考固定 S01—S11，无向简单投影含 89 个节点、848 条连接；布局版本为 `history-fa2-linlog-500-noverlap-v1`，参考拓扑 SHA-256 为 `a0e3ced9a9722627e1311878d682f65de3aa96921c866121fe52e2e9f0aa4eb0`。

历史和现在共用坐标与完整图边界。时间范围、周期／持久／爆发方法、当前查询及异常选择均不重新启动布局 Worker；同一版本刷新页面或改用 FastAPI 构建托管产生相同坐标。S12 仍显示全部 89 个节点、461 条有向交易边、1,208 次交互；默认局部 core 仍是 57 人，结构视图有 417 条内部有向边，与查询统计的 283 条无向内部连接分别计数。历史三种默认结果仍为 35／73／70 人。原始 CSV、节点配置、数据版本、后端算法及 SLADE 权重均未改动。

前端 **9 项逻辑测试通过**，命令 `npm --prefix demo/frontend test`；覆盖规范化投影、指纹、确定性、空图／单点／孤立点／不连通分量、防重叠、历史区间稳定、诱导子图、完整交易事实、未来坐标／原份额与标签避让。后端相关回归 **39 项通过**（6.52 秒），命令 `uv run --directory demo/backend pytest -q tests/test_import_email_dept3.py tests/test_analysis.py`。前端生产构建成功，Worker 独立产物约 84 kB；保留既有 ECharts 大分块提示。

实际浏览器 **52 项检查通过**：主要流程 43 项、故障与竞态 9 项。覆盖 Sigma 实际节点拾取、标签无透明点击矩形、箭头隐藏／悬停／结构视图、双向边真实渲染曲率、查询草稿独立、异常账户返回全图并移入视野、历史三方法与单片区间、区间变化不重挖／不重排、未来源账户与 Top 不移动节点、合成与真实数据切换、开发代理和 FastAPI 构建托管。1440／1024／390 像素布局通过，390 像素全部 89 个节点和工具栏在画布内，无页面横向溢出。

参考图读取失败、Worker 计算失败均可重试并释放资源；更新期间隐藏不匹配的旧图，延迟的旧区间响应与旧数据集 Worker 消息不能覆盖新选择。无浏览器运行时错误或 Vue 警告，无 S13 快照或未来观测请求。Dept3 未接入亲和度的状态保留，SLADE 账户定位不改变查询结构、04 证据或未来成员范围。

实现与参数见 [图布局说明](frontend/src/graph/README.md)。产物：[验收摘要](exports/graph-layout-2026-11-17/validation-report.json)、[43 项流程检查](exports/graph-layout-2026-11-17/browser-checks.json)、[9 项故障检查](exports/graph-layout-2026-11-17/fault-checks.json)。截图：[全图 1440](exports/graph-layout-2026-11-17/present-all-1440.png)、[结构聚焦](exports/graph-layout-2026-11-17/present-structure-1440.png)、[邻域悬停](exports/graph-layout-2026-11-17/present-hover-1440.png)、[异常定位](exports/graph-layout-2026-11-17/present-anomaly-1440.png)、[历史区间](exports/graph-layout-2026-11-17/history-range-1440.png)、[1024](exports/graph-layout-2026-11-17/present-all-1024.png)、[390](exports/graph-layout-2026-11-17/present-all-390.png)、[构建托管](exports/graph-layout-2026-11-17/built-all-1440.png)、[未来示例](exports/graph-layout-2026-11-17/synthetic-future-1440.png)。

## Email Dept3：SLADE GPU 训练与在线启用

验证日期：2026-11-17。已实际运行 `uv run --directory demo/backend python -m scripts.train_slade --dataset email-eu-core-dept3`，为 `email-eu-core-dept3-v2-430dde7de92f` 生成并启用独立模型 **`slade-69b41533b46a5efd`**。本节取代下方历史阶段“Dept3 尚未训练”的状态。未改算法、交易数据、前端代码或依赖；合成模型及其指针保持独立。

训练只使用 S01—S11 的 9,525 条逐笔交互，10 epochs，默认 256／128 维、Adam 3e-6、batch size 100、种子 20261116。实际设备为 cuda:0／RTX 5060 Laptop GPU，PyTorch 2.8.0+cu128、CUDA 12.8。训练与最终参数历史预热共 49.963 秒，峰值显存分配 124.04 MiB；10 轮损失均有限，从 9.47118766 降至 9.30165313。训练事件指纹为 `0884f9584f76abe807fea1a2b109daf6a1f766a52a10b28e67628c65edfbad0c`。

候选权重重新加载到 GPU，预热记忆逐项一致，原模型与加载模型继续处理 S12 的 1,208 条交互后评分一致，验证通过才切换当前指针。另从空记忆完整重放历史，结果与保存的预热状态一致。S12 的 88 个账户可评分，账户 `34` 截至该时刻无交互历史，单列未评分。总分范围为 0.18847570—0.54312491；两项余弦距离范围及综合公式通过浮点容差验证，分数不代表异常真值或分类概率。

实际产物验证：重复请求及 **3 个并发请求**的全部账户评分一致；Top-20 等于完整排名的前 20，原权重 SHA-256 不变。读取守卫确认训练准备仅访问 S01—S11，检测仅额外读取 S12，不读取 S13、揭晓文件或场景注释；所有检测读取均属于 Dept3。运行中的 8000 接口已返回相同模型版本和完整分数，异常能力为 ready，默认当前查询仍返回 57 人。

实际浏览器 **17 项检查通过**：03 展示真实 Top-20，刷新排名及选中账户保持一致；点击账户显示两项距离并在图中定位，不修改 q=49、57 人结构或时间证据。历史和未来仍展示 S12 评分，未来保留当前查询范围；Dept3 群内份额预测仍独立显示未接入。开发页和现有构建托管页均通过，1440／1024／390 像素布局正常，无运行时异常或 Vue 警告，未请求 S13 交易或观测接口。本轮未修改前端，未重新构建。

产物：[训练报告](exports/slade-dept3-2026-11-17/training-report.json)、[模型与数据隔离验证](exports/slade-dept3-2026-11-17/validation-report.json)、[完整 S12 评分](exports/slade-dept3-2026-11-17/scores-s12.json)、[默认 Top-20](exports/slade-dept3-2026-11-17/scores-s12-top20.json)、[浏览器检查](exports/slade-dept3-2026-11-17/browser-checks.json)、[排名页面](exports/slade-dept3-2026-11-17/present-ranking-1440.png)、[账户依据](exports/slade-dept3-2026-11-17/present-account-evidence-1440.png)、[1024 像素](exports/slade-dept3-2026-11-17/present-ranking-1024.png)、[390 像素](exports/slade-dept3-2026-11-17/present-ranking-390.png)、[构建托管](exports/slade-dept3-2026-11-17/built-ranking-1440.png)。模型位于 `models/email-eu-core-dept3/slade/`，二进制权重和导出按既有规则仅保留本地。

## 默认页面切换为 Email Dept3

验证日期：2026-11-17。工作台默认选择 `email-eu-core-dept3`，当前及周期／持久默认账户改为 `49`，其他算法参数不变。S12 自动执行 `k=4` 局部 core，返回 57 人；02 展示全部 89 个节点、461 条有向聚合边，查询只改变高亮。移除合成数据固定画布边界，按真实节点范围适配。页脚展示真实数据来源，相对时间导航不展示虚构钟点，未来窗口使用 58,091 分钟。合成数据保留独立接入及对应账户默认值。

Dept3 未训练 SLADE，03 显示模型未就绪；未来保留当前查询的 57 人范围，但未配置份额预测，接口明确返回 503，画布不生成示例连线。新增接口测试确认未读取 S13／揭晓文件、未回退合成预测。

相关后端 **39 项测试通过**（6.23 秒），覆盖真实数据、历史三种算法、当前查询、未配置预测及合成查询／份额回归。Ruff E9/F/I 与格式检查通过，前端生产构建通过。实际浏览器 **27 项检查通过**：开发页和构建托管页均默认 Dept3；周期／持久／爆发高亮 35／73／70 人，拖动展示范围不重新挖掘；1440、1024、390 像素画布内均保留全部 89 个顶点，窄屏无横向溢出。无运行时异常或 Vue 警告，页面未请求 S13 原始交易或观测接口。

产物：[浏览器检查](exports/email-dept3-default-2026-11-17/checks.json)、[当前页面](exports/email-dept3-default-2026-11-17/present-1440.png)、[周期](exports/email-dept3-default-2026-11-17/history-periodic-1440.png)、[持久](exports/email-dept3-default-2026-11-17/history-durable-1440.png)、[爆发](exports/email-dept3-default-2026-11-17/history-burst-1440.png)、[未来未就绪](exports/email-dept3-default-2026-11-17/future-not-ready-1440.png)、[1024 像素](exports/email-dept3-default-2026-11-17/present-1024.png)、[390 像素](exports/email-dept3-default-2026-11-17/present-390.png)、[构建托管](exports/email-dept3-default-2026-11-17/built-present-1440.png)。本节取代下方记录中的页面默认合成数据描述。

## Email Dept3 v2：连续活跃前段与非空等宽快照

验证日期：2026-11-17。当前数据版本为 `email-eu-core-dept3-v2-430dde7de92f`，取代下方 v1 全范围划分。原始文件最大相邻交互间隔为 23,595,211 秒（约 273.09 天），第二大为 596,254 秒（约 6.90 天）。固定保留 `0 ≤ t < 45,310,384`，输出 12,099 条（99.04%）、89 个节点，舍弃长空白之后的 117 条；原始压缩包及其 12,216 条记录完整保留，归档 SHA-256 未变化。

保留范围逐条比对源文件：方向、节点 ID、时间戳、165 条完全重复记录、同时间戳原始顺序和内部时间间隔均保留。固定截断范围及分片规则进入版本指纹，旧 v1 读取和计算请求均返回 409。13 个窗口连续、等宽、不重叠，宽度为 58,091 分钟（3,485,460 秒），边界左闭右开；每条保留记录恰好属于一个窗口。逐片记录数为 `809, 816, 799, 609, 1025, 1520, 790, 601, 1075, 995, 486, 1208, 1366`，全部非空。S01—S11 历史／S12 当前／S13 保留观测分别有 9,525／1,208／1,366 条。

当前实现经 HTTP 接口验证：周期／持久／爆发分别返回 35／73／70 个成员，参数为 `q=49,k=4,epsilon=0.2`、`q=49,k=4`、`l=3,delta=3`。S12 包含 320 条无向连接，`q=49,k=4` 的局部 core 返回 57 个成员。历史挖掘、历史证据和训练准备均验证不读取 S12／S13 交互或预测场景；当前结构查询只读取 S12 和节点配置。普通快照请求 S13 返回 404。没有为 Dept3 训练 SLADE 权重，异常请求返回模型未就绪 503。

后端 **246 项测试通过**（69.96 秒），本数据包的导入和接口测试共 21 项；新增覆盖截断排他边界、边界重复记录、无保留记录、截断规则指纹变化、当前 57 人结构及旧版本拒绝。Ruff E9/F/I 检查及格式检查通过。实际服务与浏览器 **21 项检查通过**，覆盖全部已观测非空快照、历史聚合、三种算法、当前查询、版本冲突、未来隔离、Vite 代理以及开发和现有构建托管页面；无浏览器运行时错误或 Vue 警告。页面仍默认合成样例，本轮未修改前端代码；生产页面使用现有构建产物验证。数据包重建后已重启 8000 端口的项目开发服务。

数据规则见 [数据包说明](data/email-eu-core-dept3/README.md)。验证产物：[导入报告](exports/email-dept3-v2-2026-11-17/import-report.json)、[接口响应](exports/email-dept3-v2-2026-11-17/api-results.json)、[浏览器检查](exports/email-dept3-v2-2026-11-17/checks.json)、[服务重启记录](exports/email-dept3-v2-2026-11-17/restart.json)、[开发页面](exports/email-dept3-v2-2026-11-17/development-default-1440.png)、[构建托管页面](exports/email-dept3-v2-2026-11-17/built-default-1440.png)。

## Email Dept3 v1 真实数据格式接入（历史记录）

验证日期：2026-11-17。已归档 SNAP 官方原始 `email-Eu-core-temporal-Dept3.txt.gz`，转换为 `data/email-eu-core-dept3/` 下 S01—S13 的 `u,v,t` CSV、节点清单、快照清单及来源配置。数据 ID 为 `email-eu-core-dept3`，版本为 `email-eu-core-dept3-v1-61a60d09d78f`，标记 `synthetic=false`。

逐行核验保留 89 个节点、12,216 次交互、165 条完全重复记录，以及同时间戳的原始行顺序；方向和时间间隔不变。原始数据为相对秒，新增 `timestamp_basis=relative`，ISO 1970 日期只作为技术零点，不伪造真实日历。完整时间范围等宽划为 13 片，宽度 88,869 分钟；S10、S11、S12 保留为空快照，历史共 12,099 次交互，S13 的 117 次交互单独保存。

三种历史算法经现有 HTTP 接口读取此数据，周期／持久／爆发返回 36／83／78 个成员，建议参数分别为 `q=49,k=4,epsilon=0.2`、`q=49,k=4`、`l=3,delta=3`。已验证快照边界、区间聚合次数、保留孤立成员、来源指纹、重建一致性、输入错误和拒绝覆盖其他数据集；历史挖掘、时间证据及训练准备不读取 S13 或场景注释。没有为该数据训练 SLADE 模型，异常请求明确返回 503；没有添加预测示例权重。

后端 **241 项测试通过**（100.50 秒），包含本轮新增 16 项导入及接口检查；Ruff E9/F 检查和前端生产构建通过。实际服务与浏览器 **12 项检查通过**，覆盖真实数据注册、S01 聚合、S12 空图、三种历史接口、模型未就绪，以及开发代理和构建托管的默认页面。新增数据集不会抢占合成样例的默认选择；无浏览器运行时错误或 Vue 警告。此阶段完成数据准备与后端可读性，页面仍默认展示合成样例。

转换命令与口径见 [数据包说明](data/email-eu-core-dept3/README.md)。验证产物：[导入报告](exports/email-dept3-2026-11-17/import-report.json)、[接口响应](exports/email-dept3-2026-11-17/api-results.json)、[浏览器检查](exports/email-dept3-2026-11-17/checks.json)、[开发页面](exports/email-dept3-2026-11-17/development-default-1440.png)、[构建托管页面](exports/email-dept3-2026-11-17/built-default-1440.png)。

## 原始交互改为逐快照 CSV

验证日期：2026-11-17。原始交互已从 JSON 迁移为 `data/synthetic-small/S01.csv`—`S13.csv`，固定表头 `u,v,t`，`t` 使用 Unix 秒时间戳。每行代表一次交互，重复行完整保留，同时间戳保持原顺序。`observed.json` 和 `replay.json` 仅保存各快照的账户集合；节点布局、时间范围与场景配置继续使用 JSON。HTTP 接口仍返回 JSON。本节取代下方历史记录中的物理存储方式，数据三字段含义保持一致。

逐条核对 13 个快照的 4,810 笔交互及节点集合，与转换前完全一致。训练事件指纹和 26 个账户的全部 SLADE 分数保持一致，因此继续使用 `synthetic-small-v3` 和 `slade-82d7e3115c065a60`，未重新训练模型。样例中“交互＋快照账户信息”的文件总量由 200,584 字节降为 113,863 字节，减少 **43.23%**；其他配置文件不计入此项比较。

读取层只打开请求对应的 CSV，不加载其他时刻的交互；普通接口不能读取 S13。支持 UTF-8 BOM、CRLF、标准引号转义及小数秒。缺失 CSV 返回 404；错误表头、列数、时间数值或范围返回 422；空快照保存只有表头的 CSV。生成器可重复生成 13 个 CSV 和 5 个配置 JSON，并与落盘文件逐字节一致。

后端 **225 项测试**、Ruff E9/F 检查通过。新增 CSV 测试覆盖表头、缺列／多列、错误时间、BOM、CRLF、带引号账户、小数秒、单快照文件隔离和文件缺失，原有三字段、社区、查询、模型及未来份额测试全部通过。实际浏览器 **39 项检查**通过，覆盖开发代理、FastAPI 构建托管、历史／当前／未来联动、故障恢复及 1440／1024／390 布局；无运行时错误或 Vue 警告，未请求未来观测。

当前数据格式见 [图数据结构](data/README.md)，可直接查看 [S01.csv](data/synthetic-small/S01.csv)。验证产物：[迁移及存储比较](exports/csv-data-2026-11-17/migration-report.json)、[浏览器检查](exports/csv-data-2026-11-17/checks.json)、[API 响应](exports/csv-data-2026-11-17/api-results.json)、[构建托管截图](exports/csv-data-2026-11-17/built-account-evidence-1440.png)。

## 三字段交互数据：u、v、t

验证日期：2026-11-17。当前样例版本为 `synthetic-small-v3`，每条原始交互仅保存 `u、v、t`，其中 `t` 为数值 Unix 秒时间戳；当前样例为整数秒，校验支持小数秒。金额、资产、首位数字、交易 ID 及金额时间证据已移除。节点清单、节点坐标、快照账户集合与时间边界独立保留，用于孤立账户、空快照及界面定位。字段说明见 [图数据结构](data/README.md)。本节取代下方记录中当前数据格式、金额展示、数据版本及当前模型版本的描述，其余历史记录按验证日期保留。

转换前后逐条对比 13 个快照，共 4,810 笔交互：端点、发生时间、重复次数及各快照账户集合完全一致。历史默认周期／持久／爆发仍返回 5／5／6 个成员，S12 仍为 26 个账户、52 条结构连接、183 笔交互。原始记录不保存交易次数，图接口按有向账户对实时派生 `transaction_count`；04 只提供内部连接数和交易次数。相同 `(u,v,t)` 不去重，同时间戳按文件顺序稳定处理。

SLADE 已在 cuda:0 上用三字段输入重新完成 S01—S11 的 4,263 笔交互、10 轮训练，当前模型为 **`slade-82d7e3115c065a60`**。最终参数预热、保存和加载后的 S12 评分一致；与格式转换前的 26 个账户分数逐项比较也完全一致。训练仍不读取 S12，训练与检测均不读取 S13。

后端 **216 项测试**、Ruff E9/F 检查和前端生产构建通过。新增契约检查覆盖三字段限定、数值时间类型、小数秒、同时间重复交互、双向／自环的结构投影、毫秒误传与快照左右边界、旧版本及已移除金额指标的拒绝；既有社区、异常、证据和未来份额回归通过。

实际浏览器 **39 项检查**通过：目录和图响应不再携带金额字段，04 仅提供两种有效指标并可请求次数轨迹；账户评分、历史区间、当前查询、未来份额及故障恢复正常。开发代理与构建托管均通过；1440、1024、390 像素宽度无横向溢出，无运行时错误或 Vue 警告，页面不请求 S13 交易或观测份额。

产物位于 `exports/uvt-data-2026-11-17/`：[迁移与 GPU 模型报告](exports/uvt-data-2026-11-17/migration-report.json)、[浏览器检查](exports/uvt-data-2026-11-17/checks.json)、[接口完整响应](exports/uvt-data-2026-11-17/api-results.json)、[当前账户评分](exports/uvt-data-2026-11-17/present-account-evidence-1440.png)、[历史聚合](exports/uvt-data-2026-11-17/history-current-slade-1440.png)、[1024 像素](exports/uvt-data-2026-11-17/present-account-1024.png)、[390 像素](exports/uvt-data-2026-11-17/present-account-390.png)、[构建托管](exports/uvt-data-2026-11-17/built-account-evidence-1440.png)。

## SLADE 账户检测与 Python 3.10 GPU 环境

验证日期：2026-11-17。本节为当前实现口径，取代下方历史记录中的“结构 OR 金额”、异常子图和异常示例结果。03 现展示 SLADE 账户异常程度排名，未来仍继承 01 选择的查询结构；历史、现在、未来的异常面板统一使用 S12 检测结果。

### 环境与实际训练

后端已切换为 Python 3.10.11，项目解释器为 `backend/.venv/Scripts/python.exe`。通过 `--system-site-packages` 复用 `D:/Workshop/Python310/Lib/site-packages/torch` 中已有的 **PyTorch 2.8.0+cu128**，没有另装一份 PyTorch，也未向主 Python 环境安装项目依赖。FastAPI 使用兼容 Python 3.10 的 0.162.5；uv 管理其他项目依赖，并将外部提供的 torch 排除在安装解析之外。初始化脚本、`uv sync --locked` 和 `uv run` 均已实际验证。环境不完全隔离，主环境的 PyTorch 及其依赖需继续保留。

模型及记忆实际运行在 **cuda:0 / NVIDIA GeForce RTX 5060 Laptop GPU**，CUDA 12.8；GPU 不可用时明确报错。训练命令为：

```powershell
uv run --directory backend python -m scripts.train_slade --dataset synthetic-small
```

| 项目 | 实测结果 |
| --- | --- |
| 当前模型版本 | `slade-72e289751d004a0e` |
| 训练范围 | S01—S11，4,263 笔逐笔交互 |
| 训练轮数与耗时 | 10 epochs，17.355 秒 |
| 峰值显存分配 | 120.12 MiB |
| 每轮损失 | 有限；首轮 7.14280，末轮 7.13760 |
| 检测范围 | 冻结参数后处理 S12 的 183 笔交互，26 个账户可评分 |
| 评分时刻 | S12 结束时刻，2026-01-01 12:00:00 +08:00 |
| 保存／加载验证 | 最终参数重放 S01—S11；保存、加载后的预热状态与 S12 分数完全一致，随后启用当前模型 |

训练不读取 S12，训练与检测均不读取 S13。金额、首位数字、core number 和场景注释不参与 SLADE 输入或评分。模型保留原文两项余弦距离及 `(时间对比 + 记忆生成) / 4` 综合公式，不增加二分类阈值。训练按前一批交互更新记忆，同时间戳事件不拆批；在线处理同时间戳事件时使用共同更新前状态。实现细节与作者代码差异见 [SLADE 复现说明](backend/algorithms/anomaly/README.md)。

### 检查结果

后端 **203 项测试**、Ruff E9/F 检查、uv 锁文件检查及前端生产构建通过。测试覆盖原文评分和损失、因果顺序、零向量／空邻域、重复交互、同时间戳、真实训练、GPU 状态恢复、重复和并发评分一致性、数据指纹与模型损坏、CUDA 缺失，以及金额和后续快照不影响评分。历史三种算法和当前查询仍通过回归，默认周期／持久／爆发分别返回 5／5／6 个成员。

实际浏览器 **35 项检查**通过，覆盖开发代理与 FastAPI 构建托管、账户排名及两项评分、异常账户定位、查询结构与 04 轨迹保持独立、未来源账户和 Top 筛选保持、历史区间展示、模型版本变化、请求延迟、接口失败与手动重试。1440、1024、390 像素下无页面横向溢出；选中账户后评分依据可见。没有请求 S13 交易或观测份额，没有浏览器运行时错误或 Vue 警告。评分 Top-20 仅为展示范围，不代表已判定为异常。

验证产物位于 `exports/slade-gpu-2026-11-17/`：

- [环境与张量设备](exports/slade-gpu-2026-11-17/runtime.json)、[训练报告](exports/slade-gpu-2026-11-17/model-report.json)、[训练日志](exports/slade-gpu-2026-11-17/training.log)。
- [完整 API 响应](exports/slade-gpu-2026-11-17/api-results.json)、[35 项浏览器检查及请求记录](exports/slade-gpu-2026-11-17/checks.json)。
- [当前账户排名](exports/slade-gpu-2026-11-17/present-ranking-1440.png)、[选中账户与评分依据](exports/slade-gpu-2026-11-17/present-account-evidence-1440.png)、[历史及当前 SLADE 结果](exports/slade-gpu-2026-11-17/history-current-slade-1440.png)、[未来查询范围](exports/slade-gpu-2026-11-17/future-query-scope-1440.png)。
- [1024 像素](exports/slade-gpu-2026-11-17/present-account-1024.png)、[390 像素](exports/slade-gpu-2026-11-17/present-account-390.png)、[失败与重试](exports/slade-gpu-2026-11-17/anomaly-unavailable-retry-1440.png)、[构建托管](exports/slade-gpu-2026-11-17/built-account-evidence-1440.png)。

当前合成样例只验证训练、检测和界面流程，不用于宣称真实金融异常检测效果。以下保留各阶段的历史验证记录。

## v2 样例支持默认历史查询

验证日期：2026-11-16。将样例升级为 `synthetic-small-v2`，在原背景交易上补充周期性五账户完全图，以及 S07—S09 连续出现的六账户完全图。新增连接通过独立随机流生成逐笔交易，生成脚本与已提交 JSON 完全一致。原有 S12 交易的 SHA-256 核对通过，当前默认五账户查询与 S13 回放保持原数据。生成方式与成员范围见 [样例说明](data/synthetic-small/README.md)。本节取代此前记录中的“默认条件无解”和手动降阈值示例。

三个方法的算法及默认参数均保持原样，实际响应如下：

| 方法 | 默认条件 | 输出 |
| --- | --- | --- |
| 周期 | `q=a-001,k=4,epsilon=0.2` | 5 个账户，序列 `10010010010`，周期 3、重复 3 次 |
| 持久 | `q=a-001,k=4` | 同一组 5 个账户；形成于 S01，稳定至 S06，持续 5 个时间步 |
| 爆发 | `l=3,delta=3.0` | 6 个账户；每个成员 MSD 为 5，见证区间 S07—S09 |

后端 **169 项测试**、Ruff E9/F 检查及实际浏览器 **20 项检查**通过。测试覆盖默认结果及真实时间证据、生成器复现与落盘一致、金额和次数聚合、过严条件仍为空、旧版本拒绝、当前查询回归。现有开发服务已读取 v2；刷新页面即可获取新数据版本和缓存上下文。

浏览器确认三种方法默认自动返回结果，02 高亮 5／5／6 个实际成员、04 统计 11 个原始快照，展示范围切换不重新挖掘；03 保持 S12 异常背景。1440、1024、390 像素布局正常，现有 FastAPI 托管的前端构建也能直接使用新数据。未发起 S13 交易或观测请求，无运行时异常或 Vue 警告。

截图和结果位于 `exports/default-history-data-v2-2026-11-16/`：[周期默认值](exports/default-history-data-v2-2026-11-16/periodic-default-1440.png)、[持久默认值](exports/default-history-data-v2-2026-11-16/durable-default-1440.png)、[爆发默认值](exports/default-history-data-v2-2026-11-16/burst-default-1440.png)、[区间切换](exports/default-history-data-v2-2026-11-16/durable-range-1440.png)、[1024 像素](exports/default-history-data-v2-2026-11-16/default-history-1024.png)、[390 像素](exports/default-history-data-v2-2026-11-16/default-history-390.png)、[构建托管](exports/default-history-data-v2-2026-11-16/built-durable-default-1440.png)、[默认 API 完整响应](exports/default-history-data-v2-2026-11-16/default-api-results.json)及 [20 项检查明细](exports/default-history-data-v2-2026-11-16/checks.json)。以下为此前验证记录。

## 历史三种论文算法接入

验证日期：2026-11-16。周期 TD＋FT/AC、持久 ONCE、爆发 MBC-B 已替换历史成员注释，按 S01—S11 的原始无向简单快照实时计算。三种算法使用独立纯函数和公共 `PatternResult` 契约；数据、接口、前端统一由公共适配层衔接。详细方法与边界见 [算法说明](backend/algorithms/patterns/README.md)。本节取代此前记录中“历史模式示例”的口径，异常和未来预测仍为示例结果。

后端 **166 项测试**通过，包含三个算法的独立测试、HTTP 参数与结构复核、原有接口回归；Ruff E9/F 检查及前端生产构建通过。实际浏览器 **45 项检查**通过，开发代理及 FastAPI 构建托管均验证，无运行时异常、Vue 或 Element Plus 警告。

- 算法输入仅使用历史逐快照投影，缺席账户补为空邻居，保留空时间位置；双向及重复交易合并、自环忽略。测试断言不读取场景成员、S12 或 S13。
- 周期覆盖论文二值序列、周期 2／3、联合剥离传播、两两 Jaccard、ε 边界、确定性及已知 TD 漏解例。持久和爆发分别用独立小图穷举核验结果、阈值与并列边界。重复计算不修改输入、不依赖账户遍历顺序。
- 三种方法分别保存参数草稿和已提交条件。编辑参数、点击账户只更改草稿；提交后执行计算。切换方法保留各自条件，延迟响应不能覆盖当前方法；失败隐藏旧高亮与证据，并可按已提交条件重试。
- 历史聚合 start/end 不参与挖掘请求或缓存键。范围切换改变展示拓扑，成员与共同账户视角保持稳定；04 仍统计固定成员的 11 个逐快照原始值，并标出当前展示选区。
- 默认周期、持久的 `q=a-001,k=4` 如实显示空结果，不回退为原有成员。结果列表显示论文指标，不将历史证据当作异常分数。
- 当前 S12 默认五账户查询、异常两侧依据、未来继承与 Top 筛选正常；Top-1 不重新归一化。历史查看期间 03 仍展示 S12 异常信息，页面未请求 S13 交易或观测接口。
- 1440、1024、390 像素下无页面横向溢出，参数表单可用。桌面保留完整主图，窄屏纵向展示。

当前数据的非空演示条件如下，默认值保持原样：

| 方法 | 条件 | 实际结果 |
| --- | --- | --- |
| 周期 | `q=a-001,k=1,epsilon=0.2` | 20 个账户；真实序列 `11010010000`，周期 3、重复 3 次，最佳段 S01—S09 |
| 持久 | `q=a-001,k=2` | 23 个账户；持续 4 个时间步，稳定截止 S07 |
| 爆发 | `l=3,delta=1.5` | 23 个账户；最小成员 MSD 为 5/3，不强制共有见证区间 |

周期实现遵循论文 TD 候选流程，保留固定谱筛选与离散化约定；已验证其候选空间存在漏解，因此不承诺全顶点子集范围的全局最优。边界与反例见 [周期复现说明](backend/algorithms/patterns/PERIODIC.md)。本轮未增加 Python 依赖；ECharts 运行时分块仍约 529 kB，存在原有构建体积提示，构建成功。

截图和请求明细位于 `exports/history-algorithms-2026-11-16/`：

| 状态 | 截图 |
| --- | --- |
| 三种非空算法结果 | [周期](exports/history-algorithms-2026-11-16/periodic-1440.png)、[持久](exports/history-algorithms-2026-11-16/durable-1440.png)、[爆发](exports/history-algorithms-2026-11-16/burst-1440.png) |
| 默认空结果与失败重试 | [空结果](exports/history-algorithms-2026-11-16/periodic-empty-1440.png)、[请求失败](exports/history-algorithms-2026-11-16/mining-error-1440.png) |
| 区间展示与当前回归 | [区间](exports/history-algorithms-2026-11-16/history-final-1440.png)、[现在](exports/history-algorithms-2026-11-16/present-1440.png)、[异常依据](exports/history-algorithms-2026-11-16/anomaly-1440.png)、[未来](exports/history-algorithms-2026-11-16/future-1440.png) |
| 响应式与构建托管 | [1024 像素](exports/history-algorithms-2026-11-16/history-1024.png)、[390 像素](exports/history-algorithms-2026-11-16/history-390.png)、[FastAPI 托管](exports/history-algorithms-2026-11-16/built-history-1440.png) |

[checks.json](exports/history-algorithms-2026-11-16/checks.json) 保存 45 项检查和 API 请求记录；[非空响应](exports/history-algorithms-2026-11-16/nonempty-api-results.json) 保存三种方法的完整参数、成员、证据及版本，便于复核。以下为此前验证记录。

## 02 面板精简与画布扩展

验证日期：2026-11-16。02 删除重复的区间／方法说明、所选结构摘要及底部解释文字，保留单行标题、总量、图形工具与紧凑图例。1440×900 下标题区为 40px，底部图例为 28px，图画布高度为 427px；1024、390 像素宽度下画布分别为 405px、380px。

前端构建及 **10 项专项浏览器检查**通过：历史模式切换、当前结构高亮、未来预测与 Top 筛选、缩放和标签开关、1440/1024/390 布局及 FastAPI 构建托管。无运行时异常或 Vue 警告。

截图及检查明细位于 `exports/compact-graph-2026-11-16/`：[历史](exports/compact-graph-2026-11-16/history-1440.png)、[现在](exports/compact-graph-2026-11-16/present-1440.png)、[未来](exports/compact-graph-2026-11-16/future-1440.png)、[1024 像素](exports/compact-graph-2026-11-16/future-1024.png)、[390 像素](exports/compact-graph-2026-11-16/future-390.png)、[构建托管](exports/compact-graph-2026-11-16/built-history-1440.png)及 `checks.json`。

## 历史视图展示当前异常

验证日期：2026-11-16。历史视图的 03 改为展示当前 S12 的异常排名、综合分数和两侧依据，标题明确标注“当前 S12 整图异常”，支持刷新与失败重试。切换历史区间保持当前异常结果；点击异常返回 S12 定位，随后可进入预测。

前端构建及 **17 项专项浏览器检查**通过：历史与现在排名和依据一致、区间切换、刷新加载与失败重试不抢占历史结构、仅请求 S12 异常、点击定位与未来继承、1440/1024/390 像素布局及 FastAPI 构建托管。无运行时异常或 Vue 警告。

截图及检查明细位于 `exports/history-current-anomalies-2026-11-16/`：[桌面](exports/history-current-anomalies-2026-11-16/history-1440.png)、[1024 像素](exports/history-current-anomalies-2026-11-16/history-1024.png)、[390 像素](exports/history-current-anomalies-2026-11-16/history-390.png)、[构建托管](exports/history-current-anomalies-2026-11-16/built-history-1440.png)及 `checks.json`。以下为此前各轮验证记录，历史 03 的展示口径以本节为准。

## 03 面板底部预测导航

验证日期：2026-11-16。现在的“进行预测”和未来的“返回现在更换结构”统一放入 03 底部独立操作行，与异常信息滚动区以分隔线隔开；历史不显示。01、02 不再提供重复返回入口，无选中结构时禁用预测。

前端构建及 **19 项专项浏览器检查**通过：查询和异常结构均可进入未来、返回后保留选择与参数草稿、异常内容滚动时操作行固定、空结果与无选择状态、1440/1024/390 像素布局、开发代理及 FastAPI 构建托管。预测导航不读取 S13 交易或观测接口，无运行时异常或 Vue 警告。

截图及检查明细位于 `exports/prediction-actions-2026-11-16/`：[当前异常](exports/prediction-actions-2026-11-16/present-anomaly-1440.png)、[未来](exports/prediction-actions-2026-11-16/future-query-1440.png)、[1024 像素](exports/prediction-actions-2026-11-16/future-1024.png)、[390 像素](exports/prediction-actions-2026-11-16/future-390.png)、[构建托管](exports/prediction-actions-2026-11-16/built-future-1440.png)及 `checks.json`。

## 三角形时间手柄

验证日期：2026-11-16。start 为左指三角形 ◀，end 为右指三角形 ▶，按“◀ ── ▶”向区间外侧指向，同轨道显示，移除浮动文字与上下错位。历史导航由 54px 控件区收至 28px，与 S12/S13 一致，释放的空间用于主图。

前端构建及 **16 项专项浏览器检查**通过：鼠标、键盘、390 像素触摸、重合后分别拖开、S12/S13 单时刻、1440/1024/390 布局和 FastAPI 构建托管；无运行时异常或 Vue 警告。本轮只调整前端时间控件。

截图及检查明细位于 `exports/triangle-navigation-outward-2026-11-16/`： [桌面](exports/triangle-navigation-outward-2026-11-16/history-1440.png)、[重合手柄](exports/triangle-navigation-outward-2026-11-16/coincident-1440.png)、[1024 像素](exports/triangle-navigation-outward-2026-11-16/history-1024.png)、[390 像素](exports/triangle-navigation-outward-2026-11-16/history-390.png)、[构建托管](exports/triangle-navigation-outward-2026-11-16/built-history-1440.png)及 `checks.json`。

## 历史双端时间导航与区间聚合图

验证日期：2026-11-16。后端 **37 项测试**、实际浏览器 **48 项检查**及前端生产构建通过。开发代理与 FastAPI 构建托管均已验证，浏览器无运行时异常、Vue 或 Element Plus 警告。

- start、end 支持真实鼠标、键盘和 390 像素下的触摸拖动，重合后可分别拖开；当前和未来保持单时刻，历史起点跨视图保留。
- 区间包含两端，账户及交易边取并集；次数、金额及逐笔首位数字计数累计；孤立账户保留，无向结构与 core number 重新计算。
- 单快照区间与原快照图字段完全一致；未知、逆序、S12/S13 边界、版本冲突、空图和零交易均覆盖。
- 01 明确标注全历史模式示例与 S11 参考统计；模式切换更新配色并保持区间拓扑。03 显示区间尚未评估，不复用 S12 证据。
- 04 保留逐快照数值、全部轨迹与实际曲线点击；选区跟随起止范围；移除回放入口及定时器。
- 约 150ms 防抖只请求连续输入的最终范围，释放立即提交；延迟响应、失败重试不串用旧范围。加载时保留画布实例、缩放和平移，共同账户位置稳定。
- S12 三种查询、独立异常选择、参数草稿、S13 份额和 Top 过滤通过回归检查。页面不请求 S13 交易或观测接口。
- 1440×900 可完整显示主要图和 04；1024、390 像素布局无页面横向溢出。

截图与检查明细保存在 `exports/history-interval-2026-11-16/`：

| 状态 | 截图 |
| --- | --- |
| 历史 S03—S07 聚合图 | [history-1440.png](exports/history-interval-2026-11-16/history-1440.png) |
| 单快照区间与重合手柄 | [single-snapshot-1440.png](exports/history-interval-2026-11-16/single-snapshot-1440.png) |
| 当前单快照 | [present-1440.png](exports/history-interval-2026-11-16/present-1440.png) |
| 未来单时间片 | [future-1440.png](exports/history-interval-2026-11-16/future-1440.png) |
| 聚合请求失败与空图 | [aggregate-error-1440.png](exports/history-interval-2026-11-16/aggregate-error-1440.png)、[aggregate-empty-1440.png](exports/history-interval-2026-11-16/aggregate-empty-1440.png) |
| 1024 像素布局 | [history-1024.png](exports/history-interval-2026-11-16/history-1024.png) |
| 390 像素布局 | [history-390.png](exports/history-interval-2026-11-16/history-390.png)、[future-390.png](exports/history-interval-2026-11-16/future-390.png) |
| FastAPI 构建托管 | [built-history-1440.png](exports/history-interval-2026-11-16/built-history-1440.png) |

`checks.json` 保存 48 项检查结果和本地 API 请求记录。图数据与统计实时计算，历史模式、当前异常与预测仍按现有示例口径呈现。本轮 ECharts 运行时分块约 529 kB，仍有默认 500 kB 提示，构建成功。

## 此前：四面板职责调整

验证日期：2026-11-16。后端 **23 项测试**、实际浏览器 **37 项检查**及前端生产构建通过。开发代理和 FastAPI 构建托管均已验证，浏览器无运行时异常、Vue 或 Element Plus 警告。

- 01 保留方法、参数和结果选择，02 固定展示图结构，03 在所有时刻固定展示异常信息，04 保留时间轨迹与回放。
- 默认异常加载与重试不抢占查询；查询和异常选择分别保留，点击后联动图与真实时间证据；参数草稿不改变当前范围。
- 异常接口兼容省略快照字段；历史返回 `not_evaluated`，与 `ok` 下的无异常结果分别展示，S13 不作为异常检测输入。
- 未来保留完整候选归一化和 Top 过滤；03 明确显示 S12 背景；选择其他异常先返回 S12，实际结构改变后重置源账户和 Top。
- 旧详情、未来排名与观测对照不再渲染，完整页面操作中没有发起观测或 S13 交易请求。
- 延迟响应不覆盖新快照；异常加载隐藏旧依据，失败后可重试；1440、1024、390 像素下无页面横向溢出。
- 修复时间图点击的横坐标换算，实际点击曲线可切换快照，回放与手动暂停有效。

本轮截图和检查明细保存在 `exports/four-panels-2026-11-16/`：

| 状态 | 截图 |
| --- | --- |
| 默认四面板 | [present-1440.png](exports/four-panels-2026-11-16/present-1440.png) |
| 异常选择与依据 | [anomaly-evidence-1440.png](exports/four-panels-2026-11-16/anomaly-evidence-1440.png) |
| 历史未评估 | [history-1440.png](exports/four-panels-2026-11-16/history-1440.png) |
| 查询结构的未来份额 | [future-query-1440.png](exports/four-panels-2026-11-16/future-query-1440.png) |
| 异常结构与 S12 背景 | [future-anomaly-1440.png](exports/four-panels-2026-11-16/future-anomaly-1440.png) |
| 异常失败与已评估无结果 | [anomaly-error.png](exports/four-panels-2026-11-16/anomaly-error.png)、[anomaly-empty.png](exports/four-panels-2026-11-16/anomaly-empty.png) |
| 1024 像素布局 | [anomaly-1024.png](exports/four-panels-2026-11-16/anomaly-1024.png) |
| 390 像素布局 | [anomaly-390.png](exports/four-panels-2026-11-16/anomaly-390.png)、[future-390.png](exports/four-panels-2026-11-16/future-390.png) |
| FastAPI 构建托管 | [built-1440.png](exports/four-panels-2026-11-16/built-1440.png) |

13 张截图及 `checks.json` 保存了主要状态、37 项检查结果和本地 API 请求记录。异常依据和预测仍为后端示例，历史快照没有接入正式异常判据。本轮 ECharts 运行时分块约 525 kB，仍有默认 500 kB 提示，构建成功。

## 初次工作台迁移记录

以下为四面板调整之前的验证与截图，包含当时的详情和观测对照功能；当前界面以上一节为准。

验证日期：2026-11-16。使用随工程提供的 `synthetic-small-v1` 合成样例。

| 验证 | 结果 |
| --- | --- |
| `uv sync --directory backend --locked` | 通过，使用后端项目虚拟环境 |
| `uv run --directory backend pytest -q` | 18 项通过 |
| `npm --prefix frontend run build` | 通过 |
| 主演示与响应式浏览器检查 | 36 项通过 |
| 故障恢复、画布交互和延迟响应检查 | 17 项通过 |
| 大结构标签、范围重置与构建托管检查 | 20 项通过 |

浏览器检查共 73 项，使用 Chrome 的 DevTools 协议执行实际页面操作，WebGL 图形在无头浏览器的软件渲染模式下截图。开发代理地址 `127.0.0.1:5173` 和 FastAPI 构建托管地址 `127.0.0.1:8000` 均已验证；`/docs`、健康检查、未知 API 与缺失资源状态符合预期。

## 主要检查范围

- 固定种子逐文件重建一致；交易金额、次数、首位数字聚合与逐笔记录一致。
- S12 的 26 账户、52 条结构连接，以及默认 `q=a-001, k=4` 的五账户结果。
- Core 的多连通分量、空结果、无效账户和参数；单账户无候选；成员缺席与零交易分开。
- 模式切换保持拓扑；快照切换改变拓扑；共同账户坐标稳定；回放和手动暂停有效。
- 参数草稿保留已提交范围；当前选择直接进入未来；结构变化重置源账户、Top 和观测。
- 完整候选归一化，Top 筛选保持原份额；揭晓前没有请求 S13 快照或观测，后续份额与回放交易一致。
- 源账户变化不改变未来布局；较大结构的 26 个账户标签在 1440 和 390 像素宽度下无重叠。
- 通过拦截请求模拟查询、证据、预测、观测和服务连接失败，验证隐藏旧结果及手动重试恢复；延迟响应不覆盖新快照或新模式。
- 1440×900 为主要演示尺寸，另检查 1920、1280、1024、390 像素宽度，无页面横向溢出。
- 全部浏览器检查无运行时异常、Vue 或 Element Plus 组件警告。

## 截图与检查明细

主要状态和三份 JSON 检查记录保存在本地 `exports/validation-2026-11-16/`，导出文件按工程约定不纳入版本控制。

| 状态 | 截图 |
| --- | --- |
| 默认当前查询 | [present.png](exports/validation-2026-11-16/present.png) |
| 历史模式 | [history.png](exports/validation-2026-11-16/history.png) |
| 全部历史轨迹 | [history-all.png](exports/validation-2026-11-16/history-all.png) |
| 异常与两侧证据 | [anomaly.png](exports/validation-2026-11-16/anomaly.png) |
| 群内未来份额 | [future.png](exports/validation-2026-11-16/future.png) |
| 揭晓后的对照 | [future-replay.png](exports/validation-2026-11-16/future-replay.png) |
| 无有效观测 | [future-no-interactions.png](exports/validation-2026-11-16/future-no-interactions.png) |
| 无已选结构 | [future-empty.png](exports/validation-2026-11-16/future-empty.png) |
| 26 账户未来视图 | [future-26-source13.png](exports/validation-2026-11-16/future-26-source13.png) |
| 390 像素当前视图 | [present-390.png](exports/validation-2026-11-16/present-390.png) |
| 390 像素大结构未来视图 | [future-26-390.png](exports/validation-2026-11-16/future-26-390.png) |
| 请求失败与连接恢复入口 | [query-failure.png](exports/validation-2026-11-16/query-failure.png)、[disconnected.png](exports/validation-2026-11-16/disconnected.png) |
| FastAPI 托管 | [built-hosting.png](exports/validation-2026-11-16/built-hosting.png) |

其他桌面宽度、预测失败和所选证据状态同样保存在该目录。检查明细分别为 `checks-initial.json`、`checks-resilience.json` 和 `checks-final.json`。

## 实现边界

Core、统计、时间证据与揭晓后的交易份额实际计算；密度筛选是演示算法；历史成员、异常证据和预测份额仍为明确标注的示例，未训练或接入正式模型。此记录验证工程行为，不构成正式算法的精度或性能评价。

前端已按功能引入并动态加载图形库。当前构建会提示图表运行时约 547 kB 的分块超过默认 500 kB 提示线；构建和功能验证通过。
