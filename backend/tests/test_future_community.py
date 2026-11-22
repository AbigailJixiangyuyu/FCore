from datetime import datetime
from itertools import combinations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.repositories.datasets import DatasetRepository
from app.services import link_prediction
from app.repositories.dataset_writer import write_dataset
from scripts.generate_sample import DATASET_ID, DATASET_VERSION, generate_dataset


def triangle(a, b, c):
    return [(a, b), (b, c), (c, a)]


def test_future_local_core_uses_snapshot_member_union_and_strict_threshold(
    tmp_path, app_with_test_core, monkeypatch
):
    settings = Settings(project_root=tmp_path)
    directory = settings.data_dir / DATASET_ID
    files = generate_dataset(directory)
    q, a, b, c, d, e, leaf, cross_window, current_only = [
        f"a-{index:03}" for index in range(1, 10)
    ]
    observed = {
        "S01": [*triangle(q, a, b), (a, q), (q, q)],
        "S02": triangle(q, c, d),
        "S03": triangle(q, e, leaf),
        "S04": [(q, cross_window)],
        "S05": [(a, cross_window)],
        "S12": triangle(q, a, current_only),
    }
    for meta, frame in zip(files["manifest.json"]["snapshots"], files["observed.json"]):
        sid = meta["snapshot_id"]
        pairs = observed.get(sid, [])
        frame["present_accounts"] = sorted({node for pair in pairs for node in pair})
        start = int(datetime.fromisoformat(meta["starts_at"]).timestamp())
        files[f"{sid}.csv"] = [
            {"u": u, "v": v, "t": start + offset}
            for offset, (u, v) in enumerate(pairs)
        ]
    write_dataset(directory, files)

    read = DatasetRepository.read
    snapshots_read = set()

    def observed_only(repository, dataset_id, filename):
        if filename.endswith(".csv"):
            snapshots_read.add(filename.removesuffix(".csv"))
        assert filename not in {"S13.csv", "replay.json"}
        return read(repository, dataset_id, filename)

    monkeypatch.setattr(DatasetRepository, "read", observed_only)

    candidate_pairs = list(
        combinations(sorted([q, a, b, c, d, e, leaf, cross_window, current_only]), 2)
    )
    positive = {
        tuple(sorted(pair))
        for pair in [
            *triangle(q, a, b), *triangle(c, d, e), (q, leaf),
            (q, cross_window), (a, cross_window), (q, current_only), (a, current_only),
        ]
    }
    probabilities = {pair: 0.8 for pair in positive}
    probabilities[q, c] = probabilities[a, c] = probabilities[b, c] = 0.5
    scored_horizons = []

    def fixture_scores(repository, manifest, models_dir, *, horizon):
        scored_horizons.append(horizon)
        return {
            "model_version": "test-model",
            "pairs": [
                {
                    "u": u, "v": v,
                    "probability": probabilities.get((u, v), 0.1),
                    "currently_connected": (u, v) == (q, a),
                }
                for u, v in candidate_pairs
            ],
        }

    monkeypatch.setattr(link_prediction, "full_network_prediction", fixture_scores)
    body = {
        "dataset_id": DATASET_ID, "dataset_version": DATASET_VERSION,
        "account": q, "k": 2,
    }
    with TestClient(app_with_test_core(settings)) as client:
        def predict(**overrides):
            response = client.post("/api/link-prediction/community", json={**body, **overrides})
            assert response.status_code == 200, response.text
            return response.json()

        result = predict(account=f" {q} ")
        assert result["account"] == q and result["k"] == 2
        assert result["target_snapshot"] == "S13" and result["threshold"] == 0.5
        assert result["model"] == "zebra" and result["model_version"] == "test-model"
        assert scored_horizons == [1]
        assert set(result["history_snapshot_ids"]) == {
            f"S{index:02d}" for index in range(1, 12)
        }
        assert snapshots_read == set(result["history_snapshot_ids"]) | {"S12"}
        assert result["candidate_member_count"] == 7
        assert result["candidate_pair_count"] == result["scored_pair_count"] == 21
        assert result["threshold_edge_count"] == 7  # two triangles and a leaf
        assert result["status"] == "ok" and result["members"] == [q, a, b]
        assert {(edge["u"], edge["v"]) for edge in result["edges"]} == {(q, a), (q, b), (a, b)}
        assert all(edge["probability"] == 0.8 for edge in result["edges"])
        assert result["comparison"] == {
            "retained": [q, a],
            "added": [b],
            "exited": [current_only],
            "max_coreness": 2,
            "key_nodes": [
                {"account_id": member, "observed_coreness": before, "predicted_coreness": 2}
                for member, before in [(q, 2), (a, 2), (b, None)]
            ],
        }

        # Advancing the forecast target uses a different scorer but the same observed history.
        for horizon in (2, 3):
            later = predict(horizon=horizon)
            assert later["target_snapshot"] == f"S{12 + horizon}"
            window = datetime.fromisoformat(result["target_ends_at"]) - datetime.fromisoformat(result["target_starts_at"])
            assert datetime.fromisoformat(later["target_starts_at"]) == (
                datetime.fromisoformat(result["target_starts_at"]) + (horizon - 1) * window
            )
            assert later["observed_until"] == "S12"
        assert scored_horizons == [1, 2, 3]
        assert client.post("/api/link-prediction/community", json={**body, "horizon": 4}).status_code == 422
        assert snapshots_read == set(result["history_snapshot_ids"]) | {"S12"}

        result_without_baseline = predict(account=b)
        assert result_without_baseline["comparison"]["added"] == [q, a, b]
        assert result_without_baseline["comparison"]["retained"] == []
        assert result_without_baseline["comparison"]["exited"] == []
        assert all(
            node["observed_coreness"] is None
            for node in result_without_baseline["comparison"]["key_nodes"]
        )

        result = predict(threshold=0.4)
        assert result["threshold"] == 0.4
        assert result["members"] == [q, a, b, c, d, e]
        assert result["threshold_edge_count"] == 10
        # The joined triangles contain a 3-core of four nodes.
        comparison = result["comparison"]
        assert comparison["max_coreness"] == 3
        assert [node["account_id"] for node in comparison["key_nodes"]] == [q, a, b, c]
        assert all(node["predicted_coreness"] == 3 for node in comparison["key_nodes"])

        result = predict(threshold=0.8)
        assert result["status"] == "no_threshold_edges" and result["threshold_edge_count"] == 0
        assert result["comparison"] == {
            "retained": [], "added": [], "exited": [q, a, current_only],
            "max_coreness": None, "key_nodes": [],
        }

        zero_core = predict(k=0, threshold=0.8)
        assert zero_core["status"] == "ok" and zero_core["members"] == [q]
        assert zero_core["edges"] == []
        assert zero_core["comparison"]["max_coreness"] == 0

        # Remaining edges are enough for the other triangle, but no longer support q.
        probabilities[q, a] = probabilities[q, b] = 0.5
        result = predict()
        assert result["status"] == "no_predicted_community" and result["threshold_edge_count"] > 0
        assert result["members"] == result["edges"] == []

        probabilities.clear()
        probabilities[b, c] = 0.5
        result = predict()
        assert result["status"] == "no_threshold_edges" and result["max_probability"] == 0.5
        assert result["threshold_edge_count"] == 0

        calls_before = len(scored_horizons)
        result = predict(k=3)
        assert result["status"] == "no_historical_community" and result["candidate_member_count"] == 0
        assert result["model_version"] is None and len(scored_horizons) == calls_before
        assert result["comparison"] is None

        candidate_pairs.clear()
        result = predict()
        assert result["status"] == "no_scored_pairs" and result["comparison"] is None
