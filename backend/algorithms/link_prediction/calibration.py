"""Calibrate frozen link logits using each pair's recent interaction history."""

import math
from collections import Counter

import torch
import torch.nn.functional as F

from .data import labels_for

METHOD = "recent-pair-logistic-v1"
_FEATURE_COUNT = 4


def _pair_features(pairs, logits, observed_windows):
    counts = [
        Counter(
            tuple(sorted((event.u, event.v)))
            for event in window.events if event.u != event.v
        )
        for window in observed_windows[-3:]
    ]
    rows = []
    for pair in pairs:
        occurrences = [snapshot[pair] for snapshot in counts]
        rows.append([
            int(occurrences[-1] > 0),
            sum(count > 0 for count in occurrences),
            math.log1p(sum(occurrences)),
        ])
    interaction_features = logits.new_tensor(rows, dtype=torch.float64).reshape(-1, 3)
    return torch.column_stack((logits.double(), interaction_features))


def fit_probability_calibration(adapter, model, history, *, horizon=1) -> dict | None:
    """Fit on S11 labels using history through the cutoff for this horizon."""
    observed, target = history[:-horizon], history[-1]
    with torch.no_grad():
        state = model.initial_state()
        for window in observed:
            adapter.advance(model, state, window)
        pairs, logits = model.all_pairs(state, observed[-1].end)
        labels = logits.new_tensor(labels_for(pairs, target), dtype=torch.float64)
        if labels.unique().numel() < 2:
            return None
        features = _pair_features(pairs, logits, observed)
        center = features.mean(dim=0)
        scale = features.std(dim=0, correction=0).clamp_min(1e-6)
        normalized = (features - center) / scale

    coefficients = logits.new_zeros(_FEATURE_COUNT, dtype=torch.float64, requires_grad=True)
    intercept = labels.mean().logit().requires_grad_()
    optimizer = torch.optim.LBFGS([coefficients, intercept], max_iter=80, line_search_fn="strong_wolfe")

    def closure():
        optimizer.zero_grad()
        loss = F.binary_cross_entropy_with_logits(normalized @ coefficients + intercept, labels)
        loss = loss + 0.001 * coefficients.square().sum()
        loss.backward()
        return loss

    optimizer.step(closure)
    calibration = {
        "method": METHOD,
        "target_snapshot_id": target.snapshot_id,
        "center": center.tolist(),
        "scale": scale.tolist(),
        "coefficients": coefficients.detach().tolist(),
        "intercept": intercept.detach().item(),
    }
    validate_calibration(calibration, target.snapshot_id)
    return calibration


def validate_calibration(calibration, target_snapshot_id: str) -> None:
    if calibration["method"] != METHOD or calibration["target_snapshot_id"] != target_snapshot_id:
        raise ValueError("Invalid probability calibration method or target")
    values = torch.tensor([calibration[key] for key in ("center", "scale", "coefficients")], dtype=torch.float64)
    if (
        values.shape != (3, _FEATURE_COUNT)
        or not torch.isfinite(values).all()
        or not (values[1] > 0).all()
        or not math.isfinite(calibration["intercept"])
    ):
        raise ValueError("Invalid probability calibration coefficients")


def link_probabilities(pairs, logits, observed_windows, temperature, calibration=None) -> torch.Tensor:
    if calibration is None:
        return torch.sigmoid(logits / temperature)
    features = _pair_features(pairs, logits, observed_windows)
    center, scale, coefficients = (
        features.new_tensor(calibration[key]) for key in ("center", "scale", "coefficients")
    )
    calibrated_logits = ((features - center) / scale) @ coefficients + calibration["intercept"]
    return torch.sigmoid(calibrated_logits)
