# 前端

使用 Vite 官方 Vue JavaScript 模板，采用 Vue 3、Composition API 与 `<script setup>`。

依赖由 npm 管理。基础 UI 使用 Element Plus；Pinia 已注册，接口数据与请求状态由 TanStack Vue Query 管理，HTTP 请求使用原生 fetch。完整安装、启动和架构说明见上一级 `README.md`。

## Element Plus

- 在 `src/plugins/elementPlus.js` 显式按需注册组件，并引入基础变量与对应组件样式；包含按钮、选择器、数值输入、单选切换、提示和空状态。使用 `app.component` 直接注册，避免部分子组件的空安装器导致组件未注册。
- 在 `App.vue` 通过 ConfigProvider 统一使用简体中文和 `small` 尺寸。
- 在 `src/styles/element-plus.css` 统一设置主题色、字号、边框和紧凑尺寸，之后加载工作台布局样式。
- 后续新增基础组件时，在同一插件中注册并引入其样式，不新增自动导入插件或生成 TypeScript 声明文件。

在此目录执行 `npm ci`、`npm run dev` 或 `npm run build`。开发服务为 `127.0.0.1:5173`，将 `/api` 代理到 `127.0.0.1:8000`。构建产物位于 `dist/`，由 FastAPI 托管。

## 工作台与可视化

仅维护桌面工作台，主要演示尺寸为 1440×900，页面最小宽度为 1280px。窗口更小时使用横向滚动，保持顶部 01、中间 02／03／04 三列及底部 05 的布局。

普通地址默认使用录屏布局。在同一标签页的地址末尾加上 `#paper` 并回车，即可在当前查询结果上切换到论文截图布局。将其改为 `#video` 即可恢复录屏高度，已选社区、图的缩放和对话可继续使用。

默认布局由 `DEFAULT_LAYOUT` 控制，取值为 `video` 或 `paper`。截图样式开头集中设置了中间一排的压缩量及高度下限、底部面板高度和统计行距。[工作台入口](src/views/AnalysisWorkbench.vue) · [截图样式](src/styles/paper-layout.css)

`views/AnalysisWorkbench.vue` 装配五块面板：01 快照时间导航、02 方法与参数、03 图结构、04 异常信息、05 时间证据。`composables/useWorkbenchData.js` 装配各业务模块并协调跨面板操作。快照、查询、异常、证据、预测的请求分别在 `composables/workbench/` 下；提交参数与缓存键使用同一份值。`stores/workbench.js` 保存交互状态，`api/analysis.js` 负责 HTTP，`domain/timeline.js` 提供 S01—S13 的共享边界。`styles/main.css` 按顺序引入公共布局与面板样式。

默认数据集为 `ethereum-eth`。S12 全图展示 89 个地址，执行默认查询 `q=E025, k=2` 后展示 27 个成员和 50 条内部边。切换数据集恢复其独立参数，EmailDept3 使用查询节点 `49`，合成样例使用 `a-001`。切换数据集重置画布，调整历史展示区间保留视角，未来窗口长度从数据集配置读取。[查询配置](../config/README.md)

04 底部由 `PredictionNavigation.vue` 提供独立操作行：现在选中结构后可“进行预测”，未来可“返回现在更换结构”。操作行与上方可滚动的异常信息分隔；历史不显示。

关系图使用 Sigma.js 4.0.6＋Graphology 0.26.0。03 默认显示完整无向图，获得查询结果后展示成员和内部边。坐标由 S01—S11 无向并集经 ForceAtlas2 0.10.1 和 Noverlap 0.4.2 生成，历史和现在共享这套坐标。每对节点画一条无箭头连线，实际边为实线，预测边为虚线。

`useGraphLayout.js` 管理独立 Worker、错误重试和最多 8 份版本缓存；缓存键包括数据版本、参考拓扑 SHA-256 与布局版本。范围、查询和异常选择不参与布局缓存键。`GraphCanvas.vue` 渲染画布容器和覆盖层，`useGraphCanvas.js` 管交互、相机与生命周期，`graph/sigmaRenderer.js` 按需加载并配置 Sigma，`graph/labels.js` 负责标签避让。HTML 标签不截获鼠标；标签优先查询、异常和悬停账户。悬停所选社区成员或内部边时，突出该社区全部可见成员及内部边。双向边轻微分弯；键盘方向键定位、Enter 选择账户。完整参数与来源见 [布局说明](src/graph/README.md)，运行 `npm test` 验证布局、场景和社区悬停逻辑。

时间证据使用 ECharts 6.1.0 的按需模块；图表与 WebGL 模块延迟加载，组件销毁时释放实例、Worker 和监听器。

03 使用单行标题和紧凑图例，移除重复的范围／方法说明、所选结构摘要及底部解释文字，扩大图画布。

01 左侧提供数据集选择、时间粒度选择和数据集新增三个入口。可切换已有数据集，粒度入口显示所选数据集的现有配置，新增入口暂不可用。右侧时间轴标明历史、现在和未来，用同一轨道上的三角形手柄选择历史范围：◀ 为 start、▶ 为 end，朝区间外侧指向，支持鼠标和键盘；重合时两侧仍可分别拖动。end 控制 S12/S13 单时刻入口，历史起点跨视图保留。请求按起止范围缓存，拖动约 150ms 防抖、释放立即提交；加载时隐藏旧图并保留画布实例及视角。时间证据仍显示逐快照数值，背景选区与时间轴同步。

历史六种方法通过 API 查询提交窗口，各自保存草稿与已提交参数。首项 Historical k-Core Query 在固定窗口查找所有连通的 `k`-core。Result Analysis 可切换社区并查看达标成员数，Submit 将所选社区加入报告。Scalable Time-Range k-Core Query 按各结果的最紧区间展示。两项查询均可在浏览其他快照后从分析面板返回原结果。点击历史账户可填写周期和持久查询的 q 草稿。[查询默认配置](../config/README.md)

04 在所有时刻展示 S12 的 SLADE 账户评分，选中后显示综合分数与时间对比、记忆生成两项距离。点击账户回到 S12，在 03 以红橙色及尺寸定位；查询条件、查询成员、05 轨迹和未来范围保持原选择。排名刷新不自动定位，模型／数据版本改变清除旧依据。未来背景固定 S12，只有当前查询结构决定未来范围；页面不请求观测数据，固定 Top-10 显示不改变预测概率。

未来模块在 02 的 Target snapshot 提供 S13、S14、S15。Run Prediction 提交所选目标及查询参数，并通过 `/link-prediction/community` 查询包含 q 的预测 k-core。01 的 Future 格显示已提交的目标。运行后，拖动 Edge threshold 会沿用已提交的目标、q 和 k 更新 03 和 05。页面按步长、模型版本、查询条件和阈值核对结果。
