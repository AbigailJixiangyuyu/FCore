# LLM-Assisted Interpretation 提示词与证据规则

FCore 以用户提交的历史社区为基线，比较当前社区新增和退出了哪些成员，再分析这些成员在未来社区中的预计去向。后端按节点 ID 计算成员变化，并将历史算法的发现和当前 S12 的 SLADE 分数交给 LLM，用于解释哪些成员值得关注。

## 首次点击 Send 时，模型收到什么

用户在 **History、Current、Future** 各运行算法并点击 **Submit**，前端保存对应结果的引用。三项齐全后，用户点击 **Send**，后端核对数据集版本、观察截止、所选结构和模型结果，然后向 DeepSeek 发送同一请求中的两条消息。[证据复核](app/services/reports/evidence.py) · [消息组装](app/services/reports/messages.py)

| 消息顺序 | 角色 | 实际内容 |
| --- | --- | --- |
| 1 | `system` | 固定的英文提示词，规定分析对象、证据引用方式、语言及输出格式。完整原文见下节。 |
| 2 | `user` | 一个序列化为文本的 JSON 对象。`evidence` 是四条证据，`membership_groups` 是成员在三个阶段的归属。用户填写的首问放在可选字段 `initial_prompt`，留空时省略该字段。 |

界面中的 **Ask FCore** 是输入框占位文字。直接点击 **Send** 会生成英文全周期报告。填写首问时，模型围绕该问题组织同一组证据。首句概括主要发现，随后用三个 Markdown 列表项解释历史规律、当前变化与异常成员、未来预计变化。每项给出结论及支持它的数字、顶点或快照，相关判断后紧跟证据编号。请求启用 Thinking 和流式输出，页面随正文到达更新排版。[前端提交逻辑](../frontend/src/composables/workbench/useLifecycleReport.js) · [上游请求与流式响应](app/services/reports/provider.py)

## 首份报告的系统提示词原文

```text
Write a concise English Markdown report for a graph analyst. Open with one sentence stating the
main finding. After a blank line, give exactly three bullet points in this order:
- **Historical pattern**: explain the historical method's finding.
- **Current changes and unusual members**: connect observed turnover to current SLADE evidence.
- **Predicted changes**: explain expected retention or turnover for the target snapshot.
Lead each point with its conclusion, then support it with specific counts, vertices or snapshots.
Place each evidence ID immediately after the claim it supports. Use initial_prompt, when supplied,
to focus the analysis. Keep each point short.

Use only the three submitted community results. Cite evidence using its ID,
such as 〔H01〕, 〔C01〕, 〔C02〕 or 〔P01〕. Each stage has its own method, window and, where applicable,
query node and k. When these differ, describe the overlap between the selections and avoid
attributing every membership difference to the passage of time.

Use the historical method's actual finding. Periodic presence refers to the listed snapshots.
A burst witness describes an individual member's window. Compare history with current, then
current with the submitted prediction. Give the number retained, added and exited and use net
change alongside turnover. Retention is the share of the earlier selection that appears in the
later one. Use the membership groups and node aliases to identify members shared across stages.
Describe every future membership or change as predicted for the specified target snapshot.

Use SLADE scores only for scored members of the current selection. Describe coverage, mean,
median and any notable members in the context of both community and global rank. Higher scores
indicate more unusual current interactions. Connect a named member's score to its historical
and predicted membership when supported. If scoring evidence is unavailable, state which
conclusions the evidence can support. Missing forecast scores leave future membership unknown.
```

## 四条证据怎样解释

| 引用 | 分析对象 | 报告可以使用的事实 |
| --- | --- | --- |
| 〔H01〕 | 所提交的历史社区 | 历史算法、实际分析范围、成员数和该算法找到的模式。各方法的专属指标见下表。 |
| 〔C01〕 | 所提交的当前社区与历史社区 | 当前查询方法及窗口、成员数、内部边数，以及历史 → 当前的保留、新增、退出、净变化和留存率。全局最大核另给出求得的最高核阶数。 |
| 〔C02〕 | 当前社区成员在 S12 的 SLADE 评分 | 已评分与未评分人数、已评分成员的均值和中位数、进入全图前十的人数。列出社区内前三名，以及该社区其余进入全图前十的成员。每位列出者都有分数、社区排名和全图排名，可关联其历史与预计成员身份。 |
| 〔P01〕 | 所提交的未来社区与当前社区 | 预测方法、目标快照和预计成员数。给出当前 → 未来的预计保留、新增、退出、净变化、留存率，以及三个结果共有多少人。 |

