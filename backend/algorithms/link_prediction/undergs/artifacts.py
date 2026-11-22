"""UnderGS checkpoint restoration and model-specific validation."""

import pickle

import torch

from ..checkpoint import CheckpointStore
from ..runtime import ModelUnavailable, cuda_device
from .model import METHOD, UnderGS, UnderGSConfig, UnderGSState

_STORE = CheckpointStore("undergs", "UnderGS", METHOD, version_includes_method=True)
save_artifact = _STORE.save
read_artifact = _STORE.read
activate_artifact = _STORE.activate


def load_artifact(models_dir, dataset_id, expected, version=None):
    directory, artifact = read_artifact(models_dir, dataset_id, expected, version)
    device = cuda_device("UnderGS")
    try:
        config = UnderGSConfig(**artifact["config"])
        payload = torch.load(directory / "checkpoint.pt", map_location="cpu", weights_only=True)
        model = UnderGS(config).to(device)
        model.load_state_dict(payload["weights"])
        model.eval()
        state = UnderGSState.restore(payload["state"], config, device)
        temperature = float(payload["temperature"])
        if not 0.05 <= temperature <= 10 or temperature != artifact["temperature"]:
            raise ValueError("Invalid UnderGS temperature")
        if payload.get("probability_calibration") != artifact.get("probability_calibration"):
            raise ValueError("Probability calibration does not match the checkpoint")
        if state.last_end != expected["warmup_cutoff"] or state.snapshot_index != len(expected["history_snapshot_ids"]) - 1:
            raise ValueError("Invalid UnderGS warmup cutoff")
        if any(not torch.isfinite(value).all() for value in model.state_dict().values()):
            raise ValueError("Non-finite UnderGS weights")
        return model, state, temperature, artifact
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, EOFError, pickle.UnpicklingError, IndexError, AttributeError) as error:
        raise ModelUnavailable("UnderGS 权重或预热状态加载失败，请重新训练后重试") from error
