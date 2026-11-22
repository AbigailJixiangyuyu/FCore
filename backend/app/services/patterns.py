"""Adapt historical transaction snapshots to the independent mining functions."""

from copy import deepcopy

from fastapi import HTTPException

from algorithms.patterns.common import PatternResult, TemporalSnapshots
from app.schemas.analysis import PatternQuery
from app.services.context import AnalysisScope
from app.services.graphs import window_bounds
from app.services.statistics import graph_of
from app.services.structures import COLORS, make_structure

# Method version, public label, result ID and palette index for each algorithm.
_PATTERN_DETAILS = {
    "periodic": ("lpc-td-ftac-v1", "Periodic Community", "P1", 0),
    "durable": ("tdc-once-v1", "Durable Community", "D1", 1),
    "burst": ("mbc-exact-segments-v1", "Bursting Core", "B1", 2),
    "frequency": ("frequency-aware-kcore-online-v1", "Frequency-Aware Core", "F1", 3),
}


def historical_snapshots(
    scope: AnalysisScope, request: PatternQuery
) -> tuple[list[str], TemporalSnapshots]:
    metadata = sorted(
        (meta for meta in scope.manifest.snapshots if meta.kind == "history"),
        key=lambda meta: meta.index,
    )
    if request.start_snapshot_id is not None and request.end_snapshot_id is not None:
        start, end = window_bounds(scope, request.start_snapshot_id, request.end_snapshot_id)
        if start.kind != "history" or end.kind != "history":
            raise HTTPException(422, "Mining requires a range of historical snapshots.")
        if start.index > end.index:
            raise HTTPException(422, "The first snapshot to mine must be at or before the last snapshot.")
        metadata = [meta for meta in metadata if start.index <= meta.index <= end.index]
    if not metadata:
        raise HTTPException(404, "No historical snapshots are available to mine.")
    frames = [
        scope.repository.snapshot(scope.context.dataset_id, meta.snapshot_id)
        for meta in metadata
    ]
    accounts = sorted(
        {account for frame in frames for account in frame.present_accounts}
    )
    graphs = [graph_of(frame) for frame in frames]
    snapshots = tuple(
        {account: frozenset(graph.get(account, ())) for account in accounts}
        for graph in graphs
    )
    return [meta.snapshot_id for meta in metadata], snapshots


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


def find_patterns(scope: AnalysisScope, request: PatternQuery) -> dict:
    snapshot_ids, snapshots = historical_snapshots(scope, request)
    result = mine_pattern(request, snapshots)
    method, label, identifier, color_index = _PATTERN_DETAILS[request.pattern]
    parameters = request.model_dump(
        exclude={"dataset_id", "dataset_version", "observed_until"}, exclude_none=True
    )
    structures = []
    if result is not None:
        structure = make_structure(
            scope,
            identifier,
            list(result.members),
            "pattern",
            parameters,
            "computed",
            method,
            COLORS[color_index],
            snapshot_id=snapshot_ids[-1],
            evidence=public_pattern_evidence(
                request.pattern, result.evidence, snapshot_ids
            ),
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
