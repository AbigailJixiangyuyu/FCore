"""SLADE, KDD 2024, equations (1)--(10). Request-local memory on an explicit device."""

from dataclasses import dataclass

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from .events import Event, chronological_batches
from .state import MemoryState

METHOD = "slade-v1"


@dataclass(frozen=True, slots=True)
class SladeConfig:
    memory_dim: int = 256
    message_dim: int = 128
    neighbors: int = 20
    heads: int = 2
    dropout: float = 0.1
    alpha: float = 10.0
    beta: float = 25.6
    learning_rate: float = 3e-6
    weight_decay: float = 1e-4
    lr_decay: float = 0.8
    epochs: int = 10
    batch_size: int = 100
    seed: int = 20261116
    contrast_weight: float = 1.0
    generation_weight: float = 0.1

    def __post_init__(self):
        if (
            min(
                self.memory_dim,
                self.message_dim,
                self.neighbors,
                self.heads,
                self.epochs,
                self.batch_size,
            )
            < 1
            or self.memory_dim % self.heads
        ):
            raise ValueError("Invalid SLADE dimensions, batch size, or epoch count.")
        if not 0 <= self.dropout < 1 or self.alpha <= 0 or self.beta <= 0:
            raise ValueError("Invalid SLADE encoding or dropout configuration.")


class FixedTimeEncoding(nn.Module):
    def __init__(self, config: SladeConfig):
        super().__init__()
        # Paper equation (2): alpha^(-j / beta), not the reference code's linspace(0, 9).
        self.register_buffer(
            "frequencies",
            config.alpha
            ** (-torch.arange(config.memory_dim, dtype=torch.float64) / config.beta),
        )

    def forward(self, deltas: Tensor) -> Tensor:
        return torch.cos(
            deltas.to(torch.float64).unsqueeze(-1) * self.frequencies
        ).float()


def contrastive_loss(query: Tensor, positive: Tensor, negatives: Tensor) -> Tensor:
    """Equations (4)/(5), including the observed node itself in the denominator."""
    query = F.normalize(query, dim=-1)
    positive = F.normalize(positive, dim=-1)
    negatives = F.normalize(negatives, dim=-1)
    return torch.logsumexp(query @ negatives.T, dim=-1) - (query * positive).sum(-1)


def anomaly_scores(memory: Tensor, previous: Tensor, generated: Tensor):
    contrast = 1 - F.cosine_similarity(memory, previous, dim=-1).clamp(-1, 1)
    generation = 1 - F.cosine_similarity(memory, generated, dim=-1).clamp(-1, 1)
    return (contrast + generation) / 4, contrast, generation


