from collections import Counter
from urllib.parse import quote

from algorithms.core.queries import adjacency, structural_metrics
from app.schemas.analysis import SnapshotData


def graph_of(snapshot: SnapshotData) -> dict[str, set[str]]:
    return adjacency(
        snapshot.present_accounts, ((t.u, t.v) for t in snapshot.transactions)
    )


def aggregate_edges(snapshot: SnapshotData) -> list[dict]:
    counts = Counter((t.u, t.v) for t in snapshot.transactions)
    return [
        {
            "id": f"{quote(u, safe='')}:{quote(v, safe='')}",
            "u": u,
            "v": v,
            "transaction_count": count,
        }
        for (u, v), count in sorted(counts.items())
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
    return {
        **structural_metrics(adjacency(snapshot.present_accounts, pairs), members),
        "transaction_count": len(pairs),
    }
