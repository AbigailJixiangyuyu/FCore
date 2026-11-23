import pytest
import torch

from algorithms.anomaly.events import Event as AnomalyEvent
from algorithms.anomaly.slade import Slade, SladeConfig, anomaly_scores
from algorithms.anomaly.state import MemoryState
from algorithms.link_prediction.data import Event, Window, labels_for, prepare_history
from algorithms.link_prediction.tppr import Santa
from algorithms.link_prediction.undergs.tcns import prepare_snapshot
from algorithms.runtime import ModelUnavailable, inference_device
from app.core.config import Settings
from app.repositories.datasets import DatasetRepository
from app.services.anomalies import prepare_training


def test_cpu_inference_and_explicit_cuda_without_gpu(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setenv("FCORE_DEVICE", "cpu")
    assert inference_device("SLADE") == torch.device("cpu")
    assert inference_device("Zebra") == torch.device("cpu")
    monkeypatch.delenv("FCORE_DEVICE")
    with pytest.raises(ModelUnavailable, match="requires CUDA"):
        inference_device("Zebra")


def test_slade_scores_match_the_paper():
    memory = torch.tensor([[1.0, 0.0], [1.0, 0.0], [0.0, 0.0]])
    previous = torch.tensor([[0.0, 1.0], [1.0, 0.0], [0.0, 0.0]])
    generated = torch.tensor([[-1.0, 0.0], [1.0, 0.0], [0.0, 0.0]])
    score, temporal, generation = anomaly_scores(memory, previous, generated)
    assert temporal.tolist() == [1.0, 0.0, 1.0]
    assert generation.tolist() == [2.0, 0.0, 1.0]
    assert score.tolist() == [0.75, 0.0, 0.5]


def test_current_training_batch_cannot_update_its_own_memory_or_neighbors():
    model = Slade(SladeConfig(memory_dim=8, message_dim=4, heads=2)).eval()
    state = MemoryState.empty(["a", "b", "c"], 8)
    previous = (AnomalyEvent("a", "b", 1.0),)
    current = (AnomalyEvent("b", "c", 2.0),)
    loss = model.training_loss(state, current, previous)
    assert torch.isfinite(loss) and loss.requires_grad
    assert state.last_update.tolist() == [1.0, 1.0, 0.0]
    assert state.neighbors == [[(1, 1.0)], [(0, 1.0)], []]
    assert not state.seen[2]
    first = MemoryState.empty(["a", "b", "c"], 8)
    assert model.training_loss(first, current).requires_grad
    assert torch.count_nonzero(first.memory) == 0


def test_santa_two_step_recurrence_uses_pre_event_state():
    santa = Santa(20, ((0.1, 0.5),))
    santa.update(1, 2, 1.0, 1)
    assert santa.neighbors[0][1] == {(1, 2, 1.0): pytest.approx(0.09)}
    santa.update(1, 3, 2.0, 2)
    assert santa.neighbors[0][1] == {(1, 2, 1.0): pytest.approx(0.03), (2, 3, 2.0): pytest.approx(0.06)}
    assert santa.neighbors[0][3] == {(1, 2, 1.0): pytest.approx(0.081), (2, 1, 2.0): pytest.approx(0.09)}
    assert santa.norms[0][1] == pytest.approx(0.75)


def test_window_labels_include_recurring_edges_both_directions_and_no_duplicates():
    target = Window("S02", 10, 20, (Event("b", "a", 11), Event("a", "b", 11), Event("a", "a", 12)))
    assert labels_for([("a", "b"), ("a", "c")], target) == [1, 0]


def window(step, edges):
    start = step * 10.0
    return Window(f"S{step + 1:02}", start, start + 10, tuple(Event(str(u), str(v), start + 1) for u, v in edges))


def test_paper_figure_three_importance_and_shortest_paths():
    # Figure 3: r1=6; r5=6; r3=r4=r7=r8=4; r6=5; r2=6.
    edges = [
        (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),
        (3, 4), (3, 5), (4, 5), (5, 6), (7, 8), (8, 2),
        (2, 9), (2, 10), (2, 11), (2, 12), (2, 13),
        (4, "x1"), (5, "x1"), (3, "x2"), (5, "x3"), (6, "x3"),
        (6, "x4"), (6, "x5"), (7, "x5"), (7, "x7"), (8, "x7"),
    ]
    topology = prepare_snapshot(window(0, edges))
    assert topology.importance["1"] == pytest.approx(3.91, abs=0.005)
    assert topology.importance["2"] == pytest.approx(0.24, abs=0.005)
    candidates = dict(topology.candidates["10"])
    assert candidates["2"] == topology.importance["2"]
    assert candidates["8"] == pytest.approx(0.1 * topology.importance["8"])
    assert "1" not in candidates and "10" not in candidates


def test_training_preparation_stops_at_s11(monkeypatch):
    dataset = "email-eu-core-dept3"
    repository = DatasetRepository(Settings().data_dir)
    _, manifest = repository.locate(dataset)
    read_snapshot = repository.snapshot
    visited = []

    def history_only(dataset_id, snapshot_id):
        assert snapshot_id not in {"S12", "S13"}
        visited.append(snapshot_id)
        return read_snapshot(dataset_id, snapshot_id)

    monkeypatch.setattr(repository, "snapshot", history_only)
    history_ids = [f"S{index:02}" for index in range(1, 12)]
    events, _ = prepare_training(repository, manifest)
    assert visited == history_ids and len(events) == 9525
    visited.clear()
    _, metadata = prepare_history(repository, manifest)
    assert visited == history_ids and metadata["history_event_count"] == 9525
    assert metadata["training_target_snapshot_ids"] == history_ids[1:9]
