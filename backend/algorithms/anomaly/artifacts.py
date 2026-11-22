"""Versioned local weights and a fresh, private bootstrap state for each request."""

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict
from pathlib import Path

import torch

from .runtime import CudaUnavailable, cuda_device
from .slade import METHOD, Slade, SladeConfig
from .state import MemoryState


class ModelNotReady(ValueError):
    pass


class ModelConflict(ValueError):
    pass


def save_artifact(
    models_dir: Path,
    dataset_id: str,
    model: Slade,
    bootstrap: MemoryState,
    training: dict,
    report: dict,
    *,
    activate: bool = True,
) -> dict:
    directory = models_dir / dataset_id / "slade"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="training-", dir=directory) as temporary:
        checkpoint = Path(temporary) / "checkpoint.pt"
        with checkpoint.open("wb") as stream:
            torch.save(
                {
                    "method": METHOD,
                    "config": asdict(model.config),
                    "model_state": {
                        name: value.detach().cpu()
                        for name, value in model.state_dict().items()
                    },
                    "bootstrap": bootstrap.to_payload(),
                    "training": training,
                },
                stream,
            )
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        version = f"slade-{digest[:16]}"
        manifest = {
            "method": METHOD,
            "model_version": version,
            "checkpoint_sha256": digest,
            "config": asdict(model.config),
            "training": training,
            "report": report,
        }
        destination = directory / version
        destination.mkdir(exist_ok=True)
        os.replace(checkpoint, destination / "checkpoint.pt")
        manifest_path = Path(temporary) / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(manifest_path, destination / "manifest.json")
    if activate:
        activate_artifact(models_dir, dataset_id, manifest)
    return manifest


def activate_artifact(models_dir: Path, dataset_id: str, manifest: dict):
    directory = models_dir / dataset_id / "slade"
    with tempfile.TemporaryDirectory(prefix="activate-", dir=directory) as temporary:
        pointer = Path(temporary) / "current.json"
        pointer.write_text(
            json.dumps({"model_version": manifest["model_version"]}) + "\n",
            encoding="utf-8",
        )
        os.replace(pointer, directory / "current.json")


def load_artifact(
    models_dir: Path,
    dataset_id: str,
    expected_training: dict,
    *,
    model_version: str | None = None,
):
    directory = models_dir / dataset_id / "slade"
    try:
        version = model_version
        if version is None:
            pointer = json.loads(
                (directory / "current.json").read_text(encoding="utf-8")
            )
            version = pointer["model_version"]
        if not isinstance(version, str) or not re.fullmatch(
            r"slade-[0-9a-f]{16}", version
        ):
            raise ValueError("Invalid model version format.")
        directory = directory / version
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        checkpoint = directory / "checkpoint.pt"
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if (
            manifest["method"] != METHOD
            or manifest["model_version"] != version
            or digest != manifest["checkpoint_sha256"]
            or version != f"slade-{digest[:16]}"
        ):
            raise ValueError("Model file checksum verification failed.")
        if manifest["training"] != expected_training:
            raise ModelConflict("The dataset version or interaction history does not match the SLADE model. Retrain SLADE.")
        payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if (
            payload["method"] != METHOD
            or payload["training"] != expected_training
            or payload["config"] != manifest["config"]
        ):
            raise ValueError("Model metadata does not match the weights.")
        device = cuda_device()
        model = Slade(SladeConfig(**payload["config"])).to(device)
        model.load_state_dict(payload["model_state"], strict=True)
        model.eval()
        state = MemoryState.from_payload(payload["bootstrap"], device)
        count, dimension = len(state.accounts), model.config.memory_dim
        if (
            len(set(state.accounts)) != count
            or state.memory.shape != (count, dimension)
            or state.previous.shape != (count, dimension)
            or state.last_update.shape != (count,)
            or state.seen.shape != (count,)
            or len(state.neighbors) != count
        ):
            raise ValueError("Invalid dimensions in the saved warm-up state.")
        tensors = [
            *model.state_dict().values(),
            state.memory,
            state.previous,
            state.last_update,
        ]
        if not all(torch.isfinite(tensor).all() for tensor in tensors):
            raise ValueError("The model or its warm-up state contains nonfinite values.")
        return model, state, manifest
    except (ModelConflict, CudaUnavailable):
        raise
    except Exception as error:
        raise ModelNotReady(
            "The SLADE model is missing or corrupt. Run scripts.train_slade to prepare it."
        ) from error
