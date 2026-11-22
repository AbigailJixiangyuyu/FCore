# 后端

使用 uv 管理 Python 3.10 项目虚拟环境及依赖，FastAPI 0.162.5 的入口为 `app.main:app`。SLADE、Zebra 与 UnderGS 的训练和模型评分使用 cuda:0，通过系统包共享复用主 Python 已安装的 PyTorch 2.8.0+cu128。

在 `demo/` 下先执行 `.\setup-backend.ps1`。该脚本以 `D:/Workshop/Python310/python.exe` 创建 `backend/.venv`，启用 `--system-site-packages`，安装其他锁定依赖并验证 CUDA；不向主环境安装项目依赖。PyTorch 被 `tool.uv.exclude-dependencies` 排除 uv 安装，不重复下载 GPU 包。共享主环境的包不由 uv.lock 管理。

```powershell
uv run --directory backend python -m scripts.build_parallel_core
uv run --directory backend python -m scripts.train_slade --dataset email-eu-core-dept3
uv run --directory backend python -m scripts.train_zebra --dataset email-eu-core-dept3
uv run --directory backend python -m scripts.train_undergs --dataset email-eu-core-dept3
uv run --directory backend fastapi dev --host 127.0.0.1 --port 8000
```

在本目录执行时去掉 `--directory backend` 即可。后续 `uv sync --locked` 保留共享系统包配置。若误建普通隔离环境，请先保留或移除该虚拟环境，再运行初始化脚本；不要直接执行 uv sync 创建缺少系统 PyTorch 的环境。

日常回归在 `demo/` 下运行 `.\test.ps1`。只跑后端时用 `uv run --no-sync --directory backend pytest -q -m 'not hardware'`；去掉标记筛选即运行全部后端用例，包括小样本 GPU 训练与推理，以及已构建的 WSL 程序对照。

HTTP 路由位于 `app/api`，业务编排位于 `app/services`，本地文件读取位于 `app/repositories`，算法位于 `algorithms`，离线脚本位于 `scripts`。当前 S12 查询使用 [并行核分解](algorithms/core/README.md)；首次启动前构建一次 WSL 程序即可。历史四种算法及统计实际计算；密度使用演示候选，未来链接预测使用 `algorithms/link_prediction` 中的 Zebra 和 UnderGS，旧 affinity 接口仅兼容保留。

每个分析请求先由 `services/context.py` 验证数据上下文。`graphs.py` 组装快照和区间图，`queries.py` 和 `patterns.py` 分别负责当前搜索与历史挖掘。`structures.py` 计算结构指纹及统计，`selection.py` 按原条件复核结构后才交给时间证据、预测或旧份额接口。SLADE 的模型、记忆状态和训练分别在 `slade.py`、`state.py`、`training.py`；Zebra 和 UnderGS 各自恢复模型状态，共用 `checkpoint.py` 的产物读写、校验和激活。上传入口与两套离线数据脚本复用 `repositories/dataset_writer.py` 写入快照。

原始交互按快照保存在 `Sxx.csv`，表头为 `u,v,t`，`t` 是数值秒时间戳，重复行保留。`timestamp_basis=unix` 为默认口径；官方来源只有相对时间时必须明确标记 `relative`，保留原值，ISO 边界以技术零点编码，不冒充真实日期。节点和时间配置独立保存为 JSON，读取只打开对应快照的 CSV，标准库即可处理。字段与实时派生统计见 [图数据结构](../data/README.md)。SLADE 使用该边流，不读取场景注释，原始评分按账户返回。每次请求加载独立 GPU 模型及 S11 预热状态后处理 S12，缺少权重或 CUDA 时返回明确 503；不在请求中训练。配置、模型产物和训练截止见 [算法说明](algorithms/anomaly/README.md)。

在 `demo/` 下执行 `uv run --directory backend python -m scripts.import_email_dept3`，可从本地归档生成 Email Dept3 的无向快照。数据包含 89 个节点、12,099 次交互和 13 个等宽快照，每片 58,091 分钟。读取既有 CSV 时自动统一排列端点，接口版本带 `-undirected-v1`。SLADE、Zebra 和 UnderGS 均有匹配的 GPU 权重。替换数据包后重启后端以清除文件缓存。[数据包说明](../data/email-eu-core-dept3/README.md)

完整安装与启动见上一级 README，字段、结构传递和错误见 [接口接入说明](API_INTEGRATION.md)。仅 `DatasetRepository.replay()` 可读取未来交易，页面不调用保留的观测接口。

Zebra 保留当前环境的所有库版本，只修改算法代码适配。使用 S02—S09 标签训练、S10 选模、S11 校准、S12 独立回测，不读 S13。详见 [算法与训练说明](algorithms/link_prediction/README.md)。

UnderGS 使用相同数据划分，模块为 `algorithms/link_prediction/undergs/`，由 `adapters.py` 与 Zebra 分别加载和推进状态。邻居库和节点表示持久驻留 GPU；完整快照的重复交互计数与两跳路径参与编码。Dept3 已激活 `undergs-d00b82e22d5c3ee9`，50 轮耗时 40.020 秒。实现修正、默认配置和回测结果见 [UnderGS 说明](algorithms/link_prediction/undergs/README.md)。
