"""Canonical structure members, statistics and identity shared by all queries."""

import hashlib
import json

from app.schemas.analysis import SnapshotData, Structure
from app.services.context import AnalysisScope
from app.services.statistics import selection_metrics

COLORS = ["#477be7", "#9670c7", "#36a194", "#c99c43"]


def pattern_qualified_pairs(evidence: dict | None) -> set[tuple[str, str]] | None:
    if evidence is None or "qualified_edges" not in evidence:
        return None
    return {(edge["u"], edge["v"]) for edge in evidence["qualified_edges"]}


def make_structure(
    scope: AnalysisScope,
    identifier: str,
    members: list[str],
    origin: str,
    parameters: dict,
    result_kind: str,
    method: str,
    color: str,
    description: str = "",
    snapshot_id: str | None = None,
    evidence: dict | None = None,
    metrics_frame: SnapshotData | None = None,
    metrics: dict | None = None,
) -> Structure:
    snapshot_id = snapshot_id or scope.manifest.observed_until
    members = sorted(set(members))
    fingerprint = [
        scope.context.dataset_id,
        scope.context.dataset_version,
        scope.context.observed_until,
        snapshot_id,
        origin,
        parameters,
        members,
    ]
    if origin == "pattern":
        fingerprint.append(method)
        if evidence and "witness_start_snapshot_id" in evidence:
            fingerprint.append(evidence["witness_start_snapshot_id"])
    membership_hash = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True).encode()
    ).hexdigest()[:24]
    if metrics is None:
        if metrics_frame is None:
            metrics_frame = scope.repository.snapshot(scope.context.dataset_id, snapshot_id)
        metrics = selection_metrics(metrics_frame, members, pattern_qualified_pairs(evidence))
    label = f"Community {identifier}"
    if origin == "pattern":
        label = f"Subgraph {identifier}"
    return Structure(
        structure_id=identifier,
        label=label,
        dataset_id=scope.context.dataset_id,
        dataset_version=scope.context.dataset_version,
        observed_until=scope.context.observed_until,
        snapshot_id=snapshot_id,
        origin=origin,
        parameters=parameters,
        members=members,
        membership_hash=membership_hash,
        color=color,
        result_kind=result_kind,
        method=method,
        description=description,
        metrics=metrics,
        evidence=evidence,
    )
