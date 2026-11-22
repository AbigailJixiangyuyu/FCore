import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from algorithms.core.parallel import METHOD, ParallelCoreError, decompose, is_built
from algorithms.core.queries import core_numbers
from app.core.config import Settings
from app.core.interactions import undirected_dataset_version
from app.main import create_app
from app.repositories.datasets import DatasetRepository
from app.services.statistics import graph_of
from scripts.generate_sample import DATASET_VERSION, generate_dataset

CONTEXT = {"dataset_id": "synthetic-small", "dataset_version": DATASET_VERSION}
QUERY = "/api/queries/local-core"
SNAPSHOT = "/api/datasets/synthetic-small/snapshots/S12"


@pytest.fixture
def settings(tmp_path):
    generate_dataset(tmp_path / "data" / CONTEXT["dataset_id"])
    return Settings(project_root=tmp_path)


def test_concurrent_queries_and_revalidation_share_per_version_decomposition(
    settings, monkeypatch
):
    calls = []
    reads = []
    original_snapshot = DatasetRepository.snapshot

    def snapshot(repository, dataset_id, snapshot_id):
        reads.append(snapshot_id)
        return original_snapshot(repository, dataset_id, snapshot_id)

    def solve(graph):
        calls.append(graph)
        return core_numbers(graph)

    monkeypatch.setattr(DatasetRepository, "snapshot", snapshot)
    app = create_app(settings, core_solver=solve)
    requests = [
        {"account": "a-001", "k": 4},
        {"account": "a-002", "k": 4},
        {"account": "a-026", "k": 0},
        {"account": "a-001", "k": 100},
    ]
    start = Barrier(len(requests), timeout=5)
    with TestClient(app) as client:
        def submit(fields):
            start.wait()
            return client.post(QUERY, json={**CONTEXT, **fields})

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            responses = list(pool.map(submit, requests))
        assert reads == ["S12"] and len(calls) == 1
        assert all(response.status_code == 200 for response in responses)
        results = [response.json() for response in responses]
        assert all(result["method"] == METHOD for result in results)
        selected, = results[0]["structures"]
        assert len(selected["members"]) == 5
        assert results[1]["structures"][0]["members"] == selected["members"]
        assert set(results[2]["structures"][0]["members"]) == set(calls[0])
        assert results[3]["structures"] == []

        evidence = client.post(
            "/api/evidence/series", json={**CONTEXT, "structures": [selected]}
        )
        assert evidence.status_code == 200, evidence.text
        assert evidence.json()["series"][0]["membership_hash"] == selected["membership_hash"]
        assert len(calls) == 1 and "S13" not in reads

        path = settings.data_dir / CONTEXT["dataset_id"] / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["dataset_version"] = "synthetic-small-test-version"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        assert client.post(QUERY, json=CONTEXT).status_code == 409
        changed = client.post(
            QUERY, json={**CONTEXT, "dataset_version": undirected_dataset_version(manifest["dataset_version"])}
        )
        assert changed.status_code == 200 and len(calls) == 2


def test_missing_engine_still_allows_snapshot_viewing_and_account_validation(settings):
    with TestClient(create_app(settings)) as client:
        missing = client.post(QUERY, json=CONTEXT)
        assert missing.status_code == 503
        assert "scripts.build_parallel_core" in missing.json()["detail"]
        assert client.get(SNAPSHOT, params=CONTEXT).status_code == 200
        assert client.post(QUERY, json={**CONTEXT, "account": "unknown"}).status_code == 422
        capabilities = client.get("/api/capabilities").json()["capabilities"]
        assert next(item for item in capabilities if item["id"] == "local_core")[
            "status"
        ] == "unavailable"


def test_failed_decomposition_is_not_cached(settings):
    attempts = []

    def solve(graph):
        attempts.append(graph)
        if len(attempts) == 1:
            raise ParallelCoreError("Parallel core decomposition timed out. Try again.")
        return core_numbers(graph)

    with TestClient(create_app(settings, core_solver=solve)) as client:
        assert client.post(QUERY, json=CONTEXT).status_code == 503
        assert client.post(QUERY, json=CONTEXT).status_code == 200
        assert client.post(QUERY, json=CONTEXT).status_code == 200
        assert len(attempts) == 2


@pytest.mark.hardware
def test_wsl_decomposition_matches_serial_on_dept3():
    settings = Settings()
    if not is_built(settings.parallel_core_binary):
        pytest.skip("Build the WSL adapter to run the native solver test")
    repository = DatasetRepository(settings.data_dir)
    graph = graph_of(repository.snapshot("email-eu-core-dept3", "S12"))
    assert decompose(graph, settings.parallel_core_binary) == core_numbers(graph)
