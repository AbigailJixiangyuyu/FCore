# 稳定力导向布局

借鉴 PRISM 图 2 显示的 Force-Directed 布局及结果强调方式；PRISM 原文未指明具体力导向实现。本项目采用 [Graphology ForceAtlas2](https://graphology.github.io/standard-library/layout-forceatlas2.html) 与 [Noverlap](https://graphology.github.io/standard-library/layout-noverlap.html)。布局是显示方法，不是社区划分或异常判据。

## 数据与固定参数

- 参考范围固定 S01—S11，复用后端聚合接口的无向边。节点保留全部账户。S12／S13 的交互、交易次数权重、模型分数和查询结果不参与坐标计算。
- 节点和边排序，种子 `20261116`；每个非平凡连通分量使用网格加微小扰动初始化。ForceAtlas2 固定 500 次，`linLogMode=true, adjustSizes=true, edgeWeightInfluence=0, scalingRatio=10, gravity=1, slowDown=1, barnesHutOptimize=false`。
- 每个分量等比缩放，Noverlap 最多 500 次，`size=4, margin=2, ratio=1, gridSize=10, speed=3`；分量按成员数及 ID 确定性排序后按包围盒排列，孤立节点在外围紧凑排列。分量布局是连接关系的呈现，不按算法结果人为拉开社区。
- 布局版本 `history-fa2-linlog-500-noverlap-v1`。独立 Vite 模块 Worker 一次完成，缓存键包含数据集、数据版本、布局版本、规范化参考拓扑的 SHA-256；仅保留最近 8 份。任务取消、完成、失败或组件销毁均终止 Worker。

## 坐标和显示范围

三个阶段共享世界坐标。相同社区在区间变化时保留相机，各社区按自身包围盒适应画布。布局键仅由数据与布局版本决定。浏览器刷新后用相同输入计算相同坐标。

03 默认展示全图，历史使用所选区间的聚合图，当前和未来使用最新观测 S12。提交后只展示查询结果中实际存在的成员和内部边。周期社区使用区间终点的快照，未形成时显示空状态。频率感知核仅保留达到频率要求的内部关系。预测结果展示 S13 社区内的全部无向预测边，悬停可查看概率。切换算法或阶段时恢复全图。

全图账户半径 3.5、社区成员 4.5、当前查询账户 6、未来查询账户 7、异常定位账户 8 像素。悬停社区的成员或内部边时，社区内全部可见成员与内部边统一置于上层，所有内部边透明度为 0.85。实际边用无箭头实线，预测边用无箭头虚线，每对节点各画一条。悬停提示展示两端、时间和交互次数或预测概率。移开后恢复场景原始样式。标签优先查询、异常及悬停账户，其余按当前无向度降序，尝试八个位置并避让节点、标签和工具栏。实际节点事件由 Sigma 拾取，方向键／Enter 提供键盘入口。

## 模块与验证

- `layoutReference.js`：规范化投影、SHA-256、包围盒与版本。
- `forceLayout.js` / `layout.worker.js`：纯坐标计算与 Worker 入口。
- `scene.js`：当前／历史诱导子图及未来场景，保留事实与独立连边概率。
- `hover.js`：按当前所选社区统一强调成员和内部边，恢复原始样式。
- `labels.js`：屏幕标签避让。
- `../composables/useGraphLayout.js`：请求上下文、取消、缓存、重试。

前端目录执行 `npm test`；测试直接读取 S01—S11 与 S12 CSV，不依赖服务或 S13。浏览器故障测试另覆盖参考请求失败、Worker 失败、过期响应和切换数据集后的旧 Worker 消息。截图和记录见工程 `VALIDATION.md`。
