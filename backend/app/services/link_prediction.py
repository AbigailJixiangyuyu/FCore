"""Model registry and immutable full-network predictions, filtered by community."""

from collections import OrderedDict
from pathlib import Path
from threading import RLock

import torch
from fastapi import HTTPException

from algorithms.link_prediction.adapters import MODELS
from algorithms.link_prediction.calibration import link_probabilities
from algorithms.link_prediction.checkpoint import ModelConflict
from algorithms.link_prediction.data import (
    event_fingerprint,
    positive_pairs,
    prepare_history,
    read_window,
)
from algorithms.link_prediction.runtime import ModelUnavailable, cuda_device
from app.schemas.analysis import LinkModel, LinkPredictionQuery
from app.services.context import AnalysisScope
from app.services.parallel_core import ParallelCoreCache
from app.services.selection import resolve_structure

_LOCK = RLock()
_CACHE = OrderedDict()
_VERIFIED = OrderedDict()
_CACHE_LIMIT = 4


def model_catalog(scope: AnalysisScope, models_dir: Path) -> dict:
    models = list_models(scope.repository, scope.manifest, models_dir)
    return {**scope.metadata("computed", "link-prediction-registry-v1"), "models": models}


def _remember(cache, key, value):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)


def list_models(repository, manifest, models_dir):
    rows = [
        {"id": model_id, "name": adapter.name, "status": "not_ready", "model_version": None, "message": ""}
        for model_id, adapter in MODELS.items()
    ]
    try:
        _, metadata = prepare_history(repository, manifest)
    except ValueError as error:
        for row in rows:
            row["message"] = str(error)
        return rows
    for row in rows:
        adapter = MODELS[row["id"]]
        try:
            _, artifact = adapter.artifacts.read_artifact(models_dir, manifest.dataset_id, metadata)
            cuda_device(adapter.name)
            key = (str(models_dir.resolve()), manifest.dataset_id, row["id"], artifact["model_version"], artifact["checkpoint_sha256"])
            with _LOCK:
                if key not in _VERIFIED:
                    adapter.artifacts.load_artifact(models_dir, manifest.dataset_id, metadata, artifact["model_version"])
                    _remember(_VERIFIED, key, True)
            calibration = artifact.get("probability_calibration")
            row.update(
                status="ready", model_version=artifact["model_version"],
                probability_calibration=calibration["method"] if calibration else None,
            )
        except ModelConflict as error:
            row.update(status="conflict", message=str(error))
        except (ModelUnavailable, ValueError) as error:
            row["message"] = str(error)
    return rows


def full_network_prediction(repository, manifest, models_dir, model_id="zebra"):
    adapter = MODELS[model_id]
    history, metadata = prepare_history(repository, manifest)
    _, artifact = adapter.artifacts.read_artifact(models_dir, manifest.dataset_id, metadata)
    cuda_device(adapter.name)
    current_meta = next(m for m in manifest.snapshots if m.snapshot_id == manifest.observed_until)
    current = read_window(repository, manifest, current_meta, metadata["origin_timestamp"])
    key = (
        str(models_dir.resolve()), manifest.dataset_id, manifest.dataset_version, model_id,
        artifact["model_version"], artifact["checkpoint_sha256"],
        metadata["history_fingerprint"], current.snapshot_id, current.end,
        event_fingerprint(current.events),
    )
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
        model, state, temperature, artifact = adapter.artifacts.load_artifact(models_dir, manifest.dataset_id, metadata, artifact["model_version"])
        with torch.inference_mode():
            adapter.advance(model, state, current)
            pairs, logits = model.all_pairs(state, current.end)
            probabilities = link_probabilities(
                pairs, logits, (*history, current), temperature,
                artifact.get("probability_calibration"),
            ).cpu().tolist()
        connected = positive_pairs(current)
        rows = [
            {"u": u, "v": v, "probability": probability, "currently_connected": (u, v) in connected}
            for (u, v), probability in zip(pairs, probabilities)
        ]
        rows.sort(key=lambda row: (-row["probability"], row["u"], row["v"]))
        value = {"pairs": rows, "known": frozenset(state.known_accounts()), "model_version": artifact["model_version"]}
        _remember(_CACHE, key, value)
        return value


def score_network(scope: AnalysisScope, models_dir: Path, model: LinkModel) -> dict:
    try:
        return full_network_prediction(scope.repository, scope.manifest, models_dir, model)
    except ModelConflict as error:
        raise HTTPException(409, str(error)) from error
    except ModelUnavailable as error:
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def predict_selected_links(
    scope: AnalysisScope,
    request: LinkPredictionQuery,
    models_dir: Path,
    parallel_core: ParallelCoreCache,
) -> dict:
    selection = request.structure.model_copy(
        update={"members": sorted(request.structure.members)}
    )
    structure = resolve_structure(scope, selection, parallel_core)
    manifest = scope.manifest
    if structure.origin == "pattern" or structure.snapshot_id != manifest.observed_until:
        raise HTTPException(422, "链接预测需要当前 S12 的查询结构")
    result = score_network(scope, models_dir, request.model)
    members = set(structure.members)
    rows = [row for row in result["pairs"] if row["u"] in members and row["v"] in members]
    rows = [{**row, "rank": rank} for rank, row in enumerate(rows, 1)]
    unscored = [{"account_id": account, "reason": "no_interaction_history"} for account in sorted(members - result["known"])]
    target = next(meta for meta in manifest.snapshots if meta.kind == "future")
    current = next(meta for meta in manifest.snapshots if meta.snapshot_id == manifest.observed_until)
    status, message = "ok", ""
    if len(members) < 2:
        status, message = "no_candidates", "所选结构少于两个账户，没有候选顶点对。"
    elif not rows:
        status, message = "no_history", "所选结构没有具备历史交互的可评分顶点对。"
    elif unscored:
        message = "部分账户尚无交互历史，相关顶点对未评分。"
    return {
        **scope.metadata("computed", MODELS[request.model].method),
        "model": request.model, "model_version": result["model_version"],
        "structure_id": structure.structure_id, "membership_hash": structure.membership_hash,
        "scored_at": current.ends_at, "target_snapshot": target.snapshot_id,
        "target_starts_at": target.starts_at, "target_ends_at": target.ends_at,
        "window_seconds": manifest.snapshot_minutes * 60, "directed": False,
        "candidate_pair_count": len(members) * (len(members) - 1) // 2,
        "scored_pair_count": len(rows), "pairs": rows, "unscored_accounts": unscored,
        "status": status, "message": message,
    }
