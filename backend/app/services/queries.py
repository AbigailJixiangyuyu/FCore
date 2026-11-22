"""Core queries on S12 and its retrospective windows."""

from fastapi import HTTPException

from algorithms.core.parallel import METHOD as PARALLEL_CORE_METHOD
from algorithms.core.pkmc import METHOD as PKMC_METHOD
from algorithms.core.pkmc import pkmc_maximum_core
from algorithms.core.queries import density_candidates, local_core, maximum_core
from app.schemas.analysis import DensityQuery, LocalCoreQuery, MaxCoreQuery, SnapshotQuery
from app.services.context import AnalysisScope
from app.services.graphs import graph_payload, observed_window, window_bounds
from app.services.parallel_core import ParallelCoreCache
from app.services.statistics import graph_of
from app.services.structures import COLORS, make_structure


def query_structures(
    scope: AnalysisScope,
    request: SnapshotQuery,
    parallel_core: ParallelCoreCache,
    *,
    include_window_graph: bool = True,
) -> dict:
    local_query = request if isinstance(request, LocalCoreQuery) else None
    use_pkmc = isinstance(request, MaxCoreQuery) and request.algorithm == "pkmc"
    start_snapshot_id = request.snapshot_id
    if local_query and local_query.start_snapshot_id is not None:
        start_snapshot_id = local_query.start_snapshot_id
    start, end = window_bounds(scope, start_snapshot_id, request.snapshot_id)
    if end.snapshot_id != scope.manifest.observed_until or (
        use_pkmc and end.snapshot_id != "S12"
    ):
        raise HTTPException(422, "The current query range must end at S12.")
    use_tccs = False
    if local_query:
        spans_snapshots = start.snapshot_id != end.snapshot_id
        if spans_snapshots and local_query.algorithm == "parallel":
            raise HTTPException(422, "Parallel core decomposition runs on S12 only.")
        use_tccs = spans_snapshots or local_query.algorithm == "tccs"

    numbers = None
    if local_query and not use_tccs:
        index = parallel_core.index(scope.repository, scope.context, local_query.account)
        frame, graph, numbers = index.frame, index.graph, index.numbers
        snapshot_ids = [end.snapshot_id]
    else:
        frame, snapshot_ids = observed_window(scope, start, end)
        graph = graph_of(frame)
    result_kind = "computed"
    if local_query:
        if use_tccs and local_query.account not in graph:
            raise HTTPException(422, "The query node is absent from the selected range.")
        origin = "local_core"
        parameters = {"account": local_query.account, "k": local_query.k}
        if local_query.algorithm is not None:
            parameters["algorithm"] = local_query.algorithm
        components = local_core(graph, local_query.account, local_query.k, numbers=numbers)
        prefix, method = "L", PARALLEL_CORE_METHOD
        description = "Decompose the undirected S12 graph in parallel and return the k-core component containing q."
        if use_tccs:
            parameters["start_snapshot_id"] = start.snapshot_id
            method = "tccs-online-v1"
            description = "Return the k-core component containing q in the undirected graph of the selected window."
    elif isinstance(request, DensityQuery):
        origin = "density"
        parameters = {"threshold": request.threshold}
        components = density_candidates(graph, request.threshold)
        prefix, method = "R", "core-neighborhood-density-demo-v1"
        result_kind = "demo_heuristic"
        description = "Demo heuristic that filters core components and closed one-hop neighborhoods by density."
    else:
        origin = "max_core"
        prefix = "M"
        if use_pkmc:
            maximum, members = pkmc_maximum_core(graph)
            components = [members] if members else []
            parameters = {"algorithm": "pkmc", "max_core": maximum}
            method = PKMC_METHOD
            description = "Run PKMC on the undirected S12 graph and return the entire highest nonempty core."
        else:
            maximum, components = maximum_core(graph)
            parameters = {"max_core": maximum}
            method = "maximum-core-v1"
            description = "Return the highest nonempty core and its connected components in the current graph."
    structures = [
        make_structure(
            scope,
            f"{prefix}{index + 1}",
            members,
            origin,
            parameters,
            result_kind,
            method,
            COLORS[index % len(COLORS)],
            description,
            snapshot_id=end.snapshot_id,
            metrics_frame=frame,
        )
        for index, members in enumerate(components)
    ]
    result = {
        "structures": structures,
        "message": "" if structures else "No community matches the query.",
    }
    if use_tccs and include_window_graph:
        result["window_graph"] = {
            "start_snapshot_id": start.snapshot_id,
            "end_snapshot_id": end.snapshot_id,
            "snapshot_ids": snapshot_ids,
            **graph_payload(scope, frame),
        }
    return {**scope.metadata(result_kind, method), **result}
