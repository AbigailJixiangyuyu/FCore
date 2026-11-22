import math
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from algorithms.anomaly.artifacts import save_artifact as save_slade
from algorithms.anomaly.slade import SladeConfig
from algorithms.anomaly.training import train as train_slade
from algorithms.link_prediction import artifacts as zebra_artifacts
from algorithms.link_prediction.data import prepare_history
from algorithms.link_prediction.forecast_training import fit_forecast_head
from algorithms.link_prediction.model import ZebraConfig
from algorithms.link_prediction.training import train as train_zebra
from app.core.config import Settings
from app.repositories.datasets import DatasetRepository
from app.services.anomalies import prepare_training
from app.repositories.dataset_writer import write_dataset
from scripts.generate_sample import DATASET_VERSION, generate_dataset

DATASET = "synthetic-small"
CONTEXT = {"dataset_id": DATASET, "dataset_version": DATASET_VERSION}
HISTORY = [f"S{index:02d}" for index in range(1, 12)]
ANOMALIES = "/api/anomalies/discover"
MODELS = f"/api/datasets/{DATASET}/link-prediction/models"
PREDICT = "/api/link-prediction/predict"


@pytest.fixture
def model_sample(tmp_path, app_with_test_core, monkeypatch):
    settings = Settings(project_root=tmp_path)
    directory = settings.data_dir / DATASET
    files = generate_dataset(directory)
    accounts = ["a-001", "a-002", "a-007", "a-008", "a-013"]
    ring = list(zip(accounts, accounts[1:] + accounts[:1]))
    for meta in files["manifest.json"]["snapshots"][:11]:
        start = int(datetime.fromisoformat(meta["starts_at"]).timestamp())
        files[f"{meta['snapshot_id']}.csv"] = [
            {"u": u, "v": v, "t": start + offset}
            for offset, (u, v) in enumerate(ring, 1)
        ]
    write_dataset(directory, files)
    read = DatasetRepository.read

    def observed_only(repository, dataset_id, filename):
        assert filename not in {"S13.csv", "replay.json", "scenarios.json"}
        return read(repository, dataset_id, filename)

    monkeypatch.setattr(DatasetRepository, "read", observed_only)
    with TestClient(app_with_test_core(settings)) as client:
        yield client, settings


def current_community(client: TestClient) -> dict:
    response = client.post("/api/queries/local-core", json=CONTEXT)
    assert response.status_code == 200, response.text
    structure, = response.json()["structures"]
    assert len(structure["members"]) == 5
    return structure


def model_statuses(client: TestClient, horizon: int = 1) -> dict[str, str]:
    response = client.get(MODELS, params={"dataset_version": DATASET_VERSION, "horizon": horizon})
    assert response.status_code == 200, response.text
    assert response.json()["horizon"] == horizon
    return {row["id"]: row["status"] for row in response.json()["models"]}


def test_untrained_models_do_not_stop_current_queries(model_sample):
    client, _ = model_sample
    historical = client.post(ANOMALIES, json={**CONTEXT, "snapshot_id": "S11"})
    assert historical.status_code == 200 and historical.json()["status"] == "not_evaluated"
    assert client.post(ANOMALIES, json=CONTEXT).status_code == 503
    assert model_statuses(client) == {"zebra": "not_ready"}
    assert model_statuses(client, horizon=2) == {"zebra": "not_ready"}
    structure = current_community(client)
    assert client.post(PREDICT, json={**CONTEXT, "structure": structure, "model": "zebra"}).status_code == 503
    assert client.post("/api/link-prediction/community", json={**CONTEXT, "k": 2}).status_code == 503
    assert client.post(PREDICT, json={**CONTEXT, "structure": structure, "model": "undergs"}).status_code == 422
    assert client.post("/api/link-prediction/community", json={**CONTEXT, "k": 2, "model": "undergs"}).status_code == 422


