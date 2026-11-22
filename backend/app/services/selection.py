"""Reproduce submitted structures before accepting them as input to analyses."""

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from app.schemas.analysis import (
    DensityQuery,
    LocalCoreQuery,
    MaxCoreQuery,
    PatternQuery,
    Structure,
)
from app.services.context import AnalysisScope
from app.services.parallel_core import ParallelCoreCache
from app.services.patterns import find_patterns
from app.services.queries import query_structures

PATTERN_QUERY_ADAPTER = TypeAdapter(PatternQuery)


def resolve_structure(
    scope: AnalysisScope, structure: Structure, parallel_core: ParallelCoreCache
) -> Structure:
    if (
        structure.dataset_id != scope.context.dataset_id
        or structure.dataset_version != scope.context.dataset_version
        or structure.observed_until != scope.context.observed_until
    ):
        raise HTTPException(409, "所选结构与当前数据上下文不一致，请重新选择")
    base = scope.context.model_dump(
        include={"dataset_id", "dataset_version", "observed_until"}
    )
    try:
        if structure.origin == "pattern":
            result = find_patterns(
                scope,
                PATTERN_QUERY_ADAPTER.validate_python(
                    {**base, **structure.parameters}
                ),
            )
        elif structure.origin == "local_core":
            result = query_structures(
                scope,
                LocalCoreQuery(**base, **structure.parameters),
                parallel_core,
                include_window_graph=False,
            )
        elif structure.origin == "max_core":
            result = query_structures(
                scope,
                MaxCoreQuery(
                    **base,
                    snapshot_id=structure.snapshot_id,
                    algorithm=structure.parameters.get("algorithm"),
                ),
                parallel_core,
            )
        else:
            result = query_structures(
                scope, DensityQuery(**base, **structure.parameters), parallel_core
            )
    except (ValidationError, TypeError) as error:
        raise HTTPException(422, "所选结构的原查询条件无效") from error
    for expected in result["structures"]:
        if (
            expected.structure_id == structure.structure_id
            and expected.members == structure.members
            and expected.membership_hash == structure.membership_hash
            and expected.snapshot_id == structure.snapshot_id
        ):
            return expected
    raise HTTPException(422, "所选结构的成员或条件已变化，请重新查询")
