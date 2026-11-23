# 时序交易图分析 Demo

Vite＋Vue 3＋JavaScript＋Element Plus 前端，uv＋Python 3.10＋FastAPI 后端。

默认展示 Email Dept3 真实邮件网络（89 个节点），保留可复现的 26 账户合成交易数据。`demo-ui` 的交互已迁移为浅色紧凑分析工作台。顶部统一滑轨控制历史 S01—S11、当前 S12 和未来 S13。历史拖动 start、end 查看区间聚合图。当前在 02 选择并行核分解、时序核连通分量（TCCS）或全局最大核（PKMC）。TCCS 支持以 S12 为终点的回溯窗口，默认 S12—S12。未来页独立选择查询节点 q、核心阶数 k 和预测模型。

快照、Core 查询、历史周期／持久／爆发／频率感知核挖掘、交易聚合和固定成员时间证据实际计算。CSV 读入时统一两个端点的顺序。同一对节点在图上只有一条无向边，逐笔交互保留各自的时间并累加次数。密度查询仅保留旧接口。04 使用 SLADE 展示账户评分。未来模块使用 Zebra 为历史候选顶点对评分，再用超过概率阈值的边求目标快照中包含 q 的 k-core 社区。目标可选 S13、S14 或 S15。

**01 快照时间导航**选择历史区间或进入现在、未来视图。**02 方法与参数**选择方法并提交参数，未来视图可在此选择目标快照。**03 图结构**展示历史区间、当前查询窗口的图或未来预测社区。**04 异常信息**独立展示 S12 的账户异常排名、时间对比和记忆生成分数。**05 分析概览**展示数据集统计、查询结果分析和摘要。

03 默认展示整个图，点击「开始挖掘」「开始查询」或「开始预测」并得到结果后，只绘制查到的社区成员和内部边。切换算法或阶段时清除结果，恢复全图。三个阶段共用基于 S01—S11 计算的 ForceAtlas2 坐标。标签自动避让，悬停成员或内部边时突出整个社区。点击 04 账户返回 S12 定位，可通过「返回社区」结束社区外账户的单独定位。实现与固定参数见 [图布局说明](frontend/src/graph/README.md)。

## 环境与安装

- Node.js 24.x（自带 npm）。
- uv（`uv --version` 可正常运行）。
- 主 Python 3.10 已安装 PyTorch 2.8.0+cu128，CUDA 可用。本机基础解释器为 `D:/Workshop/Python310/python.exe`，显卡为 RTX 5060 Laptop GPU。

以下命令均从本文件所在的 `demo/` 目录执行：

```powershell
.\setup-backend.ps1
npm --prefix frontend ci
```

后端环境位于 `backend/.venv/`，无需手动激活。初始化脚本以现有 Python 3.10 创建启用 `--system-site-packages` 的环境，复用主环境的 GPU PyTorch；其他项目依赖由 uv 安装，不向主环境安装 FastAPI。`tool.uv.exclude-dependencies=["torch"]` 防止重复下载；主 PyTorch 及其系统依赖不由 uv.lock 管理。后续可运行 `uv sync --directory backend --locked`。指定其他基础解释器使用 `.\setup-backend.ps1 -Python <完整路径>`。前端仍通过 package-lock.json 管理。

## SLADE GPU 训练与模型准备

初始化环境后，在 `demo/` 下执行：

```powershell
uv run --directory backend python -m scripts.train_slade --dataset email-eu-core-dept3
```

Dept3 使用 S01—S11 的 9,525 条交互训练 10 轮，冻结参数后处理 S12 的 1,208 条交互。当前模型为 `slade-d73301cecdf93996`，在 RTX 5060 Laptop GPU 的 cuda:0 上训练 24.879 秒，损失从 9.47120 降至 9.30169。S12 有 88 个账户可评分，另 1 个没有交互历史的账户单列。合成样例的无向模型为 `slade-bf2fec907f9ca6f5`。

权重、配置、训练指纹与最终参数重放得到的 S11 预热状态存入 `models/email-eu-core-dept3/slade/`；保存、重新加载并核对 S12 评分后，才切换当前模型。模型使用 cuda:0，缺少 CUDA 时明确报错。将命令的 `--dataset` 改为 `synthetic-small` 可重建独立的合成模型，其历史／当前分别为 4,263／183 条交互。训练与检测均不读取 S13。

