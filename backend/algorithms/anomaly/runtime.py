"""SLADE GPU training configuration and provenance."""

import torch

from algorithms.runtime import ModelUnavailable, cuda_device as training_cuda_device

# Existing SLADE callers can keep catching the original CUDA exception name.
CudaUnavailable = ModelUnavailable


def cuda_device() -> torch.device:
    return training_cuda_device("SLADE")


def runtime_info() -> dict:
    device = cuda_device()
    return {
        "device": str(device),
        "torch_version": str(torch.__version__),
        "cuda_version": torch.version.cuda,
        "gpu_name": torch.cuda.get_device_name(device),
        "gpu_capability": list(torch.cuda.get_device_capability(device)),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
    }
