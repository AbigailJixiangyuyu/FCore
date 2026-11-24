"""Reproduce each submitted result locally before sharing its statistics."""

from pathlib import Path

from fastapi import HTTPException

from app.schemas.analysis import AnomalyQuery, FutureCommunityQuery, Structure
from app.schemas.reports import FutureEvidence, ReportRequest, StructureReference
from app.services.anomalies import score_accounts
from app.services.context import AnalysisScope
from app.services.future_community import forecast_community
from app.services.parallel_core import ParallelCoreCache
from app.services.selection import resolve_structure

from .facts import ReportFacts, collect_facts


def _structure(scope: AnalysisScope, reference: StructureReference, cache: ParallelCoreCache, stage: str) -> Structure:
    try:
        return resolve_structure(scope, reference, cache)
    except HTTPException as error:
        if error.status_code not in (404, 409, 422):
            raise
        raise HTTPException(409, f"{stage} evidence changed. Run the query and submit {stage} evidence again.") from error


def verify_evidence(
    scope: AnalysisScope, request: ReportRequest, cache: ParallelCoreCache, models_dir: Path
) -> ReportFacts:
    context = request.model_dump(include={"dataset_id", "dataset_version", "observed_until"})
    for stage in ("history", "current", "future"):
        ref = getattr(request, stage)
        if ref is None:
            continue
        if any(getattr(ref, key) != value for key, value in context.items()):
            raise HTTPException(409, f"Submit {stage.title()} evidence from the active dataset version.")
    history = _structure(scope, request.history, cache, "History") if request.history else None
    current = _structure(scope, request.current, cache, "Current") if request.current else None
    scores = None
    if request.current and request.current.risk_model_version is not None:
        try:
            scores = score_accounts(
                scope, AnomalyQuery(**context, snapshot_id=scope.context.observed_until, top_r=None), models_dir,
            )
        except HTTPException as error:
            raise HTTPException(error.status_code, "Current SLADE evidence could not be verified. Check the model and resubmit Current evidence.") from error
        if scores["model_version"] != request.current.risk_model_version:
            raise HTTPException(409, "The SLADE model changed. Submit Current evidence again.")

    forecast = _verified_forecast(scope, request.future, models_dir) if request.future else None
    return collect_facts(history, current, scores, forecast)


def _verified_forecast(scope: AnalysisScope, ref: FutureEvidence, models_dir: Path) -> dict:
    query = FutureCommunityQuery.model_validate(ref.model_dump(exclude={"result_fingerprint", "model_version", "target_snapshot"}))
    try:
        result = forecast_community(scope, query, models_dir)
    except HTTPException as error:
        raise HTTPException(error.status_code, "Future evidence could not be verified. Check the prediction model and resubmit Future evidence.") from error
    if (result["model_version"] != ref.model_version or result["target_snapshot"] != ref.target_snapshot
            or result["result_fingerprint"] != ref.result_fingerprint):
        raise HTTPException(409, "The forecast changed. Run the prediction and submit Future evidence again.")
    return result
