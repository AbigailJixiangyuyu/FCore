"""Train Zebra on historical windows, backtest S12, verify, then activate."""

import argparse
import json
from time import perf_counter

import torch

from algorithms.link_prediction.artifacts import (
    activate_artifact,
    load_artifact,
    save_artifact,
)
from algorithms.link_prediction.data import prepare_history, read_window
from algorithms.link_prediction.evaluation import backtest
from algorithms.link_prediction.model import ZebraConfig
from algorithms.link_prediction.runtime import runtime_info
from algorithms.link_prediction.training import train
from app.core.config import Settings
from app.repositories.datasets import DatasetRepository


def main():
    parser = argparse.ArgumentParser(description="GPU Zebra：训练、窗口校准与独立 S12 回测；不读取 S13")
    parser.add_argument("--dataset", default="email-eu-core-dept3")
    arguments = parser.parse_args()
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

    model, state, temperature, report = train(windows, ZebraConfig(), progress)
    torch.cuda.synchronize()
    report.update(runtime)
    report["training_seconds"] = round(perf_counter() - started, 3)
    report["peak_memory_mib"] = round(torch.cuda.max_memory_allocated() / 1024**2, 2)
    # S12 is opened only after training, model selection and calibration finish.
    current_meta = next(m for m in manifest.snapshots if m.snapshot_id == manifest.observed_until)
    current = read_window(repository, manifest, current_meta, metadata["origin_timestamp"])
    report["backtest"] = backtest(model, state, windows, current, temperature)
    artifact = save_artifact(settings.models_dir, model, state, temperature, metadata, report)
    restored, restored_state, restored_temperature, _ = load_artifact(
        settings.models_dir, manifest.dataset_id, metadata, artifact["model_version"],
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
    if model.device.type != "cuda" or state.memory.device.type != "cuda":
        raise RuntimeError("Zebra model and memory must be on GPU")
    activate_artifact(settings.models_dir, manifest.dataset_id, artifact)
    print(json.dumps({
        "model_version": artifact["model_version"], "best_epoch": report["best_epoch"],
        "training_seconds": report["training_seconds"], "temperature": temperature,
        "backtest": report["backtest"], "reload_equal": True,
        "prediction_pair_count": len(actual_pairs), "scored_account_count": len(state.known_accounts()),
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
