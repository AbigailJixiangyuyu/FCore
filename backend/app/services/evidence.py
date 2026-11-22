"""Fixed-member time series on each structure's observed snapshots."""

from app.schemas.analysis import EvidenceQuery
from app.services.context import AnalysisScope
from app.services.parallel_core import ParallelCoreCache
from app.services.selection import resolve_structure
from app.services.statistics import selection_metrics
from app.services.structures import pattern_qualified_pairs


def evidence_series(
    scope: AnalysisScope, request: EvidenceQuery, parallel_core: ParallelCoreCache
) -> dict:
    structures = [
        resolve_structure(scope, item, parallel_core) for item in request.structures
    ]
    unit = {
        "internal_edges": "undirected edges",
        "transaction_count": "interactions",
    }[request.metric]
    series = []
    for structure in structures:
        qualified_pairs = pattern_qualified_pairs(structure.evidence)
        pattern_snapshots = (
            set(structure.evidence["analysis_snapshot_ids"])
            if structure.origin == "pattern"
            else None
        )
        points = []
        for meta in scope.manifest.snapshots:
            if meta.kind == "future" or (
                pattern_snapshots is not None and meta.snapshot_id not in pattern_snapshots
            ):
                continue
            frame = scope.repository.snapshot(
                scope.context.dataset_id, meta.snapshot_id
            )
            metrics = selection_metrics(frame, structure.members, qualified_pairs)
            points.append(
                {
                    "snapshot_id": meta.snapshot_id,
                    "index": meta.index,
                    "value": metrics[request.metric]
                    if metrics["present_count"]
                    else None,
                    "present_count": metrics["present_count"],
                    "status": "ok" if metrics["present_count"] else "absent",
                }
            )
        series.append(
            {
                "structure_id": structure.structure_id,
                "membership_hash": structure.membership_hash,
                "label": structure.label,
                "color": structure.color,
                "member_count": len(structure.members),
                "points": points,
            }
        )
    return {
        **scope.metadata("computed", "fixed-members-transaction-statistics-v1"),
        "metric": request.metric,
        "unit": unit,
        "series": series,
    }
