from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class Capability(BaseModel):
    id: str
    name: str
    description: str
    status: Literal["not_implemented", "unavailable", "ready", "demo"] = (
        "not_implemented"
    )


class CapabilitiesResponse(BaseModel):
    capabilities: list[Capability]


class DatasetQueryDefaults(BaseModel):
    current_account: str
    current_k: int
    history_account: str | None


class DatasetSummary(BaseModel):
    dataset_id: str
    dataset_version: str
    name: str
    synthetic: bool = False
    timestamp_unit: Literal["seconds"] = "seconds"
    timestamp_basis: Literal["unix", "relative"] = "unix"
    snapshot_minutes: int = 10
    observed_until: str = ""
    query_defaults: DatasetQueryDefaults | None = None


class DatasetsResponse(BaseModel):
    datasets: list[DatasetSummary] = Field(default_factory=list)
