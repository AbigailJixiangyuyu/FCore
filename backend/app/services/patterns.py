"""Adapt historical transaction snapshots to the independent mining functions."""

from copy import deepcopy

from fastapi import HTTPException

from algorithms.patterns.common import PatternResult, TemporalSnapshots
from algorithms.patterns.temporal_core import mine_temporal_cores
from app.schemas.analysis import PatternQuery, SnapshotData
from app.services.context import AnalysisScope
from app.services.graphs import combine_snapshots, window_bounds
from app.services.historical_core import historical_cores
from app.services.statistics import graph_of
from app.services.structures import COLORS, make_structure

# Method version, public label, result ID and palette index for each algorithm.
_PATTERN_DETAILS = {
    "periodic": ("lpc-td-ftac-v1", "Periodic Community", "P1", 0),
    "durable": ("tdc-once-v1", "Durable Community", "D1", 1),
    "burst": ("mbc-exact-segments-v1", "Bursting Core", "B1", 2),
    "frequency": ("frequency-aware-kcore-online-v1", "Frequency-Aware Core", "F1", 3),
    "temporal_core": ("tcq-snapshot-otcd-v1", "Temporal k-Core", "TCQ", 0),
}


def mining_window(scope: AnalysisScope, request: PatternQuery, history_ids: tuple[str, ...]) -> list[str]:
    if request.start_snapshot_id is not None and request.end_snapshot_id is not None:
        start, end = window_bounds(scope, request.start_snapshot_id, request.end_snapshot_id)
        if start.kind != "history" or end.kind != "history":
            raise HTTPException(422, "Mining requires a range of historical snapshots.")
        if start.index > end.index:
            raise HTTPException(422, "The first snapshot to mine must be at or before the last snapshot.")
        first = history_ids.index(start.snapshot_id)
        last = history_ids.index(end.snapshot_id)
        return list(history_ids[first : last + 1])
    if not history_ids:
        raise HTTPException(404, "No historical snapshots are available to mine.")
    return list(history_ids)


def project_snapshots(frames: list[SnapshotData]) -> TemporalSnapshots:
    accounts = sorted(
        {account for frame in frames for account in frame.present_accounts}
    )
    graphs = [graph_of(frame) for frame in frames]
    return tuple(
        {account: frozenset(graph.get(account, ())) for account in accounts}
        for graph in graphs
    )


def mine_pattern(
    request: PatternQuery, snapshots: TemporalSnapshots
) -> PatternResult | None:
    # Import at the adapter boundary; the algorithms have no HTTP or file dependency.
    from algorithms.patterns.burst import mine_burst
    from algorithms.patterns.durable import mine_durable
    from algorithms.patterns.frequency import mine_frequency
    from algorithms.patterns.periodic import mine_periodic

    if request.pattern == "burst" and request.l > len(snapshots):
        raise HTTPException(422, "The minimum span l cannot exceed the number of snapshots in the mining range.")
    if request.pattern == "frequency" and request.t > len(snapshots):
        raise HTTPException(422, "The minimum active snapshot count t cannot exceed the number of snapshots in the mining range.")
    if not snapshots[0]:
        return None
    if (
        request.pattern in ("periodic", "durable", "burst")
        and request.account is not None
        and request.account not in snapshots[0]
    ):
        raise HTTPException(422, "The query node is absent from the selected mining range.")
    try:
        if request.pattern == "periodic":
            return mine_periodic(snapshots, request.account, request.k, request.epsilon)
        if request.pattern == "durable":
            return mine_durable(snapshots, request.account, request.k)
        if request.pattern == "frequency":
            return mine_frequency(snapshots, request.k, request.t, request.f)
        result = mine_burst(snapshots, request.l, request.delta)
        if result is not None and request.account is not None and request.account not in result.members:
            return None
        return result
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def public_pattern_evidence(
    pattern: str, evidence: dict, snapshot_ids: list[str]
) -> dict:
    result = deepcopy(evidence)
    result["analysis_snapshot_ids"] = snapshot_ids
    positions = {
        "periodic": ("start_index", "end_index"),
        "durable": ("formation_start", "formation_end", "stable_end"),
        "burst": (),
        "frequency": (),
        "temporal_core": ("witness_start", "witness_end"),
    }
    for field in positions[pattern]:
        result[f"{field}_snapshot_id"] = snapshot_ids[result[field]]
    if pattern == "burst":
        witnesses, measure = result["nodes"], "max_average_degree"
    elif pattern == "frequency":
        witnesses, measure = result["qualified_edges"], "frequency"
    else:
        return result
    for witness in witnesses:
        witness[measure] = witness["numerator"] / witness["denominator"]
        for field in ("witness_start", "witness_end"):
            witness[f"{field}_snapshot_id"] = snapshot_ids[witness[field]]
    return result


