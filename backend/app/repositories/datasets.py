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
            raise ValueError("CSV 表头必须为 u,v,t，且顺序一致")
        for row in reader:
            if len(row) != 3:
                raise ValueError("每行必须包含 u、v、t 三列")
            u, v, raw_time = row
            if not u.strip() or not v.strip():
                raise ValueError("u 和 v 必须是非空节点 ID")
            try:
                timestamp = float(raw_time)
            except ValueError:
                timestamp = math.nan
            if not math.isfinite(timestamp) or timestamp < 0:
                raise ValueError("t 必须是非负有限的秒数，可带小数")
            u, v = undirected_pair(u, v)
            yield reader.line_num, {"u": u, "v": v, "t": timestamp}
    except (csv.Error, ValueError) as error:
        raise HTTPException(
            422, f"{filename} 第 {max(1, reader.line_num)} 行无效：{error}"
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
            raise ValueError("快照标识与时间配置不一致")
        if any(not start <= event.t < end for event in frame.transactions):
            unit = "相对秒时间戳" if timestamp_basis == "relative" else "Unix 秒时间戳"
            raise ValueError(f"t 必须是位于该快照范围内的{unit}")
        frame.transactions = [event for event in frame.transactions if event.u != event.v]
        return frame
    except ValueError as error:
        raise HTTPException(422, f"{meta.snapshot_id} 交互数据无效：{error}") from error


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
        raise HTTPException(404, "数据集不存在")

    def validate_context(
        self, dataset_id: str, version: str, cutoff: str
    ) -> DatasetManifest:
        _, manifest = self.locate(dataset_id)
        if manifest.dataset_version != version:
            raise HTTPException(409, "数据版本已变化，请重新加载数据集")
        if cutoff != manifest.observed_until:
            raise HTTPException(422, "本演示的观察截止固定为 S12")
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
                raise HTTPException(404, "本地数据文件缺失") from error
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
                404, "该快照未观测或不存在；未来观测仅能通过揭晓接口获取"
            )
        records = self.read(dataset_id, "observed.json")
        record = next(
            (item for item in records if item["snapshot_id"] == snapshot_id), None
        )
        if record is None:
            raise HTTPException(404, "快照交易数据缺失")
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
