"""Shared snapshot, selection and analysis contracts."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from algorithms.link_prediction.data import MAX_FORECAST_HORIZON
from app.core.interactions import undirected_dataset_version
from app.core.query_defaults import apply_query_defaults
from app.schemas.system import DatasetQueryDefaults

ResultKind = Literal["computed", "demo_heuristic", "demo_fixture"]
Origin = Literal["local_core", "max_core", "density", "pattern"]
LinkModel = Literal["zebra"]


class AnalysisContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_version: str
    observed_until: str = "S12"


class SnapshotQuery(AnalysisContext):
    snapshot_id: str = "S12"


class MaxCoreQuery(SnapshotQuery):
    algorithm: Literal["pkmc"] | None = None


class LocalCoreQuery(SnapshotQuery):
    account: str = "a-001"
    k: int = Field(default=4, ge=0, le=10000, strict=True)
    start_snapshot_id: str | None = None
    algorithm: Literal["parallel", "tccs"] | None = None

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, value: Any) -> Any:
        return apply_query_defaults(value, "local_core")


class DensityQuery(SnapshotQuery):
    threshold: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, value: Any) -> Any:
        return apply_query_defaults(value, "density")


QueryAccount = Annotated[str, StringConstraints(min_length=1)]


class PatternContext(AnalysisContext):
    start_snapshot_id: str | None = None
    end_snapshot_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return apply_query_defaults(value, value.get("pattern"))

    @model_validator(mode="after")
    def require_both_bounds(self):
        if (self.start_snapshot_id is None) != (self.end_snapshot_id is None):
            raise ValueError("Specify both the start and end snapshots for mining.")
        return self


class PeriodicPatternQuery(PatternContext):
    pattern: Literal["periodic"]
    account: QueryAccount = "a-001"
    k: int = Field(default=4, ge=1, strict=True)
    epsilon: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)


class DurablePatternQuery(PatternContext):
    pattern: Literal["durable"]
    account: QueryAccount = "a-001"
    k: int = Field(default=4, ge=1, strict=True)


class BurstPatternQuery(PatternContext):
    pattern: Literal["burst"]
    account: QueryAccount | None = None
    l: int = Field(default=3, ge=2, strict=True)
    delta: float = Field(default=5, gt=0, allow_inf_nan=False)


class FrequencyPatternQuery(PatternContext):
    pattern: Literal["frequency"]
    k: int = Field(default=5, ge=1, strict=True)
    t: int = Field(default=3, ge=1, strict=True)
    f: float = Field(default=1, ge=0, le=1, strict=True, allow_inf_nan=False)


PatternQuery = Annotated[
    PeriodicPatternQuery
    | DurablePatternQuery
    | BurstPatternQuery
    | FrequencyPatternQuery,
    Field(discriminator="pattern"),
]


class AnomalyQuery(SnapshotQuery):
    top_r: int | None = Field(default=10, ge=1, le=100, strict=True)


class Structure(BaseModel):
    structure_id: str
    label: str
    dataset_id: str
    dataset_version: str
    snapshot_id: str
    observed_until: str
    origin: Origin
    parameters: dict[str, Any]
    members: list[str]
    membership_hash: str
    color: str
    result_kind: ResultKind
    method: str
    description: str = ""
    metrics: dict[str, Any]
    evidence: dict[str, Any] | None = None


class SelectionQuery(AnalysisContext):
    structure: Structure


class EvidenceQuery(AnalysisContext):
    structures: list[Structure] = Field(min_length=1, max_length=100)
    metric: Literal["internal_edges", "transaction_count"] = "internal_edges"


class AffinityQuery(SelectionQuery):
    source_account: str


class LinkPredictionQuery(SelectionQuery):
    model: LinkModel = "zebra"


class FutureCommunityQuery(AnalysisContext):
    account: QueryAccount
    k: int = Field(ge=0, le=10000, strict=True)
    model: LinkModel = "zebra"
    horizon: int = Field(default=1, ge=1, le=MAX_FORECAST_HORIZON, strict=True)
    threshold: float = Field(default=0.5, ge=0, le=1, strict=True, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, value: Any) -> Any:
        return apply_query_defaults(value, "future_core")


class Transaction(BaseModel):
    """One undirected interaction with ordered endpoint IDs and time in seconds."""

    model_config = ConfigDict(extra="forbid")

    u: str = Field(min_length=1)
    v: str = Field(min_length=1)
    t: float = Field(ge=0, strict=True, allow_inf_nan=False)


class SnapshotData(BaseModel):
    snapshot_id: str
    present_accounts: list[str]
    transactions: list[Transaction]

    @model_validator(mode="after")
    def validate_accounts(self) -> "SnapshotData":
        present = set(self.present_accounts)
        if len(present) != len(self.present_accounts):
            raise ValueError("Snapshot node IDs must be unique.")
        if any(t.u not in present or t.v not in present for t in self.transactions):
            raise ValueError("Both endpoints of each interaction must appear in the snapshot.")
        return self


class SnapshotMeta(BaseModel):
    snapshot_id: str
    index: int
    starts_at: str
    ends_at: str
    kind: Literal["history", "present", "future"]


class DatasetManifest(BaseModel):
    dataset_id: str
    dataset_version: str
    name: str
    synthetic: bool = True
    seed: int
    timestamp_unit: Literal["seconds"] = "seconds"
    timestamp_basis: Literal["unix", "relative"] = "unix"
    snapshot_minutes: int
    observed_until: str
    snapshots: list[SnapshotMeta]
    query_defaults: DatasetQueryDefaults | None = None

    @field_validator("dataset_version")
    @classmethod
    def version_for_graph_data(cls, value: str) -> str:
        return undirected_dataset_version(value)


class AnalysisResult(BaseModel):
    dataset_id: str
    dataset_version: str
    observed_until: str
    request_id: str
    result_kind: ResultKind
    method: str
    elapsed_ms: float
    model_version: str | None = None


class StructuresResponse(AnalysisResult):
    structures: list[Structure]
    message: str = ""


class PatternsResponse(StructuresResponse):
    analysis_snapshot_ids: list[str]
    reference_snapshot_id: str


class AccountAnomaly(BaseModel):
    account_id: str
    rank: int = Field(ge=1)
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    temporal_contrast_score: float = Field(ge=0, le=2, allow_inf_nan=False)
    memory_generation_score: float = Field(ge=0, le=2, allow_inf_nan=False)


class UnscoredAccount(BaseModel):
    account_id: str
    reason: Literal["no_interaction_history"]


class AnomaliesResponse(AnalysisResult):
    snapshot_id: str
    status: Literal["ok", "not_evaluated"]
    scored_at: str | None
    training_snapshot_ids: list[str]
    accounts: list[AccountAnomaly]
    unscored_accounts: list[UnscoredAccount]
    message: str = ""


class InteractionEdge(BaseModel):
    id: str
    u: str
    v: str
    transaction_count: int = Field(ge=1)


class GraphPayload(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[InteractionEdge]
    stats: dict[str, Any]
    core_numbers: dict[str, int]


class GraphResponse(AnalysisResult, GraphPayload):
    pass


class WindowGraph(GraphPayload):
    start_snapshot_id: str
    end_snapshot_id: str
    snapshot_ids: list[str]


class LocalCoreResponse(StructuresResponse):
    window_graph: WindowGraph | None = None


class SnapshotResponse(GraphResponse):
    snapshot_id: str


class AggregateResponse(GraphResponse):
    start_snapshot_id: str
    end_snapshot_id: str
    snapshot_ids: list[str]
    starts_at: str
    ends_at: str


class EvidenceResponse(AnalysisResult):
    metric: str
    unit: str
    series: list[dict[str, Any]]


class AffinityResponse(AnalysisResult):
    structure_id: str
    membership_hash: str
    source_account: str
    target_snapshot: str
    interaction_measure: Literal["transaction_count"] = "transaction_count"
    window_minutes: int
    status: Literal["ok", "no_candidates", "no_interactions"]
    candidates: list[dict[str, Any]]


class LinkPredictionModel(BaseModel):
    id: LinkModel
    name: str
    status: Literal["ready", "not_ready", "not_implemented", "conflict"]
    model_version: str | None
    probability_calibration: str | None = None
    message: str = ""


class LinkPredictionModelsResponse(AnalysisResult):
    horizon: int
    models: list[LinkPredictionModel]


class PredictedEdge(BaseModel):
    u: str
    v: str
    probability: float = Field(ge=0, le=1, allow_inf_nan=False)
    currently_connected: bool


class PredictedPair(PredictedEdge):
    rank: int = Field(ge=1)


class LinkPredictionResponse(AnalysisResult):
    model: LinkModel
    structure_id: str
    membership_hash: str
    scored_at: str
    target_snapshot: str
    target_starts_at: str
    target_ends_at: str
    window_seconds: int
    directed: Literal[False] = False
    candidate_pair_count: int
    scored_pair_count: int
    pairs: list[PredictedPair]
    unscored_accounts: list[UnscoredAccount]
    status: Literal["ok", "no_candidates", "no_history"]
    message: str = ""


class FutureKeyNode(BaseModel):
    account_id: str
    observed_coreness: int | None
    predicted_coreness: int


class FutureCommunityComparison(BaseModel):
    retained: list[str]
    added: list[str]
    exited: list[str]
    max_coreness: int | None
    key_nodes: list[FutureKeyNode]


class FutureCommunityResponse(AnalysisResult):
    account: str
    k: int
    model: LinkModel
    history_snapshot_ids: list[str]
    target_snapshot: str
    target_starts_at: str
    target_ends_at: str
    threshold: float
    candidate_member_count: int
    candidate_pair_count: int
    scored_pair_count: int
    max_probability: float | None
    threshold_edge_count: int
    members: list[str]
    edges: list[PredictedEdge]
    comparison: FutureCommunityComparison | None = None
    status: Literal[
        "ok", "no_historical_community", "no_scored_pairs",
        "no_threshold_edges", "no_predicted_community",
    ]
    message: str = ""
