from typing import Literal

from pydantic import BaseModel, Field, computed_field


Granularity = Literal["original", "weekly", "monthly"]
MINUTES = {"weekly": 7 * 1440, "monthly": 30 * 1440}


def available_granularities(dataset_id: str, snapshot_minutes: int) -> list[Granularity]:
    if dataset_id == "email-eu-core-dept3" or snapshot_minutes == MINUTES["weekly"]:
        return ["weekly", "monthly"]
    if snapshot_minutes == MINUTES["monthly"]:
        return ["monthly", "weekly"]
    return ["original", "weekly", "monthly"]


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
    has_demo_updates: bool = False
    query_defaults: DatasetQueryDefaults | None = None

    @computed_field
    @property
    def granularities(self) -> list[Granularity]:
        return available_granularities(self.dataset_id, self.snapshot_minutes)


class DatasetsResponse(BaseModel):
    datasets: list[DatasetSummary] = Field(default_factory=list)


class SnapshotAppendResult(BaseModel):
    dataset: DatasetSummary
    next_snapshot_id: str
    node_count: int
    edge_count: int
