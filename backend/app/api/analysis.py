from fastapi import APIRouter, Request

from app.repositories.datasets import DatasetRepository
from app.schemas.analysis import (
    AffinityQuery,
    AffinityResponse,
    AggregateResponse,
    AnalysisContext,
    AnomaliesResponse,
    AnomalyQuery,
    DensityQuery,
    EvidenceQuery,
    EvidenceResponse,
    FutureCommunityQuery,
    FutureCommunityResponse,
    LinkPredictionModelsResponse,
    LinkPredictionQuery,
    LinkPredictionResponse,
    LocalCoreQuery,
    LocalCoreResponse,
    MaxCoreQuery,
    PatternQuery,
    PatternsResponse,
    SnapshotResponse,
    StructuresResponse,
)
from app.services.anomalies import score_accounts
from app.services.context import AnalysisScope
from app.services.evidence import evidence_series
from app.services.future_community import forecast_community
from app.services.graphs import aggregate as aggregate_graph
from app.services.graphs import snapshot as snapshot_graph
from app.services.legacy_affinity import interaction_shares
from app.services.link_prediction import model_catalog, predict_selected_links
from app.services.patterns import find_patterns
from app.services.queries import query_structures

router = APIRouter(tags=["analysis"])


def analysis_scope(request: Request, context: AnalysisContext) -> AnalysisScope:
    return AnalysisScope(DatasetRepository(request.app.state.settings.data_dir), context)


@router.get("/datasets/{dataset_id}/snapshots")
def snapshot_catalog(dataset_id: str, request: Request) -> dict:
    repository = DatasetRepository(request.app.state.settings.data_dir)
    _, manifest = repository.locate(dataset_id)
    return manifest.model_dump()


@router.get(
    "/datasets/{dataset_id}/snapshots/{snapshot_id}", response_model=SnapshotResponse
)
def snapshot(
    dataset_id: str,
    snapshot_id: str,
    dataset_version: str,
    request: Request,
    observed_until: str = "S12",
) -> dict:
    context = AnalysisContext(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        observed_until=observed_until,
    )
    return snapshot_graph(analysis_scope(request, context), snapshot_id)


@router.get("/datasets/{dataset_id}/aggregate", response_model=AggregateResponse)
def aggregate(
    dataset_id: str,
    start_snapshot_id: str,
    end_snapshot_id: str,
    dataset_version: str,
    request: Request,
    observed_until: str = "S12",
) -> dict:
    context = AnalysisContext(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        observed_until=observed_until,
    )
    return aggregate_graph(
        analysis_scope(request, context), start_snapshot_id, end_snapshot_id
    )


@router.post("/queries/local-core", response_model=LocalCoreResponse)
def query_local(body: LocalCoreQuery, request: Request) -> dict:
    return query_structures(analysis_scope(request, body), body, request.app.state.parallel_core)


@router.post("/queries/max-core", response_model=StructuresResponse)
def query_maximum(body: MaxCoreQuery, request: Request) -> dict:
    return query_structures(analysis_scope(request, body), body, request.app.state.parallel_core)


@router.post("/queries/density", response_model=StructuresResponse)
def query_density(body: DensityQuery, request: Request) -> dict:
    return query_structures(analysis_scope(request, body), body, request.app.state.parallel_core)


@router.post("/patterns/mine", response_model=PatternsResponse)
def mine_patterns(body: PatternQuery, request: Request) -> dict:
    return find_patterns(analysis_scope(request, body), body)


@router.post("/anomalies/discover", response_model=AnomaliesResponse)
def discover(body: AnomalyQuery, request: Request) -> dict:
    return score_accounts(analysis_scope(request, body), body, request.app.state.settings.models_dir)


@router.post("/evidence/series", response_model=EvidenceResponse)
def evidence(body: EvidenceQuery, request: Request) -> dict:
    return evidence_series(analysis_scope(request, body), body, request.app.state.parallel_core)


@router.get("/datasets/{dataset_id}/link-prediction/models", response_model=LinkPredictionModelsResponse)
def prediction_models(dataset_id: str, dataset_version: str, request: Request, observed_until: str = "S12") -> dict:
    context = AnalysisContext(dataset_id=dataset_id, dataset_version=dataset_version, observed_until=observed_until)
    return model_catalog(analysis_scope(request, context), request.app.state.settings.models_dir)


@router.post("/link-prediction/predict", response_model=LinkPredictionResponse)
def predict_links(body: LinkPredictionQuery, request: Request) -> dict:
    return predict_selected_links(
        analysis_scope(request, body), body, request.app.state.settings.models_dir,
        request.app.state.parallel_core,
    )


@router.post("/link-prediction/community", response_model=FutureCommunityResponse)
def predict_community(body: FutureCommunityQuery, request: Request) -> dict:
    return forecast_community(
        analysis_scope(request, body), body, request.app.state.settings.models_dir
    )


@router.post("/affinity/predict", response_model=AffinityResponse, deprecated=True)
def predict(body: AffinityQuery, request: Request) -> dict:
    return interaction_shares(analysis_scope(request, body), body, request.app.state.parallel_core)


@router.post("/affinity/observed", response_model=AffinityResponse, deprecated=True)
def observed(body: AffinityQuery, request: Request) -> dict:
    return interaction_shares(
        analysis_scope(request, body), body, request.app.state.parallel_core, reveal=True
    )
