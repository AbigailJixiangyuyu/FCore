"""Turn a single interaction CSV into the demo's observed snapshot package."""

import hashlib
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

from algorithms.core.queries import adjacency, core_numbers
from app.repositories.dataset_writer import publish_dataset
from app.repositories.datasets import interaction_rows
from app.schemas.analysis import DatasetManifest, SnapshotMeta
from app.schemas.system import DatasetQueryDefaults

OBSERVED_COUNT = 12
UTC_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def snapshot_id(index: int) -> str:
    return f"S{index + 1:02}"


def observed_windows(first_time: float, last_time: float) -> tuple[int, int]:
    first_minute = int(first_time) // 60
    cutoff_minute = int(last_time) // 60 + 1
    span = cutoff_minute - first_minute
    width = (span + OBSERVED_COUNT - 1) // OBSERVED_COUNT
    return cutoff_minute - OBSERVED_COUNT * width, width


def snapshot_metadata(start_minute: int, width: int) -> list[SnapshotMeta]:
    boundaries = [
        (UTC_EPOCH + timedelta(minutes=start_minute + index * width)).isoformat()
        for index in range(OBSERVED_COUNT + 2)
    ]
    return [
        SnapshotMeta(
            snapshot_id=snapshot_id(index),
            index=index,
            starts_at=boundaries[index],
            ends_at=boundaries[index + 1],
            kind=kind,
        )
        for index, kind in enumerate(["history"] * (OBSERVED_COUNT - 1) + ["present", "future"])
    ]


def endpoints(events: list[dict]) -> set[str]:
    return {event[key] for event in events for key in ("u", "v")}


def defaults_for_windows(windows: list[list[dict]]) -> DatasetQueryDefaults:
    current = windows[-1]
    graph = adjacency(endpoints(current), ((event["u"], event["v"]) for event in current))
    numbers = core_numbers(graph)
    account = min(graph, key=lambda node: (-numbers[node], -len(graph[node]), node))
    history_accounts = {node for window in windows[:-1] for node in endpoints(window)}
    return DatasetQueryDefaults(
        current_account=account,
        current_k=min(numbers[account], 10000),
        history_account=account if account in history_accounts else min(history_accounts, default=None),
    )


def account_catalog(windows: list[list[dict]]) -> list[dict]:
    accounts = sorted({node for window in windows for node in endpoints(window)})
    catalog = []
    for index, account in enumerate(accounts):
        angle = math.tau * index / len(accounts)
        catalog.append({
            "id": account, "label": account,
            "x": round(400 + 260 * math.cos(angle), 6),
            "y": round(320 + 260 * math.sin(angle), 6),
        })
    return catalog


def import_dataset(data_dir: Path, filename: str, content: bytes) -> DatasetManifest:
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith(".csv"):
        raise HTTPException(422, "请选择一个 .csv 文件")
    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(422, "CSV 文件必须使用 UTF-8 编码") from error

    rows = sorted(interaction_rows(csv_text, filename), key=lambda row: row[1]["t"])
    if not rows:
        raise HTTPException(422, f"{filename} 第 2 行缺失：至少需要一条交互记录")
    last_line, last_event = rows[-1]
    start_minute, width = observed_windows(rows[0][1]["t"], last_event["t"])
    try:
        snapshots = snapshot_metadata(start_minute, width)
    except OverflowError as error:
        raise HTTPException(
            422, f"{filename} 第 {last_line} 行的时间范围过大，请检查 t 是否为 Unix 秒"
        ) from error

    windows: list[list[dict]] = [[] for _ in range(OBSERVED_COUNT)]
    for _, event in rows:
        minute = int(event["t"]) // 60
        windows[(minute - start_minute) // width].append(event)

    # Retrying the same named file reuses the completed package.
    fingerprint = hashlib.sha256(content).hexdigest()
    identity = hashlib.sha256(f"{filename}/{fingerprint}".encode()).hexdigest()[:24]
    dataset_id = f"imported-{identity}"
    manifest = DatasetManifest(
        dataset_id=dataset_id,
        dataset_version=f"{dataset_id}-v1",
        name=filename[:-4].strip() or "导入数据集",
        synthetic=False,
        seed=0,
        snapshot_minutes=width,
        observed_until=snapshot_id(OBSERVED_COUNT - 1),
        snapshots=snapshots,
        query_defaults=defaults_for_windows(windows),
    )
    files = {
        "manifest.json": manifest.model_dump(),
        "accounts.json": account_catalog(windows),
        "observed.json": [
            {"snapshot_id": snapshot_id(index), "present_accounts": sorted(endpoints(events))}
            for index, events in enumerate(windows)
        ],
        **{f"{snapshot_id(index)}.csv": events for index, events in enumerate(windows)},
    }
    publish_dataset(data_dir, dataset_id, files)
    return manifest
