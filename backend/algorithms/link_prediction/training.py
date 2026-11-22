"""Causal window supervision; S12 backtesting is a separate, frozen operation."""

import math

import numpy as np
import torch
from torch.nn import functional as F

from .evaluation import calibrate, evaluate, target_tensors
from .model import Zebra, ZebraConfig
from .runtime import cuda_device, seed_everything


@torch.no_grad()
def replay(model: Zebra, windows):
    state = model.initial_state()
    for window in windows:
        model.advance(state, window.events)
    return state


def train(windows, config: ZebraConfig = ZebraConfig(), progress=None):
    if len(windows) != 11 or config.epochs < 1 or config.patience < 1:
        raise ValueError("Training requires 11 historical windows and positive epochs/patience")
    device = cuda_device()
    seed_everything(config.seed)
    model = Zebra(config).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    best_loss, best_epoch, best_weights, stale = math.inf, 0, None, 0
    curve = []
    sample_counts = []
    for epoch in range(1, config.epochs + 1):
        model.train()
        state = model.initial_state()
        losses, counts = [], []
        for index in range(8):
            model.advance(state, windows[index].events)
            pairs, logits = model.all_pairs(state, windows[index].end)
            labels = target_tensors(pairs, windows[index + 1], device)
            if not pairs:
                state.memory = state.memory.detach()
                continue
            optimizer.zero_grad(set_to_none=True)
            loss = F.binary_cross_entropy_with_logits(logits, labels)
            if not torch.isfinite(loss):
                raise RuntimeError("Zebra training produced a non-finite loss")
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise RuntimeError("Zebra training produced non-finite gradients")
            optimizer.step()
            state.memory = state.memory.detach()
            losses.append(float(loss.detach()))
            counts.append(len(pairs))
            if epoch == 1:
                sample_counts.append({"input_cutoff": windows[index].snapshot_id, "target": windows[index + 1].snapshot_id, "pairs": len(pairs), "positives": int(labels.sum())})
        if not counts:
            raise ValueError("No eligible historical training pairs")
        model.eval()
        validation_state = replay(model, windows[:9])
        validation = evaluate(model, validation_state, windows[8].end, windows[9])
        value = validation["log_loss"]
        if value is None or not math.isfinite(value):
            raise ValueError("No finite validation loss")
        row = {"epoch": epoch, "training_loss": float(np.average(losses, weights=counts)), "validation": validation}
        curve.append(row)
        if progress:
            progress(row)
        if value < best_loss:
            best_loss, best_epoch, stale = value, epoch, 0
            best_weights = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
        else:
            stale += 1
        if stale >= config.patience:
            break
    model.load_state_dict(best_weights)
    model.eval()
    state = replay(model, windows[:10])
    with torch.no_grad():
        pairs, logits = model.all_pairs(state, windows[9].end)
    temperature, calibration = calibrate(logits, target_tensors(pairs, windows[10], device))
    calibrated_metrics = evaluate(model, state, windows[9].end, windows[10], temperature)
    with torch.no_grad():
        model.advance(state, windows[10].events)
    report = {
        "best_epoch": best_epoch, "epochs_completed": len(curve), "curve": curve,
        "training_samples": sample_counts, "calibration": calibration,
        "calibration_metrics": calibrated_metrics, "validation_loss": best_loss,
        "protocol": "train targets S02-S09; select S10; calibrate S11; frozen backtest S12; predict S13",
    }
    return model, state, temperature, report
