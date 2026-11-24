"""Page-local static graph snapshots. Base datasets and their replay stay on disk."""

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from io import StringIO
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import UUID, uuid4

from fastapi import HTTPException, Request

from algorithms.core.queries import adjacency, core_numbers
from app.core.interactions import undirected_dataset_version, undirected_pair
from app.repositories.datasets import DatasetRepository
from app.schemas.analysis import DatasetManifest, SnapshotData
from app.schemas.system import DatasetQueryDefaults, DatasetSummary, SnapshotAppendResult


def parse_static_graph(filename: str, content: bytes) -> tuple[list[str], list[tuple[str, str]]]:
    if not filename.lower().endswith(".csv"):
        raise HTTPException(422, "Choose a .csv file.")
    try:
        source = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        prefix = content[:error.start].replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        line = prefix.count(b"\n") + 1
        raise HTTPException(422, f"Line {line}. Use UTF-8 encoding.") from error
    reader = csv.reader(StringIO(source, newline=""), strict=True)
    nodes, edges = set(), set()
    try:
        if next(reader, None) != ["u", "v"]:
            raise ValueError("The CSV header must be u,v.")
        for row in reader:
            if len(row) != 2 or not all(value.strip() for value in row):
                raise ValueError("Provide two nonempty vertex IDs in columns u,v.")
            nodes.update(row)
            if row[0] != row[1]:
                edges.add(undirected_pair(*row))
    except (ValueError, csv.Error) as error:
        raise HTTPException(422, f"Line {max(1, reader.line_num)}. {error}") from error
    return sorted(nodes), sorted(edges)


@dataclass(frozen=True)
class Extension:
    manifest: DatasetManifest
    frames: dict[str, SnapshotData]


class SessionRepository(DatasetRepository):
    """An immutable view for one request, even if another upload advances the page."""

    def __init__(self, data_dir: Path, extensions: dict[str, Extension]):
        super().__init__(data_dir)
        self.extensions = extensions

    def manifests(self):
        return [
            self.extensions[m.dataset_id].manifest if m.dataset_id in self.extensions else m
            for m in super().manifests()
        ]

    def locate(self, dataset_id):
        directory, base = super().locate(dataset_id)
        extension = self.extensions.get(dataset_id)
        return directory, extension.manifest if extension else base

    def snapshot(self, dataset_id, snapshot_id):
        extension = self.extensions.get(dataset_id)
        if extension and snapshot_id in extension.frames:
            return extension.frames[snapshot_id]
        return super().snapshot(dataset_id, snapshot_id)

    def accounts(self, dataset_id):
        accounts = super().accounts(dataset_id)
        extension = self.extensions.get(dataset_id)
        if not extension:
            return accounts
        additions = {node for frame in extension.frames.values() for node in frame.present_accounts}
        additions.difference_update(account["id"] for account in accounts)
        return [*accounts, *({"id": node, "label": node} for node in sorted(additions))]

    def replay(self, dataset_id):
        if dataset_id in self.extensions:
            raise HTTPException(404, "No replay is available beyond this demonstration snapshot.")
        return super().replay(dataset_id)


def advance(manifest: DatasetManifest, account: str, k: int) -> DatasetManifest:
    snapshots = manifest.snapshots
    current, incoming = snapshots[-2:]
    try:
        next_end = datetime.fromisoformat(incoming.ends_at) + timedelta(minutes=manifest.snapshot_minutes)
    except OverflowError as error:
        raise HTTPException(422, "The next snapshot exceeds the supported time range.") from error
    next_window = incoming.model_copy(update={
        "snapshot_id": f"S{incoming.index + 2:02d}", "index": incoming.index + 1,
        "starts_at": incoming.ends_at, "ends_at": next_end.isoformat(),
    })
    return manifest.model_copy(update={
        "observed_until": incoming.snapshot_id,
        "dataset_version": undirected_dataset_version(f"{manifest.dataset_id}-demo-{uuid4().hex}"),
        "has_demo_updates": True,
        "query_defaults": DatasetQueryDefaults(
            current_account=account, current_k=min(k, 10000),
            history_account=manifest.query_defaults.history_account if manifest.query_defaults else None,
        ),
        "snapshots": [*snapshots[:-2], current.model_copy(update={"kind": "history"}),
                      incoming.model_copy(update={"kind": "present"}), next_window],
    })


class DemoSession:
    def __init__(self):
        self.datasets: dict[str, Extension] = {}
        self.receipts: dict[tuple[str, UUID], tuple[tuple, SnapshotAppendResult]] = {}
        self.last_used = monotonic()


class SnapshotSessions:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._lock = Lock()
        self._pages: dict[UUID, DemoSession] = {}

    def repository(self, page: UUID | None):
        with self._lock:
            session = self._pages.get(page)
            if session:
                session.last_used = monotonic()
                return SessionRepository(self.data_dir, session.datasets.copy())
        return DatasetRepository(self.data_dir)

    def discard(self, page: UUID):
        with self._lock:
            self._pages.pop(page, None)

    def append(self, page: UUID, dataset_id: str, version: str, cutoff: str,
               operation: UUID, filename: str, content: bytes) -> SnapshotAppendResult:
        nodes, edges = parse_static_graph(filename, content)
        _, base = DatasetRepository(self.data_dir).locate(dataset_id)
        graph = adjacency(nodes, edges)
        cores = core_numbers(graph)
        account = min(graph, key=lambda u: (-cores[u], -len(graph[u]), u), default="")
        signature = (version, cutoff, sha256(content).digest())
        key = (dataset_id, operation)
        with self._lock:
            # Reclaim closed pages missed by pagehide (e.g., a killed browser).
            now = monotonic()
            for expired in [p for p, s in self._pages.items() if now - s.last_used > 86400]:
                del self._pages[expired]
            session = self._pages.get(page)
            extension = session.datasets.get(dataset_id) if session else None
            manifest = extension.manifest if extension else base
            receipt = session.receipts.get(key) if session else None
            if receipt:
                if signature != receipt[0]:
                    raise HTTPException(409, "This upload ID was already used for a different request.")
                return receipt[1]
            if (version, cutoff) != (manifest.dataset_version, manifest.observed_until):
                raise HTTPException(409, "The dataset changed. Reopen Data Updates and try again.")
            frame = SnapshotData(snapshot_id=manifest.snapshots[-1].snapshot_id,
                                 present_accounts=nodes, transactions=[], static_edges=edges)
            updated = advance(manifest, account, cores.get(account, 0))
            result = SnapshotAppendResult(dataset=DatasetSummary.model_validate(updated.model_dump()),
                                          next_snapshot_id=updated.snapshots[-1].snapshot_id,
                                          node_count=len(nodes), edge_count=len(edges))
            if session is None:
                session = self._pages[page] = DemoSession()
            session.last_used = now
            frames = extension.frames if extension else {}
            session.datasets[dataset_id] = Extension(updated, {**frames, frame.snapshot_id: frame})
            session.receipts[key] = (signature, result)
            return result


def request_repository(request: Request) -> DatasetRepository:
    header = request.headers.get("X-FCore-Session")
    try:
        page = UUID(header) if header else None
    except ValueError as error:
        raise HTTPException(422, "Invalid demonstration session ID.") from error
    return request.app.state.snapshot_sessions.repository(page)
