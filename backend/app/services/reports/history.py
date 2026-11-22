"""Supply the actual criterion for each selected historical algorithm."""

from collections import Counter


def window(start: str, end: str) -> str:
    return start if start == end else f"{start}–{end}"


def history_facts(history, facts):
    p, e = history.parameters, history.evidence
    ids = e["analysis_snapshot_ids"]
    values = facts.values
    values.update(history_method=history.label, history_size=len(history.members), mining_window=window(ids[0], ids[-1]))
    if p.get("account") is not None:
        facts.node("history_query_node", p["account"])
    for key in ("k", "epsilon", "l", "delta", "t", "f"):
        if key in p:
            values[f"history_{key}"] = p[key]

    pattern = p["pattern"]
    if pattern == "periodic":
        values.update(period_snapshots=e["period"], cycles=e["frequency"],
                      periodic_window=window(e["start_index_snapshot_id"], e["end_index_snapshot_id"]),
                      presence_by_snapshot=", ".join(f"{sid}={int(bit)}" for sid, bit in zip(ids, e["kcore_series"])))
    elif pattern == "durable":
        values.update(formation_window=window(e["formation_start_snapshot_id"], e["formation_end_snapshot_id"]),
                      stable_through=e["stable_end_snapshot_id"], stable_snapshots=e["duration"])
    elif pattern == "burst":
        # A witness belongs to one member. Prefer the submitted query node.
        witnesses = e["nodes"]
        witness = next((w for w in witnesses if w["account"] == p.get("account")), None)
        if witness is None:
            witness = max(witnesses, key=lambda w: w["max_average_degree"])
        facts.node("burst_witness_node", witness["account"])
        values.update(witness_max_average_degree=f'{witness["max_average_degree"]:.2f}',
                      burst_witness_window=window(witness["witness_start_snapshot_id"], witness["witness_end_snapshot_id"]))
    elif pattern == "frequency":
        edges = e["qualified_edges"]
        degree = Counter(node for edge in edges for node in (edge["u"], edge["v"]))
        values.update(qualified_internal_edges=len(edges), min_qualified_neighbors=min(degree[n] for n in history.members),
                      weakest_qualified_frequency=f'{min(edge["frequency"] for edge in edges):.1%}')
    elif pattern == "temporal_core":
        values.update(tightest_window=window(e["witness_start_snapshot_id"], e["witness_end_snapshot_id"]),
                      tightest_internal_edges=history.metrics["internal_edges"])
        comparison = e["window_comparison"]
        labels = ("full",) if len(comparison) == 1 else ("without_last", "without_first", "full")
        for label, row in zip(labels, comparison):
            values[f"{label}_window"] = window(row["start_snapshot_id"], row["end_snapshot_id"])
            values[f"{label}_min_internal_degree"] = row["min_internal_degree"]
            values[f"{label}_members_below_k"] = row["below_k_members"]
