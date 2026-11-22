# 工作台接口接入说明

本文对应真实历史算法、SLADE 账户状态检测及 Zebra／UnderGS 下一快照链接预测。运行服务后可在 `/docs` 查看由 Pydantic 生成的完整字段定义，在 `/openapi.json` 获取机器可读契约。

## 1. 请求顺序与时间边界

1. 读取 `GET /api/health`、`GET /api/capabilities` 和 `GET /api/datasets`。
2. 根据选定数据集读取 `GET /api/datasets/{id}/snapshots`。清单包含 S01—S13 的时间位置、版本和观察截止，但不包含 S13 的交易或份额。
3. 历史读取区间聚合图；当前提交以 S12 为终点的结构查询，保存完整 `Structure`。单快照读取 S12 图，多快照使用查询返回的 `window_graph`。异常检测独立返回账户评分。
4. 时间证据请求携带完整结构。未来查询独立提交 q、k 及模型，使用截至 S12 的观测预测 S13。

图布局另外复用聚合接口读取固定的 S01—S11，仅用于前端坐标生成。画布和 ForceAtlas2 都使用无向边。全图与社区视图按各自快照或区间的图数据过滤成员与实际连接。

样例 ID 为 `synthetic-small`，观察截止为 `S12`。数据集列表返回带 `-undirected-v1` 的有效版本，前端使用此版本提交计算请求。

```json
{
  "dataset_id": "synthetic-small",
  "dataset_version": "synthetic-small-v3-undirected-v1",
  "observed_until": "S12"
}
```

`snapshot_id` 对当前查询表示固定终点 S12。快照读取示例为：

```text
GET /api/datasets/synthetic-small/snapshots/S12?dataset_version=synthetic-small-v3-undirected-v1
```

普通快照接口只读取 S01—S12。请求 S13 返回 404，未来画布使用预测社区接口返回的成员和预测边。

### 上传数据集

`POST /api/datasets/import` 接收 `multipart/form-data`，字段 `file` 为单个 UTF-8 `.csv` 文件，固定列为 `u,v,t`，`t` 使用 Unix 秒。两个端点顺序不限，重复交互按行保留。成功返回 HTTP 201 及与数据集列表一致的清单摘要，前端刷新列表并切换。格式错误返回 422，行内容错误的 `detail` 包含 CSV 行号和原因。

