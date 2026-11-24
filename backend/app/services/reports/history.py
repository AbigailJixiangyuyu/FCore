"""Describe the pattern witnessed by the submitted historical result."""

from collections import Counter
from collections.abc import Callable

from app.schemas.analysis import Structure


_METHODS = {
    "periodic": "TD", "durable": "ONCE", "burst": "MBC-B",
    "frequency": "OL", "temporal_core": "OTCD", "historical_core": "PHC-Query",
}


def window(start: str, end: str) -> str:
    return start if start == end else f"{start}–{end}"


def submitted_history_evidence(
    history: Structure, alias: Callable[[str], str],
) -> dict:
    parameters, evidence = history.parameters, history.evidence
    snapshot_ids = evidence["analysis_snapshot_ids"]
    pattern = parameters["pattern"]
    record = {
        "id": "H01",
        "topic": history.label,
        "method": _METHODS[pattern],
        "analysis_window": window(snapshot_ids[0], snapshot_ids[-1]),
        "member_count": len(history.members),
    }
    if pattern == "historical_core":
        record.update(
            internal_edges=history.metrics["internal_edges"],
            min_internal_degree=history.metrics["min_degree"],
            members_in_a_k_core_by_window_end=dict(zip(snapshot_ids, evidence["qualifying_member_counts"])),
        )
    elif pattern == "periodic":
        record.update(
            period_snapshots=evidence["period"],
            cycles=evidence["frequency"],
            periodic_window=window(evidence["start_index_snapshot_id"], evidence["end_index_snapshot_id"]),
            community_present_snapshots=[
                sid for sid, present in zip(snapshot_ids, evidence["kcore_series"]) if present
            ],
        )
    elif pattern == "durable":
        first = evidence["formation_start_snapshot_id"]
        last = evidence["stable_end_snapshot_id"]
        record.update(
            formation_window=window(first, evidence["formation_end_snapshot_id"]),
            stable_through=last,
            stable_snapshots=evidence["duration"],
        )
    elif pattern == "burst":
        witnesses = evidence["nodes"]
        witness = next((row for row in witnesses if row["account"] == parameters.get("account")), None)
        if witness is None:
            witness = max(witnesses, key=lambda row: row["max_average_degree"])
        windows = Counter(window(row["witness_start_snapshot_id"], row["witness_end_snapshot_id"]) for row in witnesses)
        most_members = max(windows.values())
        record.update(
            witness_node=alias(witness["account"]),
            witness_max_average_degree=round(witness["max_average_degree"], 2),
            burst_witness_window=window(witness["witness_start_snapshot_id"], witness["witness_end_snapshot_id"]),
            most_common_member_witness_windows=sorted(name for name, count in windows.items() if count == most_members),
            members_per_most_common_window=most_members,
        )
    elif pattern == "frequency":
        edges = evidence["qualified_edges"]
        degree = Counter(node for edge in edges for node in (edge["u"], edge["v"]))
        record.update(
            qualified_internal_edges=len(edges),
            min_qualified_neighbors=min(degree[node] for node in history.members),
            weakest_qualified_frequency=round(min(edge["frequency"] for edge in edges), 4),
        )
    elif pattern == "temporal_core":
        first, last = evidence["witness_start_snapshot_id"], evidence["witness_end_snapshot_id"]
        record.update(
            tightest_window=window(first, last),
            tightest_internal_edges=history.metrics["internal_edges"],
            min_internal_degree_by_window=[
                {
                    "window": window(row["start_snapshot_id"], row["end_snapshot_id"]),
                    "min_internal_degree": row["min_internal_degree"],
                }
                for row in evidence["window_comparison"]
            ],
        )

    return record
