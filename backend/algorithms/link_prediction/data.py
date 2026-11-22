"""Window labels and immutable inputs. This module never opens replay/S13 data."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

MAX_FORECAST_HORIZON = 3


@dataclass(frozen=True)
class Event:
    u: str
    v: str
    timestamp: float


@dataclass(frozen=True)
class Window:
    snapshot_id: str
    start: float
    end: float
    events: tuple[Event, ...]


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def event_fingerprint(events) -> str:
    return fingerprint([(e.u, e.v, e.timestamp) for e in events])


def read_window(repository, manifest, meta, origin_timestamp: float) -> Window:
    if meta.kind == "future":
        raise ValueError("Link prediction cannot read future observations")
    frame = repository.snapshot(manifest.dataset_id, meta.snapshot_id)
    events = tuple(sorted(
        (Event(t.u, t.v, t.t - origin_timestamp) for t in frame.transactions),
        key=lambda event: event.timestamp,
    ))
    return Window(
        meta.snapshot_id,
        datetime.fromisoformat(meta.starts_at).timestamp() - origin_timestamp,
        datetime.fromisoformat(meta.ends_at).timestamp() - origin_timestamp,
        events,
    )


def prepare_history(repository, manifest) -> tuple[tuple[Window, ...], dict]:
    metas = sorted(manifest.snapshots, key=lambda m: m.index)
    if [m.kind for m in metas] != ["history"] * 11 + ["present", "future"]:
        raise ValueError("Link prediction requires 11 historical snapshots, one current snapshot, and one future snapshot of equal duration.")
    if metas[11].snapshot_id != manifest.observed_until:
        raise ValueError("The observation cutoff must match the current snapshot.")
    origin = datetime.fromisoformat(metas[0].starts_at).timestamp()
    width = manifest.snapshot_minutes * 60
    for i, meta in enumerate(metas):
        start = datetime.fromisoformat(meta.starts_at).timestamp()
        end = datetime.fromisoformat(meta.ends_at).timestamp()
        if start != origin + i * width or end != start + width:
            raise ValueError("Link prediction requires consecutive snapshots of equal duration.")
    windows = tuple(read_window(repository, manifest, meta, origin) for meta in metas[:11])
    metadata = {
        "dataset_id": manifest.dataset_id, "dataset_version": manifest.dataset_version,
        "origin_timestamp": origin, "window_seconds": width,
        "history_snapshot_ids": [w.snapshot_id for w in windows],
        "training_target_snapshot_ids": [w.snapshot_id for w in windows[1:9]],
        "validation_snapshot_id": windows[9].snapshot_id,
        "calibration_snapshot_id": windows[10].snapshot_id,
        "warmup_until": windows[-1].snapshot_id, "warmup_cutoff": windows[-1].end,
        "history_event_count": sum(len(w.events) for w in windows),
        "history_fingerprint": event_fingerprint(e for w in windows for e in w.events),
        "task": "undirected-next-snapshot-occurrence",
    }
    return windows, metadata


def positive_pairs(window: Window) -> set[tuple[str, str]]:
    return {tuple(sorted((e.u, e.v))) for e in window.events if e.u != e.v}


def labels_for(pairs, target: Window) -> list[float]:
    positive = positive_pairs(target)
    return [float(tuple(sorted(pair)) in positive) for pair in pairs]
