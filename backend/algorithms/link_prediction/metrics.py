"""Tie-aware binary metrics, using NumPy already present in the project."""

import numpy as np


def binary_metrics(labels, probabilities) -> dict:
    y = np.asarray(labels, dtype=np.float64)
    p = np.asarray(probabilities, dtype=np.float64)
    if len(y) != len(p) or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("Invalid binary predictions")
    if not len(y):
        return {"pairs": 0, "positives": 0, "ap": None, "roc_auc": None, "brier": None, "log_loss": None}
    positive, negative = int(y.sum()), int(len(y) - y.sum())
    order = np.argsort(-p, kind="stable")
    ordered_y, ordered_p = y[order], p[order]
    ends = np.r_[np.flatnonzero(np.diff(ordered_p)), len(y) - 1]
    tp = np.cumsum(ordered_y)[ends]
    fp = (ends + 1) - tp
    ap = float(np.sum(np.diff(np.r_[0, tp]) * tp / (ends + 1)) / positive) if positive else None
    auc = None
    if positive and negative:
        tpr, fpr = np.r_[0, tp / positive], np.r_[0, fp / negative]
        auc = float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2))
    bounded = np.clip(p, 1e-12, 1 - 1e-12)
    return {
        "pairs": len(y), "positives": positive, "prevalence": positive / len(y),
        "ap": ap, "roc_auc": auc, "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(bounded) + (1 - y) * np.log1p(-bounded))),
    }
