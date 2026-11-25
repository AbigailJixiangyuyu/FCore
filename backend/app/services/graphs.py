"""Read observed graph frames and build the shared graph response."""

from fastapi import HTTPException

from algorithms.core.queries import core_numbers
from app.schemas.analysis import SnapshotData, SnapshotMeta
from app.services.context import AnalysisScope
from app.services.statistics import aggregate_edges, graph_of, selection_metrics


def graph_payload(scope: AnalysisScope, frame: SnapshotData) -> dict:
    present = set(frame.present_accounts)
    return {
        "nodes": [
            node
            for node in scope.repository.accounts(scope.context.dataset_id)
            if node["id"] in present
        ],
        "edges": aggregate_edges(frame),
        "stats": selection_metrics(frame, frame.present_accounts),
        "core_numbers": core_numbers(graph_of(frame)),
    }


def snapshot(scope: AnalysisScope, snapshot_id: str) -> dict:
    frame = scope.repository.snapshot(scope.context.dataset_id, snapshot_id)
    payload = graph_payload(scope, frame)
    return {
        **scope.metadata("computed", "static-graph-v1" if frame.static_edges is not None else "transaction-aggregation-v1"),
        "snapshot_id": snapshot_id,
        **payload,
    }


def window_bounds(
    scope: AnalysisScope, start_snapshot_id: str, end_snapshot_id: str
) -> tuple[SnapshotMeta, SnapshotMeta]:
    by_id = {meta.snapshot_id: meta for meta in scope.manifest.snapshots}
    if start_snapshot_id not in by_id or end_snapshot_id not in by_id:
        raise HTTPException(404, "The range contains an unknown snapshot.")
    return by_id[start_snapshot_id], by_id[end_snapshot_id]


def combine_snapshots(frames: list[SnapshotData]) -> SnapshotData:
    if len(frames) == 1:
        return frames[0]
    return SnapshotData(
        snapshot_id=f"{frames[0].snapshot_id}:{frames[-1].snapshot_id}",
        present_accounts=sorted(
            {account for frame in frames for account in frame.present_accounts}
        ),
        transactions=[t for frame in frames for t in frame.transactions],
        static_edges=(
            sorted({edge for frame in frames for edge in frame.static_edges or ()})
            if any(frame.static_edges is not None for frame in frames) else None
        ),
    )


def observed_window(
    scope: AnalysisScope, start: SnapshotMeta, end: SnapshotMeta
) -> tuple[SnapshotData, list[str]]:
    if start.index > end.index:
        raise HTTPException(422, "The start snapshot must be at or before the end snapshot.")
    selected = sorted(
        (
            meta
            for meta in scope.manifest.snapshots
            if start.index <= meta.index <= end.index
        ),
        key=lambda meta: meta.index,
    )
    if any(meta.kind == "future" for meta in selected):
        raise HTTPException(422, "Choose a range of observed snapshots.")
    snapshot_ids = [meta.snapshot_id for meta in selected]
    frames = [
        scope.repository.snapshot(scope.context.dataset_id, snapshot_id)
        for snapshot_id in snapshot_ids
    ]
    return combine_snapshots(frames), snapshot_ids


def current_window_coreness(scope: AnalysisScope, start_snapshot_id: str) -> dict:
    start, end = window_bounds(scope, start_snapshot_id, scope.manifest.observed_until)
    frame, _ = observed_window(scope, start, end)
    return {
        **scope.metadata("computed", "window-core-numbers-v1"),
        "start_snapshot_id": start.snapshot_id,
        "end_snapshot_id": end.snapshot_id,
        "core_numbers": core_numbers(graph_of(frame)),
    }


def aggregate(scope: AnalysisScope, start_snapshot_id: str, end_snapshot_id: str) -> dict:
    start, end = window_bounds(scope, start_snapshot_id, end_snapshot_id)
    if start.kind != "history" or end.kind != "history":
        raise HTTPException(422, "Choose two historical snapshots for aggregation.")
    return aggregate_payload(scope, start, end)


def observed_aggregate(scope: AnalysisScope) -> dict:
    start = min(scope.manifest.snapshots, key=lambda meta: meta.index)
    _, end = window_bounds(scope, start.snapshot_id, scope.manifest.observed_until)
    return aggregate_payload(scope, start, end)


def aggregate_payload(scope: AnalysisScope, start: SnapshotMeta, end: SnapshotMeta) -> dict:
    frame, snapshot_ids = observed_window(scope, start, end)
    payload = graph_payload(scope, frame)
    period = "historical" if end.kind == "history" else "observed"
    data = "graph" if frame.static_edges is not None else "transaction"
    return {
        **scope.metadata("computed", f"{period}-{data}-union-v1"),
        "start_snapshot_id": start.snapshot_id,
        "end_snapshot_id": end.snapshot_id,
        "snapshot_ids": snapshot_ids,
        "starts_at": start.starts_at,
        "ends_at": end.ends_at,
        **payload,
    }
