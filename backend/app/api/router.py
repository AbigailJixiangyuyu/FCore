from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, Response, UploadFile

from app.api.analysis import router as analysis_router
from app.schemas.system import (
    CapabilitiesResponse,
    DatasetsResponse,
    DatasetSummary,
    HealthResponse,
    SnapshotAppendResult,
)
from app.services.anomalies import model_ready
from app.services.capabilities import list_capabilities
from app.services.dataset_import import import_dataset
from app.services.link_prediction import list_models
from app.services.snapshot_updates import request_repository

PageId = Annotated[UUID, Header(alias="X-FCore-Session")]

def session_cache_headers(response: Response):
    response.headers["Vary"] = "X-FCore-Session"
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(tags=["system"], dependencies=[Depends(session_cache_headers)])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(service=settings.service_name, version=settings.version)


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(request: Request) -> CapabilitiesResponse:
    repository = request_repository(request)
    manifests = repository.manifests()
    return CapabilitiesResponse(
        capabilities=list_capabilities(
            bool(manifests),
            any(
                model_ready(repository, manifest, request.app.state.settings.models_dir)
                for manifest in manifests
            ),
            any(
                any(model["status"] == "ready" for model in list_models(repository, manifest, request.app.state.settings.models_dir))
                for manifest in manifests
            ),
            parallel_core_ready=request.app.state.parallel_core.ready,
        )
    )


@router.get("/datasets", response_model=DatasetsResponse)
def datasets(request: Request) -> DatasetsResponse:
    repository = request_repository(request)
    return DatasetsResponse(
        datasets=[
            DatasetSummary.model_validate(item.model_dump())
            for item in repository.manifests()
        ]
    )


@router.post("/datasets/import", response_model=DatasetSummary, status_code=201)
def upload_dataset(request: Request, files: Annotated[list[UploadFile], File(alias="file")]) -> DatasetSummary:
    if len(files) != 1:
        raise HTTPException(422, "Upload exactly one CSV file.")
    file = files[0]
    try:
        manifest = import_dataset(request.app.state.settings.data_dir, file.filename or "", file.file.read())
    except OSError as error:
        raise HTTPException(500, "Could not save the dataset. Check the local data directory and try again.") from error
    # A repeated import can select a dataset already expanded in this page.
    _, active = request_repository(request).locate(manifest.dataset_id)
    return DatasetSummary.model_validate(active.model_dump())


@router.post("/datasets/{dataset_id}/snapshots", response_model=SnapshotAppendResult, status_code=201)
def append_snapshot(dataset_id: str, request: Request, page: PageId,
                    dataset_version: Annotated[str, Form()], observed_until: Annotated[str, Form()],
                    operation_id: Annotated[UUID, Form()], files: Annotated[list[UploadFile], File(alias="file")]):
    if len(files) != 1:
        raise HTTPException(422, "Choose one static graph CSV.")
    file = files[0]
    return request.app.state.snapshot_sessions.append(
        page, dataset_id, dataset_version, observed_until, operation_id, file.filename or "", file.file.read()
    )


@router.delete("/demo-session", status_code=204)
def release_session(request: Request, page: PageId):
    request.app.state.snapshot_sessions.discard(page)
    return Response(status_code=204)


router.include_router(analysis_router)
