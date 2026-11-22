"""Deprecated interaction-share APIs, including the explicit S13 replay path."""

from fastapi import HTTPException

from algorithms.affinity.demo import profile_weights
from app.schemas.analysis import AffinityQuery
from app.services.context import AnalysisScope
from app.services.parallel_core import ParallelCoreCache
from app.services.selection import resolve_structure


def interaction_shares(
    scope: AnalysisScope,
    request: AffinityQuery,
    parallel_core: ParallelCoreCache,
    *,
    reveal: bool = False,
) -> dict:
    structure = resolve_structure(scope, request.structure, parallel_core)
    if (
        structure.origin == "pattern"
        or structure.snapshot_id != scope.manifest.observed_until
    ):
        raise HTTPException(422, "未来分析必须来自现在选中的查询结构")
    if request.source_account not in structure.members:
        raise HTTPException(422, "查看账户不在所选结构中")
    source_index = structure.members.index(request.source_account)
    ordered = (
        structure.members[source_index + 1 :] + structure.members[:source_index]
    )
    result_kind, method = "demo_fixture", "normalized-profile-demo-v1"
    values = []
    if reveal:
        result_kind, method = "computed", "replay-transaction-share-v1"
        # Only this branch can read future transactions.
        replay = scope.repository.replay(scope.context.dataset_id)
        counts = {target: 0 for target in ordered}
        for transaction in replay.transactions:
            if transaction.u == request.source_account and transaction.v in counts:
                counts[transaction.v] += 1
            elif transaction.v == request.source_account and transaction.u in counts:
                counts[transaction.u] += 1
        values = [counts[target] for target in ordered]
    else:
        try:
            profile = scope.repository.scenarios(scope.context.dataset_id)[
                "prediction_profile"
            ]
        except HTTPException as error:
            if error.status_code != 404:
                raise
            raise HTTPException(
                503, "当前数据集尚未接入群内交互份额预测"
            ) from error
        values = profile_weights(len(ordered), profile)
    total = sum(values)
    candidates = [
        {
            "target_account": target,
            "share": value / total if total else None,
            "transaction_count": int(value) if reveal else None,
        }
        for target, value in zip(ordered, values)
    ]
    candidates.sort(
        key=lambda item: (-(item["share"] or 0), item["target_account"])
    )
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank
    status = "ok"
    if not ordered:
        status = "no_candidates"
    elif not total:
        status = "no_interactions"
    return {
        **scope.metadata(result_kind, method),
        "structure_id": structure.structure_id,
        "membership_hash": structure.membership_hash,
        "source_account": request.source_account,
        "target_snapshot": "S13",
        "window_minutes": scope.manifest.snapshot_minutes,
        "interaction_measure": "transaction_count",
        "status": status,
        "candidates": candidates,
    }
