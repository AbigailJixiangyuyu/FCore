"""Fixed-duration views anchored at the source observation cutoff."""
from datetime import datetime, timedelta
from functools import cached_property

from fastapi import HTTPException

from app.repositories.datasets import DatasetRepository
from app.schemas.analysis import SnapshotData, SnapshotMeta

from app.schemas.system import MINUTES, available_granularities


def view_repository(source, dataset_id, granularity=None):
    _, base = source.locate(dataset_id)
    choices = available_granularities(dataset_id, base.snapshot_minutes)
    if granularity is None:
        granularity = choices[0]
    if dataset_id == "email-eu-core-dept3" and granularity not in choices:
        raise HTTPException(422, "Select weekly or monthly for EmailDept3.")
    if granularity == "original" or MINUTES[granularity] == base.snapshot_minutes:
        return source
    return GranularityRepository(source, base, granularity)


def for_version(source, dataset_id, version):
    for granularity in MINUTES:
        if version.endswith(f":{granularity}"):
            return view_repository(source, dataset_id, granularity)
    return source


def model_directory(root, manifest):
    return root if manifest.granularity == "original" else root / "granularity" / manifest.granularity


class GranularityRepository(DatasetRepository):
    def __init__(self, source, base, granularity):
        super().__init__(source.data_dir)
        self.source = source
        self.base = base
        width = timedelta(minutes=MINUTES[granularity])
        observed = [m for m in base.snapshots if m.kind != "future"]
        self.directory, _ = source.locate(base.dataset_id)
        self.source_windows = [
            (datetime.fromisoformat(m.starts_at), datetime.fromisoformat(m.ends_at), m.snapshot_id)
            for m in observed
        ]
        start, cutoff = self.source_windows[0][0], self.source_windows[-1][1]
        # Integer division on timedeltas also preserves fractional boundary timestamps.
        full_windows, remainder = divmod(cutoff - start, width)
        count = full_windows + bool(remainder)
        snapshots = []
        if cutoff > datetime.max.replace(tzinfo=cutoff.tzinfo) - width:
            raise HTTPException(422, "The future window exceeds the supported date range.")
        for index in range(count + 1):
            end = cutoff + (index + 1 - count) * width
            snapshots.append(SnapshotMeta(
                snapshot_id=f"S{index + 1:02d}", index=index,
                starts_at=(start if index == 0 else end - width).isoformat(), ends_at=end.isoformat(),
                kind="future" if index == count else "present" if index == count - 1 else "history",
            ))
        self.manifest = base.model_copy(update={
            "snapshots": snapshots, "observed_until": snapshots[-2].snapshot_id,
            "snapshot_minutes": MINUTES[granularity], "granularity": granularity,
            "dataset_version": f"{base.dataset_version}:{granularity}",
        })
        self._source_frames = {}
        self._frames = {}

    def locate(self, dataset_id):
        if dataset_id != self.base.dataset_id:
            raise HTTPException(404, "Dataset not found.")
        return self.directory, self.manifest

    def accounts(self, dataset_id):
        return self.source.accounts(dataset_id)

    @cached_property
    def observed(self):
        return {m.snapshot_id: m for m in self.manifest.snapshots if m.kind != "future"}

    def snapshot(self, dataset_id, snapshot_id):
        meta = self.observed.get(snapshot_id)
        if dataset_id != self.base.dataset_id or meta is None:
            raise HTTPException(404, "Snapshot not observed in this view.")
        if snapshot_id in self._frames:
            return self._frames[snapshot_id]
        start, end = datetime.fromisoformat(meta.starts_at), datetime.fromisoformat(meta.ends_at)
        lo, hi = start.timestamp(), end.timestamp()
        accounts, events, static = set(), [], None
        for left, right, source_id in self.source_windows:
            if left >= end or right <= start:
                continue
            if source_id not in self._source_frames:
                self._source_frames[source_id] = self.source.snapshot(dataset_id, source_id)
            frame = self._source_frames[source_id]
            # A static update is one observation of the graph at the close of its source window.
            if frame.static_edges is not None and right > end:
                continue
            selected = [t for t in frame.transactions if lo <= t.t < hi]
            events.extend(selected)
            if dataset_id.startswith("imported-") and frame.static_edges is None:
                # Imported event files specify vertices only through their endpoints.
                accounts.update(u for t in selected for u in (t.u, t.v))
            else:
                accounts.update(frame.present_accounts)
            if frame.static_edges is not None:
                if static is None:
                    static = set()
                static.update(frame.static_edges)
        result = SnapshotData(snapshot_id=snapshot_id, present_accounts=sorted(accounts),
                              transactions=events, static_edges=sorted(static) if static is not None else None)
        self._frames[snapshot_id] = result
        return result

    def replay(self, dataset_id):
        raise HTTPException(404, "Replay observations are available only at the original granularity.")
