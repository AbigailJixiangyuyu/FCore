# SLADE 模型产物

每个数据集使用独立的权重。默认 Ethereum 的 SLADE 和 Zebra 使用 S01—S11 的转账记录训练。开发机使用 `cuda:0` 训练，服务端可设置 `FCORE_DEVICE=cpu` 加载同一组权重。[金融样本训练命令](../data/ethereum-eth/README.md)

在 `demo/` 下训练：

```powershell
uv run --directory backend python -m scripts.train_slade --dataset ethereum-eth
```

```text
models/
├── ethereum-eth/                # SLADE 与三个预测窗口的 Zebra
├── synthetic-small/slade/       # 独立的合成数据模型
└── email-eu-core-dept3/slade/
    ├── current.json
    └── slade-<checkpoint哈希前16位>/
        ├── checkpoint.pt
        └── manifest.json
```

权重包含模型参数、配置、账户映射、训练事件元数据，以及用最终参数重新回放 S01—S11 得到的预热状态。manifest 包含 SHA-256、训练范围与事件指纹、软件／GPU 信息和训练报告。候选产物保存、重新加载并核对 S12 评分后才切换 current.json；失败保留原指针。

Dept3 当前模型为 `slade-d73301cecdf93996`，合成样例为 `slade-bf2fec907f9ca6f5`。两份模型使用 `-undirected-v1` 的事件指纹。重建合成模型时将 `--dataset` 改为 `synthetic-small`，两者的 `current.json` 分别激活。

为便于文件移植，张量以 CPU 格式序列化；在线加载后放到 GPU，这不表示训练或推理在 CPU 上执行。每个请求恢复独立预热状态，固定模型继续处理 S12，不修改磁盘权重，不读取 S13。模型文件和导出默认不纳入版本控制，可用上述命令重建。详细实现见 [算法说明](../backend/algorithms/anomaly/README.md)。

## Zebra

`{dataset_id}/zebra/{model_version}/checkpoint.pt` 保存当前 PyTorch 张量、账户映射与 S11 预热状态；manifest.json 保存配置、指纹、训练曲线、温度校准及 S12 独立回测报告。current.json 在恢复验证通过后激活。模型不读取 S13；界面输出下一快照无向连边概率，非原份额。重训命令和差异见 [Zebra 说明](../backend/algorithms/link_prediction/README.md)。

## UnderGS

`{dataset_id}/undergs/{model_version}/checkpoint.pt` 保存 GCN 与预测头参数、账户映射、S11 截止的节点表示和时序邻居库、校准温度。manifest.json 记录配置、历史事件指纹、训练梯度和曲线、S12 回测、运行环境及 SHA-256。序列化使用 CPU 张量，加载后模型与状态放入 cuda:0；这不改变 GPU 训练和推理口径。

Dept3 当前为校准后的 `undergs-ea61cb576ce05a4b`。使用无向输入训练 50 轮，训练耗时 23.068 秒，采用第 50 轮。保存、恢复并继续处理 S12 的结果一致后更新 `current.json`。[UnderGS 说明](../backend/algorithms/link_prediction/undergs/README.md)
