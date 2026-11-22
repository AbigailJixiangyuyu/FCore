"""Zebra checkpoint restoration and model-specific validation."""

import pickle

import torch

from .checkpoint import CheckpointStore
from .model import METHOD, Zebra, ZebraConfig, ZebraState
from .runtime import ZebraUnavailable, cuda_device

_STORE = CheckpointStore("zebra", "Zebra", METHOD)
save_artifact = _STORE.save
read_artifact = _STORE.read
activate_artifact = _STORE.activate


def load_artifact(models_dir, dataset_id, expected, version=None):
    directory, artifact = read_artifact(models_dir, dataset_id, expected, version)
    device = cuda_device()
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
        raise ZebraUnavailable("Zebra 权重或预热状态加载失败，请重新训练后重试") from error
