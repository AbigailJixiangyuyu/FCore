"""Validated dataset and response metadata for a single analysis request."""

from time import perf_counter
from uuid import uuid4

from app.repositories.granularity import for_version
from app.repositories.datasets import DatasetRepository
from app.schemas.analysis import AnalysisContext, AnalysisResult, SnapshotQuery


class AnalysisScope:
    def __init__(self, repository: DatasetRepository, context: AnalysisContext):
        repository = for_version(repository, context.dataset_id, context.dataset_version)
        self.repository = repository
        self.context = context
        cutoff_was_supplied = "observed_until" in context.model_fields_set
        self.manifest = repository.validate_context(
            context.dataset_id, context.dataset_version, context.observed_until if cutoff_was_supplied else None
        )
        if not cutoff_was_supplied:
            context.observed_until = self.manifest.observed_until
            if isinstance(context, SnapshotQuery) and "snapshot_id" not in context.model_fields_set:
                context.snapshot_id = self.manifest.observed_until
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