**历史社区提供的指标随方法变化。** [历史证据提取](app/services/reports/history.py)

| 历史方法 | 〔H01〕提供的指标 |
| --- | --- |
| PHC-Query（历史固定窗口核） | 所选连通社区的内部边数、最小内部度，以及从同一起点延长窗口时，已进入相应阶数核的成员人数。 |
| TD（周期） | 周期长度、重复次数、周期所在区间，以及社区实际出现的快照。 |
| ONCE（持久） | 形成窗口、稳定截止快照、形成结束后继续稳定的快照数。 |
| MBC-B（爆发） | 代表成员的最大平均内部度及对应窗口，另给出最多成员共有的窗口和人数。代表成员优先取查询点，其不在结果中时取最大平均内部度最高的成员。报告将代表成员的窗口归于该成员。 |
| OL（频率感知） | 达标内部边数、成员中最少的达标邻居数、达标边中最低的实际频率。 |
| OTCD（时域核） | 最紧窗口、该窗口的内部边数，以及完整窗口和可比较的缩短窗口各自的最小内部度。 |

**怎样计算跨期变化。** 设较早和较晚的成员集合分别为 `A`、`B`。保留人数等于交集大小，新增人数等于只在 `B` 中的人数，退出人数等于只在 `A` 中的人数。净变化等于新增减退出。留存率以较早社区为分母，计算为 `保留人数 / |A|`，分母为零时记为 `null`。报告同时给出净变化和成员更替，这样即使两次人数相同，也能看出有多少人换了。[成员比较与风险统计](app/services/reports/facts.py)

**怎样对齐查询。** 各阶段保留各自适用的查询点 `q`（JSON 中为 `query_node`）和核阶数 `k`。例如，PKMC 的 `maximum_core_order` 是算法求得的值。若三次提交的查询条件不同，能够直接说明的是所选社区重合多少、哪些成员进出。相似度 ε、连边阈值等输入参数用于后端复核。报告对未来的判断以所提交阈值下的那一次预测为依据。

**怎样定位成员。** `membership_groups` 按 `history`、`current`、`predicted` 的实际组合列出节点，每个节点出现一次。同一份报告对同一节点使用同一代号，例如 `N002`。首问和追问中“节点 12”这类带节点标记的 ID 会映射到相应代号，页面显示回复时再还原原始 ID。[节点代号与提问处理](app/services/reports/messages.py) · [页面显示](../frontend/src/components/analysis-summary/AnalysisReport.vue)

**怎样处理证据不足。** SLADE 均值和中位数只计入有分数的当前成员。当前查询使用回溯窗口时，SLADE 的评分时刻仍为 S12。评分越高表示该节点在当前时刻的交互越偏离模型学到的模式。整组缺少评分时，〔C02〕给出覆盖人数及 `evidence_gap`。未来有候选对获评分、预测社区为空时，预计成员数为 0，此时所提交的当前成员均计入预计退出。若候选对均无法评分，〔P01〕给出 `evidence_gap`，未来成员归属和变化记为未知。[证据组装](app/services/reports/facts.py)

## EmailDept3 的首次发送实例

这次提交选用历史 S10–S11 的 OTCD（`k=7`）、当前 S12 的 PKMC，以及预测 S13 的 Zebra（`q=49`、`k=4`、连边阈值 0.50）。首问是 “Which new members warrant attention, and are they predicted to stay?”。下面是项目使用本地数据和模型实际组装的第二条消息正文，仅调整了 JSON 缩进。

<details>
<summary>展开完整的首条 user 消息</summary>