class Slade(nn.Module):
    def __init__(self, config: SladeConfig):
        super().__init__()
        self.config = config
        dimension = config.memory_dim
        self.time_encoding = FixedTimeEncoding(config)
        self.message = nn.Sequential(
            nn.Linear(2 * dimension, dimension),
            nn.ReLU(),
            nn.Linear(dimension, config.message_dim),
        )
        self.updater = nn.GRUCell(config.message_dim, dimension)
        self.attention = nn.MultiheadAttention(
            dimension,
            config.heads,
            kdim=2 * dimension,
            vdim=2 * dimension,
            dropout=config.dropout,
            batch_first=True,
        )

    def generate(
        self, state: MemoryState, nodes: Tensor, timestamp: float | Tensor
    ) -> Tensor:
        count, limit = len(nodes), self.config.neighbors
        device = state.memory.device
        timestamps = torch.as_tensor(
            timestamp, dtype=torch.float64, device=device
        ).expand(count)
        index_rows, time_rows, mask_rows = [], [], []
        for node, query_time in zip(nodes.tolist(), timestamps.tolist()):
            history = [
                (other, time)
                for other, time in state.neighbors[node]
                if time < query_time
            ][-limit:]
            padding = limit - len(history)
            index_rows.append([other for other, _ in history] + [0] * padding)
            time_rows.append([time for _, time in history] + [0.0] * padding)
            mask_rows.append([False] * len(history) + [True] * padding)
        indices = torch.tensor(index_rows, dtype=torch.long, device=device)
        times = torch.tensor(time_rows, dtype=torch.float64, device=device)
        mask = torch.tensor(mask_rows, dtype=torch.bool, device=device)
        memories = state.memory[indices]
        # Mask the target memory even when a self-interaction appears as a neighbor.
        memories = memories.masked_fill((indices == nodes[:, None]).unsqueeze(-1), 0)
        values = torch.cat(
            (memories, self.time_encoding(timestamps[:, None] - times)), dim=-1
        )
        invalid = mask.all(dim=1)
        safe_mask = mask.clone()
        safe_mask[invalid, 0] = False
        query = self.time_encoding(
            torch.zeros(count, 1, dtype=torch.float64, device=device)
        )
        generated, _ = self.attention(
            query, values, values, key_padding_mask=safe_mask, need_weights=False
        )
        return generated[:, 0, :].masked_fill(invalid[:, None], 0)

    def advance(
        self, state: MemoryState, events: tuple[Event, ...]
    ) -> tuple[Tensor, Tensor, Tensor]:
        if not events:
            raise ValueError("The update batch must contain events.")
        state.ensure_accounts(a for event in events for a in (event.u, event.v))
        mapping = {account: index for index, account in enumerate(state.accounts)}
        device = state.memory.device
        u_ids = [mapping[event.u] for event in events]
        v_ids = [mapping[event.v] for event in events]
        u = torch.tensor(u_ids, device=device)
        v = torch.tensor(v_ids, device=device)
        times = torch.tensor(
            [event.timestamp for event in events], dtype=torch.float64, device=device
        )
        nodes, others = torch.cat((u, v)), torch.cat((v, u))
        endpoint_times = times.repeat(2)
        if torch.any(endpoint_times < state.last_update[nodes]):
            raise ValueError("Cannot write earlier interactions to the node memory.")
        raw = torch.cat(
            (
                state.memory[others],
                self.time_encoding(endpoint_times - state.last_update[nodes]),
            ),
            dim=-1,
        )
        unique, inverse, counts = torch.unique(
            nodes, sorted=True, return_inverse=True, return_counts=True
        )
        pooled = raw.new_zeros((len(unique), raw.shape[1])).index_add(0, inverse, raw)
        pooled = pooled / counts[:, None]
        before = state.memory
        updated = self.updater(self.message(pooled), before[unique])
        state.previous = state.previous.index_copy(0, unique, before[unique])
        state.memory = before.index_copy(0, unique, updated)
        last = state.last_update[unique].clone()
        last.scatter_reduce_(
            0, inverse, endpoint_times, reduce="amax", include_self=True
        )
        state.last_update[unique] = last
        state.seen[unique] = True
        for event, first, second in zip(events, u_ids, v_ids):
            state.neighbors[first].append((second, event.timestamp))
            state.neighbors[second].append((first, event.timestamp))
        for node in unique.tolist():
            state.neighbors[node] = state.neighbors[node][-self.config.neighbors :]
        return u, v, before

    def training_loss(
        self,
        state: MemoryState,
        events: tuple[Event, ...],
        previous_events: tuple[Event, ...] = (),
    ) -> Tensor:
        """Paper section 4.2: only earlier batches may update the current memory."""
        state.ensure_accounts(a for event in events for a in (event.u, event.v))
        before = state.memory
        if previous_events:
            self.advance(state, previous_events)
        mapping = {account: index for index, account in enumerate(state.accounts)}
        device = state.memory.device
        nodes = torch.tensor(
            [mapping[event.u] for event in events] + [mapping[event.v] for event in events],
            device=device,
        )
        query_times = torch.tensor(
            [event.timestamp for event in events], dtype=torch.float64, device=device
        ).repeat(2)
        generated = self.generate(state, nodes, query_times)
        observed = state.seen.clone()
        observed[nodes] = True
        memory, negatives = state.memory[nodes], state.memory[observed]
        contrast = contrastive_loss(memory, before[nodes], negatives)
        generation = contrastive_loss(generated, memory, negatives)
        # One event contributes the two endpoint losses with equal weights.
        config = self.config
        return (config.contrast_weight * contrast + config.generation_weight * generation).sum() / len(events)

    def replay(self, state: MemoryState, events: tuple[Event, ...]):
        """Timestamp batches of size one: simultaneous events are still pooled together."""
        with torch.no_grad():
            for batch in chronological_batches(events, 1):
                self.advance(state, batch)

    def score(self, state: MemoryState, accounts: list[str], timestamp: float):
        if torch.any(state.last_update[state.seen] >= timestamp):
            raise ValueError("The scoring cutoff must be later than all interactions in memory.")
        mapping = {account: index for index, account in enumerate(state.accounts)}
        valid, unscored = [], []
        seen = state.seen.tolist()
        for account in sorted(accounts):
            if account in mapping and seen[mapping[account]]:
                valid.append(account)
            else:
                unscored.append(
                    {"account_id": account, "reason": "no_interaction_history"}
                )
        if not valid:
            return [], unscored
        nodes = torch.tensor(
            [mapping[account] for account in valid], device=state.memory.device
        )
        with torch.no_grad():
            generated = self.generate(state, nodes, timestamp)
            total, contrast, generation = anomaly_scores(
                state.memory[nodes], state.previous[nodes], generated
            )
        values = torch.stack((total, contrast, generation), dim=1).tolist()
        rows = [
            {
                "account_id": account,
                "score": scores[0],
                "temporal_contrast_score": scores[1],
                "memory_generation_score": scores[2],
            }
            for account, scores in zip(valid, values)
        ]
        rows.sort(key=lambda row: (-row["score"], row["account_id"]))
        return [{"rank": rank, **row} for rank, row in enumerate(rows, 1)], unscored
