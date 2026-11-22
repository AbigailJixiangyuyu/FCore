"""Train Zebra on historical windows, backtest S12, verify, then activate."""

import argparse
import json
from time import perf_counter

import torch

from algorithms.link_prediction.adapters import ZEBRA
from algorithms.link_prediction.artifacts import (
    activate_artifact,
    load_artifact,
    save_artifact,
)
from algorithms.link_prediction.calibration import fit_probability_calibration, link_probabilities
from algorithms.link_prediction.data import MAX_FORECAST_HORIZON, prepare_history, read_window
from algorithms.link_prediction.evaluation import backtest
from algorithms.link_prediction.forecast_training import fit_forecast_head
from algorithms.link_prediction.model import ZebraConfig
from algorithms.link_prediction.runtime import runtime_info
from algorithms.link_prediction.training import replay, train
from app.core.config import Settings
from app.repositories.datasets import DatasetRepository


def main():
    parser = argparse.ArgumentParser(description="Train and calibrate Zebra on the GPU, with S12 held out for evaluation.")
    parser.add_argument("--dataset", default="email-eu-core-dept3")
    parser.add_argument("--horizon", type=int, choices=range(1, MAX_FORECAST_HORIZON + 1), default=1)
    arguments = parser.parse_args()
    horizon = arguments.horizon
    settings = Settings()
    repository = DatasetRepository(settings.data_dir)
    _, manifest = repository.locate(arguments.dataset)
    windows, metadata = prepare_history(repository, manifest)
    runtime = runtime_info()
    print(json.dumps(runtime, ensure_ascii=False), flush=True)
    torch.cuda.reset_peak_memory_stats()
    started = perf_counter()

    def progress(row):
        print(json.dumps(row, ensure_ascii=False), flush=True)

    probability_calibration = None
    if horizon == 1:
        model, state, temperature, report = train(windows, ZebraConfig(), progress)
    else:
        model, _, _, base = load_artifact(settings.models_dir, manifest.dataset_id, metadata)
        state, temperature, report = fit_forecast_head(model, windows, horizon, progress)
        report["source_model_version"] = base["model_version"]
        probability_calibration = fit_probability_calibration(ZEBRA, model, windows, horizon=horizon)
    torch.cuda.synchronize()
    report.update(runtime)
    report["training_seconds"] = round(perf_counter() - started, 3)
    report["peak_memory_mib"] = round(torch.cuda.max_memory_allocated() / 1024**2, 2)
    # S12 is opened only after training, model selection and calibration finish.
    current_meta = next(m for m in manifest.snapshots if m.snapshot_id == manifest.observed_until)
    current = read_window(repository, manifest, current_meta, metadata["origin_timestamp"])
    backtest_history = windows[:len(windows) + 1 - horizon]
    backtest_state = state if horizon == 1 else replay(model, backtest_history)
    report["backtest_input_cutoff"] = backtest_history[-1].snapshot_id
    report["backtest"] = backtest(
        model, backtest_state, backtest_history, current, temperature,
        probability_calibration=probability_calibration,
    )
    artifact = save_artifact(
        settings.models_dir, model, state, temperature, metadata, report,
        probability_calibration=probability_calibration, horizon=horizon,
    )
    restored, restored_state, restored_temperature, restored_artifact = load_artifact(
        settings.models_dir, manifest.dataset_id, metadata, artifact["model_version"],
        horizon=horizon,
    )
    torch.testing.assert_close(state.memory, restored_state.memory, rtol=0, atol=0)
    assert state.tppr.payload() == restored_state.tppr.payload()
    with torch.no_grad():
        model.advance(state, current.events)
        restored.advance(restored_state, current.events)
        expected_pairs, expected_logits = model.all_pairs(state, current.end)
        actual_pairs, actual_logits = restored.all_pairs(restored_state, current.end)
        assert expected_pairs == actual_pairs and temperature == restored_temperature
        torch.testing.assert_close(expected_logits, actual_logits, rtol=0, atol=0)
        observed = (*windows, current)
        expected_probabilities = link_probabilities(
            expected_pairs, expected_logits, observed, temperature, probability_calibration,
        )
        actual_probabilities = link_probabilities(
            actual_pairs, actual_logits, observed, restored_temperature,
            restored_artifact.get("probability_calibration"),
        )
        torch.testing.assert_close(expected_probabilities, actual_probabilities, rtol=0, atol=0)
    if model.device.type != "cuda" or state.memory.device.type != "cuda":
        raise RuntimeError("Zebra model and memory must be on GPU")
    activate_artifact(settings.models_dir, manifest.dataset_id, artifact, horizon=horizon)
    print(json.dumps({
        "model_version": artifact["model_version"], "best_epoch": report["best_epoch"],
        "forecast_horizon": horizon, "backtest_input_cutoff": report["backtest_input_cutoff"],
        "training_seconds": report["training_seconds"], "temperature": temperature,
        "backtest": report["backtest"], "reload_equal": True,
        "prediction_pair_count": len(actual_pairs), "scored_account_count": len(state.known_accounts()),
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
