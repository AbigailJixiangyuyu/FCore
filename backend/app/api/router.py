from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.api.analysis import router as analysis_router
from app.repositories.datasets import DatasetRepository
from app.schemas.system import (
    CapabilitiesResponse,
    DatasetsResponse,
    DatasetSummary,
    HealthResponse,
)
from app.services.anomalies import model_ready
from app.services.capabilities import list_capabilities
from app.services.dataset_import import import_dataset
from app.services.link_prediction import list_models

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(service=settings.service_name, version=settings.version)


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(request: Request) -> CapabilitiesResponse:
    repository = DatasetRepository(request.app.state.settings.data_dir)
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
    repository = DatasetRepository(request.app.state.settings.data_dir)
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
    return DatasetSummary.model_validate(manifest.model_dump())


router.include_router(analysis_router)
