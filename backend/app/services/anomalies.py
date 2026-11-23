"""SLADE input boundary, artifact validation and stateless S12 account scoring."""

from pathlib import Path

from fastapi import HTTPException

from algorithms.anomaly.artifacts import ModelConflict, ModelNotReady, load_artifact
from algorithms.anomaly.events import event_fingerprint, seconds, snapshot_events
from algorithms.runtime import ModelUnavailable
from algorithms.anomaly.slade import METHOD
from app.schemas.analysis import AnomalyQuery
from app.services.context import AnalysisScope


def prepare_training(repository, manifest):
    metas = sorted(
        (meta for meta in manifest.snapshots if meta.kind == "history"),
        key=lambda meta: meta.index,
    )
    present = next(
        meta
        for meta in manifest.snapshots
        if meta.snapshot_id == manifest.observed_until
    )
    if not metas or any(meta.index >= present.index for meta in metas):
        raise ValueError("The training range is invalid.")
    origin = metas[0].starts_at
    events = tuple(
        event
        for meta in metas
        for event in snapshot_events(
            repository.snapshot(manifest.dataset_id, meta.snapshot_id), meta, origin
        )
    )
    metadata = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "snapshot_ids": [meta.snapshot_id for meta in metas],
        "origin_time": origin,
        "starts_at": metas[0].starts_at,
        "ends_at": metas[-1].ends_at,
        "event_count": len(events),
        "event_fingerprint": event_fingerprint(events),
    }
    return events, metadata


def model_ready(repository, manifest, models_dir: Path) -> bool:
    try:
        _, metadata = prepare_training(repository, manifest)
        load_artifact(models_dir, manifest.dataset_id, metadata)
        return True
    except (ModelNotReady, ModelConflict, ModelUnavailable, ValueError, HTTPException):
        return False


def score_accounts(scope: AnalysisScope, request: AnomalyQuery, models_dir: Path) -> dict:
    repository, manifest = scope.repository, scope.manifest
    snapshot_id = request.snapshot_id
    frame = repository.snapshot(manifest.dataset_id, snapshot_id)
    if snapshot_id != manifest.observed_until:
        return {
            **scope.metadata("computed", METHOD),
            "snapshot_id": snapshot_id,
            "status": "not_evaluated",
            "scored_at": None,
            "training_snapshot_ids": [],
            "accounts": [],
            "unscored_accounts": [],
            "message": "This snapshot has not been evaluated. Anomaly scores are available for S12.",
        }
    try:
        _, training = prepare_training(repository, manifest)
        model, state, artifact = load_artifact(
            models_dir, manifest.dataset_id, training
        )
        meta = next(
            meta for meta in manifest.snapshots if meta.snapshot_id == snapshot_id
        )
        events = snapshot_events(frame, meta, training["origin_time"])
        if seconds(meta.starts_at, training["origin_time"]) < seconds(
            training["ends_at"], training["origin_time"]
        ):
            raise ValueError("The scoring window overlaps the training range.")
        model.replay(state, events)
        accounts, unscored = model.score(
            state,
            frame.present_accounts,
            seconds(meta.ends_at, training["origin_time"]),
        )
    except ModelConflict as error:
        raise HTTPException(409, str(error)) from error
    except ModelNotReady as error:
        raise HTTPException(503, str(error)) from error
    except ModelUnavailable as error:
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {
        **scope.metadata("computed", METHOD),
        "snapshot_id": snapshot_id,
        "status": "ok",
        "model_version": artifact["model_version"],
        "scored_at": meta.ends_at,
        "training_snapshot_ids": training["snapshot_ids"],
        "accounts": accounts[:request.top_r],
        "unscored_accounts": unscored,
        "message": "" if accounts else "No nodes have interaction history to score.",
    }
