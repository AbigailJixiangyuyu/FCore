"""Zebra SANTA streaming top-k recurrence, using ordinary Python containers.

Temporal neighbors are (event_id, node_index, timestamp), not unique accounts.
Both endpoint updates use the state before the event, as in the author code.
"""

from copy import deepcopy


class Santa:
    def __init__(self, topk: int, metrics: tuple[tuple[float, float], ...]):
        if topk < 1 or not metrics:
            raise ValueError("T-PPR requires positive topk and at least one metric")
        if any(not 0 <= a <= 1 or not 0 < b <= 1 for a, b in metrics):
            raise ValueError("Invalid T-PPR alpha/beta")
        self.topk = topk
        self.metrics = metrics
        self.neighbors = [[] for _ in metrics]
        self.norms = [[] for _ in metrics]

    def extend(self, size: int) -> None:
        for neighbors, norms in zip(self.neighbors, self.norms):
            while len(norms) < size:
                neighbors.append({})
                norms.append(0.0)

    def update(self, source: int, target: int, timestamp: float, event_id: int) -> None:
        self.extend(max(source, target) + 1)
        for metric, (alpha, beta) in enumerate(self.metrics):
            neighbors, norms = self.neighbors[metric], self.norms[metric]
            updates = {}
            for u, v in ((source, target), (target, source)):
                if u in updates:
                    continue
                if norms[u] == 0:
                    merged, incoming_scale = {}, 1 - alpha
                else:
                    new_norm = norms[u] * beta + beta
                    old_scale = norms[u] * beta / new_norm
                    incoming_scale = beta * (1 - alpha) / new_norm
                    merged = {key: value * old_scale for key, value in neighbors[u].items()}
                for key, value in neighbors[v].items():
                    merged[key] = merged.get(key, 0.0) + incoming_scale * value
                merged[(event_id, v, timestamp)] = incoming_scale * (alpha if alpha else 1)
                # Explicit tie order makes replay independent of dict iteration order.
                ordered = sorted(merged.items(), key=lambda item: (-item[1], item[0]))
                updates[u] = dict(ordered[:self.topk])
            for node, selected in updates.items():
                neighbors[node] = selected
                norms[node] = norms[node] * beta + beta

    def payload(self) -> dict:
        return {
            "neighbors": [
                [[[*key, weight] for key, weight in node.items()] for node in metric]
                for metric in self.neighbors
            ],
            "norms": deepcopy(self.norms),
        }

    def restore(self, payload: dict) -> None:
        self.neighbors = [
            [{(int(e), int(n), float(t)): float(w) for e, n, t, w in node} for node in metric]
            for metric in payload["neighbors"]
        ]
        self.norms = deepcopy(payload["norms"])
