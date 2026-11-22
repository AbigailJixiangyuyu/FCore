"""Synchronous UnderGS-GCN state updates and read-only symmetric pair scoring."""

from dataclasses import asdict, dataclass
from itertools import combinations
import math

import torch
from torch import nn

from .tcns import SnapshotTopology, TemporalNeighborStore, prepare_snapshot

METHOD = "undergs-window-v1"


@dataclass(frozen=True)
class UnderGSConfig:
    node_dim: int = 128
    time_dim: int = 8
    topk: int = 16
    max_hops: int = 2
    path_decay: float = 0.1
    snapshot_decay: float = 0.05
    filter_ratio: float = 0.3
    dropout: float = 0.1
    learning_rate: float = 1e-4
    batch_size: int = 200
    epochs: int = 50
    patience: int = 5
    seed: int = 20261116

    def __post_init__(self):
        if any(type(getattr(self, name)) is not int or getattr(self, name) < 1 for name in (
            "node_dim", "time_dim", "topk", "max_hops", "batch_size", "epochs", "patience",
        )):
            raise ValueError("UnderGS dimensions and training counts must be positive integers")
        if not 0 < self.path_decay < 1 or not 0 < self.snapshot_decay < 1:
            raise ValueError("UnderGS decay factors must lie in (0,1)")
        if not 0 <= self.filter_ratio <= 1 or not 0 <= self.dropout < 1:
            raise ValueError("Invalid UnderGS masking probability")
        if not math.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError("Invalid UnderGS learning rate")

    def payload(self):
        return asdict(self)


class UnderGSState:
    def __init__(self, config: UnderGSConfig, device):
        self.accounts = []
        self.index = {}
        self.embeddings = torch.zeros((0, config.node_dim), device=device)
        self.neighbors = TemporalNeighborStore(config.topk, device)
        self.snapshot_index = -1
        self.last_end = None

    def add_accounts(self, accounts) -> None:
        added = sorted(set(accounts) - self.index.keys())
        for account in added:
            self.index[account] = len(self.accounts)
            self.accounts.append(account)
        if added:
            padding = self.embeddings.new_zeros((len(added), self.embeddings.shape[1]))
            self.embeddings = torch.cat((self.embeddings, padding))

    def known_accounts(self):
        return sorted(self.accounts)

    def detach(self):
        self.embeddings = self.embeddings.detach()

    def payload(self):
        return {
            "accounts": list(self.accounts), "embeddings": self.embeddings.detach().cpu().clone(),
            "neighbors": self.neighbors.payload(), "snapshot_index": self.snapshot_index, "last_end": self.last_end,
        }

    @classmethod
    def restore(cls, payload, config, device):
        state = cls(config, device)
        state.accounts = list(payload["accounts"])
        if any(not isinstance(a, str) or not a for a in state.accounts) or len(set(state.accounts)) != len(state.accounts):
            raise ValueError("Invalid UnderGS account mapping")
        state.index = {account: index for index, account in enumerate(state.accounts)}
        state.embeddings = payload["embeddings"].detach().clone().to(device)
        state.snapshot_index = int(payload["snapshot_index"])
        state.last_end = float(payload["last_end"])
        if (
            state.embeddings.shape != (len(state.accounts), config.node_dim)
            or state.embeddings.dtype != torch.float32
            or not torch.isfinite(state.embeddings).all()
            or state.snapshot_index < 0 or not math.isfinite(state.last_end)
        ):
            raise ValueError("Invalid UnderGS embedding state")
        state.neighbors.restore(payload["neighbors"], len(state.accounts), state.snapshot_index)
        return state


def normalized_weights(store, step, filter_ratio=0.0, training=False):
    weights = store.weights.clone()
    if training and filter_ratio:
        historical = (store.snapshots >= 0) & (store.snapshots < step)
        keep = torch.rand(weights.shape, device=weights.device) >= filter_ratio
        weights = weights.masked_fill(historical & ~keep, 0)
    total = weights.sum(dim=1, keepdim=True)
    return (weights / total.clamp_min(torch.finfo(weights.dtype).tiny)).to(torch.float32)


class UnderGS(nn.Module):
    def __init__(self, config: UnderGSConfig):
        super().__init__()
        self.config = config
        dim = config.node_dim
        self.register_buffer("frequencies", 10.0 ** (-torch.linspace(0, 9, config.time_dim)))
        self.source_transform = nn.Sequential(nn.Linear(dim, dim), nn.ReLU(), nn.Dropout(config.dropout), nn.Linear(dim, dim))
        self.neighbor_transform = nn.Sequential(
            nn.Linear(dim + config.time_dim + 1, dim), nn.ReLU(), nn.Dropout(config.dropout), nn.Linear(dim, dim),
        )
        self.update = nn.Linear(2 * dim, dim)
        self.decoder = nn.Sequential(nn.Linear(2 * dim, dim), nn.ReLU(), nn.Linear(dim, 1))
        for module in (self.source_transform, self.neighbor_transform, self.decoder):
            for layer in module:
                if isinstance(layer, nn.Linear):
                    nn.init.xavier_normal_(layer.weight)

    @property
    def device(self):
        return self.frequencies.device

    def initial_state(self):
        return UnderGSState(self.config, self.device)

    def advance_window(self, state: UnderGSState, window) -> None:
        topology = window if isinstance(window, SnapshotTopology) else prepare_snapshot(window, self.config.path_decay, self.config.max_hops)
        if state.last_end is not None and topology.start != state.last_end:
            raise ValueError("UnderGS snapshots must advance once in contiguous time order")
        state.add_accounts(topology.accounts)
        step = state.snapshot_index + 1
        state.neighbors.advance(topology, state.accounts, state.index, step, self.config.snapshot_decay)
        if state.accounts:
            previous = state.embeddings
            neighbors = state.neighbors.neighbors.clamp_min(0)
            ages = (step - state.neighbors.snapshots).to(torch.float32)
            time = torch.cos(ages[:, :, None] * self.frequencies)
            edge_features = previous.new_zeros((*neighbors.shape, 1))
            messages = self.neighbor_transform(torch.cat((previous[neighbors], edge_features, time), dim=-1))
            weights = normalized_weights(state.neighbors, step, self.config.filter_ratio, self.training)
            aggregate = (messages * weights[:, :, None]).sum(dim=1)
            # No detach here: the same window's pair losses must reach the encoder.
            state.embeddings = self.update(torch.cat((self.source_transform(previous), aggregate), dim=1))
        state.snapshot_index = step
        state.last_end = topology.end

    def pair_logits(self, state: UnderGSState, pairs):
        if not pairs:
            return state.embeddings.new_empty((0,))
        indices = torch.tensor([[state.index[u], state.index[v]] for u, v in pairs], device=self.device)
        left, right = state.embeddings[indices[:, 0]], state.embeddings[indices[:, 1]]
        forward = self.decoder(torch.cat((left, right), dim=1))
        reverse = self.decoder(torch.cat((right, left), dim=1))
        return ((forward + reverse) / 2).squeeze(-1)

    def all_pairs(self, state: UnderGSState, cutoff: float):
        if cutoff != state.last_end:
            raise ValueError("UnderGS scoring cutoff does not match the observed state")
        pairs = list(combinations(state.known_accounts(), 2))
        chunks = [self.pair_logits(state, pairs[start:start + self.config.batch_size]) for start in range(0, len(pairs), self.config.batch_size)]
        logits = torch.cat(chunks) if chunks else state.embeddings.new_empty((0,))
        return pairs, logits