def temporal_core_window_comparison(
    result: PatternResult, snapshots: TemporalSnapshots, snapshot_ids: list[str], k: int
) -> list[dict]:
    first = result.evidence["witness_start"]
    last = result.evidence["witness_end"]
    members = set(result.members)
    neighbors_by_snapshot = [
        [frame[node] & members for node in result.members]
        for frame in snapshots[first : last + 1]
    ]
    windows = [(first, last, 0)]
    if first < last:
        # Both ends count each undirected link once at the dropped timestamp.
        first_edges = sum(map(len, neighbors_by_snapshot[0])) // 2
        last_edges = sum(map(len, neighbors_by_snapshot[-1])) // 2
        windows = [(first, last - 1, last_edges), (first + 1, last, first_edges), *windows]

    comparison = []
    for start, end, omitted_edges in windows:
        window = neighbors_by_snapshot[start - first : end - first + 1]
        # Each row keeps the same member order, including members absent from that snapshot.
        degrees = [len(set().union(*neighbors)) for neighbors in zip(*window)]
        comparison.append({
            "start_snapshot_id": snapshot_ids[start],
            "end_snapshot_id": snapshot_ids[end],
            "min_internal_degree": min(degrees),
            "below_k_members": sum(degree < k for degree in degrees),
            "omitted_temporal_edges": omitted_edges,
        })
    return comparison


def find_patterns(scope: AnalysisScope, request: PatternQuery) -> dict:
    history_ids = tuple(
        meta.snapshot_id for meta in sorted(scope.manifest.snapshots, key=lambda meta: meta.index)
        if meta.kind == "history"
    )
    snapshot_ids = mining_window(scope, request, history_ids)
    if request.pattern == "historical_core":
        return historical_cores(scope, request, history_ids, snapshot_ids)
    frames = [scope.repository.snapshot(request.dataset_id, sid) for sid in snapshot_ids]
    snapshots = project_snapshots(frames)
    temporal_core = request.pattern == "temporal_core"
    if temporal_core:
        results = mine_temporal_cores(snapshots, request.k)
    else:
        result = mine_pattern(request, snapshots)
        results = [result] if result is not None else []

    method, label, identifier, color_index = _PATTERN_DETAILS[request.pattern]
    parameters = request.model_dump(
        exclude={"dataset_id", "dataset_version", "observed_until"}, exclude_none=True
    )
    if temporal_core:
        parameters.update(start_snapshot_id=snapshot_ids[0], end_snapshot_id=snapshot_ids[-1])

    structures = []
    for result in results:
        evidence = public_pattern_evidence(request.pattern, result.evidence, snapshot_ids)
        metrics_frame = frames[-1]
        snapshot_id = metrics_frame.snapshot_id
        structure_id = identifier
        if temporal_core:
            first, last = evidence["witness_start"], evidence["witness_end"]
            evidence["window_comparison"] = temporal_core_window_comparison(
                result, snapshots, snapshot_ids, request.k
            )
            metrics_frame = combine_snapshots(frames[first : last + 1])
            snapshot_id = snapshot_ids[last]
            structure_id = f"{identifier}:{snapshot_ids[first]}:{snapshot_id}"
        structure = make_structure(
            scope,
            structure_id,
            list(result.members),
            "pattern",
            parameters,
            "computed",
            method,
            COLORS[color_index],
            snapshot_id=snapshot_id,
            evidence=evidence,
            metrics_frame=metrics_frame,
        )
        structure.label = label
        structures.append(structure)
    empty_message = f"No {label.lower()} matches the query."
    if request.pattern == "burst" and request.account is not None:
        empty_message = f"No {label.lower()} containing node {request.account} matches the query."
    return {
        **scope.metadata("computed", method),
        "analysis_snapshot_ids": snapshot_ids,
        "reference_snapshot_id": snapshot_ids[-1],
        "structures": structures,
        "message": "" if structures else empty_message,
    }
