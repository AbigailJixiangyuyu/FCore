"""Causal preparation of undirected (u, v, seconds) interactions."""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Event:
    u: str
    v: str
    timestamp: float


def seconds(value: str, origin: str) -> float:
    time, start = datetime.fromisoformat(value), datetime.fromisoformat(origin)
    if time.tzinfo is None or start.tzinfo is None:
        raise ValueError("Interaction and snapshot timestamps must include a time zone.")
    result = (time - start).total_seconds()
    if not math.isfinite(result):
        raise ValueError("Timestamps must be finite.")
    return result


def snapshot_events(frame, meta, origin: str) -> tuple[Event, ...]:
    start, end = seconds(meta.starts_at, origin), seconds(meta.ends_at, origin)
    origin_timestamp = datetime.fromisoformat(origin).timestamp()
    events = []
    for transaction in frame.transactions:
        timestamp = transaction.t - origin_timestamp
        if not start <= timestamp < end:
            raise ValueError(f"{meta.snapshot_id} contains interactions outside its time window.")
        events.append(Event(transaction.u, transaction.v, timestamp))
    # Python's stable sort preserves file order and repeated identical interactions.
    return tuple(sorted(events, key=lambda event: event.timestamp))


def chronological_batches(events: Iterable[Event], batch_size: int):
    """Only split between timestamps; tied events see the same pre-update state."""
    if batch_size < 1:
        raise ValueError("batch_size must be a positive integer.")
    batch = []
    previous_time = -math.inf
    for timestamp, group in groupby(events, key=lambda event: event.timestamp):
        if timestamp < previous_time:
            raise ValueError("Interaction events must be sorted by time.")
        previous_time = timestamp
        batch.extend(group)
        if len(batch) >= batch_size:
            yield tuple(batch)
            batch = []
    if batch:
        yield tuple(batch)


def event_fingerprint(events: Iterable[Event]) -> str:
    records = [(e.u, e.v, e.timestamp) for e in events]
    return hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode()
    ).hexdigest()
