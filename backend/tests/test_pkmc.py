from itertools import combinations, pairwise

import pytest

from algorithms.core import pkmc
from algorithms.core.queries import adjacency, core_numbers


def test_pkmc_stops_with_all_top_components_before_lower_estimates_converge(monkeypatch):
    graph = adjacency(
        "abcdefghijklm",
        [*combinations("abcd", 2), *combinations("efgh", 2), *pairwise("ijklm")],
    )
    neighbor_h_index = pkmc._neighbor_h_index
    updated = []

    def record_update(neighbors, estimates):
        value = neighbor_h_index(neighbors, estimates)
        updated.append(value)
        return value

    monkeypatch.setattr(pkmc, "_neighbor_h_index", record_update)
    assert pkmc.pkmc_maximum_core(graph) == (3, list("abcdefgh"))
    assert len(updated) == len(graph)
    # The middle of the path still estimates 2 in round one, but its core number is 1.
    assert updated[list(graph).index("k")] == 2


@pytest.mark.parametrize(
    "nodes,edges",
    [
        ("", []),
        ("ab", []),
        ("abcdefg", [("a", "b"), ("b", "c"), ("a", "d"), ("a", "e"), ("c", "f"), ("c", "g")]),
        ("abcdefgh", [*combinations("abc", 2), *pairwise("defgh")]),
    ],
    ids=["empty", "zero_core", "insufficient_top_members", "stable_order_shrinking_members"],
)
def test_pkmc_matches_full_decomposition(nodes, edges):
    graph = adjacency(nodes, edges)
    numbers = core_numbers(graph)
    order = max(numbers.values(), default=0)
    assert pkmc.pkmc_maximum_core(graph) == (
        order, sorted(node for node, number in numbers.items() if number == order)
    )
