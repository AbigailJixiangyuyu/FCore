import csv
import gzip
from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from algorithms.anomaly.events import snapshot_events
from app.core.config import Settings
from app.main import create_app
from app.repositories.datasets import DatasetRepository
from app.repositories.dataset_writer import write_dataset
from scripts.generate_sample import DATASET_VERSION, generate_dataset
from scripts.import_email_dept3 import SOURCE_FILENAME, import_dataset

ENDPOINT = "/api/datasets/synthetic-small/aggregate"


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    root = tmp_path_factory.mktemp("historical-aggregate")
    files = generate_dataset(root / "data/synthetic-small")
    with TestClient(create_app(Settings(project_root=root))) as client:
        yield client, files


def parameters(start="S03", end="S07", **overrides):
    return {
        "dataset_version": DATASET_VERSION,
        "start_snapshot_id": start,
        "end_snapshot_id": end,
        **overrides,
    }


def test_dept3_import_preserves_the_active_prefix_and_snapshot_boundaries(tmp_path):
    source = Settings().data_dir / "raw" / SOURCE_FILENAME
    output = tmp_path / "dept3"
    files = import_dataset(source, output)
    raw = [line.split() for line in gzip.decompress(source.read_bytes()).decode().splitlines()]
    expected = sorted(
        [(min(u, v), max(u, v), int(t)) for u, v, t in raw if 0 <= int(t) < 45_310_384],
        key=lambda row: row[2],
    )
    assert len(raw) == 12_216
    assert len(expected) == 12_099
    converted = []
    previous_end = 0
    for meta in files["manifest.json"]["snapshots"]:
        start = datetime.fromisoformat(meta["starts_at"]).timestamp()
        end = datetime.fromisoformat(meta["ends_at"]).timestamp()
        assert start == previous_end and end - start == 58_091 * 60
        previous_end = end
        with (output / f"{meta['snapshot_id']}.csv").open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == ["u", "v", "t"]
            rows = [(row["u"], row["v"], int(row["t"])) for row in reader]
        assert rows and all(start <= t < end for _, _, t in rows)
        converted.extend(rows)
    assert len(files["manifest.json"]["snapshots"]) == 13
    assert converted == expected


def test_undirected_loading_counts_duplicate_interactions_and_retains_isolated_nodes(tmp_path):
    directory = tmp_path / "data/synthetic-small"
    files = generate_dataset(directory)
    records = [
        {"u": "a-001", "v": "a-002", "t": 1767232805},
        {"u": "a-001", "v": "a-002", "t": 1767232805},
        {"u": "a-002", "v": "a-001", "t": 1767232805.125},
        {"u": "a-003", "v": "a-003", "t": 1767232806},
    ]
    files["observed.json"][0]["present_accounts"] = ["a-001", "a-002", "a-003"]
    files["S01.csv"] = records
    write_dataset(directory, files)
    repository = DatasetRepository(tmp_path / "data")
    frame = repository.snapshot("synthetic-small", "S01")
    _, manifest = repository.locate("synthetic-small")
    meta = manifest.snapshots[0]
    events = snapshot_events(frame, meta, meta.starts_at)
    assert [(e.u, e.v, e.timestamp) for e in events] == [
        ("a-001", "a-002", 5.0),
        ("a-001", "a-002", 5.0),
        ("a-001", "a-002", 5.125),
    ]
    with TestClient(create_app(Settings(project_root=tmp_path))) as client:
        payload = client.get(
            "/api/datasets/synthetic-small/snapshots/S01",
            params={"dataset_version": DATASET_VERSION},
        ).json()
    assert payload["stats"]["transaction_count"] == 3
    assert payload["stats"]["internal_edges"] == 1
    assert payload["core_numbers"] == {"a-001": 1, "a-002": 1, "a-003": 0}
    assert payload["edges"] == [
        {"id": "a-001:a-002", "u": "a-001", "v": "a-002", "transaction_count": 3}
    ]


