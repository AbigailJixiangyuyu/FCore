from itertools import combinations
from random import Random

from algorithms.core.queries import core_numbers
from algorithms.patterns.burst import mine_burst
from algorithms.patterns.common import PatternResult, TemporalSnapshots
from algorithms.patterns.durable import mine_durable
from algorithms.patterns.frequency import mine_frequency
from algorithms.patterns.periodic import mine_periodic
from algorithms.patterns.temporal_core import mine_temporal_cores


def snapshots_for(nodes, frames) -> TemporalSnapshots:
    snapshots = []
    for edges in frames:
        graph = {node: set() for node in nodes}
        for u, v in edges:
            graph[u].add(v)
            graph[v].add(u)
        snapshots.append({node: frozenset(neighbors) for node, neighbors in graph.items()})
    return tuple(snapshots)


def test_periodic_paper_sequence_keeps_three_complete_cycles():
    sequence = "1001001001"
    edges = list(combinations("abc", 2))
    snapshots = snapshots_for("abc", [edges if bit == "1" else [] for bit in sequence])
    result = mine_periodic(snapshots, "a", 2, 0.8)
    assert result is not None
    assert result.members == ("a", "b", "c")
    evidence = result.evidence
    assert evidence["kcore_series"] == list(map(int, sequence))
    assert (evidence["period"], evidence["frequency"]) == (3, 3)
    assert (evidence["start_index"], evidence["end_index"]) == (0, 8)


def test_durable_paper_example_stops_before_the_core_grows():
    snapshots = snapshots_for(
        ("v1", "v2", "v3", "v4", "v6"),
        [
            [("v1", "v2"), ("v2", "v3")],
            [("v1", "v3")],
            [],
            [],
            [("v1", "v4"), ("v3", "v4"), ("v1", "v6"), ("v3", "v6")],
            [],
        ],
    )
    assert mine_durable(snapshots, "v2", 2) == PatternResult(
        ("v1", "v2", "v3"),
        {
            "formation_start": 0,
            "formation_end": 1,
            "stable_end": 3,
            "duration": 2,
            "member_count_series": [0, 3, 3, 3, 5, 5],
        },
    )


def test_burst_paper_example_recomputes_evidence_after_peeling():
    core = ["v1", "v2", "v3", "v4", "v5"]
    outer = ["v5", "v6", "v7"]
    burst = ["v1", "v2", "v4", "v5"]
    snapshots = snapshots_for(
        [f"v{index}" for index in range(1, 8)],
        [combinations(nodes, 2) for nodes in (core, outer, burst, core, core, outer)],
    )
    result = mine_burst(snapshots)
    assert result is not None
    assert result.members == tuple(burst)
    for node in result.evidence["nodes"]:
        assert node["degree_sequence"] == [3, 0, 3, 3, 3, 0]
        assert (node["numerator"], node["denominator"]) == (9, 3)
        assert (node["witness_start"], node["witness_end"]) == (2, 4)


def test_frequency_paper_example_counts_both_window_endpoints():
    snapshots = snapshots_for(
        "ab", [[("a", "b")] if time in {2, 5, 9, 13} else [] for time in range(1, 14)]
    )
    result = mine_frequency(snapshots, k=1, t=3, f=0.375)
    assert result is not None
    assert result.members == ("a", "b")
    assert result.evidence["qualified_edges"] == [
        {"u": "a", "v": "b", "numerator": 3, "denominator": 8, "witness_start": 1, "witness_end": 8}
    ]
    assert mine_frequency(snapshots, k=1, t=3, f=0.375001) is None


def test_temporal_cores_keep_time_edges_and_remove_equivalent_windows():
    triangle = list(combinations("abc", 2))
    snapshots = snapshots_for("abcde", [[], triangle, [("d", "e")], triangle, []])
    results = mine_temporal_cores(snapshots, k=2)
    assert results == [
        PatternResult(tuple("abc"), {"witness_start": start, "witness_end": end})
        for start, end in ((1, 1), (3, 3), (1, 3))
    ]

    # Two incomplete snapshot graphs form a core together. Repeated links and
    # isolated nodes do not raise core degree.
    two_triangles = snapshots_for("abcdefg", [
        [("a", "b"), ("b", "c"), ("d", "e"), ("e", "f")],
        [("a", "c"), ("a", "c"), ("d", "f")],
    ])
    assert mine_temporal_cores(two_triangles, k=2) == [
        PatternResult(tuple("abcdef"), {"witness_start": 0, "witness_end": 1})
    ]
    assert mine_temporal_cores(two_triangles, k=3) == []


def exhaustive_temporal_windows(snapshots, k):
    results = {}
    for start in range(len(snapshots)):
        for end in range(start, len(snapshots)):
            graph = {
                node: set().union(*(frame[node] for frame in snapshots[start : end + 1]))
                for node in snapshots[start]
            }
            members = tuple(sorted(node for node, number in core_numbers(graph).items() if number >= k))
            if not members:
                continue
            member_set = set(members)
            times = [
                time for time in range(start, end + 1)
                if any(snapshots[time][node] & member_set for node in members)
            ]
            results[times[0], times[-1]] = members
    return results


def test_temporal_core_pruning_matches_independent_window_enumeration():
    rng = Random(20261122)
    nodes = "abcdef"
    pairs = list(combinations(nodes, 2))
    for _ in range(60):
        probabilities = [rng.choice((0.0, 0.15, 0.35, 0.6)) for _ in range(7)]
        snapshots = snapshots_for(nodes, [
            [pair for pair in pairs if rng.random() < probability]
            for probability in probabilities
        ])
        for k in (1, 2, 3, 4):
            results = mine_temporal_cores(snapshots, k)
            assert {
                (result.evidence["witness_start"], result.evidence["witness_end"]): result.members
                for result in results
            } == exhaustive_temporal_windows(snapshots, k)
