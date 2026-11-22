"""ONCE temporal durable community search (Zhou et al., PVLDB 2025)."""

from algorithms.core.queries import local_core
from algorithms.patterns.common import PatternResult, TemporalSnapshots


def mine_durable(
    snapshots: TemporalSnapshots, account: str = "a-001", k: int = 4
) -> PatternResult | None:
    """Return a longest-lived connected temporal k-core containing ``account``.

    Each window uses the union of its original snapshot edges. With the start
    fixed, duration is the difference between the last unchanged end position
    and the community's formation end. All positions are zero-based, inclusive,
    and bounded by the supplied snapshots. See DURABLE.md for paper references
    and the deterministic tie and zero-duration conventions.
    """
    if not snapshots:
        raise ValueError("Durable community search requires at least one snapshot.")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer for durable community search.")
    accounts = sorted({node for snapshot in snapshots for node in snapshot})
    if account not in accounts:
        raise ValueError("The query node is absent from the historical snapshots.")

    # Each of the T(T+1)/2 projected cores is computed once. The adjacency sets
    # belong to this function; the caller's snapshots remain unchanged.
    communities: dict[tuple[int, int], tuple[str, ...]] = {}
    for start in range(len(snapshots)):
        projection = {node: set() for node in accounts}
        for end in range(start, len(snapshots)):
            for node, neighbors in snapshots[end].items():
                projection[node].update(neighbors)
            components = local_core(projection, account, k)
            communities[start, end] = tuple(components[0]) if components else ()

    best_priority = None
    last = len(snapshots) - 1
    for (start, end), members in communities.items():
        if not members:
            continue

        # Fixed-start cores only grow, so equality with the current member set
        # is a monotone predicate for ONCE's binary search.
        left, right = end, last
        while left < right:
            middle = (left + right + 1) // 2
            if communities[start, middle] == members:
                left = middle
            else:
                right = middle - 1

        duration = left - end
        priority = (-duration, start, end, members)
        if best_priority is None or priority < best_priority:
            best_priority = priority

    if best_priority is None:
        return None
    negative_duration, start, end, members = best_priority
    duration = -negative_duration
    return PatternResult(
        members=members,
        evidence={
            "formation_start": start,
            "formation_end": end,
            "stable_end": end + duration,
            "duration": duration,
            "member_count_series": [
                len(communities[start, window_end])
                for window_end in range(start, last + 1)
            ],
        },
    )
