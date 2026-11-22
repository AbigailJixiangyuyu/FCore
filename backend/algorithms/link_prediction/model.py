"""Zebra encoder plus a symmetric next-snapshot Bernoulli prediction head."""

from dataclasses import asdict, dataclass
from itertools import combinations
import math

import torch
from torch import nn

from .tppr import Santa

METHOD = "zebra-window-v1"


@dataclass(frozen=True)
class ZebraConfig:
    memory_dim: int = 100
    node_dim: int = 100
    time_dim: int = 100
    topk: int = 20
    metrics: tuple[tuple[float, float], ...] = ((0.1, 0.5), (0.1, 0.95))
    dropout: float = 0.1
    learning_rate: float = 1e-4
    epochs: int = 50
    patience: int = 5
    seed: int = 20261116

    def payload(self) -> dict:
        return asdict(self)


class ZebraState:
    def __init__(self, config: ZebraConfig, device: torch.device):
        self.accounts = [""]  # padding index; actual account "0" has its own index
        self.index = {}
        self.memory = torch.zeros((1, config.memory_dim), device=device)
        self.last_update = [0.0]
        self.counts = [0]
        self.event_count = 0
        self.last_event_time = -1.0
        self.tppr = Santa(config.topk, config.metrics)
        self.tppr.extend(1)

    def add_accounts(self, accounts) -> None:
        added = sorted(set(accounts) - self.index.keys())
        if not added:
            return
        for account in added:
            if not account:
                raise ValueError("Empty account ID")
            self.index[account] = len(self.accounts)
            self.accounts.append(account)
            self.last_update.append(0.0)
            self.counts.append(0)
        padding = self.memory.new_zeros((len(added), self.memory.shape[1]))
        self.memory = torch.cat((self.memory, padding))
        self.tppr.extend(len(self.accounts))

    def known_accounts(self) -> list[str]:
        return sorted(account for account, i in self.index.items() if self.counts[i])

    def payload(self) -> dict:
        return {
            "accounts": list(self.accounts), "memory": self.memory.detach().cpu().clone(),
            "last_update": list(self.last_update), "counts": list(self.counts),
            "event_count": self.event_count, "last_event_time": self.last_event_time,
            "tppr": self.tppr.payload(),
        }

    @classmethod
    def restore(cls, payload: dict, config: ZebraConfig, device: torch.device):
        state = cls(config, device)
        state.accounts = list(payload["accounts"])
        if not state.accounts or state.accounts[0] != "" or len(set(state.accounts)) != len(state.accounts):
            raise ValueError("Invalid Zebra account mapping")
        state.index = {account: i for i, account in enumerate(state.accounts) if i}
        state.memory = payload["memory"].detach().clone().to(device)
        state.last_update = list(payload["last_update"])
        state.counts = list(payload["counts"])
        state.event_count = int(payload["event_count"])
        state.last_event_time = float(payload["last_event_time"])
        state.tppr.restore(payload["tppr"])
        n = len(state.accounts)
        if state.memory.shape != (n, config.memory_dim) or len(state.counts) != n or len(state.last_update) != n:
            raise ValueError("Invalid Zebra memory dimensions")
        if not torch.isfinite(state.memory).all():
            raise ValueError("Non-finite Zebra state")
        if len(state.tppr.norms) != len(config.metrics) or any(len(x) != n for x in state.tppr.norms):
            raise ValueError("Invalid Zebra T-PPR state")
        return state