每个检测请求独立恢复记忆，不读取 S13，不受金额、core 或场景注释影响。模型缺失／损坏或 CUDA 不可用时，04 显示错误与重试，结构查询仍可使用；数据／模型指纹冲突返回 409。配置和复现边界见 [SLADE 说明](backend/algorithms/anomaly/README.md)。合成数据只验证流程，不能据此宣称真实金融异常效果。

## 开发启动

在 Ubuntu 24.04 x86_64 服务器上使用 Docker 和 CPU 运行 Demo，见[远程服务器部署说明](deploy/README.md)。

**LLM-Assisted Interpretation** 输入框显示 **History**、**Current**、**Future** 三项证据提示。分别运行三个阶段的算法并点击 **Submit**，对应位置会填入已提交结果的算法和时间范围。三项齐全后，按钮变为 **Send**，可直接生成报告或先补充问题。三项齐全时，如果当前阶段有新结果，可点击 **Update Evidence** 更新该项。刷新页面会清空会话并恢复三项提示。

报告以提交的 History 社区为基线，按节点 ID 比较 History → Current、Current → Future 的保留、新增和退出成员，并计算三阶段共有成员。留存率以较早阶段的成员数为分母。各阶段使用自己的时间范围、查询节点和核阶数，历史部分引用所选算法找到的模式。异常分析使用 Current 成员的 S12 SLADE 评分，并结合其历史和预计成员身份解释社区内高分节点。输入框的首个问题可留空。

报告完成后，在面板底部输入问题并点击 **Send**。每次追问使用同一组证据、首份报告和此前完成的问答。回复随生成进度追加，**Retry** 可重试中断的回复。首条消息的完整提示词、证据统计口径和 EmailDept3 实例见[报告提示词与证据规则](backend/REPORT_PROMPT.md)。

在 `backend/.env` 填写 `LLM_API_KEY`，保存后重启后端。新检出项目可从 `backend/.env.example` 复制此文件。DeepSeek 使用 `LLM_BASE_URL=https://api.deepseek.com` 和 API 模型 ID `LLM_MODEL=deepseek-flash`。系统环境变量优先。实际 Key 由后端读取，`.env` 已加入 Git 忽略规则。

首次使用并行核分解时，在 `demo/` 目录构建本地程序。

```powershell
uv run --directory backend python -m scripts.build_parallel_core
```

使用现有 WSL Ubuntu 24.04、`g++` 和本地作者源码（含 ParlayLib）。构建后由 Windows 上的 FastAPI 自动调用，不需要手动打开 WSL。构建与算法说明见 [并行核分解](backend/algorithms/core/README.md)。

打开终端一，启动后端：

```powershell
uv run --directory backend fastapi dev --host 127.0.0.1 --port 8000
```

打开终端二，启动前端：

```powershell
npm --prefix frontend run dev
```

- 工作台：<http://127.0.0.1:5173>
- 后端接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

Vite 将 `/api` 原路径代理到后端。前端固定使用 5173 端口，占用时直接报错。浏览器统一请求相对路径 `/api/...`，开发阶段无需配置跨域。

FastAPI 官方 CLI 在底层调用 Uvicorn，无需单独启动另一个服务器。关闭服务时在相应终端按 `Ctrl+C`。

## 构建与单服务演示

先构建前端，再启动或重启后端：

```powershell
npm --prefix frontend run build
uv run --directory backend fastapi run --host 127.0.0.1 --port 8000
```

访问 <http://127.0.0.1:8000>。FastAPI 在应用创建时检测 `frontend/dist/index.html`，存在时托管构建文件；不存在时仍可使用 API 与 `/docs`。

当前是单页入口，无 Vue Router 或子页面路径回退。静态文件挂载在 API 与文档路由之后，未知 API 和缺失资源保持 404。仅运行 `npm run preview` 是查看构建产物；完整演示使用上面的 FastAPI 托管方式。

## 工程分层