```json
{
  "evidence": [
    {
      "id": "H01",
      "topic": "Temporal k-Core",
      "method": "OTCD",
      "analysis_window": "S10–S11",
      "member_count": 18,
      "tightest_window": "S10–S11",
      "tightest_internal_edges": 79,
      "min_internal_degree_by_window": [
        {"window": "S10", "min_internal_degree": 5},
        {"window": "S11", "min_internal_degree": 2},
        {"window": "S10–S11", "min_internal_degree": 7}
      ],
      "k": 7
    },
    {
      "id": "C01",
      "topic": "submitted current community compared with submitted history",
      "method": "PKMC (global maximum k-core)",
      "window": "S12",
      "member_count": 30,
      "internal_edges": 145,
      "change_from_history": {"retained": 13, "added": 17, "exited": 5, "net_change": 12, "retention_rate": 0.7222},
      "maximum_core_order": 7
    },
    {
      "id": "C02",
      "topic": "SLADE scores within the submitted current community",
      "snapshot": "S12",
      "scored_members": 30,
      "unscored_members": 0,
      "mean": 0.2153,
      "median": 0.2148,
      "scored_members_in_global_top_10": 0,
      "highest_scoring_members": [
        {
          "node": "N002",
          "score": 0.246,
          "community_rank": 1,
          "global_rank": 27,
          "in_submitted_history": false,
          "in_submitted_prediction": false
        },
        {
          "node": "N003",
          "score": 0.2338,
          "community_rank": 2,
          "global_rank": 34,
          "in_submitted_history": false,
          "in_submitted_prediction": true
        },
        {
          "node": "N004",
          "score": 0.2311,
          "community_rank": 3,
          "global_rank": 39,
          "in_submitted_history": false,
          "in_submitted_prediction": false
        }
      ]
    },
    {
      "id": "P01",
      "topic": "submitted prediction compared with the submitted current community",
      "method": "Zebra",
      "target_snapshot": "S13",
      "predicted_member_count": 23,
      "change_from_current": {"retained": 16, "added": 7, "exited": 14, "net_change": -7, "retention_rate": 0.5333},
      "members_in_all_three": 11,
      "query_node": "N001",
      "k": 4
    }
  ],
  "membership_groups": [
    {
      "stages": ["current"],
      "nodes": ["N005", "N006", "N002", "N007", "N016", "N018", "N021", "N022", "N031", "N039", "N004", "N040"]
    },
    {
      "stages": ["history", "current", "predicted"],
      "nodes": ["N008", "N009", "N013", "N014", "N017", "N024", "N001", "N026", "N029", "N035", "N036"]
    },
    {
      "stages": ["predicted"],
      "nodes": ["N010", "N015", "N023", "N032", "N034"]
    },
    {
      "stages": ["history"],
      "nodes": ["N011", "N027", "N033"]
    },
    {
      "stages": ["current", "predicted"],
      "nodes": ["N012", "N003", "N019", "N028", "N030"]
    },
    {
      "stages": ["history", "current"],
      "nodes": ["N020", "N038"]
    },
    {
      "stages": ["history", "predicted"],
      "nodes": ["N025", "N037"]
    }
  ],
  "initial_prompt": "Which new members warrant attention, and are they predicted to stay?"
}
```

</details>

这次首问涉及的两名新增成员，在未来预测中有不同去向。

- 历史社区有 18 名成员，当前社区有 30 名。13 人保留、17 人新增、5 人退出，净增 12 人。历史成员留存率为 13/18，即 72.22%。〔H01〕〔C01〕
- 当前 30 人均有 SLADE 分数。节点 12（`N002`）是当前新增成员，分数 0.2460，居社区第 1、全图第 27。节点 30（`N003`）也是新增成员，居社区第 2。前者预计退出，后者预计保留。〔C02〕〔P01〕
- S13 预计有 23 名成员，其中 16 人来自当前社区，另有 7 人预计新增、14 人预计退出。共有 11 人出现在历史、当前及预测三个结果中。〔P01〕

## 后续追问如何延续上下文

每次追问发送的消息依次为 `system`（追问规则）、`user`（同一组证据及原首问）、`assistant`（首份报告原文）、按时间排列的每轮已完成问答，最后是 `user`（本轮问题）。更新任何一个阶段的已提交证据后，下一次 **Send** 会基于新组合重新生成首份报告。[前端会话管理](../frontend/src/composables/workbench/useLifecycleReport.js) · [报告接口说明](API_INTEGRATION.md#全周期联合报告)

追问使用提问者的语言。单个数值或顶点问题直接回答，多个发现或比较分点展开。前端保存回复的原始 Markdown 供后续追问，显示时还原节点 ID。以下提示词之后复用从 “Use only the three submitted community results” 起的证据规则。[原文](app/services/reports/messages.py)

```text
Answer the latest question about the lifecycle report in the language it uses.
Use earlier replies to resolve references. Use the supplied evidence in the first user message for
factual claims. Explain what information is missing when the question goes beyond that evidence.
Answer a question about a single value or vertex directly. For multiple findings or comparisons,
use a Markdown list with one finding per point. Bold only key conclusions. Place evidence IDs
immediately after the claims they support.
```
