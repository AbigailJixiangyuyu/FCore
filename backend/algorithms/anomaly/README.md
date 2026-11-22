# SLADE 账户状态检测

依据 Lee、Kim、Shin 的 **SLADE: Detecting Dynamic Anomalies in Edge Streams without Labels via Self-Supervised Learning，KDD 2024**。论文：[DOI](https://doi.org/10.1145/3637528.3671845)；本地原件为 `参考论文/异常检测/异常检测.pdf`，作者参考代码为该目录下的 `代码/`，公开仓库为 [jhsk777/SLADE](https://github.com/jhsk777/SLADE)。

## 输入与时间边界

模型读取 `Event(u, v, timestamp)`，`u` 和 `v` 是统一排列后的无向端点，`timestamp` 为相对历史起点的秒数。保留重复交互及真实时间间隔。按时间稳定排序，同时间戳保留文件顺序且不拆批。两个端点共享记忆更新方式，损失贡献等权。

交互保存在逐快照 `Sxx.csv` 中，固定表头为 `u,v,t`。读取器统一排列端点并滤除自环。训练只打开 S01—S11，检测额外打开 S12。模型指纹与 `-undirected-v1` 有效数据版本绑定。

合成样例模型 `slade-bf2fec907f9ca6f5` 使用 S01—S11 的 4,263 次交互训练。参数冻结后回放 S12 的 183 次交互，在 S12 结束时刻 `2026-01-01T12:00:00+08:00` 对账户评分。

Dept3 无向模型 `slade-d73301cecdf93996` 使用 S01—S11 的 9,525 次交互训练 10 轮，损失从 9.47120 降至 9.30169，耗时 24.879 秒，峰值显存分配 124.04 MiB。随后处理 S12 的 1,208 次交互，88 个账户可评分，另 1 个无交互历史的账户单列。

## 论文实现

- 式（1）—（3）：对端记忆与时间间隔编码组成原始消息，按账户均值聚合，再经 MLP＋GRU 更新；保存更新前的记忆。
- 式（2）：固定时间频率 `alpha ** (-j / beta)`，默认 alpha=10、beta=25.6。
- 记忆生成：遮蔽目标账户记忆，最近 20 条邻域交互记录组成单层、双头 TGAT 注意力输入，允许同一邻居重复出现。查询只有零时间差编码。
- 式（4）—（7）：时间对比与记忆生成两项对比损失；分母为已出现节点（含当前节点）的完整记忆集合，使用 logsumexp 稳定计算。
- §4.2 批次训练：当前批次只利用前序批次更新的记忆。每批先应用上一批交互，再用当前端点及其时间计算损失；当前批交互到下一批才更新记忆。批间截断梯度。第一批零记忆仍保留生成器计算图。
- 在线回放按时间戳推进，同时间戳交互共享更新前状态，先聚合再更新；不使用未来时间戳的记忆。

最终两项余弦距离与综合分数严格采用式（8）—（10）：

```text
sc = 1 - cosine(current_memory, previous_memory)          # [0, 2]
sg = 1 - cosine(current_memory, generated_memory)         # [0, 2]
s  = (sc + sg) / 4                                      # [0, 1]
```

没有分类阈值、结构 OR 金额规则或额外校准。Top-20 只是显示范围。零向量采用 PyTorch 的有限余弦定义；没有交互历史的账户单列为未评分，不填入正常标签。

## 默认训练配置

| 参数 | 默认值 |
| --- | --- |
| 记忆／消息维度 | 256／128 |
| 最近交互记录 | 20 |
| TGAT 层数／注意力头／dropout | 1／2／0.1 |
| Adam 学习率／weight decay | 3e-6／1e-4 |
| epochs／目标 batch size／逐轮学习率倍率 | 10／100／0.8 |
| 两端时间对比权重 | 各 1 |
| 两端记忆生成权重 | 各 0.1 |
| 随机种子／设备 | 20261116／cuda:0 |

## GPU 环境与训练

当前使用 Python 3.10 项目虚拟环境，通过 `--system-site-packages` 复用 `D:/Workshop/Python310` 已安装的 `torch==2.8.0+cu128`。FastAPI 固定 0.162.5，其他项目依赖由 uv 锁定并安装在 `.venv`。`tool.uv.exclude-dependencies=["torch"]` 明确将 PyTorch 作为外部环境前提，避免 `uv sync` 重复下载；它及其系统依赖不由项目锁文件管理。

在 `demo/` 下执行：

```powershell
.\setup-backend.ps1
uv run --directory backend python -m scripts.train_slade --dataset email-eu-core-dept3
```

模型、账户记忆及临时张量显式位于 GPU，邻域记录与账户 ID 保持普通 Python 数据。CUDA 不可用时训练报错、在线接口返回 503，不自动切到 CPU。配置 CUDA 随机种子、确定性算子、cuBLAS 工作空间，关闭 TF32 和 cuDNN benchmark。主环境中的 PyTorch 升级后需重新核验兼容性。

训练结束后用最终参数从空记忆重新回放 S01—S11，生成一致的预热状态。候选权重先保存，再加载到 GPU，比较预热状态及 S12 评分；验证通过才原子更新 `current.json`。报告记录设备、CUDA、显卡、PyTorch、损失、耗时与峰值显存。

## 文件与请求隔离

`events.py` 负责事件边界及指纹，`slade.py` 负责纯模型与计算，`runtime.py` 负责 CUDA 配置，`artifacts.py` 负责版本产物。服务适配位于 `app/services/anomalies.py`。

产物目录为 `models/<dataset_id>/slade/<model_version>/`，含 `checkpoint.pt` 和 `manifest.json`。权重和预热张量以 CPU 存储格式序列化以便移植；加载后显式放到 GPU，文件存储位置不代表计算设备。每个请求加载独立模型与记忆，不共享可变在线状态。重复、并发请求不修改磁盘权重或训练截止状态。

## 与作者代码的边界

时间编码遵循论文式（2），作者代码的 `10 ** -linspace(0, 9, d)` 不直接照搬。训练保持前序批次更新语义，但邻域只使用已处理批次，避免同批后续事件进入状态；在线推理采用同时间戳共同状态，不逐条打破并列时间。原生 PyTorch index_add／scatter_reduce 替代 torch-scatter。空邻域显式返回零向量，避免全遮蔽注意力 NaN；目标记忆按每一行遮蔽，避免索引副本赋值失效。首次出现时间为零也不与填充节点混淆。

这是依据论文公式与公开实现的工程复现，不声称与作者程序逐位一致。合成数据用于流程验证，Dept3 用于真实邮件交互验证；两者不提供真实金融异常准确率结论，Dept3 也没有异常真值标签可用于准确率评估。