导入生成 S01—S12 的等宽观测快照及 S13 的预测窗口。清单中的 `query_defaults` 提供新数据集的 `current_account`、`current_k` 和可空的 `history_account`。页面按此提交新数据集的 `account`、`k`。快照存储与时间口径见下方说明。 [上传格式与分片规则](../data/README.md#从工作台新增)

### Email Dept3 数据包

页面默认选择 `email-eu-core-dept3`，版本从 `GET /api/datasets` 响应读取；`synthetic=false`、`timestamp_unit=seconds`、`timestamp_basis=relative`。当前和周期／持久查询默认账户为 `49`。合成样例及省略该字段的旧清单默认为 `timestamp_basis=unix`。相对数据的 ISO 日期仅为 UTC 1970 技术零点编码，不能用作真实发生日期；`t` 完整保留源文件中的相对秒。

相同接口直接支持该数据包。历史挖掘请求示例（`dataset_version` 替换为清单中的实际值）：

```json
{
  "dataset_id": "email-eu-core-dept3",
  "dataset_version": "email-eu-core-dept3-v2-430dde7de92f-undirected-v1",
  "observed_until": "S12",
  "pattern": "periodic",
  "account": "49",
  "k": 4,
  "epsilon": 1
}
```

v2 固定保留 `0 ≤ t < 45,310,384` 的 12,099 条交互，原始压缩包仍完整保留 12,216 条。保留时段等宽分为 13 片，每片 58,091 分钟。S01—S11 有 9,525 条交互，S12 有 1,208 条，S13 单独保留 1,366 条。S12 返回 89 个节点和 320 条无向边。默认 `account="49", k=7` 的局部 core 返回 30 人、145 条内部边。

版本校验同时覆盖快照配置和读取口径。使用旧版本的请求返回 409，重新读取清单可取得当前版本。Dept3 的 SLADE、Zebra 和 UnderGS 按无向事件独立训练。`POST /api/anomalies/discover` 在 S12 评分，默认返回 Top-10，`top_r: null` 可取全部 88 个已评分账户。来源、逐片统计和重建命令见 [数据包说明](../data/email-eu-core-dept3/README.md)。

历史区间读取示例：

```text
GET /api/datasets/synthetic-small/aggregate?start_snapshot_id=S03&end_snapshot_id=S07&dataset_version=synthetic-small-v3-undirected-v1&observed_until=S12
```

仅接受 S01—S11 内包含两端的连续区间，允许 start=end。响应为 `AggregateResponse`：公共计算元数据、`start_snapshot_id`、`end_snapshot_id`、按时间排列的 `snapshot_ids`、`starts_at`、`ends_at`，以及与单快照一致的 `nodes`、`edges`、`stats`、`core_numbers`。实际时间从起始快照开始至结束快照结束，例如 S03—S07 为 `[10:20, 11:10)`。

账户取实际存在集合的并集，保留孤立账户。无向边按节点对累计交互次数，密度和 core number 在聚合后的无向图上重新计算。单快照区间的四项图字段与对应快照接口相同。`result_kind=computed`，`method=historical-transaction-union-v1`。

未知快照返回 404，逆序或端点为 S12/S13 返回 422，版本冲突返回 409。该接口只读取所选历史快照。历史挖掘使用单独提交的挖掘区间，其默认值为 S01—S11。

## 2. 查询与结构传递

当前 S12 并行核分解请求示例：

```text
POST /api/queries/local-core
Content-Type: application/json
```

```json
{
  "dataset_id": "synthetic-small",
  "dataset_version": "synthetic-small-v3-undirected-v1",
  "observed_until": "S12",
  "snapshot_id": "S12",
  "account": "a-001",
  "k": 4
}
```

页面默认在 S12 执行并行核分解，提交 `account`（`q`）和 `k`。响应使用 `method=sigmod25-parallel-kcore-v1`、`result_kind=computed`、`window_graph=null`。合成数据默认结果为五账户 `{a-001,a-002,a-007,a-008,a-013}`。省略 `account` 或 `k` 时使用数据集默认值。S12 无向简单投影的核数在后端进程内按数据版本复用。

选择 TCCS 时发送 `algorithm="tccs"`，`start_snapshot_id` 可选 S01—S12，默认 S12。包含两端的窗口使用 `method=tccs-online-v1`。即使窗口只有 S12 或没有匹配结构，也返回 `window_graph`，含 `start_snapshot_id`、`end_snapshot_id`、`snapshot_ids`、`nodes`、`edges`、`stats`、`core_numbers`。核分解和显示使用窗口的无向并集，边上累计逐笔交互。

返回的连通分量包含 `q`，`Structure.snapshot_id` 为 S12。显式提交的算法及 TCCS 起点写入 `Structure.parameters`，参与结构哈希，并用于时间证据和兼容成对预测接口的复核。结构统计基于查询窗口。

显式传 `algorithm="parallel"` 时只接受 S12 单快照。旧请求省略 `algorithm` 时，省略起点或指定 S12 执行并行核分解，起点在 S01—S11 时执行 TCCS，沿用旧结构参数和指纹。

`q` 存在但核数低于 `k` 时返回 200 和空 `structures`，页面展示查询所用的完整图。未知快照为 404，未来端点、结束不为 S12、逆序窗口或无效账户及参数为 422，版本冲突为 409。并行程序缺失、异常退出或超时返回 503。普通快照读取、TCCS 和 PKMC 由 Python 执行。查询读取的逐笔交互来自所选已观测窗口。

全局最大核使用 `POST /api/queries/max-core`，提交公共数据上下文及 `algorithm="pkmc"`，`snapshot_id` 默认为 S12。PKMC 只读取 S12，从完整无向简单投影自动求出最高非空核阶数及其成员。接口返回 `method="pkmc-v1"`、`result_kind="computed"`，完整最高阶核作为一个 `origin="max_core"` 的结构，包含所有同阶连通分量。例如 EmailDept3 返回 `parameters={"algorithm":"pkmc","max_core":7}`。时间证据和链接预测使用相同算法复核所选结构。空图返回空 `structures`，非空无边图返回 0-core。

| 接口 | 参数 | 当前行为 |
| --- | --- | --- |
| `/api/queries/max-core` | 可选 `snapshot_id`、`algorithm="pkmc"` | PKMC 返回完整最高阶核。省略算法时按原协议返回最高阶核的各个连通分量，方法为 `maximum-core-v1` |
| `/api/queries/density` | `snapshot_id`、`threshold ∈ [0,1]`（默认 1） | 保留兼容，Core 分量与闭一跳邻域候选筛选 |
| `/api/patterns/mine` | 按 `pattern` 区分的参数、可选起止快照 | 在所选区间的逐快照数据上运行 TD＋FT/AC、ONCE、MBC-B 或在线频率感知核 |
| `/api/anomalies/discover` | 可选 `snapshot_id`（默认 S12）、`top_r`（默认 10） | S12 返回 SLADE 实际账户评分；历史直接请求返回未评估状态 |

`Structure` 包含来源 `origin`、已提交条件 `parameters`、`members`、`snapshot_id`、版本与截止、`membership_hash`、方法标识、统计与可选证据。时间证据和兼容成对预测接口使用服务端返回的完整对象。

异常响应不再包含 `structures`，而是 `snapshot_id`、`status: ok / not_evaluated`、`method=slade-v1`、`model_version`、`scored_at`、`training_snapshot_ids`、`accounts`、`unscored_accounts` 和 `message`。账户项包含 `account_id,rank,score,temporal_contrast_score,memory_generation_score`，按分数降序、ID 升序。综合分数为两项余弦距离的和除以 4，范围 [0,1]，分项范围 [0,2]；不设分类阈值，不解释为欺诈概率。`top_r` 接受 1—100 的整数或 `null`，省略时返回前 10 个账户。页面用 `top_r: null` 读取全部评分，供查询结果分析筛选社区成员，异常排名显示前 10 名。

S01—S11 直接请求为 `not_evaluated`、空 accounts；S12 返回 `ok`，空 accounts 表示没有可评分账户，不等于已证明无异常。没有交互历史的账户列入 `unscored_accounts`，reason 为 `no_interaction_history`。请求 S13 或未知快照返回 404。省略 snapshot_id 仍默认为 S12；旧异常 Structure 不再受支持。

04 在历史、现在和未来均独立加载 S12 SLADE 账户评分，未来标为 S12 异常背景。点击账户先回 S12 并在 03 以红橙色和尺寸定位，不改变查询参数、查询成员、05 轨迹或未来范围。刷新不自动定位，保留仍有效的同模型账户选择；数据／模型版本改变时清除旧依据。提交查询或显式选择结果清除账户定位。

服务端按照来源重新执行查询或历史算法，复核结构 ID、版本、快照、成员和哈希，并使用重新得到的统计。不要自行拼造结构或把参数草稿混入已提交结构。历史模式的结构参考快照为 S11，其成员时间轨迹独立逐快照计算。

### 历史挖掘参数与输出

`POST /api/patterns/mine` 的请求以 `pattern` 为判别字段，OpenAPI 提供四个 `oneOf` 输入定义：

| pattern | Email Dept3 默认值 | 合成数据默认值 | 方法版本 |
| --- | --- | --- | --- |
| `periodic` | `account="49", k=4, epsilon=1` | `account="a-001", k=4, epsilon=1` | `lpc-td-ftac-v1` |
| `durable` | `account="49", k=3` | `account="a-001", k=4` | `tdc-once-v1` |
| `burst` | `l=3, delta=5.60`（界面提交 `account="49"`） | `l=3, delta=5`（界面提交 `account="a-014"`） | `mbc-exact-segments-v1` |
| `frequency` | `k=6, t=4, f=0.8` | `k=5, t=3, f=1` | `frequency-aware-kcore-online-v1` |

前后端共用 `demo/config/query-defaults.json`。查询账户和爆发阈值按数据集设置，爆发最小长度默认为 3 个快照。Dept3 默认持久社区有 76 人，在 S01—S06 形成，稳定至 S10，共持续 4 个快照。各方法的默认结果见 [默认配置说明](../config/README.md)。

四种方法均可同时提交 `start_snapshot_id` 和 `end_snapshot_id`，首尾均包含。省略两端时使用 S01—S11。仅填一端、逆序或选择 S12／S13 均返回 422，未知快照返回 404。

周期、持久与爆发查询中，提交的 `account` 须非空且存在于所选历史区间的账户并集。内置数据集去除账户首尾空白，导入数据集使用原始 ID。爆发查询仅在最大爆发核包含该节点时返回结果，省略 `account` 仍返回全局爆发核。k 为正整数，epsilon 在 `[0,1]`，l 为不超过区间快照数且不少于 2 的整数，delta 为正有限数。频率感知核不接受 account，t 为不超过区间快照数的正整数，f 为 `[0,1]` 内的有限数。其他方法的字段及未知字段均返回 422。仅发送 `{公共上下文, pattern}` 使用该方法的默认参数。无数据集为 404，版本冲突为 409，本地历史文件或帧缺失为 404。

响应为 `PatternsResponse`，`analysis_snapshot_ids` 给出实际计算的快照，`reference_snapshot_id` 为区间终点。结果标记为 `computed`。合法无解返回 200、空列表及原因。

结构 `parameters` 保存归一化后的完整提交条件，哈希还包含算法方法版本；`evidence` 保留以下算法原始量，并补充 `analysis_snapshot_ids` 和对应位置的快照 ID：

- 周期：`kcore_series`、`period`、`frequency`、`start_index`、`end_index`，后两者分别对应 `start_index_snapshot_id`、`end_index_snapshot_id`，另含谱筛选信息。
- 持久证据包含 `formation_start`、`formation_end`、`stable_end` 和 `duration`，各位置带有对应的 `_snapshot_id`。持续时间为结束稳定和形成时的位置差，保留零时长有效解。`member_count_series` 固定窗口起点为 `formation_start`，按终点顺序记录各次查询的社区成员数，对应 `analysis_snapshot_ids[formation_start:]`。没有社区的窗口记为 0。
- 爆发：`nodes[]` 中的 `account`、`degree_sequence`、`numerator`、`denominator`、`witness_start`、`witness_end`，并补 `max_average_degree` 和见证位置对应的 `_snapshot_id`。不同成员可有不同见证区间。
- 频率感知核：`qualified_edges[]` 中的 `u`、`v`、`numerator`（见证区间内活跃快照数）、`denominator`（区间快照数）、`frequency`、`witness_start`、`witness_end` 及相应的 `_snapshot_id`。只返回最终核内的达标无向边，各边见证可不同；多个连通分量仍属于同一个返回结构。

内部位置以区间起点为零，两端均包含。逐快照证据复核输入的挖掘范围及完整参数，并使用该范围内的快照。原始度与平均度均按不同邻居计数。算法来源、TD 的复现约定和已知漏解限制见 [历史算法说明](algorithms/patterns/README.md)。v3 样例在完整历史中的默认结果包括周期社区 5 个成员、周期 3、重复 3 次，持久社区 5 个成员、持续 5 个时间步、稳定至 S06，以及爆发核 6 个成员、MSD 为 5、见证区间 S07—S09。数据构造见 [样例说明](../data/synthetic-small/README.md)。

频率感知核的默认结果在 Dept3 为 7 个成员、21 条达标无向边，在合成样例为 6 个成员、15 条。频率以快照编号为时间单位，同一对账户一次快照内的多次交互只计一次。区间末尾的结构统计和时间证据以结果中的达标边为限。界面保留展示区间中实际出现的交易方向和次数。

## 3. 统计与时间证据

逐笔交互按快照保存在 `Sxx.csv`，固定表头为 `u,v,t`。读取时排列端点 ID，保留重复交互。自环行涉及的节点仍保留，自环排除在图、交互统计和模型输入之外。快照、历史聚合及 TCCS `window_graph` 的 `edges` 统一返回 `id、u、v、transaction_count`，每对不同节点只有一条边。`stats.internal_edges` 统计边数，`stats.transaction_count` 统计逐笔事件数。旧 `/api/affinity/observed` 的 `source_account` 表示查看账户，累计它与其他成员间的全部交互。原始数据与时间口径见 [图数据结构](../data/README.md)。

`POST /api/evidence/series` 在公共字段之上提交：

```js
{
  structures: [selectedStructure],
  metric: 'internal_edges' // 或 transaction_count
}
```

此处的 `selectedStructure` 为之前的完整响应对象。`series[].points` 返回 `snapshot_id`、`index`、`value`、`present_count` 和 `status`：

- 固定该结构的完整成员范围，统计成员之间的实际交易；频率感知核进一步固定达标边，只统计这些账户对。
- 全部成员缺席时，`status=absent`、`value=null`；存在成员但没有内部交易时为 `status=ok` 和零。
- 次数和内部边数为整数，单位由响应的 `unit` 指定。金额指标已移除，提交 `total_amount` 返回 422。
- 历史模式覆盖 S01—S11；当前查询结构覆盖 S01—S12；均不包含 S13 事实。

前端轨迹按各自最大值缩放，提示框和下方数值保留接口原值。历史背景选区标明 start—end，曲线不累加、不裁剪。切换方法或提交条件更新算法结果与配色，历史拓扑始终来自聚合接口；拖动只改变展示区间，不重新挖掘。页面保留手动时间导航，已移除历史回放。

## 4. 未来 k-core 社区预测

先读取 `GET /api/datasets/{id}/link-prediction/models?dataset_version=...&observed_until=S12`。模型目录返回 Zebra 和 UnderGS：`status` 为 `ready / not_ready / conflict / not_implemented`，同时返回 `model_version` 和原因。两种方案均已接入，当前均按对应权重返回 ready、not_ready 或 conflict；not_implemented 仅保留类型兼容。

已接入近期交互校准的模型返回 `probability_calibration=recent-pair-logistic-v1`。校准输入包含基础模型分数、最后一个已观测快照是否连边，以及最近三个快照内的连边快照数和交互总次数。基础版本的这一字段为 null，概率沿用温度校准。两个预测接口使用当前模型版本的同一份概率。

```text
POST /api/link-prediction/community
{ ...公共上下文, "account": "49", "k": 4, "model": "zebra", "threshold": 0.5 }
```

默认选择 Zebra，默认查询条件读自 `config/query-defaults.json`。`account` 必须是数据集内的节点，`k` 为 0 至 10000 的整数。当前搜索和未来预测的核数快捷项均取查询节点在 S12 整图的 `core_numbers`。S01—S11 每片单独使用无向简单投影求包含 q 的 k-core 连通分量。取成员并集作为候选，再用截至 S12 的概率为候选节点对建图。未舍入的概率须严格大于 `threshold`，最终返回预测图上包含 q 的 k-core 连通分量。k=0 时，已有候选对评分且 q 没有保留连边，可返回仅包含 q 的 0-core。阈值允许 0 至 1，省略时为 0.50。页面滑条每档 0.1，松开后使用已提交的 q、k 更新预测。

| 响应字段 | 含义 |
|---|---|
| account / k / model / model_version | 查询条件和实际模型版本 |
| history_snapshot_ids / observed_until / target_snapshot | 候选快照范围、模型观察截止和目标快照 |
| candidate_member_count / candidate_pair_count / scored_pair_count | 并集成员数、无序顶点对数和实际评分数 |
| threshold / threshold_edge_count / max_probability | 本次阈值、预筛选保留边数和候选顶点对最高概率 |
| members / edges | 最终社区成员及全部内部边。每条边带 `u`、`v`、`probability` 和 `currently_connected` |
| comparison | 同一 q、k 下 S12 实际社区与 S13 预测社区的成员对照及最高核数节点 |

空结果返回 200。按失败阶段区分 `no_historical_community`、`no_scored_pairs`、`no_threshold_edges` 与 `no_predicted_community`，成功为 `ok`。历史成员并集为空时直接返回，`model_version` 为 null。没有可评分对时 `max_probability` 为 null。

`comparison` 的 `retained`、`added`、`exited` 分别列出两个社区的交集、S13 独有成员和 S12 独有成员。`max_coreness` 是预测社区内的最高核数，`key_nodes` 包含所有并列最高的节点及其 `account_id`、`observed_coreness` 和 `predicted_coreness`。新增节点的 `observed_coreness` 为 null。预测未形成社区时，`max_coreness` 为 null、关键节点列表为空。没有历史候选或可评分对时，整个 `comparison` 为 null。

页面按数据版本、已提交的 q、k、阈值和模型版本匹配响应。03 展示最终社区并支持悬停查看无向连边概率，05 展示成员变化和关键节点。两种模型均以 S12 为观察截止且共享各自的全图概率缓存。权重缺失、损坏或 CUDA 不可用返回 503，数据版本或模型指纹冲突返回 409。

### 成对预测兼容接口

```text
POST /api/link-prediction/predict
{ ...公共上下文, "structure": <完整 Structure>, "model": "zebra" }
```

结构必须来自以 S12 为截止的当前查询，回溯结构沿用完整成员。两种模型均使用截至 S12 的全图历史预测 S13，`currently_connected` 只表示 S12 内是否已有连接。省略 model 默认 Zebra，指定 `model="undergs"` 使用 UnderGS。未知模型或多余 source_account 字段返回 422。成员顺序会先规范化，增删成员或更改查询条件仍须重新查询。

两个方案分别加载自身权重和 S11 预热状态，再消费真实 S12。Zebra 使用事件流，UnderGS 使用完整快照；都只读取截至 S12 的信息。目录分别报告状态，一个方案缺失或损坏不会隐藏另一方案，也不会自动替代用户的选择。群内链接预测能力在至少一个匹配模型就绪时标记可用。

缓存同时包含模型名称、权重版本及 SHA-256、历史／S12 指纹和观察截止。缓存命中仍检查模型文件和 CUDA。

响应使用 `LinkPredictionResponse`，含公共元数据、`method=zebra-window-v1 / undergs-window-v1`、`result_kind=computed`，以及：

| 字段 | 含义 |
|---|---|
| model / model_version | 方案与实际权重版本 |
| structure_id / membership_hash | 已验证的当前查询结构 |
| scored_at | S12 结束时刻 |
| target_snapshot / target_starts_at / target_ends_at | S13 及其完整左闭右开窗口 |
| window_seconds / directed | 预测窗口秒数，directed=false |
| candidate_pair_count | 社区所有无序非自环顶点对数量 |
| scored_pair_count | 有交互历史且实际得到分数的数量 |
| pairs | u、v、probability、rank、currently_connected |
| unscored_accounts | 无历史账户 ID 与 no_interaction_history 原因 |
| status / message | ok、no_candidates、no_history 及说明 |

`u<v` 按字符串字典序规范化，返回按概率降序、u/v 升序排列。`currently_connected` 表示 S12 任意方向存在该连接。每对的概率是 S13 内至少交互一次的模型估计。提交默认的 30 人当前结构有 435 个候选对。

同一对顶点跨社区概率一致。真实事件推进与成对评分分开，评分只读模型状态。

权重缺失/损坏、GPU 不可用或未接入方案返回 503；模型与历史数据指纹或数据版本冲突返回 409。前端隐藏失配结果并提供重试，不回退旧示例。

### 兼容接口

`POST /api/affinity/predict`、`POST /api/affinity/observed` 仍接受旧 `structure + source_account` 请求并保留旧份额响应，OpenAPI 标记 deprecated。新页面不调用这两个接口。只有显式调用旧 observed 接口才读取 S13 交易；它不参与 Zebra／UnderGS 训练、校准、回测或预测。

## 5. 来源、错误与前端缓存

计算响应公共字段含 `request_id`、`result_kind`、`method`、`elapsed_ms`、数据上下文与 `model_version`。SLADE 包含实际模型版本，其他无模型模块的 model_version 为 null。

| `result_kind` | 用途 |
| --- | --- |
| `computed` | 单快照／历史区间聚合、Core、历史三种算法、SLADE 账户评分、固定成员证据、揭晓后的观测 |
| `demo_heuristic` | 原型密度候选筛选，不保证枚举所有合格子图 |
| `demo_fixture` | 场景定义的预测份额 |

异常已完整替换为 SLADE，自监督训练只使用 S01—S11 的 4,263 笔源、目标、时间事件；固定参数后从 S11 预热状态继续处理 S12 的 183 笔交易，在结束时刻 12:00:00+08:00 评分。训练与评分均使用 cuda:0，不使用金额、首位数字、core 或场景注释，不读取 S13。每个请求独立恢复状态，避免刷新与并发改变结果。训练命令和配置见 [算法说明](algorithms/anomaly/README.md)。

| HTTP 状态 | 当前含义 |
| --- | --- |
| 200 + `structures=[]` | 查询无匹配结构；异常使用 accounts 和独立的 status，不返回 structures |
| 404 | 数据集、已观测快照或本地数据文件不存在 |
| 409 | 数据版本、模型训练事件指纹或所选结构上下文不一致 |
| 422 | 参数、时间边界、账户、结构成员或来源无效 |
| 503 | SLADE、Zebra 或 UnderGS 权重缺失／损坏／加载失败，或 CUDA 不可用 |

错误信息使用 FastAPI 的 `detail` 字段。前端错误时隐藏失配结果并提供重试。聚合缓存键包含版本和起止快照，拖动约 150ms 防抖、释放立即提交。历史挖掘缓存键包含版本、方法和已提交参数。当前查询缓存包含版本、快照、已提交条件，证据增加成员哈希。未来社区缓存按观察截止、数据版本、已提交的 q、k、阈值、模型和模型版本区分。

## 6. 替换正式方法的位置

- `algorithms/core/queries.py`：Core、连通分量与密度候选。
- `algorithms/patterns/periodic.py`、`durable.py`、`burst.py`：三种历史论文算法。
- `app/services/patterns.py`：历史逐快照投影、参数分发和结果证据映射。
- `app/services/analysis.py` 的 `patterns()`：统一结构、参考统计和来源元数据。
- `algorithms/anomaly/`：SLADE 原始模型、事件准备、CUDA 配置和版本权重；`app/services/anomalies.py` 负责数据与请求适配。
- `algorithms/link_prediction/`：Zebra 编码与公共窗口标签、指标；`undergs/`：UnderGS 邻居库、GCN、训练及产物；`adapters.py`：模型分派。
- `app/services/link_prediction.py`：模型目录、指纹检查、全图概率缓存与社区筛选。
- `app/services/future_community.py`：逐快照成员并集、按概率建图和未来局部核查询。
- `algorithms/affinity/demo.py`：仅供旧接口兼容的份额适配器。
- `app/repositories/datasets.py`：本地数据读取与未来回放隔离。

接入正式方法时保留数据版本、时间边界、固定成员、完整候选归一化与来源标识，再为该方法补充相应验证。SLADE 已实际训练并接入 GPU，正式亲和度模型与真实金融数据仍属于后续阶段。