def test_millisecond_timestamps_fail_snapshot_validation(tmp_path):
    directory = tmp_path / "data/synthetic-small"
    files = generate_dataset(directory)
    files["S01.csv"][0]["t"] = 1_767_232_800_000
    write_dataset(directory, files)
    with TestClient(create_app(Settings(project_root=tmp_path))) as client:
        response = client.get(
            "/api/datasets/synthetic-small/snapshots/S01",
            params={"dataset_version": DATASET_VERSION},
        )
    assert response.status_code == 422
    assert "Unix seconds" in response.json()["detail"]


def test_range_aggregation_matches_inclusive_transactions(sample):
    client, files = sample
    original_snapshot = DatasetRepository.snapshot
    accessed = []

    def historical_only(repository, dataset_id, snapshot_id):
        accessed.append(snapshot_id)
        assert snapshot_id in {"S03", "S04", "S05", "S06", "S07"}
        return original_snapshot(repository, dataset_id, snapshot_id)

    with (
        patch.object(DatasetRepository, "snapshot", historical_only),
        patch.object(DatasetRepository, "replay", side_effect=AssertionError("S13")),
    ):
        response = client.get(ENDPOINT, params=parameters())
    assert response.status_code == 200
    result = response.json()
    assert result["snapshot_ids"] == accessed == [f"S{i:02}" for i in range(3, 8)]
    assert result["start_snapshot_id"] == "S03" and result["end_snapshot_id"] == "S07"
    metas = files["manifest.json"]["snapshots"]
    assert result["starts_at"] == metas[2]["starts_at"]
    assert result["ends_at"] == metas[6]["ends_at"]
    assert result["result_kind"] == "computed"
    raw = [t for index in range(3, 8) for t in files[f"S{index:02}.csv"]]
    assert result["stats"]["transaction_count"] == len(raw)
    expected = Counter((event["u"], event["v"]) for event in raw)
    counts = {(edge["u"], edge["v"]): edge["transaction_count"] for edge in result["edges"]}
    assert counts == expected
    present = {
        account
        for frame in files["observed.json"][2:7]
        for account in frame["present_accounts"]
    }
    assert {node["id"] for node in result["nodes"]} == present


def test_union_recomputes_core_and_retains_isolated_accounts(tmp_path: Path):
    directory = tmp_path / "data/synthetic-small"
    files = generate_dataset(directory)
    frames = files["observed.json"]

    def transaction(snapshot_index, source, target):
        return {
            "u": f"a-{source:03}",
            "v": f"a-{target:03}",
            "t": 1767232800 + snapshot_index * 600,
        }

    frames[0]["present_accounts"] = ["a-001", "a-002", "a-004"]
    frames[1]["present_accounts"] = ["a-001", "a-002", "a-003"]
    frames[2]["present_accounts"] = ["a-001", "a-003"]
    files["S01.csv"] = [transaction(0, 1, 2)]
    files["S02.csv"] = [
        transaction(1, 1, 2),
        transaction(1, 2, 1),
        transaction(1, 2, 3),
    ]
    files["S03.csv"] = [transaction(2, 3, 1)]
    write_dataset(directory, files)
    with TestClient(create_app(Settings(project_root=tmp_path))) as client:
        result = client.get(ENDPOINT, params=parameters("S01", "S03")).json()
        assert result["core_numbers"] == {
            "a-001": 2,
            "a-002": 2,
            "a-003": 2,
            "a-004": 0,
        }
        assert result["stats"]["internal_edges"] == len(result["edges"]) == 3
        assert result["stats"]["density"] == 0.5
        assert result["stats"]["transaction_count"] == 5
        repeated = next(edge for edge in result["edges"] if (edge["u"], edge["v"]) == ("a-001", "a-002"))
        assert repeated["transaction_count"] == 3
        for index in range(1, 4):
            single = client.get(
                ENDPOINT, params=parameters(f"S{index:02}", f"S{index:02}")
            ).json()
            assert max(single["core_numbers"].values()) == 1