@pytest.mark.hardware
def test_slade_training_and_s12_rankings(model_sample):
    client, settings = model_sample
    repository = DatasetRepository(settings.data_dir)
    _, manifest = repository.locate(DATASET)
    events, metadata = prepare_training(repository, manifest)
    config = SladeConfig(memory_dim=8, message_dim=4, heads=2, epochs=1)
    model, state, report = train_slade(events, config)
    assert next(model.parameters()).is_cuda and state.memory.is_cuda
    loss, = report["epoch_losses"]
    assert math.isfinite(loss)
    artifact = save_slade(settings.models_dir, DATASET, model, state, metadata, report)

    response = client.post(ANOMALIES, json=CONTEXT)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["snapshot_id"] == "S12" and result["training_snapshot_ids"] == HISTORY
    assert result["method"] == "slade-v1" and result["model_version"] == artifact["model_version"]
    accounts = result["accounts"]
    assert [row["rank"] for row in accounts] == list(range(1, 11))
    assert accounts == sorted(accounts, key=lambda row: (-row["score"], row["account_id"]))
    for row in accounts:
        assert 0 <= row["score"] <= 1
        assert row["score"] == pytest.approx(
            (row["temporal_contrast_score"] + row["memory_generation_score"]) / 4
        )
    assert client.post(ANOMALIES, json=CONTEXT).json()["accounts"] == accounts


@pytest.mark.hardware
def test_zebra_trains_and_scores_all_current_community_pairs(model_sample):
    client, settings = model_sample
    repository = DatasetRepository(settings.data_dir)
    _, manifest = repository.locate(DATASET)
    windows, metadata = prepare_history(repository, manifest)
    config = ZebraConfig(node_dim=8, memory_dim=8, time_dim=4, topk=3, epochs=1)
    model, state, temperature, report = train_zebra(windows, config)
    assert next(model.parameters()).is_cuda and math.isfinite(temperature)
    artifact = zebra_artifacts.save_artifact(settings.models_dir, model, state, temperature, metadata, report)
    zebra_artifacts.activate_artifact(settings.models_dir, DATASET, artifact)

    assert model_statuses(client) == {"zebra": "ready"}
    structure = current_community(client)
    body = {**CONTEXT, "structure": structure}
    response = client.post(PREDICT, json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["model"] == "zebra" and result["model_version"] == artifact["model_version"]
    assert result["target_snapshot"] == "S13" and not result["directed"]
    assert result["membership_hash"] == structure["membership_hash"]
    assert result["candidate_pair_count"] == result["scored_pair_count"] == 10
    rows = result["pairs"]
    assert [row["rank"] for row in rows] == list(range(1, 11))
    assert len({(row["u"], row["v"]) for row in rows}) == 10
    assert all(row["u"] < row["v"] and 0 <= row["probability"] <= 1 for row in rows)
    assert rows == sorted(rows, key=lambda row: (-row["probability"], row["u"], row["v"]))
    assert result["unscored_accounts"] == []
    assert client.post(PREDICT, json={**body, "model": "zebra"}).json()["pairs"] == rows

    for horizon in (2, 3):
        model, _, _, _ = zebra_artifacts.load_artifact(settings.models_dir, DATASET, metadata)
        state, temperature, report = fit_forecast_head(model, windows, horizon)
        assert all(int(sample["target"][1:]) - int(sample["input_cutoff"][1:]) == horizon
                   and sample["target"] < "S10" for sample in report["training_samples"])
        assert report["validation_input_cutoff"] == f"S{10 - horizon:02d}"
        assert report["calibration_input_cutoff"] == f"S{11 - horizon:02d}"
        future = zebra_artifacts.save_artifact(
            settings.models_dir, model, state, temperature, metadata, report, horizon=horizon,
        )
        zebra_artifacts.activate_artifact(settings.models_dir, DATASET, future, horizon=horizon)
        assert model_statuses(client, horizon) == {"zebra": "ready"}
        response = client.post("/api/link-prediction/community", json={
            **CONTEXT, "account": "a-001", "k": 2, "threshold": 0, "horizon": horizon,
        })
        assert response.status_code == 200, response.text
        forecast = response.json()
        assert forecast["model_version"] == future["model_version"]
        assert forecast["target_snapshot"] == f"S{12 + horizon}"
        assert forecast["observed_until"] == "S12" and forecast["status"] == "ok"
        assert len(forecast["members"]) == 5 and len(forecast["edges"]) == 10

    assert client.post(PREDICT, json=body).json()["model_version"] == artifact["model_version"]
