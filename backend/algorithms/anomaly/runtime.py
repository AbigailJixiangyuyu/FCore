"""CUDA is required by training and serving; never silently fall back to CPU."""

import os

# Must be configured before the first cuBLAS operation, including API inference.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch


class CudaUnavailable(RuntimeError):
    pass


def cuda_device() -> torch.device:
    if not torch.cuda.is_available():
        raise CudaUnavailable(
            "SLADE 需要 cuda:0，但当前环境无法使用 CUDA；请使用项目的 GPU 虚拟环境并检查显卡驱动"
        )
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return torch.device("cuda:0")


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
