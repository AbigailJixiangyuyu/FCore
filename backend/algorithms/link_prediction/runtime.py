"""Reproducible GPU training for link prediction."""

import random

import numpy as np
import torch

from algorithms.runtime import ModelUnavailable, cuda_device


# Keep existing Zebra callers and tests compatible.
ZebraUnavailable = ModelUnavailable


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def runtime_info(model_name: str = "Zebra") -> dict:
    device = cuda_device(model_name)
    return {
        "device": str(device), "torch_version": str(torch.__version__),
        "cuda_version": torch.version.cuda, "gpu_name": torch.cuda.get_device_name(device),
        "numpy_version": np.__version__, "deterministic": True,
    }