```text
demo/
├── frontend/                    # Vite、Vue、Element Plus、Pinia、TanStack Vue Query
│   └── src/
│       ├── api/                 # 原生 fetch 封装和接口请求
│       ├── components/          # 可复用界面组件
│       ├── composables/         # 工作台请求与面板交互
│       ├── domain/              # 共享快照编号和阶段边界
│       ├── graph/               # 图场景、渲染、布局与标签
│       ├── charts/              # 时间证据图表运行时
│       ├── plugins/             # Element Plus 等插件的统一接入
│       ├── stores/              # Pinia 共享交互状态
│       ├── views/               # 分析工作台
│       └── styles/              # 公共布局和各面板样式
├── backend/
│   ├── pyproject.toml           # 依赖、FastAPI 入口与测试配置
│   ├── uv.lock                  # uv 依赖锁文件
│   ├── .python-version         # Python 3.10
│   ├── .venv/                   # uv 虚拟环境
│   ├── app/
│   │   ├── main.py              # 应用工厂、路由与静态托管
│   │   ├── core/                # 配置和基于文件位置的项目路径
│   │   ├── api/                 # HTTP 路由
│   │   ├── schemas/             # Pydantic 输入输出定义
│   │   ├── services/            # 业务与算法调用编排
│   │   └── repositories/        # 本地数据文件读写
│   ├── algorithms/
│   │   ├── core/                # Core 与结构查询
│   │   ├── patterns/            # 历史模式挖掘
│   │   ├── anomaly/             # SLADE 账户状态检测
│   │   ├── link_prediction/     # Zebra 未来链接预测
│   │   └── affinity/            # 旧份额接口兼容适配器
│   ├── scripts/                 # 数据准备、训练和评价
│   └── tests/                   # 接口与关键集成检查
├── data/                        # 清单、逐笔交易与快照
├── models/                      # 权重、配置与预处理参数
└── exports/                     # 主动导出的分析结果
```

原始交互原型保留在同级的 `../demo-ui/`。前端图形使用 Sigma.js＋Graphology，时间证据使用 ECharts。

| 要维护的功能 | 入口与职责 |
| --- | --- |
| 时间轴与快照 | `SnapshotNavigation.vue` 管界面，`composables/workbench/useSnapshotQueries.js` 管区间请求，后端 `services/graphs.py` 读取快照并组装图。 |
| 历史挖掘与当前查询 | `HistoryControls.vue`、`CurrentControls.vue` 管参数表单；`useStructureQueries.js` 管提交和选择；后端 `services/patterns.py`、`services/queries.py` 调用对应算法。 |
| 图结构 | `GraphPanel.vue` 选择展示范围，`graph/scene.js` 组装场景，`useGraphCanvas.js` 管交互与销毁，`graph/sigmaRenderer.js`、`graph/labels.js` 分别管 Sigma 和标签。 |
| 异常、时间证据、未来预测 | 前端在 `composables/workbench/` 下各有请求模块，后端分别由 `services/anomalies.py`、`services/evidence.py`、`services/future_community.py` 处理。未来社区复用 `services/link_prediction.py` 的模型评分。 |

后端路由按请求创建 `AnalysisScope`，统一核对数据版本和观察截止，并生成响应元数据。`services/structures.py` 组装结构及其指纹，`services/selection.py` 按原条件复核结构；时间证据和预测共用这条路径。旧份额接口在 `services/legacy_affinity.py`。

