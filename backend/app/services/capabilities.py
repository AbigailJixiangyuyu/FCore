from app.schemas.system import Capability


def list_capabilities(
    has_data: bool = False,
    anomaly_ready: bool = False,
    prediction_ready: bool = False,
    *,
    parallel_core_ready: bool = False,
) -> list[Capability]:
    capabilities = [
        Capability(
            id="patterns",
            name="历史模式挖掘",
            description="在快照序列中挖掘周期、持久与爆发模式。",
        ),
        Capability(
            id="local_core",
            name="并行核分解",
            description="查询指定账户在 S12 的 k-core 中所属的连通结构。",
        ),
        Capability(
            id="max_core",
            name="最大核查询",
            description="提取当前快照的最大非空核及其连通分量。",
        ),
        Capability(
            id="density",
            name="密度约束查询",
            description="按照确定的密度条件与算法查找图中结构。",
        ),
        Capability(
            id="anomaly",
            name="SLADE 账户异常检测",
            description="基于时间对比与记忆生成，计算当前账户异常程度排名。",
        ),
        Capability(
            id="evidence",
            name="子图时间证据",
            description="统计固定账户集合在各快照中的指标变化。",
        ),
        Capability(
            id="affinity",
            name="群内链接预测",
            description="选择 Zebra 或 UnderGS，预测所选结构内各顶点对在下一快照的连边概率。",
        ),
    ]
    computed = {"patterns", "max_core", "evidence"}
    for capability in capabilities:
        capability.status = "unavailable"
        if has_data:
            capability.status = "ready" if capability.id in computed else "demo"
        if capability.id == "local_core":
            capability.status = "ready" if has_data and parallel_core_ready else "unavailable"
        if capability.id == "anomaly":
            capability.status = "ready" if has_data and anomaly_ready else "unavailable"
        if capability.id == "affinity":
            capability.status = "ready" if has_data and prediction_ready else "unavailable"
    return capabilities
