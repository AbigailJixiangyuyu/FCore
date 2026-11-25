from itertools import combinations
from random import Random

from fastapi.testclient import TestClient

from algorithms.core.queries import adjacency
from algorithms.patterns.historical_core import HistoricalCoreIndex
from app.core.config import Settings
from app.repositories.datasets import DatasetRepository
from app.schemas.analysis import Structure
from app.services.historical_core import _index_cache
from app.services.reports.history import submitted_history_evidence


def test_phc_core_times_match_independent_peeling_in_every_inclusive_window():
    rng = Random(20261124)
    frames = [
        [[], [("a", "b"), ("b", "a"), ("c", "c")], [("a", "c"), ("b", "c")], [],
         [("a", "b"), ("a", "c"), ("b", "c"), ("d", "e"), ("e", "f"), ("f", "d")]],
        *[
            [[pair for pair in combinations("abcdef", 2) if rng.random() < 0.4] for _ in range(5)]
            for _ in range(20)
        ],
    ]
    for history in frames:
        index = HistoricalCoreIndex(history)
        for start in range(len(history)):
            first_ends = {k: {} for k in range(1, 7)}
            for end in range(start, len(history)):
                graph = adjacency("abcdef", (edge for frame in history[start : end + 1] for edge in frame))
                for k, expected in first_ends.items():
                    remaining = set(graph)
                    while True:
                        low = {u for u in remaining if len(graph[u] & remaining) < k}
                        if not low:
                            break
                        remaining -= low
                    for node in remaining:
                        expected.setdefault(node, end)
                    assert index.core_times(start, end, k) == expected


def test_fixed_window_communities_evidence_and_index_reuse(app_with_test_core, monkeypatch):
    _index_cache.clear()
    read = DatasetRepository.read
    history_reads = []

    def history_only(repository, dataset_id, filename):
        if filename.endswith(".csv"):
            assert "S01.csv" <= filename <= "S11.csv"
            history_reads.append((dataset_id, filename))
        assert filename != "replay.json"
        return read(repository, dataset_id, filename)

    monkeypatch.setattr(DatasetRepository, "read", history_only)
    with TestClient(app_with_test_core(Settings())) as client:
        contexts = {
            d["dataset_id"]: {key: d[key] for key in ("dataset_id", "dataset_version", "observed_until")}
            for d in client.get("/api/datasets").json()["datasets"]
        }
        endpoint = "/api/patterns/mine"
        for dataset, members, edges, counts in (
            ("ethereum-eth", 12, 24, [11, 12]),
            ("email-eu-core-dept3", 18, 79, [0, 18]),
            ("synthetic-small", 5, 10, [5]),
        ):
            request = {**contexts[dataset], "pattern": "historical_core"}
            response = client.post(endpoint, json=request)
            assert response.status_code == 200, response.text
            result, = response.json()["structures"]
            assert result["method"] == "phc-query-v1" and result["result_kind"] == "computed"
            assert (result["metrics"]["node_count"], result["metrics"]["internal_edges"]) == (members, edges)
            assert result["metrics"]["min_degree"] >= result["parameters"]["k"]
            assert result["evidence"]["qualifying_member_counts"] == counts
            record = submitted_history_evidence(Structure(**result))
            assert record["method"] == "PHC-Query"
            assert list(record["members_in_a_k_core_by_window_end"].values()) == counts

        # Two disconnected 2-cores must remain independently selectable and reproducible.
        request = {**contexts["synthetic-small"], "pattern": "historical_core",
                   "start_snapshot_id": "S01", "end_snapshot_id": "S01", "k": 2}
        before = len(history_reads)
        components = client.post(endpoint, json=request).json()["structures"]
        assert [len(core["members"]) for core in components] == [5, 5]
        assert set(components[0]["members"]).isdisjoint(components[1]["members"])
        assert components[0]["membership_hash"] != components[1]["membership_hash"]
        assert client.post(endpoint, json={**request, "k": 100}).json()["structures"] == []
        assert len(history_reads) == before
        track = client.post("/api/evidence/series", json={**contexts["synthetic-small"], "structures": [components[1]]})
        assert track.status_code == 200, track.text
        assert track.json()["series"][0]["membership_hash"] == components[1]["membership_hash"]
        for changes, status in [
            ({"end_snapshot_id": "S12"}, 422), ({"k": 0}, 422), ({"account": "a-001"}, 422),
            ({"start_snapshot_id": "S02"}, 422), ({"end_snapshot_id": "S99"}, 404),
            ({"dataset_version": "stale"}, 409),
        ]:
            assert client.post(endpoint, json={**request, **changes}).status_code == status
