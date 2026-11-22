"""Train UnderGS, calibrate, backtest and activate only after a verified reload."""

import argparse
import json
from time import perf_counter

import torch

from algorithms.link_prediction.artifacts import read_artifact as read_zebra
from algorithms.link_prediction.checkpoint import ModelConflict
from algorithms.link_prediction.data import prepare_history, read_window
from algorithms.link_prediction.evaluation import backtest
from algorithms.link_prediction.runtime import ModelUnavailable, runtime_info
from algorithms.link_prediction.undergs.artifacts import (
    activate_artifact,
    load_artifact,
    save_artifact,
)
from algorithms.link_prediction.undergs.model import UnderGSConfig
from algorithms.link_prediction.undergs.training import train
from app.core.config import Settings
from app.repositories.datasets import DatasetRepository


def main():
    parser = argparse.ArgumentParser(description="GPU UnderGS：训练、窗口校准与 S12 独立回测；不读取 S13")
    parser.add_argument("--dataset", default="email-eu-core-dept3")
    arguments = parser.parse_args()
    settings = Settings()
    repository = DatasetRepository(settings.data_dir)
    _, manifest = repository.locate(arguments.dataset)
    windows, metadata = prepare_history(repository, manifest)
    runtime = runtime_info("UnderGS")
    print(json.dumps(runtime, ensure_ascii=False), flush=True)
    torch.cuda.reset_peak_memory_stats()
    started = perf_counter()

    def progress(row):
        print(json.dumps(row, ensure_ascii=False), flush=True)

    model, state, temperature, report = train(windows, UnderGSConfig(), progress)
    torch.cuda.synchronize()
    report.update(runtime)
    report["training_seconds"] = round(perf_counter() - started, 3)
    report["peak_memory_mib"] = round(torch.cuda.max_memory_allocated() / 1024**2, 2)
    current_meta = next(m for m in manifest.snapshots if m.snapshot_id == manifest.observed_until)
    current = read_window(repository, manifest, current_meta, metadata["origin_timestamp"])
    report["backtest"] = backtest(model, state, windows, current, temperature, model_name="undergs")
    try:
        _, zebra_artifact = read_zebra(settings.models_dir, manifest.dataset_id, metadata)
        report["zebra_comparison"] = {
            "model_version": zebra_artifact["model_version"],
            "backtest": zebra_artifact["report"]["backtest"],
            "source": "existing frozen S12 report; not used for model selection",
        }
    except (ModelConflict, ModelUnavailable) as error:
        report["zebra_comparison"] = {"status": "unavailable", "message": str(error)}
    artifact = save_artifact(settings.models_dir, model, state, temperature, metadata, report)
    restored, restored_state, restored_temperature, _ = load_artifact(
        settings.models_dir, manifest.dataset_id, metadata, artifact["model_version"],
    )
    assert state.accounts == restored_state.accounts and temperature == restored_temperature
    torch.testing.assert_close(state.embeddings, restored_state.embeddings, rtol=0, atol=0)
    for name in ("neighbors", "snapshots", "weights"):
        torch.testing.assert_close(getattr(state.neighbors, name), getattr(restored_state.neighbors, name), rtol=0, atol=0)
    with torch.no_grad():
        model.advance_window(state, current)
        restored.advance_window(restored_state, current)
        pairs, logits = model.all_pairs(state, current.end)
        restored_pairs, restored_logits = restored.all_pairs(restored_state, current.end)
        assert pairs == restored_pairs
        torch.testing.assert_close(logits, restored_logits, rtol=0, atol=0)
    if any(tensor.device.type != "cuda" for tensor in (model.frequencies, state.embeddings, state.neighbors.weights)):
        raise RuntimeError("UnderGS model and persistent state must be on GPU")
    activate_artifact(settings.models_dir, manifest.dataset_id, artifact)
    print(json.dumps({
        "model_version": artifact["model_version"], "best_epoch": report["best_epoch"],
        "training_seconds": report["training_seconds"], "temperature": temperature,
        "backtest": report["backtest"], "reload_equal": True,
        "prediction_pair_count": len(pairs), "scored_account_count": len(state.known_accounts()),
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
