import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.repositories.datasets import DatasetRepository
from app.services.parallel_core import ParallelCoreCache

DATASET = "email-eu-core-dept3"
HISTORY = [f"S{index:02d}" for index in range(1, 12)]


@pytest.fixture(scope="module")
def dept3(app_with_test_core):
    settings = Settings()
    _, manifest = DatasetRepository(settings.data_dir).locate(DATASET)
    context = {"dataset_id": DATASET, "dataset_version": manifest.dataset_version}
    with TestClient(app_with_test_core(settings)) as client:
        yield client, context


def test_dept3_catalog_and_observed_snapshots(dept3):
    client, context = dept3
    catalog = client.get("/api/datasets").json()["datasets"]
    dept3_entry = next(item for item in catalog if item["dataset_id"] == DATASET)
    assert dept3_entry["timestamp_basis"] == "relative" and not dept3_entry["synthetic"]
    snapshots = client.get(f"/api/datasets/{DATASET}/snapshots").json()["snapshots"]
    assert [item["kind"] for item in snapshots] == ["history"] * 69 + ["present", "future"]
    endpoint = f"/api/datasets/{DATASET}/snapshots"
    response = client.get(f"{endpoint}/S12", params=context)
    assert response.status_code == 200
    frame = response.json()
    assert len(frame["nodes"]) == 89 and frame["stats"]["transaction_count"] == 1208
    assert client.get(f"{endpoint}/S13", params=context).status_code == 404


@pytest.mark.parametrize(
    "pattern,expected_members",
    [("periodic", 35), ("durable", 76), ("burst", 45), ("frequency", 7)],
)
def test_history_defaults_and_evidence_only_read_history(
    dept3, monkeypatch, pattern, expected_members
):
    client, context = dept3
    read = DatasetRepository.read

    def history_only(repository, dataset_id, filename):
        assert filename not in {"S12.csv", "S13.csv", "replay.json", "scenarios.json"}
        return read(repository, dataset_id, filename)

    monkeypatch.setattr(DatasetRepository, "read", history_only)
    response = client.post("/api/patterns/mine", json={**context, "pattern": pattern})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["result_kind"] == "computed"
    assert result["analysis_snapshot_ids"] == HISTORY
    structure, = result["structures"]
    assert len(structure["members"]) == expected_members
    if pattern == "durable":
        evidence = structure["evidence"]
        assert evidence["formation_start_snapshot_id"] == "S01"
        assert evidence["formation_end_snapshot_id"] == "S06"
        assert evidence["stable_end_snapshot_id"] == "S10"
        assert evidence["duration"] == 4
        assert evidence["member_count_series"] == [50, 66, 68, 71, 72, 76, 76, 76, 76, 76, 79]

    response = client.post("/api/evidence/series", json={**context, "structures": [structure]})
    assert response.status_code == 200, response.text
    track, = response.json()["series"]
    assert track["membership_hash"] == structure["membership_hash"]
    assert [point["snapshot_id"] for point in track["points"]] == HISTORY


def test_burst_query_point_must_belong_to_the_bursting_core(dept3):
    client, context = dept3
    endpoint = "/api/patterns/mine"
    request = {**context, "pattern": "burst"}
    global_core, = client.post(endpoint, json=request).json()["structures"]
    assert "account" not in global_core["parameters"]

    response = client.post(endpoint, json={**request, "account": "49"})
    assert response.status_code == 200, response.text
    structure, = response.json()["structures"]
    assert structure["parameters"]["account"] == "49"
    assert structure["members"] == global_core["members"]
    assert any(node["account"] == "49" for node in structure["evidence"]["nodes"])
    assert structure["membership_hash"] != global_core["membership_hash"]
    evidence = client.post("/api/evidence/series", json={**context, "structures": [structure]})
    assert evidence.status_code == 200, evidence.text

    excluded = client.post(endpoint, json={**request, "account": "0"})
    assert excluded.status_code == 200
    assert excluded.json()["structures"] == []
    assert client.post(endpoint, json={**request, "account": "missing"}).status_code == 422


