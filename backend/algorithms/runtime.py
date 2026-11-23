"""Device selection for serving trained models and for explicit GPU training."""

import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch


class ModelUnavailable(RuntimeError):
    pass


def cuda_device(model_name: str = "Zebra") -> torch.device:
    if not torch.cuda.is_available():
        raise ModelUnavailable(
            f"{model_name} requires CUDA on the selected device. "
            "Use FCORE_DEVICE=cpu for CPU inference or check the GPU driver."
        )
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return torch.device("cuda:0")


def inference_device(model_name: str) -> torch.device:
    device = os.environ.get("FCORE_DEVICE", "cuda:0").strip().lower()
    if device == "cpu":
        torch.use_deterministic_algorithms(True)
        return torch.device("cpu")
    if device in ("cuda", "cuda:0"):
        return cuda_device(model_name)
    raise ModelUnavailable(f"Unknown FCORE_DEVICE {device!r}. Choose cpu or cuda:0.")