- **新增历史算法**：在 `algorithms/patterns/` 写纯算法，在请求 schema 和 `services/patterns.py` 接入参数、调用与证据映射，在 `config/query-defaults.json` 配置两个数据集的默认值，再补 `HistoryControls.vue` 表单及 Store 草稿校验。
- **新增数据集**：在 01 的「数据集新增」上传一个 `u,v,t` CSV，导入后自动切换。后端 `services/dataset_import.py` 校验与划分快照。 [上传格式](data/README.md#从工作台新增)
- **新增面板**：从 `AnalysisWorkbench.vue` 装配组件。面板共用已有结果，独立请求放入对应的业务模块。

## 当前接口

| 方法 | 路径 | 当前返回 |
| --- | --- | --- |
| GET | `/api/health` | `status`、`service`、`version` |
| GET | `/api/capabilities` | 实际计算标记 `ready`；演示模块标记 `demo`；没有数据时标记 `unavailable` |
| GET | `/api/datasets` | 读取本地数据集清单，附带版本、时间戳单位、快照粒度和合成数据标识 |
| POST | `/api/datasets/import` | 通过表单字段 `file` 上传单个 `u,v,t` CSV，返回新数据集清单摘要 |
| GET | `/api/datasets/{id}/snapshots` | 13 个位置的时间元信息，观察截止 S12 |
| GET | `/api/datasets/{id}/snapshots/{sid}` | S01—S12 的完整快照；需要 `dataset_version` 参数；S13 返回 404 |
| GET | `/api/datasets/{id}/aggregate` | S01—S11 的包含两端区间聚合图；需要起止快照和数据版本 |
| POST | `/api/queries/local-core` | 在 S12 执行并行核分解，或用 TCCS 查询截至 S12 的回溯窗口。返回包含 `q` 的 k-core 连通分量 |
| POST | `/api/queries/max-core` | 传入 `algorithm="pkmc"` 查询 S12 的完整最高阶核 |
| POST | `/api/queries/density` | 原型候选范围内的密度筛选，`demo_heuristic` |
| POST | `/api/patterns/mine` | 在提交区间内逐快照运行 TD＋FT/AC、ONCE、MBC-B、在线频率感知核及 OTCD |
| POST | `/api/anomalies/discover` | 可指定 `snapshot_id`，默认 S12；S12 返回 SLADE 账户评分，默认 Top-10；历史直接请求返回 `not_evaluated` |
| POST | `/api/evidence/series` | 固定成员的内部连接数或交易次数，`computed` |
| GET | `/api/datasets/{id}/link-prediction/models` | 所选预测步长的 Zebra 模型状态 |
| POST | `/api/link-prediction/community` | 根据 `account`、`k`、`threshold` 和 `horizon` 返回预测社区及筛选统计 |
| POST | `/api/link-prediction/predict` | 保留的成对预测接口，返回已提交结构内全部无序顶点对的独立连边概率 |
| POST | `/api/affinity/predict` | 已弃用的旧示例份额接口，页面不调用 |
| POST | `/api/affinity/observed` | 保留的后端接口，统计 S13 实际交易次数份额；页面不调用 |

计算请求携带 `dataset_id`、`dataset_version`、`observed_until` 及相应参数。接入流程、结构传递和错误状态见 [接口接入说明](backend/API_INTEGRATION.md)，完整字段定义可查 `/docs`。结果包含 `request_id`、`result_kind`、`method`、`elapsed_ms`。SLADE 和 Zebra 返回实际 `model_version`，无模型模块为 null。Top-10 是展示范围，不表示这些账户已被判定异常。

页面先读取服务、模块和数据集，优先选择 `email-eu-core-dept3`，加载 S12 的 89 个节点。点击「开始查询」后执行默认 `q=49、k=7` 查询，03 展示返回的 30 个成员及内部边。周期／持久也默认使用 `q=49`。前端与 API 共同读取 [查询默认配置](config/README.md)，省略字段采用各数据集经过验证的严格非空参数，明确提交的字段优先。默认数据集缺失时选择清单中可用数据，合成数据使用其对应的 `q=a-001`。每个分析面板都有加载、空结果、失败及重试状态。切换浏览器焦点或网络恢复不自动重新请求。

## Email Dept3 真实数据准备

已将 SNAP 官方 Dept3 邮件子网转换为标准快照数据，路径为 `data/email-eu-core-dept3/`，ID 为 `email-eu-core-dept3`。v2 截取长空白之前的连续活跃前段，保留 89 个节点和 12,099 条交互，包括重复记录。原始归档完整保留 12,216 条。接口的有效版本为 `email-eu-core-dept3-v2-430dde7de92f-undirected-v1`，S12 显示 320 条无向边并累计 1,208 次交互。

在 `demo/` 下重建：

```powershell
uv run --directory backend python -m scripts.import_email_dept3
```

输入归档为 `data/raw/email-Eu-core-temporal-Dept3.txt.gz`，输出为 S01—S13 的 `u,v,t` CSV 与节点、快照及来源配置。固定保留 `0 ≤ t < 45,310,384`，边界依据一次约 273 天的无交互间隔确定。保留前段重新等宽分成 13 片，每片 58,091 分钟（约 40.34 天），全部非空；历史／当前／后续观测分别有 9,525／1,208／1,366 条记录。数据来源只有相对秒，`timestamp_basis=relative`；时间戳及内部时间间隔不变，ISO 的 1970 日期仅为技术编码。重建后重启后端清除文件缓存。详细口径见 [数据包说明](data/email-eu-core-dept3/README.md)。

周期默认 `account="49", k=4, epsilon=1`，返回 35 人。持久默认 `account="49", k=3`，返回 76 人，在 S01—S06 形成，稳定至 S10，共 4 个快照。爆发默认 `l=3, delta=5.60`，返回 45 人。S12 局部 core 默认 k=7，返回 30 人。密度默认 1，返回 6 个三人结构。固定账户和爆发长度时，局部 k=8、持久 k=16 或爆发 δ=6.67 均无结果。数据版本指纹包含来源与截断、分片规则，旧 v1 请求返回 409。SLADE 已使用该 v2 历史数据独立训练并启用，异常检测不复用合成模型。Dept3 的未来模块使用独立训练的 Zebra 模型。

## 合成样例与演示流程

样例数据随源码提供，存放于 `data/synthetic-small/`。固定种子 `20261116`，接口版本 `synthetic-small-v3-undirected-v1`。逐快照原始文件为 `S01.csv`—`S13.csv`，表头为 `u,v,t`。`u` 和 `v` 为无向连接的两端，`t` 为 Unix 秒时间戳。节点和快照配置独立保存为 JSON，重复交互按行保留。字段与数据组织见 [图数据结构](data/README.md) 及 [样例说明](data/synthetic-small/README.md)。

需要重新生成时执行：

```powershell
uv run --directory backend python -m scripts.generate_sample
```

此命令只覆写该合成样例的 13 个 CSV 和 5 个配置 JSON，不用于导入真实交易。

1. 在 02 进入 History，选择算法并设置 Range，然后点击 Run Query。五种方法都使用范围内的逐快照数据。时域核查询成功后，01 和 03 定位到首项结果的最紧区间，05 可以选择其他结果。
2. 回到 S12，在 02 选择算法。并行核分解与 TCCS 接收 `q` 和 `k`，TCCS 还可设置起始快照。PKMC 选中即计算 S12 的完整最高阶核。03 高亮实际查到的成员和内部边。
3. 在 04 检查独立加载的异常排名，点击账户以红橙色和尺寸在 03 定位；02 的查询结构与 05 时间轨迹保持原选择。历史视图同样显示当前 S12 的分析结果，点击异常先返回 S12 定位。
4. 进入 Future，在 02 选择 Target snapshot，填写 q、k 后点击 Run Prediction。Zebra 使用截至 S12 的观测为 S01—S11 历史社区成员并集中的顶点对评分，再在预测图上求包含 q 的 k-core。01 的单个 Future 格显示已提交的编号。更改目标后再次提交才会切换预测。拖动阈值会即时更新已提交目标的预测社区。

历史成员来自独立算法；SLADE 只读取逐笔 `u、v、t`，同时间戳按文件顺序稳定处理，不读取 core 或场景注释。场景文件仅保留预测示例权重和数据构造参考。底部轨迹的内部连接数、次数始终来自所选数据集的实际交互。金额、资产、首位数字与交易 ID 已从当前数据契约及展示中移除。预测流程不读取 `S13.csv` 或 `replay.json`，也不在普通快照接口暴露未来交易。

01 的历史刻度可单击查看单个快照。拖动选区两端调整范围，拖动中间平移，从空白轨道拖出新区间。拖动时在 01 预览，松手后更新 03 图结构和 05 的时间选区。02 保存各算法的挖掘范围并在提交时应用。结构参考统计取所提交区间的终点，逐快照证据覆盖本次挖掘范围。

当前搜索默认采用 SIGMOD 2025 作者的并行核分解实现。每个数据版本首次查询 S12 时计算核数，后续修改 `q` 或 `k` 时直接从缓存图提取连通分量。EmailDept3 的默认 `q=49, k=7` 返回 30 个账户、145 条内部无向边。TCCS 用 Python 在线计算，选择 S10—S12 时，同样参数返回 52 个账户。03 展示对应的窗口图，05 标出查询窗口并继续逐快照统计。

PKMC 用 Python 同步执行邻居 h 指数更新。根据定理 1，当相邻两轮的最高估计值和达到该值的成员集合都相同时即可提取最高阶核。EmailDept3 的 S12 得到 30 个账户和 145 条内部无向边的 7-core。合成样例得到 5 个账户和 10 条内部无向边的 4-core。见 [ICDE 2023 论文的算法 2](https://chenhao-ma.github.io/papers/ICDE23dsd.pdf)。

合成数据历史默认参数：周期 `q=a-001、k=4、ε=1`，持久 `q=a-001、k=4`，爆发 `l=3、δ=5`。`synthetic-small-v3` 中周期返回 5 个账户、周期 3／重复 3 次；持久返回同一组 5 个账户、持续 5 个时间步／稳定至 S06；爆发返回 6 个账户、见证区间 S07—S09／MSD 为 5。参数草稿不会影响已提交结果。算法契约、来源和周期复现限制见 [历史算法说明](backend/algorithms/patterns/README.md)。

频率感知核在 Dept3 用 `k=6、t=4、f=0.8` 得到 7 个账户、21 条达标无向边；在合成样例用 `k=5、t=3、f=1` 得到 6 个账户、15 条。查询无需账户，对同一对账户在每个快照只计一次活跃。03 和 05 都从同一组达标边读取实际连线和交互次数。见 [频率感知核说明](backend/algorithms/patterns/FREQUENCY.md)。

时域核以一个快照为时间单位，搜索所选范围内每个连续子区间产生的不同 `k`-core。Dept3 默认查询 S10—S11，得到 18 个节点的 7-core。合成样例默认查询 S10，得到 5 个节点的 4-core。点击 05 的结果可查看其最紧区间和结构。手动移动时间轴后，可浏览其他范围的完整聚合图并从列表返回核。[时域核算法说明](backend/algorithms/patterns/TEMPORAL_CORE.md)

v3 精简记录字段并改为 CSV，保留 v2 全部逐笔端点、时间和次数，已训练匹配版本的 SLADE 模型。JSON 到 CSV 的物理格式转换不改变逻辑数据或模型指纹，继续使用已有 GPU 权重。其他过严条件仍可能返回正常的空结果。

## 开发约定与后续接入

1. **前端状态。** Pinia 保存历史起点、时间终点、参数草稿、已提交条件、结果选择和未来显示状态；TanStack Vue Query 按数据版本、快照或起止区间、成员范围管理接口结果，不在 Store 重复保存响应。
2. **接口分层。** 路由校验并返回数据，`services` 组织流程，`repositories` 读取文件，`algorithms` 保存算法实现及原生适配器。训练脚本与在线服务复用算法模块。
3. **数据路径。** 使用 `app/core/config.py` 中的 `Settings` 获取 `data_dir`、`models_dir`、`exports_dir`，不依赖命令执行时的工作目录。
4. **算法分层。** Core 入口在 `algorithms/core/queries.py`；历史纯函数位于 `algorithms/patterns/`，公共输入输出位于 `common.py`，数据适配位于 `app/services/patterns.py`；SLADE 位于 `algorithms/anomaly`，服务适配位于 `app/services/anomalies.py`；Zebra 位于 `algorithms/link_prediction`，服务适配位于 `app/services/link_prediction.py`；旧份额适配器仅用于兼容。模块不依赖 HTTP 或本地路径，Web 与离线脚本可共同调用。已复用 GPU PyTorch 并安装 NumPy，未安装 pandas、PyArrow 或 PyG。
5. **图形界面。** Element Plus 按需显式注册组件，统一中文和紧凑主题。Sigma 图组件提供缩放、平移、标签及方向；ECharts 提供原始值提示与多轨迹对照。页面不使用路由框架。
6. **计算方式。** HTTP 请求直接调用算法并在同次响应返回，不使用数据库、Redis、任务队列或持久化任务中心。文件缓存只存在于单次请求的 Repository 实例中。
7. **文件管理。** 虚拟环境、依赖和构建产物被忽略；小型合成样例与明确接入的公开 SNAP Dept3 数据纳入版本控制，其他真实数据、模型权重和导出结果保持本地存储。

修改依赖时使用对应工具，并保留更新后的锁文件：

```powershell
# 示例：后续确需读取 Parquet 时再执行
uv add --directory backend pandas pyarrow

# 前端修改依赖时使用 npm，并保留 package-lock.json
npm --prefix frontend install <package>
```

功能与算法定义继续以项目上层方案为准。演示中的“交易次数、下一快照 10 分钟窗口”是本轮展示配置，不替代正式模型的标签与方法选型。

## 验证

安装依赖后，在 `demo/` 下运行：

```powershell
.\test.ps1        # 日常回归
.\test.ps1 -Full  # 完整验证
```

日常回归检查服务启动、数据导入与聚合、五种历史算法、S12 查询与时间证据、评分公式及预测时间隔离。它使用已安装的项目依赖，不训练模型、不执行 CUDA 运算，也不调用 WSL。两个入口都运行全部前端用例，无需启动服务。

修改模型或原生适配器时运行完整验证。它额外用小样本在 GPU 上训练、保存并通过接口加载 SLADE 和 Zebra，并将 WSL 求出的 Dept3 核数与串行结果对照。WSL 对照需先[构建原生程序](backend/algorithms/core/README.md)。改动页面或准备演示时，另运行 `npm --prefix frontend run build`，并按上述四步在浏览器联调。主要演示尺寸为 1440×900，页面最小宽度为 1280px，图需要支持 WebGL 2 的浏览器。

SLADE GPU 训练、Python 3.10 环境、历史算法及工作台联动的验证结果见[验证记录与截图索引](VALIDATION.md)。

## Zebra GPU 链接预测

```powershell
uv run --directory backend python -m scripts.train_zebra --dataset email-eu-core-dept3
```

使用现有 Python 3.10、GPU PyTorch 和 NumPy；以现有库版本为准适配代码，不安装 Zebra 原仓库的依赖清单、不更改锁文件。训练及推理使用 cuda:0；SANTA 字典操作在主机执行。

用截至 S01—S08 的历史分别预测 S02—S09，S10 选择模型、S11 温度校准、S12 独立回测。冻结参数后读入真实 S12 并预测 S13。无序顶点对在下一快照发生至少一次交互即为正例，已有连接也参与。全图编码后按所选社区提取成对概率。截至观察截止无交互历史的账户列为未评分。训练、回测和页面预测均不读取 S13。

模型、S11 预热状态和报告保存到 `models/email-eu-core-dept3/zebra/`。恢复核对成功后才激活 `current.json`。算法依据、原文与适配差异见 [Zebra 说明](backend/algorithms/link_prediction/README.md)。

Dept3 无向基础模型 `zebra-4361fbd78cb2a8ba` 采用第 24 轮，训练耗时 275.339 秒。S12 回测 AP=0.2492、ROC-AUC=0.7864、Brier=0.0700、对数损失=0.2483。校准版本与回测结果见下文及 [验收记录](VALIDATION.md)。

当前页面使用无向校准版本 `zebra-a55d8f6ef5de5b56`。校准层使用基础模型分数和最近三个快照的成对交互特征。校准标签为 S11，S12 回测 Brier 分数为 0.0515，对数损失为 0.1941。重新训练基础模型后，可在 `demo/` 中运行 `uv run --no-sync --directory backend python -m scripts.calibrate_links --dataset email-eu-core-dept3`，生成并验证校准版本。UnderGS 代码和产物保留作[离线对照](backend/algorithms/link_prediction/undergs/README.md)。

S13、S14 和 S15 对应提前 1、2 和 3 个快照的预测。S14、S15 复用 Zebra 历史编码器，各自训练并校准预测头。[训练命令与回测](backend/algorithms/link_prediction/README.md#多步预测)

