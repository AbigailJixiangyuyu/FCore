"""Full-population next-window supervision with one update per snapshot."""

import math
from itertools import combinations

import numpy as np
import torch
from torch.nn import functional as F

from ..evaluation import calibrate, evaluate, target_tensors
from ..runtime import cuda_device, seed_everything
from .model import UnderGS, UnderGSConfig
from .tcns import prepare_snapshot


@torch.no_grad()
def replay(model, snapshots):
    state = model.initial_state()
    for snapshot in snapshots:
        model.advance_window(state, snapshot)
    return state


def backward_window(model, state, pairs, labels):
    """Accumulate a population-mean BCE; the caller steps only after all pairs."""
    total_loss = 0.0
    for start in range(0, len(pairs), model.config.batch_size):
        stop = min(start + model.config.batch_size, len(pairs))
        logits = model.pair_logits(state, pairs[start:stop])
        loss = F.binary_cross_entropy_with_logits(logits, labels[start:stop], reduction="sum") / len(pairs)
        if not torch.isfinite(loss):
            raise RuntimeError("UnderGS training produced a non-finite loss")
        loss.backward(retain_graph=stop < len(pairs))
        total_loss += float(loss.detach())
    return total_loss


def train(windows, config: UnderGSConfig = UnderGSConfig(), progress=None):
    if len(windows) != 11:
        raise ValueError("UnderGS training requires 11 historical windows")
    device = cuda_device("UnderGS")
    seed_everything(config.seed)
    snapshots = tuple(prepare_snapshot(w, config.path_decay, config.max_hops) for w in windows)
    model = UnderGS(config).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate, weight_decay=0)
    best_loss, best_epoch, best_weights, stale = math.inf, 0, None, 0
    curve, sample_counts, gradient_max = [], [], {}
    for epoch in range(1, config.epochs + 1):
        model.train()
        state = model.initial_state()
        losses, counts = [], []
        for index in range(8):
            model.advance_window(state, snapshots[index])
            pairs = list(combinations(state.known_accounts(), 2))
            if not pairs:
                state.detach()
                continue
            labels = target_tensors(pairs, windows[index + 1], device)
            optimizer.zero_grad(set_to_none=True)
            loss = backward_window(model, state, pairs, labels)
            for name, parameter in model.named_parameters():
                if parameter.grad is not None:
                    if not torch.isfinite(parameter.grad).all():
                        raise RuntimeError("UnderGS training produced non-finite gradients")
                    group = name.split(".")[0]
                    gradient_max[group] = max(gradient_max.get(group, 0.0), float(parameter.grad.abs().max()))
            optimizer.step()
            state.detach()
            losses.append(loss)
            counts.append(len(pairs))
            if epoch == 1:
                sample_counts.append({"input_cutoff": windows[index].snapshot_id, "target": windows[index + 1].snapshot_id, "pairs": len(pairs), "positives": int(labels.sum())})
        if not counts:
            raise ValueError("No eligible UnderGS training pairs")
        model.eval()
        validation_state = replay(model, snapshots[:9])
        validation = evaluate(model, validation_state, windows[8].end, windows[9])
        value = validation["log_loss"]
        if value is None or not math.isfinite(value):
            raise ValueError("No finite UnderGS validation loss")
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
    state = replay(model, snapshots[:10])
    with torch.no_grad():
        pairs, logits = model.all_pairs(state, windows[9].end)
    temperature, calibration = calibrate(logits, target_tensors(pairs, windows[10], device))
    calibrated_metrics = evaluate(model, state, windows[9].end, windows[10], temperature)
    with torch.no_grad():
        model.advance_window(state, snapshots[10])
    report = {
        "best_epoch": best_epoch, "epochs_completed": len(curve), "curve": curve,
        "training_samples": sample_counts, "calibration": calibration,
        "calibration_metrics": calibrated_metrics, "validation_loss": best_loss,
        "gradient_max_abs": gradient_max,
        "protocol": "train targets S02-S09; select S10; calibrate S11; frozen backtest S12; predict S13",
    }
    return model, state, temperature, report