@pytest.mark.parametrize(
    "pattern,start_index,expected_members",
    [("periodic", 1, 35), ("durable", 2, 56), ("burst", 2, 41), ("frequency", 2, 0)],
)
def test_windowed_patterns_and_evidence_use_only_the_submitted_snapshots(
    dept3, monkeypatch, pattern, start_index, expected_members
):
    client, context = dept3
    window = HISTORY[start_index:7]
    bounds = {"start_snapshot_id": window[0], "end_snapshot_id": window[-1]}
    snapshot = DatasetRepository.snapshot
    reads = set()

    def snapshot_in_window(repository, dataset_id, snapshot_id):
        assert snapshot_id in window
        reads.add(snapshot_id)
        return snapshot(repository, dataset_id, snapshot_id)

    monkeypatch.setattr(DatasetRepository, "snapshot", snapshot_in_window)
    response = client.post(
        "/api/patterns/mine", json={**context, "pattern": pattern, **bounds}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["analysis_snapshot_ids"] == window
    assert result["reference_snapshot_id"] == window[-1]
    assert reads == set(window)
    if not expected_members:
        assert result["structures"] == []
        return

    structure, = result["structures"]
    assert len(structure["members"]) == expected_members
    assert structure["snapshot_id"] == window[-1]
    assert {key: structure["parameters"][key] for key in bounds} == bounds
    assert structure["evidence"]["analysis_snapshot_ids"] == window
    if pattern == "periodic":
        assert structure["evidence"]["start_index_snapshot_id"] == "S02"
    if pattern == "durable":
        assert structure["evidence"]["duration"] == 0

    reads.clear()
    response = client.post(
        "/api/evidence/series", json={**context, "structures": [structure]}
    )
    assert response.status_code == 200, response.text
    track, = response.json()["series"]
    assert track["membership_hash"] == structure["membership_hash"]
    assert [(point["snapshot_id"], point["index"]) for point in track["points"]] == list(
        zip(window, range(start_index, 7))
    )
    assert reads == set(window)


def test_history_window_validation(dept3):
    client, context = dept3
    for pattern, start, end, status in (
        ("durable", "S03", None, 422),
        ("durable", "S07", "S03", 422),
        ("durable", "S10", "S12", 422),
        ("durable", "S11", "S13", 422),
        ("durable", "S00", "S03", 404),
        ("burst", "S03", "S04", 422),
        ("frequency", "S03", "S05", 422),
    ):
        response = client.post(
            "/api/patterns/mine",
            json={**context, "pattern": pattern, "start_snapshot_id": start, "end_snapshot_id": end},
        )
        assert response.status_code == status, response.text


def test_temporal_core_results_use_their_tightest_windows(dept3, monkeypatch):
    client, context = dept3
    endpoint = "/api/patterns/mine"
    query = {**context, "pattern": "temporal_core"}
    snapshot = DatasetRepository.snapshot
    reads = []

    def historical_read(repository, dataset_id, snapshot_id):
        assert snapshot_id in HISTORY
        reads.append(snapshot_id)
        return snapshot(repository, dataset_id, snapshot_id)

    monkeypatch.setattr(DatasetRepository, "snapshot", historical_read)
    default = client.post(endpoint, json=query)
    assert default.status_code == 200, default.text
    data = default.json()
    assert data["method"] == "tcq-snapshot-otcd-v1"
    assert data["analysis_snapshot_ids"] == ["S10", "S11"]
    core, = data["structures"]
    assert core["structure_id"] == "TCQ:S10:S11"
    assert core["parameters"]["k"] == 7
    assert core["evidence"]["window_comparison"] == [
        {
            "start_snapshot_id": start,
            "end_snapshot_id": end,
            "min_internal_degree": degree,
            "below_k_members": below,
            "omitted_temporal_edges": omitted,
        }
        for start, end, degree, below, omitted in (
            ("S10", "S10", 5, 4, 46),
            ("S11", "S11", 2, 14, 69),
            ("S10", "S11", 7, 0, 0),
        )
    ]
    assert reads == ["S10", "S11"]
    assert client.post(endpoint, json={**query, "start_snapshot_id": "S09"}).status_code == 422

    bounds = {"start_snapshot_id": "S07", "end_snapshot_id": "S11"}
    reads.clear()
    response = client.post(endpoint, json={**query, **bounds})
    assert response.status_code == 200, response.text
    structures = response.json()["structures"]
    assert len(structures) == 10
    assert reads == HISTORY[6:]
    by_id = {structure["structure_id"]: structure for structure in structures}
    assert structures[0]["structure_id"] == "TCQ:S10:S11"
    for identifier, expected in [("TCQ:S07:S08", (27, 140, 682)), ("TCQ:S10:S11", (18, 79, 523))]:
        structure = by_id[identifier]
        _, start, end = identifier.split(":")
        evidence = structure["evidence"]
        metrics = structure["metrics"]
        assert (evidence["witness_start_snapshot_id"], evidence["witness_end_snapshot_id"]) == (start, end)
        assert structure["snapshot_id"] == end
        assert (metrics["node_count"], metrics["internal_edges"], metrics["transaction_count"]) == expected
        assert metrics["min_degree"] >= 7

    selection = {**context, "structures": [by_id["TCQ:S07:S08"]]}
    evidence = client.post("/api/evidence/series", json=selection)
    assert evidence.status_code == 200, evidence.text
    series, = evidence.json()["series"]
    assert series["membership_hash"] == selection["structures"][0]["membership_hash"]

    empty = client.post(endpoint, json={**query, **bounds, "k": 100})
    assert empty.status_code == 200 and empty.json()["structures"] == []
    assert client.post(endpoint, json={**query, **bounds, "k": 0}).status_code == 422


def test_temporal_cores_with_same_members_and_end_keep_distinct_ids(dept3):
    client, _ = dept3
    entry = next(item for item in client.get("/api/datasets").json()["datasets"]
                 if item["dataset_id"] == "synthetic-small")
    response = client.post("/api/patterns/mine", json={
        "dataset_id": entry["dataset_id"],
        "dataset_version": entry["dataset_version"],
        "pattern": "temporal_core",
        "start_snapshot_id": "S01",
        "end_snapshot_id": "S11",
    })
    assert response.status_code == 200, response.text
    structures = response.json()["structures"]
    assert len(structures) == len({item["membership_hash"] for item in structures}) == 59
    identities_without_start = {(tuple(item["members"]), item["snapshot_id"]) for item in structures}
    assert len(identities_without_start) < len(structures)
    assert all(item["parameters"]["k"] == 4 for item in structures)
    by_id = {item["structure_id"]: item for item in structures}
    single = by_id["TCQ:S10:S10"]
    extended = by_id["TCQ:S10:S11"]
    assert single["members"] == extended["members"]
    assert single["evidence"]["window_comparison"] == [{
        "start_snapshot_id": "S10",
        "end_snapshot_id": "S10",
        "min_internal_degree": 4,
        "below_k_members": 0,
        "omitted_temporal_edges": 0,
    }]
    trimmed = extended["evidence"]["window_comparison"][0]
    assert trimmed["min_internal_degree"] == 4
    assert trimmed["below_k_members"] == 0
    assert trimmed["omitted_temporal_edges"] > 0


def test_current_default_query_and_fixed_member_evidence(dept3, monkeypatch):
    client, context = dept3
    snapshot = DatasetRepository.snapshot
    reads = []

    def record_snapshot(repository, dataset_id, snapshot_id):
        assert snapshot_id != "S13"
        reads.append(snapshot_id)
        return snapshot(repository, dataset_id, snapshot_id)

    monkeypatch.setattr(DatasetRepository, "snapshot", record_snapshot)
    endpoint = "/api/queries/local-core"
    response = client.post(endpoint, json=context)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["method"] == "sigmod25-parallel-kcore-v1" and result["window_graph"] is None
    structure, = result["structures"]
    assert structure["parameters"] == {"account": "49", "k": 7}
    assert len(structure["members"]) == 30 and structure["metrics"]["internal_edges"] == 145
    empty = client.post(endpoint, json={**context, "k": 8})
    assert empty.status_code == 200 and empty.json()["structures"] == []
    assert reads == ["S12"]

    evidence = "/api/evidence/series"
    response = client.post(evidence, json={**context, "structures": [structure]})
    assert response.status_code == 200, response.text
    track, = response.json()["series"]
    assert track["membership_hash"] == structure["membership_hash"]
    points = track["points"]
    assert [point["snapshot_id"] for point in points] == [*HISTORY, "S12"]
    assert points[-1]["value"] == 145
    tampered = {**structure, "members": structure["members"][:-1]}
    assert client.post(evidence, json={**context, "structures": [tampered]}).status_code == 422


def test_tccs_window_selection_and_replay(dept3, monkeypatch):
    client, context = dept3
    endpoint = "/api/queries/local-core"
    parallel = client.post(endpoint, json={**context, "start_snapshot_id": "S12"})
    assert parallel.status_code == 200, parallel.text
    assert parallel.json()["method"] == "sigmod25-parallel-kcore-v1"
    assert parallel.json()["window_graph"] is None
    parallel_structure, = parallel.json()["structures"]

    def unexpected_solver(*args, **kwargs):
        pytest.fail("TCCS must run independently of the parallel solver")

    monkeypatch.setattr(ParallelCoreCache, "index", unexpected_solver)
    tccs = {**context, "algorithm": "tccs"}
    single = client.post(endpoint, json=tccs)
    assert single.status_code == 200, single.text
    assert single.json()["method"] == "tccs-online-v1"
    assert single.json()["window_graph"]["snapshot_ids"] == ["S12"]
    single_structure, = single.json()["structures"]
    assert single_structure["members"] == parallel_structure["members"]
    assert single_structure["parameters"]["start_snapshot_id"] == "S12"
    assert single_structure["membership_hash"] != parallel_structure["membership_hash"]

    window_request = {**context, "start_snapshot_id": "S10"}
    multi = client.post(endpoint, json={**window_request, "algorithm": "tccs"})
    assert multi.status_code == 200, multi.text
    window = multi.json()["window_graph"]
    assert window["snapshot_ids"] == ["S10", "S11", "S12"]
    coreness = client.get(f"/api/datasets/{DATASET}/window-coreness", params=window_request)
    assert coreness.status_code == 200, coreness.text
    assert coreness.json()["core_numbers"] == window["core_numbers"]
    assert window["core_numbers"]["49"] > single.json()["window_graph"]["core_numbers"]["49"]
    structure, = multi.json()["structures"]
    assert structure["parameters"] == {"account": "49", "k": 7, "algorithm": "tccs", "start_snapshot_id": "S10"}
    assert len(structure["members"]) == 52

    legacy = client.post(endpoint, json=window_request)
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["method"] == "tccs-online-v1"
    assert legacy.json()["structures"][0]["members"] == structure["members"]
    empty = client.post(endpoint, json={**window_request, "algorithm": "tccs", "k": 100})
    assert empty.status_code == 200 and empty.json()["structures"] == []
    assert empty.json()["window_graph"] == window
    assert client.post(endpoint, json={**window_request, "algorithm": "parallel"}).status_code == 422
    assert client.post(endpoint, json={**tccs, "snapshot_id": "S13"}).status_code == 422

    response = client.post("/api/evidence/series", json={**context, "structures": [single_structure, structure]})
    assert response.status_code == 200, response.text
    for track, saved in zip(response.json()["series"], (single_structure, structure), strict=True):
        assert track["membership_hash"] == saved["membership_hash"]
        assert [point["snapshot_id"] for point in track["points"]] == [*HISTORY, "S12"]


@pytest.mark.parametrize(
    "dataset_id,order,node_count,edge_count",
    [(DATASET, 7, 30, 145), ("synthetic-small", 4, 5, 10), ("ethereum-eth", 2, 27, 50)],
)
def test_pkmc_s12_lookup_and_structure_replay(
    dept3, monkeypatch, dataset_id, order, node_count, edge_count
):
    client, _ = dept3
    settings = Settings()
    _, manifest = DatasetRepository(settings.data_dir).locate(dataset_id)
    context = {"dataset_id": dataset_id, "dataset_version": manifest.dataset_version}
    frame = client.get(f"/api/datasets/{dataset_id}/snapshots/S12", params=context).json()
    expected_members = sorted(
        node for node, number in frame["core_numbers"].items() if number == order
    )
    assert max(frame["core_numbers"].values()) == order

    read = DatasetRepository.read
    csv_reads = []

    def record_reads(repository, requested_dataset, filename):
        if filename.endswith(".csv"):
            csv_reads.append(filename)
        assert filename != "S13.csv"
        return read(repository, requested_dataset, filename)

    def unexpected_solver(*args, **kwargs):
        pytest.fail("PKMC must run independently of the WSL solver")

    monkeypatch.setattr(DatasetRepository, "read", record_reads)
    monkeypatch.setattr(ParallelCoreCache, "index", unexpected_solver)
    endpoint = "/api/queries/max-core"
    request = {**context, "algorithm": "pkmc"}
    response = client.post(endpoint, json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["method"] == "pkmc-v1" and result["result_kind"] == "computed"
    structure, = result["structures"]
    assert structure["origin"] == "max_core" and structure["snapshot_id"] == "S12"
    assert structure["parameters"] == {"algorithm": "pkmc", "max_core": order}
    assert structure["members"] == expected_members
    assert len(structure["members"]) == node_count
    assert structure["metrics"]["internal_edges"] == edge_count
    assert client.post(endpoint, json={**request, "snapshot_id": "S11"}).status_code == 422
    assert client.post(endpoint, json={**request, "snapshot_id": "S13"}).status_code == 422
    assert client.post(endpoint, json={**request, "account": "49"}).status_code == 422
    assert csv_reads == ["S12.csv"]

    legacy = client.post(endpoint, json=context)
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["method"] == "maximum-core-v1"
    old_structure, = legacy.json()["structures"]
    assert old_structure["parameters"] == {"max_core": order}
    assert old_structure["members"] == expected_members
    assert old_structure["membership_hash"] != structure["membership_hash"]

    evidence = client.post(
        "/api/evidence/series", json={**context, "structures": [structure, old_structure]}
    )
    assert evidence.status_code == 200, evidence.text
    for track, saved in zip(evidence.json()["series"], (structure, old_structure), strict=True):
        assert track["membership_hash"] == saved["membership_hash"]
        assert track["points"][-1]["snapshot_id"] == "S12"
        assert track["points"][-1]["value"] == edge_count
