"""Offline only: uv run python -m scripts.train_slade --dataset synthetic-small."""

import argparse
import json
from time import perf_counter

import torch

from algorithms.anomaly.artifacts import activate_artifact, load_artifact, save_artifact
from algorithms.anomaly.events import seconds, snapshot_events
from algorithms.anomaly.runtime import runtime_info
from algorithms.anomaly.slade import SladeConfig
from algorithms.anomaly.state import MemoryState
from algorithms.anomaly.training import train
from app.core.config import Settings
from app.repositories.datasets import DatasetRepository
from app.services.anomalies import prepare_training


def main():
    parser = argparse.ArgumentParser(
        description="Train SLADE and save its warm-up state through S11."
    )
    parser.add_argument("--dataset", default="synthetic-small")
    arguments = parser.parse_args()
    settings = Settings()
    repository = DatasetRepository(settings.data_dir)
    _, manifest = repository.locate(arguments.dataset)
    events, metadata = prepare_training(repository, manifest)
    runtime = runtime_info()
    print(json.dumps(runtime, ensure_ascii=False), flush=True)
    torch.cuda.reset_peak_memory_stats()
    started = perf_counter()
    model, state, report = train(
        events,
        SladeConfig(),
        progress=lambda epoch, loss: print(
            f"Epoch {epoch:02d}/10: loss={loss:.8f}", flush=True
        ),
    )
    torch.cuda.synchronize()
    report.update(runtime)
    report["training_seconds"] = round(perf_counter() - started, 3)
    report["peak_memory_mib"] = round(torch.cuda.max_memory_allocated() / 1024**2, 2)
    if (
        next(model.parameters()).device.type != "cuda"
        or state.memory.device.type != "cuda"
    ):
        raise RuntimeError("Training requires the model and its warm-up state on the GPU.")
    artifact = save_artifact(
        settings.models_dir,
        manifest.dataset_id,
        model,
        state,
        metadata,
        report,
        activate=False,
    )
    # Validate the persisted candidate before replacing the serving pointer.
    restored, restored_state, _ = load_artifact(
        settings.models_dir,
        manifest.dataset_id,
        metadata,
        model_version=artifact["model_version"],
    )
    torch.testing.assert_close(state.memory, restored_state.memory, rtol=0, atol=0)
    current = next(
        meta
        for meta in manifest.snapshots
        if meta.snapshot_id == manifest.observed_until
    )
    current_frame = repository.snapshot(manifest.dataset_id, current.snapshot_id)
    current_events = snapshot_events(current_frame, current, metadata["origin_time"])
    cutoff = seconds(current.ends_at, metadata["origin_time"])
    original_state = MemoryState.from_payload(state.to_payload(), state.memory.device)
    model.replay(original_state, current_events)
    restored.replay(restored_state, current_events)
    expected = model.score(original_state, current_frame.present_accounts, cutoff)
    actual = restored.score(restored_state, current_frame.present_accounts, cutoff)
    if actual != expected:
        raise RuntimeError("The restored GPU model returned different S12 scores. The previously active model is still selected.")
    activate_artifact(settings.models_dir, manifest.dataset_id, artifact)
    print(
        json.dumps(
            {
                "model_version": artifact["model_version"],
                "training": metadata,
                "report": report,
                "validation": {
                    "warmup_reload_equal": True,
                    "s12_reload_scores_equal": True,
                    "scored_accounts": len(actual[0]),
                    "detection_event_count": len(current_events),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
