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
            name="Historical Community Mining",
            description="Find periodic communities, durable communities, bursting cores, and frequency-aware cores.",
        ),
        Capability(
            id="local_core",
            name="Parallel Core Decomposition",
            description="Find the connected component of the S12 k-core containing the query node.",
        ),
        Capability(
            id="max_core",
            name="Maximum-Core Query",
            description="Find the highest nonempty core and its connected components in the current snapshot.",
        ),
        Capability(
            id="density",
            name="Density-Constrained Query",
            description="Find subgraphs that meet a density threshold.",
        ),
        Capability(
            id="anomaly",
            name="SLADE Anomaly Scoring",
            description="Rank nodes by anomaly score using temporal contrast and memory generation.",
        ),
        Capability(
            id="evidence",
            name="Subgraph Evidence over Time",
            description="Track metrics for a fixed set of nodes across snapshots.",
        ),
        Capability(
            id="affinity",
            name="Community Link Prediction",
            description="Estimate link probabilities for node pairs in a selected future snapshot using Zebra.",
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