class Zebra(nn.Module):
    def __init__(self, config: ZebraConfig):
        super().__init__()
        self.config = config
        self.register_buffer("frequencies", 10.0 ** (-torch.linspace(0, 9, config.time_dim)))
        self.gru = nn.GRUCell(2 * config.memory_dim + 1 + config.time_dim, config.memory_dim)
        self.source_transform = nn.Sequential(
            nn.Linear(config.memory_dim, config.node_dim), nn.ReLU(), nn.Dropout(config.dropout),
            nn.Linear(config.node_dim, config.node_dim),
        )
        self.neighbor_transform = nn.Sequential(
            nn.Linear(config.memory_dim + 1 + config.time_dim, config.node_dim),
            nn.ReLU(), nn.Dropout(config.dropout), nn.Linear(config.node_dim, config.node_dim),
        )
        embedding_dim = config.node_dim * (1 + len(config.metrics))
        self.decoder = nn.Sequential(nn.Linear(2 * embedding_dim, embedding_dim), nn.ReLU(), nn.Linear(embedding_dim, 1))
        for module in (self.source_transform, self.neighbor_transform, self.decoder):
            for layer in module:
                if isinstance(layer, nn.Linear):
                    nn.init.xavier_normal_(layer.weight)

    @property
    def device(self) -> torch.device:
        return self.frequencies.device

    def initial_state(self) -> ZebraState:
        return ZebraState(self.config, self.device)

    def time_encode(self, delta: torch.Tensor) -> torch.Tensor:
        return torch.cos(delta[..., None] * self.frequencies)

    def advance(self, state: ZebraState, events) -> None:
        """Consume real events only. Gradients are retained when training enables them."""
        events = tuple(events)
        if not events:
            return
        previous = state.last_event_time
        for event in events:
            if not math.isfinite(event.timestamp) or event.timestamp < max(0, previous):
                raise ValueError("Zebra events must be finite and chronological")
            previous = event.timestamp
        state.add_accounts(account for event in events for account in (event.u, event.v))
        indices = [[state.index[event.u], state.index[event.v]] for event in events]
        previous_times = list(state.last_update)
        deltas = []
        for event, (u, v) in zip(events, indices):
            deltas.append([event.timestamp - previous_times[u], event.timestamp - previous_times[v]])
            previous_times[u] = previous_times[v] = event.timestamp
        gpu_indices = torch.tensor(indices, device=self.device, dtype=torch.long)
        encodings = self.time_encode(torch.tensor(deltas, device=self.device, dtype=torch.float32))
        feature = state.memory.new_zeros((2, 1))
        for i, (event, (u, v)) in enumerate(zip(events, indices)):
            endpoints = gpu_indices[i]
            old = state.memory[endpoints]
            message = torch.cat((old, old.flip(0), feature, encodings[i]), dim=1)
            updated = self.gru(message, old)
            if u == v:
                endpoints, updated = endpoints[:1], updated[:1]
            state.memory = state.memory.index_copy(0, endpoints, updated)
            state.event_count += 1
            state.tppr.update(u, v, event.timestamp, state.event_count)
            state.counts[u] += 1
            if v != u:
                state.counts[v] += 1
        state.last_update = previous_times
        state.last_event_time = events[-1].timestamp

    def encode(self, state: ZebraState, cutoff: float) -> torch.Tensor:
        if not math.isfinite(cutoff) or cutoff <= state.last_event_time:
            raise ValueError("Prediction cutoff must be after every observed event")
        outputs = [self.source_transform(state.memory)]
        n, k = len(state.accounts), self.config.topk
        for neighbors in state.tppr.neighbors:
            indices = [[0] * k for _ in range(n)]
            deltas = [[0.0] * k for _ in range(n)]
            weights = [[0.0] * k for _ in range(n)]
            for i, entries in enumerate(neighbors):
                for j, ((_, node, timestamp), weight) in enumerate(entries.items()):
                    indices[i][j], deltas[i][j], weights[i][j] = node, cutoff - timestamp, weight
            selected = torch.tensor(indices, device=self.device, dtype=torch.long)
            times = self.time_encode(torch.tensor(deltas, device=self.device, dtype=torch.float32))
            weight = torch.tensor(weights, device=self.device, dtype=torch.float32)
            weight = weight / weight.sum(dim=1, keepdim=True).clamp_min(1e-30)
            features = torch.cat((state.memory[selected], times.new_zeros((n, k, 1)), times), dim=-1)
            transformed = self.neighbor_transform(features)
            outputs.append((transformed * weight[..., None]).sum(dim=1))
        return torch.cat(outputs, dim=1)

    def pair_logits(self, embeddings: torch.Tensor, state: ZebraState, pairs) -> torch.Tensor:
        if not pairs:
            return embeddings.new_empty((0,))
        indices = torch.tensor([(state.index[u], state.index[v]) for u, v in pairs], device=self.device)
        u, v = embeddings[indices[:, 0]], embeddings[indices[:, 1]]
        forward = self.decoder(torch.cat((u, v), dim=1)).squeeze(-1)
        reverse = self.decoder(torch.cat((v, u), dim=1)).squeeze(-1)
        return (forward + reverse) * 0.5

    def all_pairs(self, state: ZebraState, cutoff: float):
        pairs = list(combinations(state.known_accounts(), 2))
        return pairs, self.pair_logits(self.encode(state, cutoff), state, pairs)
