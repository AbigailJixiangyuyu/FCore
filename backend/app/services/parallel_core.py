"""Cache one S12 decomposition per dataset version for queries and revalidation."""

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from fastapi import HTTPException

from algorithms.core.parallel import ParallelCoreError, decompose, is_built
from app.repositories.datasets import DatasetRepository
from app.schemas.analysis import AnalysisContext, SnapshotData
from app.services.statistics import graph_of

CoreSolver = Callable[[dict[str, set[str]]], dict[str, int]]


@dataclass(frozen=True, slots=True)
class IndexedCore:
    frame: SnapshotData
    graph: dict[str, set[str]]
    numbers: dict[str, int]


class ParallelCoreCache:
    def __init__(self, binary: Path, solver: CoreSolver | None = None):
        self.binary = binary
        self._solver = solver
        self._lock = Lock()
        self._entries: OrderedDict[tuple[str, str, str], IndexedCore] = OrderedDict()

    @property
    def ready(self) -> bool:
        return self._solver is not None or is_built(self.binary)

    def index(
        self, repository: DatasetRepository, context: AnalysisContext, account: str
    ) -> IndexedCore:
        key = (context.dataset_id, context.dataset_version, context.observed_until)
        with self._lock:
            if key in self._entries:
                index = self._entries[key]
                if account not in index.graph:
                    raise HTTPException(422, "The query node is not in S12.")
                self._entries.move_to_end(key)
                return index

            frame = repository.snapshot(context.dataset_id, context.observed_until)
            graph = graph_of(frame)
            if account not in graph:
                raise HTTPException(422, "The query node is not in S12.")
            try:
                numbers = (
                    self._solver(graph) if self._solver is not None
                    else decompose(graph, self.binary)
                )
            except ParallelCoreError as error:
                raise HTTPException(503, str(error)) from error
            index = IndexedCore(frame, graph, numbers)
            self._entries[key] = index
            if len(self._entries) > 4:
                self._entries.popitem(last=False)
            return index
