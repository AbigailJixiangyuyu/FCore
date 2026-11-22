"""Use the existing CUDA environment, without dependency installation/fallback."""

import os
import random

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import numpy as np
import torch


class ModelUnavailable(RuntimeError):
    pass


# Keep existing Zebra callers and tests compatible.
ZebraUnavailable = ModelUnavailable


def cuda_device(model_name: str = "Zebra") -> torch.device:
    if not torch.cuda.is_available():
        raise ModelUnavailable(f"{model_name} 需要 cuda:0；请使用当前 GPU 虚拟环境并检查显卡驱动")
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return torch.device("cuda:0")


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
