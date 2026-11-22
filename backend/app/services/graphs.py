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
        **scope.metadata("computed", "transaction-aggregation-v1"),
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
    if len(frames) == 1:
        return frames[0], snapshot_ids
    combined = SnapshotData(
        snapshot_id=f"{start.snapshot_id}:{end.snapshot_id}",
        present_accounts=sorted(
            {account for frame in frames for account in frame.present_accounts}
        ),
        transactions=[t for frame in frames for t in frame.transactions],
    )
    return combined, snapshot_ids


def aggregate(scope: AnalysisScope, start_snapshot_id: str, end_snapshot_id: str) -> dict:
    start, end = window_bounds(scope, start_snapshot_id, end_snapshot_id)
    if start.kind != "history" or end.kind != "history":
        raise HTTPException(422, "Aggregate queries support historical snapshots S01–S11.")
    frame, snapshot_ids = observed_window(scope, start, end)
    payload = graph_payload(scope, frame)
    return {
        **scope.metadata("computed", "historical-transaction-union-v1"),
        "start_snapshot_id": start_snapshot_id,
        "end_snapshot_id": end_snapshot_id,
        "snapshot_ids": snapshot_ids,
        "starts_at": start.starts_at,
        "ends_at": end.ends_at,
        **payload,
    }
