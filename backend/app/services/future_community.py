"""Forecast the connected k-core containing a query account in a future snapshot."""

from pathlib import Path

from fastapi import HTTPException

from algorithms.core.queries import adjacency, core_numbers, local_core
from algorithms.link_prediction.adapters import ZEBRA
from app.schemas.analysis import FutureCommunityQuery
from app.services.context import AnalysisScope
from app.services.link_prediction import prediction_target, score_network
from app.services.statistics import graph_of


def _compare_communities(
    scope: AnalysisScope, request: FutureCommunityQuery, predicted_cores: dict[str, int]
) -> dict:
    frame = scope.repository.snapshot(request.dataset_id, request.observed_until)
    graph = graph_of(frame)
    observed_cores = core_numbers(graph)
    components = local_core(graph, request.account, request.k, numbers=observed_cores)
    observed_members = set(components[0]) if components else set()
    predicted_members = set(predicted_cores)
    max_coreness = max(predicted_cores.values(), default=None)
    return {
        "retained": sorted(observed_members & predicted_members),
        "added": sorted(predicted_members - observed_members),
        "exited": sorted(observed_members - predicted_members),
        "max_coreness": max_coreness,
        "key_nodes": [
            {
                "account_id": account,
                "observed_coreness": observed_cores[account] if account in observed_members else None,
                "predicted_coreness": predicted_cores[account],
            }
            for account in sorted(predicted_members)
            if predicted_cores[account] == max_coreness
        ],
    }


def forecast_community(
    scope: AnalysisScope, request: FutureCommunityQuery, models_dir: Path
) -> dict:
    repository, manifest = scope.repository, scope.manifest
    dataset_id, account, k = manifest.dataset_id, request.account, request.k
    threshold = request.threshold
    if not any(node["id"] == account for node in repository.accounts(dataset_id)):
        raise HTTPException(422, "The query node is not in this dataset.")

    history = sorted(
        (meta for meta in manifest.snapshots if meta.kind == "history"),
        key=lambda meta: meta.index,
    )
    candidates: set[str] = set()
    for meta in history:
        frame = repository.snapshot(dataset_id, meta.snapshot_id)
        for component in local_core(graph_of(frame), account, k):
            candidates.update(component)

    scored_pairs = []
    model_version = None
    if candidates:
        scores = score_network(scope, models_dir, horizon=request.horizon)
        scored_pairs = [
            edge for edge in scores["pairs"]
            if edge["u"] in candidates and edge["v"] in candidates
        ]
        model_version = scores["model_version"]

    threshold_edges = [
        edge for edge in scored_pairs if edge["probability"] > threshold
    ]
    members = []
    predicted_cores = {}
    if threshold_edges or (k == 0 and scored_pairs):
        graph = adjacency(candidates, ((edge["u"], edge["v"]) for edge in threshold_edges))
        numbers = core_numbers(graph)
        components = local_core(graph, account, k, numbers=numbers)
        if components:
            members = components[0]
            # A node's coreness is preserved within its k-core component.
            predicted_cores = {member: numbers[member] for member in members}
    selected = set(members)

    status, message = "ok", ""
    if not candidates:
        status, message = "no_historical_community", f"No historical {k}-core community contains node {account}."
    elif not scored_pairs:
        status, message = "no_scored_pairs", "No candidate node pairs can be scored."
    elif not threshold_edges and not members:
        status, message = "no_threshold_edges", f"No link probabilities exceed {threshold * 100:g}%."
    elif not members:
        status, message = "no_predicted_community", f"No predicted {k}-core community contains node {account}."

    comparison = _compare_communities(scope, request, predicted_cores) if scored_pairs else None
    target = prediction_target(manifest, request.horizon)
    n = len(candidates)
    return {
        **scope.metadata("computed", ZEBRA.method),
        "account": account,
        "k": k,
        "model": request.model,
        "model_version": model_version,
        "history_snapshot_ids": [meta.snapshot_id for meta in history],
        "target_snapshot": target.snapshot_id,
        "target_starts_at": target.starts_at,
        "target_ends_at": target.ends_at,
        "threshold": threshold,
        "candidate_member_count": n,
        "candidate_pair_count": n * (n - 1) // 2,
        "scored_pair_count": len(scored_pairs),
        "max_probability": max((edge["probability"] for edge in scored_pairs), default=None),
        "threshold_edge_count": len(threshold_edges),
        "members": members,
        "edges": [
            edge for edge in threshold_edges if edge["u"] in selected and edge["v"] in selected
        ],
        "comparison": comparison,
        "status": status,
        "message": message,
    }
