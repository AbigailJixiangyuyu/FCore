"""Read small local datasets. Replay data has a separate, explicit entry point."""

import csv
import json
import math
from collections.abc import Iterator
from datetime import datetime
from io import StringIO
from pathlib import Path

from fastapi import HTTPException

from app.core.interactions import undirected_pair
from app.schemas.analysis import DatasetManifest, SnapshotData, SnapshotMeta


def interaction_rows(content: str, filename: str) -> Iterator[tuple[int, dict]]:
    reader = csv.reader(StringIO(content, newline=""), strict=True)
    try:
        if next(reader, None) != ["u", "v", "t"]:
            raise ValueError("The CSV header must be u,v,t in that order.")
        for row in reader:
            if len(row) != 3:
                raise ValueError("Each row must contain exactly three columns (u, v, and t).")
            u, v, raw_time = row
            if not u.strip() or not v.strip():
                raise ValueError("u and v must be nonempty node IDs.")
            try:
                timestamp = float(raw_time)
            except ValueError:
                timestamp = math.nan
            if not math.isfinite(timestamp) or timestamp < 0:
                raise ValueError("t must be a nonnegative finite number of seconds. Fractional seconds are allowed.")
            u, v = undirected_pair(u, v)
            yield reader.line_num, {"u": u, "v": v, "t": timestamp}
    except (csv.Error, ValueError) as error:
        raise HTTPException(
            422, f"{filename}, line {max(1, reader.line_num)}. {error}"
        ) from error


def parse_interactions(content: str, filename: str) -> list[dict]:
    return [event for _, event in interaction_rows(content, filename)]


def parse_snapshot(
    record: dict, meta: SnapshotMeta, timestamp_basis: str = "unix"
) -> SnapshotData:
    try:
        frame = SnapshotData.model_validate(record)
        start = datetime.fromisoformat(meta.starts_at).timestamp()
        end = datetime.fromisoformat(meta.ends_at).timestamp()
        if frame.snapshot_id != meta.snapshot_id:
            raise ValueError("The snapshot ID does not match its time window.")
        if any(not start <= event.t < end for event in frame.transactions):
            unit = "a timestamp in relative seconds" if timestamp_basis == "relative" else "a timestamp in Unix seconds"
            raise ValueError(f"t must be {unit} within this snapshot.")
        frame.transactions = [event for event in frame.transactions if event.u != event.v]
        return frame
    except ValueError as error:
        raise HTTPException(422, f"Invalid interactions in {meta.snapshot_id}. {error}") from error


class DatasetRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._files: dict[tuple[str, str], object] = {}

    def manifests(self) -> list[DatasetManifest]:
        return [
            DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.data_dir.glob("*/manifest.json"))
        ]

    def locate(self, dataset_id: str) -> tuple[Path, DatasetManifest]:
        for path in sorted(self.data_dir.glob("*/manifest.json")):
            manifest = DatasetManifest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            if manifest.dataset_id == dataset_id:
                return path.parent, manifest
        raise HTTPException(404, "Dataset not found.")

    def validate_context(
        self, dataset_id: str, version: str, cutoff: str
    ) -> DatasetManifest:
        _, manifest = self.locate(dataset_id)
        if manifest.dataset_version != version:
            raise HTTPException(409, "The dataset version changed. Reload the dataset.")
        if cutoff != manifest.observed_until:
            raise HTTPException(422, "The observation cutoff is S12.")
        return manifest

    def read(self, dataset_id: str, filename: str):
        # filename is always an application constant, never a URL-supplied path.
        key = (dataset_id, filename)
        if key not in self._files:
            directory, _ = self.locate(dataset_id)
            try:
                with (directory / filename).open(encoding="utf-8-sig", newline="") as stream:
                    content = stream.read()
            except FileNotFoundError as error:
                raise HTTPException(404, "A local data file is missing.") from error
            self._files[key] = (
                parse_interactions(content, filename)
                if filename.endswith(".csv")
                else json.loads(content)
            )
        return self._files[key]

    def accounts(self, dataset_id: str) -> list[dict]:
        return self.read(dataset_id, "accounts.json")

    def scenarios(self, dataset_id: str) -> dict:
        return self.read(dataset_id, "scenarios.json")

    def snapshot(self, dataset_id: str, snapshot_id: str) -> SnapshotData:
        _, manifest = self.locate(dataset_id)
        allowed = {
            item.snapshot_id for item in manifest.snapshots if item.kind != "future"
        }
        if snapshot_id not in allowed:
            raise HTTPException(
                404, "Snapshot not found or not yet observed. Use the replay endpoint to access future observations."
            )
        records = self.read(dataset_id, "observed.json")
        record = next(
            (item for item in records if item["snapshot_id"] == snapshot_id), None
        )
        if record is None:
            raise HTTPException(404, "Interaction data for this snapshot is missing.")
        meta = next(m for m in manifest.snapshots if m.snapshot_id == snapshot_id)
        return parse_snapshot(
            {**record, "transactions": self.read(dataset_id, f"{snapshot_id}.csv")},
            meta,
            manifest.timestamp_basis,
        )

    def replay(self, dataset_id: str) -> SnapshotData:
        _, manifest = self.locate(dataset_id)
        meta = next(m for m in manifest.snapshots if m.kind == "future")
        return parse_snapshot(
            {
                **self.read(dataset_id, "replay.json"),
                "transactions": self.read(dataset_id, f"{meta.snapshot_id}.csv"),
            },
            meta,
            manifest.timestamp_basis,
        )
