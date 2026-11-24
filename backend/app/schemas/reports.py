"""References to the stages explicitly submitted for a community report."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.analysis import AnalysisContext, FutureCommunityQuery


class StructureReference(AnalysisContext):
    structure_id: str
    membership_hash: str
    method: str
    snapshot_id: str
    origin: Literal["pattern", "local_core", "max_core"]
    parameters: dict[str, Any]


class HistoricalEvidence(StructureReference):
    origin: Literal["pattern"]


class CurrentEvidence(StructureReference):
    origin: Literal["local_core", "max_core"]
    risk_model_version: str | None


class FutureEvidence(FutureCommunityQuery):
    target_snapshot: str
    model_version: str | None
    result_fingerprint: str = Field(min_length=1)


Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ReportRequest(AnalysisContext):
    history: HistoricalEvidence | None = None
    current: CurrentEvidence | None = None
    future: FutureEvidence | None = None
    initial_prompt: Question | None = None

    @model_validator(mode="after")
    def require_evidence(self):
        if self.history is None and self.current is None and self.future is None:
            raise ValueError("Submit evidence from at least one stage.")
        return self


class ReportTurn(BaseModel):
    question: Question
    answer: str = Field(min_length=1)


class ReportFollowUpRequest(ReportRequest):
    report_content: str = Field(min_length=1)
    turns: list[ReportTurn] = Field(default_factory=list)
    question: Question
