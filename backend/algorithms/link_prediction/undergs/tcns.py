"""Paper equations (1)-(2): cohesive importance and bounded temporal neighbors."""

from dataclasses import dataclass
import math

import torch


@dataclass(frozen=True)
class SnapshotTopology:
    snapshot_id: str
    start: float
    end: float
    accounts: tuple[str, ...]
    interaction_counts: dict[str, int]
    importance: dict[str, float]
    candidates: dict[str, tuple[tuple[str, float], ...]]


def prepare_snapshot(window, path_decay: float = 0.1, max_hops: int = 2) -> SnapshotTopology:
    """Counts retain multiplicity; shortest paths use the undirected simple graph."""
    if window.end <= window.start:
        raise ValueError("UnderGS requires a positive snapshot duration")
    adjacency, counts = {}, {}
    for event in window.events:
        if not window.start <= event.timestamp < window.end:
            raise ValueError("Interaction outside its UnderGS snapshot")
        u, v = event.u, event.v
        if not u or not v:
            raise ValueError("Empty account ID")
        if u == v:
            continue
        adjacency.setdefault(u, set()).add(v)
        adjacency.setdefault(v, set()).add(u)
        counts[u] = counts.get(u, 0) + 1
        counts[v] = counts.get(v, 0) + 1
    accounts = tuple(sorted(adjacency))
    importance = {
        u: math.fsum(
            math.exp(counts[u] / counts[v] if counts[v] >= counts[u] else -counts[u] / counts[v])
            for v in sorted(adjacency[u])
        )
        for u in accounts
    }
    candidates = {}
    for u in accounts:
        visited, frontier, values = {u}, {u}, {}
        for hop in range(1, max_hops + 1):
            frontier = set().union(*(adjacency[v] for v in frontier)) - visited
            visited.update(frontier)
            for v in sorted(frontier):
                values[v] = importance[v] * path_decay ** (hop - 1)
        candidates[u] = tuple(sorted(values.items()))
    return SnapshotTopology(window.snapshot_id, window.start, window.end, accounts, counts, importance, candidates)


class TemporalNeighborStore:
    """Persistent GPU arrays keyed by (account, snapshot); no candidate edge updates."""

    def __init__(self, topk: int, device):
        self.topk = topk
        self.neighbors = torch.empty((0, topk), dtype=torch.long, device=device)
        self.snapshots = torch.empty_like(self.neighbors)
        self.weights = torch.empty((0, topk), dtype=torch.float64, device=device)

    def extend(self, size: int) -> None:
        added = size - len(self.weights)
        if added < 0:
            raise ValueError("Cannot shrink the UnderGS account mapping")
        shape = (added, self.topk)
        self.neighbors = torch.cat((self.neighbors, self.neighbors.new_full(shape, -1)))
        self.snapshots = torch.cat((self.snapshots, self.snapshots.new_full(shape, -1)))
        self.weights = torch.cat((self.weights, self.weights.new_zeros(shape)))

    @torch.no_grad()
    def advance(self, topology: SnapshotTopology, accounts: list[str], index: dict[str, int], step: int, decay: float) -> None:
        size = len(accounts)
        self.extend(size)
        if not size:
            return
        width = max((len(row) for row in topology.candidates.values()), default=0)
        new_neighbors = [[-1] * width for _ in accounts]
        new_weights = [[0.0] * width for _ in accounts]
        for account, candidates in topology.candidates.items():
            row = index[account]
            for column, (neighbor, weight) in enumerate(candidates):
                new_neighbors[row][column] = index[neighbor]
                new_weights[row][column] = weight
        neighbors = torch.cat((self.neighbors, self.neighbors.new_tensor(new_neighbors)), dim=1)
        weights = torch.cat((self.weights * decay, self.weights.new_tensor(new_weights)), dim=1)
        new_steps = self.snapshots.new_full((size, width), step)
        snapshots = torch.cat((self.snapshots, new_steps), dim=1)
        valid = (neighbors >= 0) & (weights > 0)

        # Stable two-stage sorting gives exact score order and explicit lexical ties.
        ranks = {account: rank for rank, account in enumerate(sorted(accounts))}
        rank_tensor = self.neighbors.new_tensor([ranks[account] for account in accounts])
        lexical = rank_tensor[neighbors.clamp_min(0)] * (step + 1) + snapshots
        lexical = lexical.masked_fill(~valid, (size + 1) * (step + 1))
        order = torch.argsort(lexical, dim=1, stable=True)
        sorted_weights = weights.gather(1, order)
        score_order = torch.argsort(sorted_weights, dim=1, descending=True, stable=True)[:, :self.topk]
        order = order.gather(1, score_order)
        keep = valid.gather(1, order)
        self.neighbors = neighbors.gather(1, order).masked_fill(~keep, -1)
        self.snapshots = snapshots.gather(1, order).masked_fill(~keep, -1)
        self.weights = weights.gather(1, order).masked_fill(~keep, 0)

    def payload(self) -> dict:
        return {name: getattr(self, name).detach().cpu().clone() for name in ("neighbors", "snapshots", "weights")}

    def restore(self, payload: dict, size: int, step: int) -> None:
        for name, dtype in (("neighbors", torch.long), ("snapshots", torch.long), ("weights", torch.float64)):
            tensor = payload[name]
            if tensor.shape != (size, self.topk) or tensor.dtype != dtype:
                raise ValueError("Invalid UnderGS neighbor store dimensions or dtype")
            setattr(self, name, tensor.detach().clone().to(self.weights.device))
        valid = self.neighbors >= 0
        if (
            not torch.isfinite(self.weights).all()
            or (self.weights < 0).any()
            or (self.neighbors >= size).any()
            or (self.neighbors < -1).any()
            or (self.snapshots[valid] < 0).any()
            or (self.snapshots[valid] > step).any()
            or (self.weights[~valid] != 0).any()
            or (self.snapshots[~valid] != -1).any()
            or (self.weights[valid] <= 0).any()
        ):
            raise ValueError("Invalid UnderGS temporal neighbor entries")
        for row, (neighbors, snapshots) in enumerate(zip(self.neighbors.cpu().tolist(), self.snapshots.cpu().tolist())):
            keys = [(node, snapshot) for node, snapshot in zip(neighbors, snapshots) if node >= 0]
            if len(keys) != len(set(keys)) or any(node == row for node, _ in keys):
                raise ValueError("Duplicate or self UnderGS temporal neighbor")
