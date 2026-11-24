from collections import Counter
from itertools import chain
from urllib.parse import quote

from algorithms.core.queries import adjacency, structural_metrics
from app.schemas.analysis import SnapshotData


def graph_of(snapshot: SnapshotData) -> dict[str, set[str]]:
    return adjacency(
        snapshot.present_accounts,
        chain(((t.u, t.v) for t in snapshot.transactions), snapshot.static_edges or ()),
    )


def aggregate_edges(snapshot: SnapshotData) -> list[dict]:
    counts = Counter((t.u, t.v) for t in snapshot.transactions)
    static = set(snapshot.static_edges or ())
    return [
        {
            "id": f"{quote(u, safe='')}:{quote(v, safe='')}",
            "u": u,
            "v": v,
            "transaction_count": None if (u, v) in static else counts[u, v],
        }
        for u, v in sorted(counts.keys() | static)
    ]


def selection_metrics(
    snapshot: SnapshotData,
    members: list[str],
    qualified_pairs: set[tuple[str, str]] | None = None,
) -> dict:
    selected = set(members)
    pairs = [
        (t.u, t.v)
        for t in snapshot.transactions
        if t.u in selected
        and t.v in selected
        and (
            qualified_pairs is None
            or (t.u, t.v) in qualified_pairs
        )
    ]
    static = (
        (u, v) for u, v in snapshot.static_edges or ()
        if u in selected and v in selected and (qualified_pairs is None or (u, v) in qualified_pairs)
    )
    graph = adjacency(snapshot.present_accounts, chain(pairs, static))
    return {
        **structural_metrics(graph, members),
        "transaction_count": len(pairs) if snapshot.static_edges is None else None,
    }
