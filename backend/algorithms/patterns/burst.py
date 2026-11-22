"""Exact (l, delta)-MBC mining using the paper's peeling framework (MBC-B)."""

from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from algorithms.patterns.common import PatternResult, TemporalSnapshots

METHOD = "mbc-exact-segments-v1"


@dataclass(frozen=True, slots=True)
class _Segment:
    total: int
    length: int
    start: int
    end: int

    def meets(self, threshold: Fraction) -> bool:
        return self.total * threshold.denominator >= threshold.numerator * self.length


def _maximum_segment(degrees: list[int], l: int) -> _Segment:
    """Return exact MSD; ties prefer the shortest, then earliest segment."""
    prefix = [0]
    for degree in degrees:
        prefix.append(prefix[-1] + degree)

    best = _Segment(prefix[-1], len(degrees), 0, len(degrees) - 1)
    for start in range(len(degrees) - l + 1):
        for stop in range(start + l, len(degrees) + 1):
            total = prefix[stop] - prefix[start]
            length = stop - start
            difference = total * best.length - best.total * length
            if difference > 0 or (
                difference == 0 and (length, start) < (best.length, best.start)
            ):
                best = _Segment(total, length, start, stop - 1)
    return best


def _threshold(delta: float | Decimal | Fraction) -> Fraction:
    if isinstance(delta, bool) or not isinstance(delta, (int, float, Decimal, Fraction)):
        raise ValueError("delta must be a positive finite number")
    try:
        value = delta if isinstance(delta, Fraction) else Fraction(Decimal(str(delta)))
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValueError("delta must be a positive finite number") from exc
    if value <= 0:
        raise ValueError("delta must be a positive finite number")
    return value


def _core_candidates(graph: dict[str, set[str]], minimum_degree: int) -> set[str]:
    active = set(graph)
    degrees = {node: len(neighbors) for node, neighbors in graph.items()}
    queue = deque(sorted(node for node in active if degrees[node] < minimum_degree))
    while queue:
        node = queue.popleft()
        active.remove(node)
        for neighbor in graph[node] & active:
            degrees[neighbor] -= 1
            if degrees[neighbor] == minimum_degree - 1:
                queue.append(neighbor)
    return active


def mine_burst(
    snapshots: TemporalSnapshots,
    l: int = 3,
    delta: float | Decimal | Fraction = 3.0,
) -> PatternResult | None:
    """Find the unique maximal bursting core without changing the snapshots.

    Snapshots must be undirected simple graphs over the same account set, with
    missing accounts represented by isolated vertices. Empty time slots remain
    in the sequence. Evidence positions are zero-based and inclusive.
    """
    if type(l) is not int or not 2 <= l <= len(snapshots):
        raise ValueError("l must be an integer between 2 and the number of snapshots")
    threshold = _threshold(delta)
    accounts = set(snapshots[0])
    union = {
        node: set().union(*(snapshot[node] for snapshot in snapshots))
        for node in accounts
    }
    minimum_degree = (
        threshold.numerator + threshold.denominator - 1
    ) // threshold.denominator
    active = _core_candidates(union, minimum_degree)
    if not active:
        return None

    sequences = {
        node: [len(snapshot[node] & active) for snapshot in snapshots]
        for node in active
    }
    queued = {
        node
        for node in active
        if not _maximum_segment(sequences[node], l).meets(threshold)
    }
    queue = deque(sorted(queued))
    while queue:
        node = queue.popleft()
        active.remove(node)
        for neighbor in union[node] & active:
            for time, snapshot in enumerate(snapshots):
                if node in snapshot[neighbor]:
                    sequences[neighbor][time] -= 1
            if neighbor in queued:
                continue
            if not _maximum_segment(sequences[neighbor], l).meets(threshold):
                queued.add(neighbor)
                queue.append(neighbor)

    if not active:
        return None
    members = tuple(sorted(active))
    nodes = []
    for account in members:
        segment = _maximum_segment(sequences[account], l)
        nodes.append(
            {
                "account": account,
                "degree_sequence": sequences[account],
                "numerator": segment.total,
                "denominator": segment.length,
                "witness_start": segment.start,
                "witness_end": segment.end,
            }
        )
    return PatternResult(members=members, evidence={"nodes": nodes})
