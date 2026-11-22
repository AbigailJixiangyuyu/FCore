"""Online (k, t, f)-core query from Du et al. (ICDE 2025)."""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from algorithms.core.queries import adjacency, core_numbers
from algorithms.patterns.common import PatternResult, TemporalSnapshots


@dataclass(frozen=True, slots=True)
class FrequencyWitness:
    start: int
    end: int
    count: int

    @property
    def span(self) -> int:
        return self.end - self.start + 1

    @property
    def frequency(self) -> Fraction:
        return Fraction(self.count, self.span)


def _best_window(timestamps: list[int], t: int) -> FrequencyWitness | None:
    # A window with fixed endpoints is densest when it includes every hit inside.
    windows = (
        FrequencyWitness(timestamps[first], timestamps[last], last - first + 1)
        for last in range(t - 1, len(timestamps))
        for first in range(last - t + 2)
    )
    return max(
        windows,
        key=lambda window: (window.frequency, -window.span, -window.start),
        default=None,
    )


def mine_frequency(
    snapshots: TemporalSnapshots, k: int, t: int, f: float
) -> PatternResult | None:
    """Find the maximal frequency-aware core using snapshot positions as time."""
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    if type(t) is not int or not 1 <= t <= len(snapshots):
        raise ValueError("t must be an integer between 1 and the number of snapshots")
    if not 0 <= f <= 1:
        raise ValueError("f must be between 0 and 1")
    threshold = Fraction(str(f))

    timestamps: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, snapshot in enumerate(snapshots):
        for u, neighbors in snapshot.items():
            for v in neighbors:
                if u < v:
                    timestamps[u, v].append(index)
    # Use the static k-core as a necessary filter before computing frequencies.
    union = adjacency({u for edge in timestamps for u in edge}, timestamps)
    candidates = {u for u, number in core_numbers(union).items() if number >= k}
    qualified = {}
    for (u, v), times in timestamps.items():
        if u in candidates and v in candidates:
            witness = _best_window(times, t)
            if witness is not None and witness.frequency >= threshold:
                qualified[u, v] = witness

    graph = adjacency(candidates, qualified)
    members = tuple(
        sorted(u for u, number in core_numbers(graph).items() if number >= k)
    )
    if not members:
        return None
    selected = set(members)
    return PatternResult(
        members=members,
        evidence={
            "qualified_edges": [
                {
                    "u": u,
                    "v": v,
                    "numerator": witness.count,
                    "denominator": witness.span,
                    "witness_start": witness.start,
                    "witness_end": witness.end,
                }
                for (u, v), witness in sorted(qualified.items())
                if u in selected and v in selected
            ],
        },
    )
