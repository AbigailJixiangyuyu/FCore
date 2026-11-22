"""Synchronous PKMC from Luo et al. (ICDE 2023), Algorithm 2."""

METHOD = "pkmc-v1"


def _neighbor_h_index(neighbors: set[str], estimates: dict[str, int]) -> int:
    degree = len(neighbors)
    counts = [0] * (degree + 1)
    for neighbor in neighbors:
        counts[min(degree, estimates[neighbor])] += 1

    at_least = 0
    for level in range(degree, 0, -1):
        at_least += counts[level]
        if at_least >= level:
            return level
    return 0


def pkmc_maximum_core(graph: dict[str, set[str]]) -> tuple[int, list[str]]:
    """Find the order and all vertices of the highest core of a simple graph."""
    if not graph:
        return 0, []

    estimates = {node: len(neighbors) for node, neighbors in graph.items()}
    maximum = max(estimates.values())
    members = {node for node, value in estimates.items() if value == maximum}
    while True:
        updated = {
            node: _neighbor_h_index(neighbors, estimates)
            for node, neighbors in graph.items()
        }
        next_maximum = max(updated.values())
        next_members = {node for node, value in updated.items() if value == next_maximum}
        # Theorem 1 certifies the highest core before lower estimates converge.
        if (
            len(next_members) > next_maximum
            and next_maximum == maximum
            and next_members == members
        ):
            return next_maximum, sorted(next_members)
        estimates, maximum, members = updated, next_maximum, next_members
