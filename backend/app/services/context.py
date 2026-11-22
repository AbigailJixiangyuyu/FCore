"""Validated dataset and response metadata for a single analysis request."""

from time import perf_counter
from uuid import uuid4

from app.repositories.datasets import DatasetRepository
from app.schemas.analysis import AnalysisContext, AnalysisResult


class AnalysisScope:
    def __init__(self, repository: DatasetRepository, context: AnalysisContext):
        self.repository = repository
        self.context = context
        self.manifest = repository.validate_context(
            context.dataset_id, context.dataset_version, context.observed_until
        )
        self.started_at = perf_counter()

    def metadata(self, result_kind: str, method: str) -> dict:
        return AnalysisResult(
            dataset_id=self.context.dataset_id,
            dataset_version=self.context.dataset_version,
            observed_until=self.context.observed_until,
            request_id=uuid4().hex,
            result_kind=result_kind,
            method=method,
            elapsed_ms=round((perf_counter() - self.started_at) * 1000, 2),
        ).model_dump()
