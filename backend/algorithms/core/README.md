# 当前搜索：并行核分解

算法来自 Liu、Dong、Gu、Sun 的 [*Parallel k-Core Decomposition: Theory and Practice*](https://doi.org/10.1145/3725332)（SIGMOD 2025）。[作者代码](https://github.com/ucrparlay/Parallel-KCore/tree/b4966c8ffc48f6e0de8c6a50ffb626af37a91bb8)（`b4966c8`，ParlayLib `e1f1dc0`）保存在仓库同级的 `参考论文/并行核分解/代码` 目录下。项目只提供调用适配器，直接使用原版 `KCore::kcore()`，保留分层桶、局部队列及采样策略和触发条件。

在工作区根目录运行：

```powershell
uv run --directory demo/backend python -m scripts.build_parallel_core
```

该命令通过 WSL Ubuntu 24.04 调用已有的 `g++`，按 C++20 编译至 `demo/backend/.native/kcore-adapter`。可通过 `--source-dir` 指定其他作者源码目录。不会改动参考源码或安装依赖。删掉本地产物或更新源码后需重新构建；替换数据或程序后重启后端清除内存缓存。

Windows 后端读取 S12 的无向交互，按节点对建立简单邻接并保留孤立节点。账户 ID 映射为连续整数，通过标准输入传递 CSR 邻接数据。C++ 程序一次返回全部核数，使用最多 8 个 Parlay 工作线程。空图及无边图的核数直接确定。只有缓存未命中的单快照查询启动 WSL，完整快照的显示不依赖此程序。

查询按数据集、数据版本和 S12 缓存快照及其核数。切换参数时检查 `coreness[q] >= k`，再按相同条件从 `q` 搜索其连通分量。这一步是 Demo 的查询逻辑；论文求解器只计算各节点的核数。时间证据与未来预测复用该结果的成员和提交条件。

本机通过开发代理验证：EmailDept3 的 S12 无向投影有 89 个节点、320 条边。默认 `q=49, k=7` 返回 30 个节点、145 条内部无向边，合成样例返回 5 个节点；两套数据的逐节点核数均与串行结果一致。EmailDept3 一次首次查询的服务端 `elapsed_ms` 为 2930.33 ms（含 WSL 调用）；随后切换 `k` 时，缓存命中的非空查询耗时 0.62–1.17 ms。这是本机小图的端到端查询读数。
