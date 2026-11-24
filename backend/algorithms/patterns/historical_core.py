"""Snapshot PHC-Construct and PHC-Query (Yu et al., The VLDB Journal, 2025)."""

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from operator import itemgetter

from algorithms.core.queries import core_numbers

Edge = tuple[str, str]


@dataclass
class _CoreWindow:
    """A shrinking projection. Multiplicities count snapshots containing an edge."""

    neighbors: dict[str, dict[str, int]]
    levels: dict[str, int]

    def copy(self) -> "_CoreWindow":
        return _CoreWindow({u: row.copy() for u, row in self.neighbors.items()}, self.levels.copy())

    def local_core(self, node: str) -> int:
        """Algorithm 6. Count distinct neighbors supporting each possible core level."""
        level = self.levels[node]
        counts = [0] * (level + 1)
        for neighbor in self.neighbors[node]:
            counts[min(level, self.levels[neighbor])] += 1
        support = counts[level]
        while support < level:
            level -= 1
            support += counts[level]
        return level

    def remove(self, edges: Iterable[Edge]) -> dict[str, int]:
        """Remove one time slice and return each changed vertex's previous coreness."""
        pending = set()
        for u, v in edges:
            remaining = self.neighbors[u][v] - 1
            if remaining:
                self.neighbors[u][v] = self.neighbors[v][u] = remaining
            else:
                del self.neighbors[u][v]
                del self.neighbors[v][u]
                pending.update((u, v))

        previous = {}
        while pending:
            u = pending.pop()
            old = self.levels[u]
            new = self.local_core(u)
            if new < old:
                previous.setdefault(u, old)
                self.levels[u] = new
                pending.update(v for v in self.neighbors[u] if new < self.levels[v] <= old)
        return previous


class HistoricalCoreIndex:
    """Lookup of earliest qualifying end snapshots for a fixed start and k."""

    def __init__(self, snapshots: Sequence[Iterable[Edge]]) -> None:
        frames = [
            {(min(u, v), max(u, v)) for u, v in edges if u != v}
            for edges in snapshots
        ]
        self._length = len(frames)
        self._incident: dict[str, list[int]] = defaultdict(list)
        self._windows: dict[int, dict[str, list[tuple[int, int]]]] = {}
        multiplicities = Counter()
        for time, edges in enumerate(frames):
            multiplicities.update(edges)
            active = {vertex for edge in edges for vertex in edge}
            for vertex in active:
                self._incident[vertex].append(time)
        neighbors = {u: {} for u in self._incident}
        for (u, v), count in multiplicities.items():
            neighbors[u][v] = neighbors[v][u] = count
        suffix = _CoreWindow(neighbors, core_numbers({u: set(row) for u, row in neighbors.items()}))

        for start, first_edges in enumerate(frames):
            window = suffix.copy()
            # Losing level k when dropping end makes end the earliest qualifying time.
            for end in range(self._length - 1, start - 1, -1):
                lost = window.remove(frames[end])
                self._record_losses(start, end, lost, window.levels)
            if start + 1 < self._length:
                lost = suffix.remove(first_edges)
                # A level lost from the entire suffix can never be reached again.
                self._record_losses(start + 1, self._length, lost, suffix.levels)

    def _record_losses(
        self, start: int, earliest_end: int, previous: dict[str, int], levels: dict[str, int]
    ) -> None:
        for node, old in previous.items():
            for k in range(max(2, levels[node] + 1), old + 1):
                windows = self._windows.setdefault(k, {}).setdefault(node, [])
                if not windows or earliest_end > windows[-1][1]:
                    windows.append((start, earliest_end))

    def core_times(self, start: int, end: int, k: int) -> dict[str, int]:
        """Qualifying vertices and their first qualifying end, using inclusive positions."""
        if not 0 <= start <= end < self._length or k < 1:
            raise ValueError("Choose a valid historical window and a positive k.")
        found = {}
        if k == 1:
            # For k=1 membership starts at the first incident edge in the window.
            for node, times in self._incident.items():
                i = bisect_left(times, start)
                if i < len(times) and times[i] <= end:
                    found[node] = times[i]
        else:
            for node, windows in self._windows.get(k, {}).items():
                i = bisect_right(windows, start, key=itemgetter(0)) - 1
                if i >= 0 and windows[i][1] <= end:
                    found[node] = windows[i][1]
        return found
