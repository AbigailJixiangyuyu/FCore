"""Disk format shared by the two next-window models."""

import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

import torch

from .calibration import validate_calibration
from .runtime import ModelUnavailable


class ModelConflict(RuntimeError):
    pass


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(path)


@dataclass(frozen=True, slots=True)
class CheckpointStore:
    model_id: str
    name: str
    method: str
    version_includes_method: bool = False
    pointer_filename: str = "current.json"

    def model_root(self, models_dir: Path, dataset_id: str) -> Path:
        return models_dir / dataset_id / self.model_id

    def save(self, models_dir, model, state, temperature, metadata, report, *, probability_calibration=None) -> dict:
        config = model.config.payload()
        checkpoint = {
            "weights": {key: tensor.detach().cpu() for key, tensor in model.state_dict().items()},
            "state": state.payload(),
            "temperature": temperature,
        }
        if probability_calibration is not None:
            validate_calibration(probability_calibration, metadata["calibration_snapshot_id"])
            checkpoint["probability_calibration"] = probability_calibration
        buffer = io.BytesIO()
        torch.save(checkpoint, buffer)
        content = buffer.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        identity = {"checkpoint": digest, "metadata": metadata, "config": config}
        # UnderGS includes its method in the version; Zebra's existing identity does not.
        if self.version_includes_method:
            identity["method"] = self.method
        signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        version = f"{self.model_id}-{signature[:16]}"
        directory = self.model_root(models_dir, metadata["dataset_id"]) / version
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "checkpoint.pt").write_bytes(content)
        artifact = {
            "model_version": version,
            "method": self.method,
            "checkpoint_sha256": digest,
            "config": config,
            "metadata": metadata,
            "report": report,
            "temperature": temperature,
        }
        if probability_calibration is not None:
            artifact["probability_calibration"] = probability_calibration
        _atomic_json(directory / "manifest.json", artifact)
        return artifact

    def read(self, models_dir, dataset_id, expected, version=None) -> tuple[Path, dict]:
        root = self.model_root(models_dir, dataset_id)
        try:
            if version is None:
                pointer = json.loads((root / self.pointer_filename).read_text(encoding="utf-8"))
                version = pointer["model_version"]
            if not isinstance(version, str) or not re.fullmatch(
                rf"{re.escape(self.model_id)}-[0-9a-f]{{16}}", version
            ):
                raise ValueError(f"Invalid {self.name} model version")
            directory = root / version
            artifact = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            if artifact["model_version"] != version or artifact["method"] != self.method:
                raise ValueError(f"Invalid {self.name} manifest")
            if artifact["metadata"] != expected:
                raise ModelConflict(
                    f"The dataset version, interaction history, or snapshot configuration does not match the {self.name} model. Retrain the model."
                )
            calibration = artifact.get("probability_calibration")
            if calibration is not None:
                validate_calibration(calibration, expected["calibration_snapshot_id"])
            content = (directory / "checkpoint.pt").read_bytes()
            if hashlib.sha256(content).hexdigest() != artifact["checkpoint_sha256"]:
                raise ValueError("Checkpoint checksum mismatch")
            return directory, artifact
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ModelUnavailable(
                f"The {self.name} model is missing or corrupt. Run scripts.train_{self.model_id} to prepare it."
            ) from error

    def activate(self, models_dir, dataset_id, artifact) -> None:
        _atomic_json(
            self.model_root(models_dir, dataset_id) / self.pointer_filename,
            {"model_version": artifact["model_version"]},
        )
