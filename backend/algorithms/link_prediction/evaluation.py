"""Window labels, calibration and frozen backtesting shared by Zebra and UnderGS."""

import math

import torch
from torch.nn import functional as F

from .calibration import link_probabilities
from .data import labels_for, positive_pairs
from .metrics import binary_metrics


def target_tensors(pairs, window, device):
    return torch.tensor(labels_for(pairs, window), device=device, dtype=torch.float32)


@torch.no_grad()
def evaluate(model, state, cutoff: float, target, temperature: float = 1.0) -> dict:
    pairs, logits = model.all_pairs(state, cutoff)
    probabilities = torch.sigmoid(logits / temperature).cpu().tolist()
    return binary_metrics(labels_for(pairs, target), probabilities)


def calibrate(logits: torch.Tensor, labels: torch.Tensor) -> tuple[float, dict]:
    logits, labels = logits.detach(), labels.detach()
    if not len(labels) or len(torch.unique(labels)) < 2:
        return 1.0, {"status": "insufficient_classes", "temperature": 1.0}
    original = F.binary_cross_entropy_with_logits(logits, labels).item()
    log_temperature = torch.zeros((), device=logits.device, requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], max_iter=50, line_search_fn="strong_wolfe")

    def closure():
        optimizer.zero_grad()
        temperature = log_temperature.exp().clamp(0.05, 10)
        loss = F.binary_cross_entropy_with_logits(logits / temperature, labels)
        loss.backward()
        return loss

    optimizer.step(closure)
    temperature = float(log_temperature.detach().exp().clamp(0.05, 10))
    calibrated = F.binary_cross_entropy_with_logits(logits / temperature, labels).item()
    if not math.isfinite(calibrated) or calibrated > original:
        temperature, calibrated = 1.0, original
    return temperature, {"status": "fitted", "temperature": temperature, "before_log_loss": original, "after_log_loss": calibrated}


@torch.no_grad()
def backtest(model, state, history, target, temperature, model_name="zebra", *, probability_calibration=None):
    pairs, logits = model.all_pairs(state, history[-1].end)
    labels = labels_for(pairs, target)
    probabilities = link_probabilities(pairs, logits, history, temperature, probability_calibration).cpu().tolist()
    recent = positive_pairs(history[-1])
    last_three = [positive_pairs(window) for window in history[-3:]]
    recent_probs = [float(pair in recent) for pair in pairs]
    frequency_probs = [sum(pair in edges for edges in last_three) / len(last_three) for pair in pairs]
    known = set(state.known_accounts())
    target_edges = positive_pairs(target)
    excluded = [pair for pair in target_edges if not set(pair) <= known]
    subsets = {}
    for name, flag in (("existing_at_cutoff", True), ("absent_at_cutoff", False)):
        indices = [i for i, pair in enumerate(pairs) if (pair in recent) == flag]
        subsets[name] = binary_metrics([labels[i] for i in indices], [probabilities[i] for i in indices])
    return {
        "target_snapshot_id": target.snapshot_id, model_name: binary_metrics(labels, probabilities),
        "recent_snapshot": binary_metrics(labels, recent_probs),
        "last_three_frequency": binary_metrics(labels, frequency_probs),
        "subsets": subsets, "unseen_endpoint_positive_pairs": len(excluded),
        "target_used_for_parameter_updates": False,
    }
