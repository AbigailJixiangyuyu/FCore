"""Model registry and immutable full-network predictions, filtered by community."""

from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock

import torch
from fastapi import HTTPException

from algorithms.link_prediction.adapters import ZEBRA
from algorithms.link_prediction.calibration import link_probabilities
from algorithms.link_prediction.checkpoint import ModelConflict
from algorithms.link_prediction.data import (
    event_fingerprint,
    positive_pairs,
    prepare_history,
    read_window,
)
from algorithms.runtime import ModelUnavailable, inference_device
from app.schemas.analysis import LinkPredictionQuery
from app.repositories.granularity import model_directory
from app.services.context import AnalysisScope
from app.services.parallel_core import ParallelCoreCache
from app.services.selection import resolve_structure

_LOCK = RLock()
_CACHE = OrderedDict()
_VERIFIED = OrderedDict()
_CACHE_LIMIT = 4


def model_catalog(scope: AnalysisScope, models_dir: Path, *, horizon: int = 1) -> dict:
    models = list_models(scope.repository, scope.manifest, models_dir, horizon=horizon)
    return {**scope.metadata("computed", "link-prediction-registry-v1"), "horizon": horizon, "models": models}


def prediction_target(manifest, horizon=1):
    first = next(meta for meta in manifest.snapshots if meta.kind == "future")
    if horizon == 1:
        return first
    step = horizon - 1
    offset = timedelta(minutes=manifest.snapshot_minutes * step)
    index = first.index + step
    return first.model_copy(update={
        "snapshot_id": f"S{index + 1:02d}",
        "index": index,
        "starts_at": (datetime.fromisoformat(first.starts_at) + offset).isoformat(),
        "ends_at": (datetime.fromisoformat(first.ends_at) + offset).isoformat(),
    })


def _remember(cache, key, value):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)


def list_models(repository, manifest, models_dir, *, horizon=1):
    models_dir = model_directory(models_dir, manifest)
    row = {"id": "zebra", "name": ZEBRA.name, "status": "not_ready", "model_version": None, "message": ""}
    if manifest.has_demo_updates:
        row["message"] = "Zebra is unavailable for this static graph update."
        return [row]
    try:
        _, metadata = prepare_history(repository, manifest)
        _, artifact = ZEBRA.artifacts.read_artifact(models_dir, manifest.dataset_id, metadata, horizon=horizon)
        inference_device(ZEBRA.name)
        key = (str(models_dir.resolve()), manifest.dataset_id, artifact["model_version"], artifact["checkpoint_sha256"])
        with _LOCK:
            if key not in _VERIFIED:
                ZEBRA.artifacts.load_artifact(
                    models_dir, manifest.dataset_id, metadata, artifact["model_version"], horizon=horizon,
                )
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
    return [row]


def full_network_prediction(repository, manifest, models_dir, *, horizon=1):
    models_dir = model_directory(models_dir, manifest)
    history, metadata = prepare_history(repository, manifest)
    _, artifact = ZEBRA.artifacts.read_artifact(models_dir, manifest.dataset_id, metadata, horizon=horizon)
    inference_device(ZEBRA.name)
    current_meta = next(m for m in manifest.snapshots if m.snapshot_id == manifest.observed_until)
    current = read_window(repository, manifest, current_meta, metadata["origin_timestamp"])
    key = (
        str(models_dir.resolve()), manifest.dataset_id, manifest.dataset_version, horizon,
        artifact["model_version"], artifact["checkpoint_sha256"],
        metadata["history_fingerprint"], current.snapshot_id, current.end,
        event_fingerprint(current.events),
    )
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
        model, state, temperature, artifact = ZEBRA.artifacts.load_artifact(
            models_dir, manifest.dataset_id, metadata, artifact["model_version"], horizon=horizon,
        )
        with torch.inference_mode():
            ZEBRA.advance(model, state, current)
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


def score_network(scope: AnalysisScope, models_dir: Path, *, horizon: int = 1) -> dict:
    if scope.manifest.has_demo_updates:
        raise HTTPException(503, "Zebra is unavailable for this static graph update.")
    try:
        return full_network_prediction(scope.repository, scope.manifest, models_dir, horizon=horizon)
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
        raise HTTPException(422, f"Link prediction requires a community queried in {manifest.observed_until}.")
    result = score_network(scope, models_dir)
    members = set(structure.members)
    rows = [row for row in result["pairs"] if row["u"] in members and row["v"] in members]
    rows = [{**row, "rank": rank} for rank, row in enumerate(rows, 1)]
    unscored = [{"account_id": account, "reason": "no_interaction_history"} for account in sorted(members - result["known"])]
    target = prediction_target(manifest)
    current = next(meta for meta in manifest.snapshots if meta.snapshot_id == manifest.observed_until)
    status, message = "ok", ""
    if len(members) < 2:
        status, message = "no_candidates", "Select a community with at least two nodes."
    elif not rows:
        status, message = "no_history", "No node pairs in the selected community have enough interaction history to score."
    elif unscored:
        message = "Pairs that include nodes without interaction history have no scores."
    return {
        **scope.metadata("computed", ZEBRA.method),
        "model": request.model, "model_version": result["model_version"],
        "structure_id": structure.structure_id, "membership_hash": structure.membership_hash,
        "scored_at": current.ends_at, "target_snapshot": target.snapshot_id,
        "target_starts_at": target.starts_at, "target_ends_at": target.ends_at,
        "window_seconds": manifest.snapshot_minutes * 60, "directed": False,
        "candidate_pair_count": len(members) * (len(members) - 1) // 2,
        "scored_pair_count": len(rows), "pairs": rows, "unscored_accounts": unscored,
        "status": status, "message": message,
    }
