"""Zebra checkpoint restoration and model-specific validation."""

import pickle

import torch

from algorithms.runtime import inference_device

from .checkpoint import CheckpointStore
from .data import MAX_FORECAST_HORIZON
from .model import METHOD, Zebra, ZebraConfig, ZebraState
from .runtime import ZebraUnavailable

_STORES = {
    horizon: CheckpointStore(
        "zebra", "Zebra", METHOD,
        pointer_filename="current.json" if horizon == 1 else f"current-h{horizon}.json",
    )
    for horizon in range(1, MAX_FORECAST_HORIZON + 1)
}


def _forecast_metadata(metadata, horizon):
    if horizon == 1:
        return metadata
    snapshot_ids = metadata["history_snapshot_ids"]
    validation_index = snapshot_ids.index(metadata["validation_snapshot_id"])
    return {
        **metadata,
        "forecast_horizon": horizon,
        "task": "undirected-target-snapshot-occurrence",
        "training_target_snapshot_ids": snapshot_ids[horizon:validation_index],
    }


def save_artifact(
    models_dir, model, state, temperature, metadata, report, *, probability_calibration=None, horizon=1,
):
    return _STORES[horizon].save(
        models_dir, model, state, temperature, _forecast_metadata(metadata, horizon), report,
        probability_calibration=probability_calibration,
    )


def read_artifact(models_dir, dataset_id, expected, version=None, *, horizon=1):
    try:
        return _STORES[horizon].read(models_dir, dataset_id, _forecast_metadata(expected, horizon), version)
    except ZebraUnavailable as error:
        if horizon == 1:
            raise
        raise ZebraUnavailable(f"The Zebra model for a {horizon}-snapshot forecast is missing or corrupt.") from error


def activate_artifact(models_dir, dataset_id, artifact, *, horizon=1):
    if artifact["metadata"].get("forecast_horizon", 1) != horizon:
        raise ValueError("The Zebra artifact does not match the forecast horizon")
    _STORES[horizon].activate(models_dir, dataset_id, artifact)


def load_artifact(models_dir, dataset_id, expected, version=None, *, horizon=1):
    directory, artifact = read_artifact(models_dir, dataset_id, expected, version, horizon=horizon)
    device = inference_device("Zebra")
    try:
        config_values = dict(artifact["config"])
        config_values["metrics"] = tuple(tuple(item) for item in config_values["metrics"])
        config = ZebraConfig(**config_values)
        payload = torch.load(directory / "checkpoint.pt", map_location="cpu", weights_only=True)
        model = Zebra(config).to(device)
        model.load_state_dict(payload["weights"])
        model.eval()
        state = ZebraState.restore(payload["state"], config, device)
        temperature = float(payload["temperature"])
        if not 0.05 <= temperature <= 10 or temperature != artifact["temperature"]:
            raise ValueError("Invalid calibration temperature")
        if payload.get("probability_calibration") != artifact.get("probability_calibration"):
            raise ValueError("Probability calibration does not match the checkpoint")
        if any(not torch.isfinite(p).all() for p in model.parameters()):
            raise ValueError("Non-finite model weights")
        return model, state, temperature, artifact
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, EOFError, pickle.UnpicklingError, IndexError) as error:
        raise ZebraUnavailable("Could not load the Zebra weights or warm-up state. Retrain Zebra and try again.") from error
