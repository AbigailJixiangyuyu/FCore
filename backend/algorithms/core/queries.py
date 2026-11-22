"""Small, dependency-free core queries on an undirected simple projection."""

from collections.abc import Iterable


def adjacency(
    nodes: Iterable[str], pairs: Iterable[tuple[str, str]]
) -> dict[str, set[str]]:
    graph = {node: set() for node in nodes}
    for source, target in pairs:
        if source != target and source in graph and target in graph:
            graph[source].add(target)
            graph[target].add(source)
    return graph


def core_numbers(graph: dict[str, set[str]]) -> dict[str, int]:
    active = set(graph)
    degrees = {node: len(neighbors) for node, neighbors in graph.items()}
    numbers = {}
    level = 0
    while active:
        node = min(active, key=lambda item: (degrees[item], item))
        level = max(level, degrees[node])
        numbers[node] = level
        active.remove(node)
        for neighbor in graph[node] & active:
            degrees[neighbor] -= 1
    return numbers


def connected_components(
    graph: dict[str, set[str]], members: Iterable[str]
) -> list[list[str]]:
    remaining = set(members)
    components = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        component = [start]
        for node in component:
            neighbors = graph[node] & remaining
            remaining.difference_update(neighbors)
            component.extend(sorted(neighbors))
        components.append(sorted(component))
    return sorted(components, key=lambda items: (-len(items), items))


def local_core(
    graph: dict[str, set[str]],
    account: str,
    k: int,
    *,
    numbers: dict[str, int] | None = None,
) -> list[list[str]]:
    if account not in graph:
        return []
    if numbers is None:
        numbers = core_numbers(graph)
    if numbers[account] < k:
        return []
    component = [account]
    seen = {account}
    for node in component:
        for neighbor in graph[node]:
            if neighbor not in seen and numbers[neighbor] >= k:
                seen.add(neighbor)
                component.append(neighbor)
    return [sorted(component)]


def maximum_core(graph: dict[str, set[str]]) -> tuple[int, list[list[str]]]:
    numbers = core_numbers(graph)
    maximum = max(numbers.values(), default=0)
    members = [node for node, number in numbers.items() if number == maximum]
    return maximum, connected_components(graph, members)


def structural_metrics(graph: dict[str, set[str]], members: Iterable[str]) -> dict:
    selected = set(members)
    degrees = [len(graph.get(node, set()) & selected) for node in selected]
    n = len(selected)
    m = sum(degrees) // 2
    return {
        "node_count": n,
        "internal_edges": m,
        "min_degree": min(degrees, default=0),
        "density": 2 * m / (n * (n - 1)) if n > 1 else 0.0,
        "present_count": len(selected & graph.keys()),
    }


def density_candidates(graph: dict[str, set[str]], threshold: float) -> list[list[str]]:
    """Prototype heuristic; does not enumerate all dense subgraphs."""
    numbers = core_numbers(graph)
    candidates: set[tuple[str, ...]] = set()

    def add(members: Iterable[str]) -> None:
        ordered = tuple(sorted(members))
        if (
            len(ordered) >= 3
            and structural_metrics(graph, ordered)["density"] >= threshold
        ):
            candidates.add(ordered)

    for k in range(max(numbers.values(), default=0) + 1):
        active = {node for node, number in numbers.items() if number >= k}
        for component in connected_components(graph, active):
            add(component)
        for node in sorted(active):
            add({node} | (graph[node] & active))
    maximal = [
        items
        for items in candidates
        if not any(set(items) < set(other) for other in candidates)
    ]
    return [
        list(items) for items in sorted(maximal, key=lambda items: (-len(items), items))
    ]
