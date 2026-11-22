"""Train longer-horizon Zebra decoders on embeddings from the frozen encoder."""

from dataclasses import dataclass
from itertools import combinations
from math import inf, isfinite

import torch
from torch.nn import functional as F

from .data import MAX_FORECAST_HORIZON
from .evaluation import calibrate, target_tensors
from .model import Zebra


@dataclass(frozen=True)
class Example:
    cutoff: str
    target: str
    embeddings: torch.Tensor
    pairs: list[tuple[str, str]]
    labels: torch.Tensor


@torch.no_grad()
def _examples(model, windows, horizon):
    state = model.initial_state()
    examples = []
    for window, target in zip(windows, windows[horizon:]):
        model.advance(state, window.events)
        pairs = list(combinations(state.known_accounts(), 2))
        examples.append(Example(
            window.snapshot_id,
            target.snapshot_id,
            model.encode(state, window.end),
            pairs,
            target_tensors(pairs, target, model.device),
        ))
    return state, examples


def fit_forecast_head(model: Zebra, windows, horizon: int, progress=None):
    if len(windows) != 11 or not 2 <= horizon <= MAX_FORECAST_HORIZON:
        raise ValueError("Training a longer forecast requires 11 historical snapshots and horizon 2 or 3")
    model.eval().requires_grad_(False)
    model.decoder.requires_grad_(True)
    state, examples = _examples(model, windows, horizon)
    training = [example for example in examples[:-2] if example.pairs]
    validation, calibration = examples[-2:]
    if not training or not validation.pairs or not calibration.pairs:
        raise ValueError("This forecast horizon has too few historical pairs to train and calibrate")

    # Account indices are append-only. The final mapping also indexes the earlier embeddings.
    def logits(example):
        return model.pair_logits(example.embeddings, state, example.pairs)

    optimizer = torch.optim.Adam(model.decoder.parameters(), lr=model.config.learning_rate)
    best_loss, best_epoch, best_weights = inf, 0, None
    curve = []
    pair_count = sum(len(example.pairs) for example in training)
    for epoch in range(1, model.config.epochs + 1):
        loss_sum = 0.0
        for example in training:
            optimizer.zero_grad(set_to_none=True)
            loss = F.binary_cross_entropy_with_logits(logits(example), example.labels)
            if not torch.isfinite(loss):
                raise RuntimeError("Zebra forecast training produced a non-finite loss")
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.detach()) * len(example.pairs)
        with torch.no_grad():
            validation_loss = F.binary_cross_entropy_with_logits(logits(validation), validation.labels).item()
        if not isfinite(validation_loss):
            raise RuntimeError("Zebra forecast validation produced a non-finite loss")
        row = {"epoch": epoch, "training_loss": loss_sum / pair_count, "validation_loss": validation_loss}
        curve.append(row)
        if progress:
            progress(row)
        if validation_loss < best_loss:
            best_loss, best_epoch = validation_loss, epoch
            best_weights = {name: value.detach().clone() for name, value in model.decoder.state_dict().items()}
        elif epoch - best_epoch >= model.config.patience:
            break

    model.decoder.load_state_dict(best_weights)
    with torch.no_grad():
        calibration_logits = logits(calibration)
        for window in windows[-horizon:]:
            model.advance(state, window.events)
    temperature, temperature_report = calibrate(calibration_logits, calibration.labels)
    return state, temperature, {
        "forecast_horizon": horizon,
        "best_epoch": best_epoch,
        "epochs_completed": len(curve),
        "curve": curve,
        "validation_loss": best_loss,
        "validation_input_cutoff": validation.cutoff,
        "validation_target": validation.target,
        "calibration_input_cutoff": calibration.cutoff,
        "calibration_target": calibration.target,
        "calibration": temperature_report,
        "training_samples": [
            {"input_cutoff": example.cutoff, "target": example.target,
             "pairs": len(example.pairs), "positives": int(example.labels.sum())}
            for example in training
        ],
    }
