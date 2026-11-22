"""Time-range k-core queries with snapshot positions as timestamps."""

from collections import defaultdict, deque

from algorithms.patterns.common import PatternResult, TemporalSnapshots

TimedEdges = dict[int, tuple[tuple[str, str], ...]]


def _truncate_and_peel(
    parent: TimedEdges, start: int, end: int, k: int
) -> tuple[tuple[str, ...], TimedEdges]:
    window = {time: edges for time, edges in parent.items() if start <= time <= end}
    neighbors: dict[str, set[str]] = defaultdict(set)
    for edges in window.values():
        for u, v in edges:
            neighbors[u].add(v)
            neighbors[v].add(u)

    queue = deque(node for node, adjacent in neighbors.items() if len(adjacent) < k)
    while queue:
        node = queue.popleft()
        for other in neighbors.pop(node):
            adjacent = neighbors[other]
            adjacent.remove(node)
            if len(adjacent) == k - 1:
                queue.append(other)

    core_edges = {}
    for time, edges in window.items():
        internal = tuple((u, v) for u, v in edges if u in neighbors and v in neighbors)
        if internal:
            core_edges[time] = internal
    return tuple(sorted(neighbors)), core_edges


def _prune_equivalent_windows(
    schedule: list[set[int]], start: int, end: int, first: int, last: int
) -> None:
    # Algorithm 3: PoR, PoU, and PoL, in the paper's start/end schedule.
    schedule[start].difference_update(range(last, end))
    for later_start in range(start + 1, first + 1):
        schedule[later_start].difference_update(range(later_start, end + 1))
    if first > start and last < end:
        for later_start in range(first + 1, last + 1):
            schedule[later_start].difference_update(range(last + 1, end + 1))


def mine_temporal_cores(snapshots: TemporalSnapshots, k: int) -> list[PatternResult]:
    """Enumerate distinct temporal cores ordered by span, size, then start."""
    if type(k) is not int or k < 1:
        raise ValueError("Core k must be a positive integer.")

    edges_by_time = {
        time: tuple((u, v) for u, neighbors in graph.items() for v in neighbors if u < v)
        for time, graph in enumerate(snapshots)
    }
    schedule = [set(range(start, len(snapshots))) for start in range(len(snapshots))]
    anchors = [(len(snapshots) - 1, edges_by_time)]
    results: dict[tuple[int, int], PatternResult] = {}

    for start, ends in enumerate(schedule):
        if not ends:
            continue
        row_end = max(ends)
        # A previous row may have lost its widest cells to pruning. Use the
        # latest anchor that still covers this row's first window.
        parent = next(edges for end, edges in reversed(anchors) if end >= row_end)
        for end in sorted(ends, reverse=True):
            if end not in ends:
                continue
            members, parent = _truncate_and_peel(parent, start, end, k)
            if not members:
                for later_start in range(start + 1, end + 1):
                    schedule[later_start].difference_update(range(later_start, end + 1))
                break
            if end == row_end:
                anchors.append((end, parent))
            first, last = min(parent), max(parent)
            results.setdefault(
                (first, last),
                PatternResult(members, {"witness_start": first, "witness_end": last}),
            )
            _prune_equivalent_windows(schedule, start, end, first, last)

    ordered = sorted(results, key=lambda bounds: (
        bounds[1] - bounds[0], len(results[bounds].members), bounds[0]
    ))
    return [results[bounds] for bounds in ordered]
