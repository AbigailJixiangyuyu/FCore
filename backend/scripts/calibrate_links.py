"""Fit and verify a history-aware probability layer for an existing model."""

import argparse
import json

import torch

from algorithms.link_prediction.adapters import MODELS
from algorithms.link_prediction.calibration import fit_probability_calibration, link_probabilities
from algorithms.link_prediction.data import prepare_history, read_window
from algorithms.link_prediction.evaluation import backtest
from app.core.config import Settings
from app.repositories.datasets import DatasetRepository


def calibrate_model(model_id, settings, repository, manifest, history, metadata) -> dict:
    adapter = MODELS[model_id]
    artifacts = adapter.artifacts
    models_dir, dataset_id = settings.models_dir, manifest.dataset_id
    model, state, temperature, base = artifacts.load_artifact(models_dir, dataset_id, metadata)
    if base.get("probability_calibration"):
        return {"model": model_id, "model_version": base["model_version"], "status": "already_calibrated"}

    calibration = fit_probability_calibration(adapter, model, history)
    if calibration is None:
        raise ValueError(f"{adapter.name} 校准窗口需要同时包含连边与未连边样本")

    cutoff_meta = next(meta for meta in manifest.snapshots if meta.snapshot_id == manifest.observed_until)
    observed = read_window(repository, manifest, cutoff_meta, metadata["origin_timestamp"])
    original = backtest(model, state, history, observed, temperature, model_name=model_id)
    calibrated = backtest(
        model, state, history, observed, temperature, model_name=model_id,
        probability_calibration=calibration,
    )
    original_metrics = original[model_id]
    calibrated_metrics = calibrated[model_id]
    if any(calibrated_metrics[key] >= original_metrics[key] for key in ("brier", "log_loss")):
        raise RuntimeError(f"{adapter.name} 历史校准未同时改善回测的 Brier 分数和对数损失")

    report = {
        **base["report"],
        "probability_calibration_source": base["model_version"],
        "probability_calibration_backtest": calibrated,
    }
    updated = artifacts.save_artifact(
        models_dir, model, state, temperature, metadata, report,
        probability_calibration=calibration,
    )
    restored, warmup, restored_temperature, restored_artifact = artifacts.load_artifact(
        models_dir, dataset_id, metadata, updated["model_version"],
    )
    with torch.inference_mode():
        adapter.advance(model, state, observed)
        adapter.advance(restored, warmup, observed)
        pairs, logits = model.all_pairs(state, observed.end)
        restored_pairs, restored_logits = restored.all_pairs(warmup, observed.end)
        if pairs != restored_pairs:
            raise RuntimeError(f"{adapter.name} 模型恢复后的顶点对不一致")
        torch.testing.assert_close(logits, restored_logits, rtol=0, atol=0)
        expected = link_probabilities(pairs, logits, (*history, observed), temperature, calibration)
        probabilities = link_probabilities(
            restored_pairs, restored_logits, (*history, observed), restored_temperature,
            restored_artifact["probability_calibration"],
        )
        torch.testing.assert_close(expected, probabilities, rtol=0, atol=0)
    artifacts.activate_artifact(models_dir, dataset_id, updated)
    return {
        "model": model_id,
        "model_version": updated["model_version"],
        "source_model_version": base["model_version"],
        "calibration_target": calibration["target_snapshot_id"],
        "backtest_original": original_metrics,
        "backtest_calibrated": calibrated_metrics,
        "prediction_max": probabilities.max().item(),
        "prediction_edges_above_half": int((probabilities > 0.5).sum().item()),
    }


def main():
    parser = argparse.ArgumentParser(description="用 S11 校准已有链接模型，验证至 S12")
    parser.add_argument("--dataset", default="email-eu-core-dept3")
    parser.add_argument("--model", choices=MODELS, action="append")
    args = parser.parse_args()
    settings = Settings()
    repository = DatasetRepository(settings.data_dir)
    _, manifest = repository.locate(args.dataset)
    history, metadata = prepare_history(repository, manifest)
    for model_id in args.model or MODELS:
        report = calibrate_model(model_id, settings, repository, manifest, history, metadata)
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
