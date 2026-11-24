"""Evaluate PHC membership and materialize its connected communities in the query window."""

from collections import Counter, OrderedDict
from itertools import accumulate
from threading import Lock

from algorithms.core.queries import adjacency, connected_components, structural_metrics
from algorithms.patterns.historical_core import HistoricalCoreIndex
from app.schemas.analysis import HistoricalCorePatternQuery
from app.services.context import AnalysisScope
from app.services.structures import COLORS, make_structure

METHOD = "phc-query-v1"
_index_lock = Lock()
_index_cache = OrderedDict()


def _indexed_history(scope: AnalysisScope, snapshot_ids: tuple[str, ...]):
    key = (scope.repository.data_dir, scope.context.dataset_id, scope.context.dataset_version, snapshot_ids)
    with _index_lock:
        if key not in _index_cache:
            frames, static_ids = [], set()
            for snapshot_id in snapshot_ids:
                snapshot = scope.repository.snapshot(scope.context.dataset_id, snapshot_id)
                counts = Counter((event.u, event.v) for event in snapshot.transactions)
                if snapshot.static_edges is not None:
                    counts.update(snapshot.static_edges)
                    static_ids.add(snapshot_id)
                frames.append(counts)
            _index_cache[key] = HistoricalCoreIndex(frames), frames, static_ids
            if len(_index_cache) > 4:
                _index_cache.popitem(last=False)
        _index_cache.move_to_end(key)
        return _index_cache[key]


def historical_cores(
    scope: AnalysisScope,
    request: HistoricalCorePatternQuery,
    history_ids: tuple[str, ...],
    window_ids: list[str],
) -> dict:
    index, frames, static_ids = _indexed_history(scope, history_ids)
    start, end = history_ids.index(window_ids[0]), history_ids.index(window_ids[-1])
    core_times = index.core_times(start, end, request.k)
    counts = Counter()
    if core_times:
        for frame in frames[start : end + 1]:
            counts.update(frame)
    graph = adjacency(core_times, counts)
    parameters = {
        "pattern": request.pattern, "k": request.k,
        "start_snapshot_id": window_ids[0], "end_snapshot_id": window_ids[-1],
    }
    structures = []
    for rank, members in enumerate(connected_components(graph, core_times), start=1):
        # In the induced graph every neighbor belongs to the same component.
        metrics = structural_metrics(graph, members)
        metrics["transaction_count"] = (
            None if static_ids.intersection(window_ids)
            else sum(counts[u, v] for u in members for v in graph[u] if u < v)
        )
        first_ends = Counter(core_times[u] for u in members)
        qualifying_counts = list(accumulate(first_ends[i] for i in range(start, end + 1)))
        structure = make_structure(
            scope, f"PHC:{window_ids[0]}:{window_ids[-1]}:{rank}", members,
            "pattern", parameters, "computed", METHOD, COLORS[0],
            snapshot_id=window_ids[-1], metrics=metrics,
            evidence={"analysis_snapshot_ids": window_ids, "qualifying_member_counts": qualifying_counts},
        )
        structure.label = "Historical k-Core"
        structures.append(structure)
    return {
        **scope.metadata("computed", METHOD),
        "analysis_snapshot_ids": window_ids,
        "reference_snapshot_id": window_ids[-1],
        "structures": structures,
        "message": "" if structures else f"No {request.k}-core in the selected historical window.",
    }
