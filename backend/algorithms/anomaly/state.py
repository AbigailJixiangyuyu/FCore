"""Request-local SLADE memory and its checkpoint representation."""

from dataclasses import dataclass

import torch
from torch import Tensor


@dataclass
class MemoryState:
    accounts: list[str]
    memory: Tensor
    previous: Tensor
    last_update: Tensor
    seen: Tensor
    neighbors: list[list[tuple[int, float]]]

    @classmethod
    def empty(cls, accounts: list[str], dimension: int, device="cpu"):
        count = len(accounts)
        return cls(
            list(accounts),
            torch.zeros(count, dimension, device=device),
            torch.zeros(count, dimension, device=device),
            torch.zeros(count, dtype=torch.float64, device=device),
            torch.zeros(count, dtype=torch.bool, device=device),
            [[] for _ in accounts],
        )

    def ensure_accounts(self, accounts):
        additions = sorted(set(accounts) - set(self.accounts))
        if not additions:
            return
        count, dimension = len(additions), self.memory.shape[1]
        self.accounts.extend(additions)
        self.memory = torch.cat((self.memory, self.memory.new_zeros(count, dimension)))
        self.previous = torch.cat(
            (self.previous, self.previous.new_zeros(count, dimension))
        )
        self.last_update = torch.cat(
            (self.last_update, self.last_update.new_zeros(count))
        )
        self.seen = torch.cat((self.seen, self.seen.new_zeros(count)))
        self.neighbors.extend([] for _ in additions)

    def detach(self):
        self.memory = self.memory.detach()
        self.previous = self.previous.detach()

    def to_payload(self):
        return {
            "accounts": list(self.accounts),
            "memory": self.memory.detach().cpu().clone(),
            "previous": self.previous.detach().cpu().clone(),
            "last_update": self.last_update.cpu().clone(),
            "seen": self.seen.cpu().clone(),
            "neighbors": [[list(item) for item in items] for items in self.neighbors],
        }

    @classmethod
    def from_payload(cls, payload, device="cpu"):
        return cls(
            list(payload["accounts"]),
            payload["memory"].to(device).clone(),
            payload["previous"].to(device).clone(),
            payload["last_update"].to(device).clone(),
            payload["seen"].to(device).clone(),
            [
                [(int(node), float(time)) for node, time in items]
                for items in payload["neighbors"]
            ],
        )
