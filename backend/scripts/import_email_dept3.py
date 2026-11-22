"""Convert the active prefix of SNAP Email Dept3 to u,v,t snapshots."""

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings
from app.core.interactions import undirected_pair
from app.core.query_defaults import query_defaults
from app.schemas.analysis import DatasetManifest, SnapshotData
from app.repositories.dataset_writer import write_dataset

DATASET_ID = "email-eu-core-dept3"
SOURCE_FILENAME = "email-Eu-core-temporal-Dept3.txt.gz"
SOURCE_URL = f"https://snap.stanford.edu/data/{SOURCE_FILENAME}"
SOURCE_PAGE = "https://snap.stanford.edu/data/email-Eu-core-temporal.html"
SNAPSHOT_COUNT = 13
RETAINED_START_INCLUSIVE = 0
RETAINED_END_EXCLUSIVE = 45_310_384
CONVERTER_VERSION = "email-dept3-active-prefix-v2"


def read_source(path: Path) -> tuple[list[dict], dict]:
    """Read integer relative seconds, retaining duplicate rows and tied order."""
    compressed = path.read_bytes()
    content = gzip.decompress(compressed)
    events = []
    for line_number, line in enumerate(content.decode("utf-8-sig").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 3:
            raise ValueError(f"原始文件第 {line_number} 行必须包含 u v t 三列")
        u, v, timestamp = fields
        try:
            if int(u) < 0 or int(v) < 0 or int(timestamp) < 0:
                raise ValueError
            timestamp = int(timestamp)
        except ValueError as error:
            raise ValueError(
                f"原始文件第 {line_number} 行的节点和相对秒必须是非负整数"
            ) from error
        u, v = undirected_pair(u, v)
        events.append({"u": u, "v": v, "t": timestamp})
    if not events:
        raise ValueError("原始文件没有交互记录")
    events.sort(key=lambda event: event["t"])
    return events, {
        "archive_sha256": hashlib.sha256(compressed).hexdigest(),
        "uncompressed_sha256": hashlib.sha256(content).hexdigest(),
    }


def iso_time(seconds: int) -> str:
    # The epoch is an ISO transport convention; the source calendar is unknown.
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def largest_time_gaps(events: list[dict]) -> list[dict]:
    timestamps = sorted({event["t"] for event in events})
    gaps = sorted(
        ((end - start, start, end) for start, end in zip(timestamps, timestamps[1:])),
        reverse=True,
    )
    return [
        {"start_event_t": start, "end_event_t": end, "duration_seconds": duration}
        for duration, start, end in gaps[:2]
    ]


def dataset_files(source: Path) -> dict:
    source_events, fingerprints = read_source(source)
    events = [
        event
        for event in source_events
        if RETAINED_START_INCLUSIVE <= event["t"] < RETAINED_END_EXCLUSIVE
    ]
    if not events:
        raise ValueError("原始文件在指定截断范围内没有交互记录")
    accounts = sorted({e[key] for e in events for key in ("u", "v")}, key=int)
    start = events[0]["t"] // 60 * 60
    span = events[-1]["t"] - start + 1
    snapshot_minutes = (span + SNAPSHOT_COUNT * 60 - 1) // (SNAPSHOT_COUNT * 60)
    width = snapshot_minutes * 60
    frames = [
        {
            "snapshot_id": f"S{index + 1:02d}",
            "present_accounts": accounts.copy(),
            "transactions": [],
        }
        for index in range(SNAPSHOT_COUNT)
    ]
    for event in events:
        frames[(event["t"] - start) // width]["transactions"].append(event)
    snapshots = []
    for index, frame in enumerate(frames):
        kind = "history"
        if index == 11:
            kind = "present"
        elif index == 12:
            kind = "future"
        snapshots.append(
            {
                "snapshot_id": frame["snapshot_id"],
                "index": index,
                "starts_at": iso_time(start + index * width),
                "ends_at": iso_time(start + (index + 1) * width),
                "kind": kind,
            }
        )
    identity = json.dumps(
        {
            "source": fingerprints["uncompressed_sha256"],
            "converter": CONVERTER_VERSION,
            "retained_start_inclusive": RETAINED_START_INCLUSIVE,
            "retained_end_exclusive": RETAINED_END_EXCLUSIVE,
            "snapshot_count": SNAPSHOT_COUNT,
            "snapshot_minutes": snapshot_minutes,
        },
        sort_keys=True,
    )
    version = f"{DATASET_ID}-v2-{hashlib.sha256(identity.encode()).hexdigest()[:12]}"
    manifest = DatasetManifest(
        dataset_id=DATASET_ID,
        dataset_version=version,
        name="Email Dept3（真实邮件，相对时间）",
        synthetic=False,
        seed=0,
        timestamp_unit="seconds",
        timestamp_basis="relative",
        snapshot_minutes=snapshot_minutes,
        observed_until="S12",
        snapshots=snapshots,
    )
    for frame in frames:
        SnapshotData.model_validate(frame)

    # Only historical interactions determine the suggested query account.
    neighbors = {account: set() for account in accounts}
    for frame in frames[:11]:
        for event in frame["transactions"]:
            if event["u"] != event["v"]:
                neighbors[event["u"]].add(event["v"])
                neighbors[event["v"]].add(event["u"])
    query_account = min(
        accounts, key=lambda account: (-len(neighbors[account]), int(account))
    )
    recommended_parameters = {
        method: query_defaults(DATASET_ID, method)
        for method in ("local_core", "density", "periodic", "durable", "burst")
    }
    for parameters in recommended_parameters.values():
        if "account" in parameters:
            parameters["account"] = query_account
    pairs = Counter((e["u"], e["v"]) for e in events if e["u"] != e["v"])
    presence = [
        {"snapshot_id": f["snapshot_id"], "present_accounts": f["present_accounts"]}
        for f in frames
    ]
    nodes = [
        {
            "id": account,
            "label": account,
            "x": round(400 + 260 * math.cos(2 * math.pi * index / len(accounts)), 6),
            "y": round(320 + 260 * math.sin(2 * math.pi * index / len(accounts)), 6),
        }
        for index, account in enumerate(accounts)
    ]
    provenance = {
        "source_url": SOURCE_URL,
        "source_page": SOURCE_PAGE,
        "source_filename": source.name,
        **fingerprints,
        "citation": {
            "title": "Motifs in Temporal Networks",
            "authors": ["Ashwin Paranjape", "Austin R. Benson", "Jure Leskovec"],
            "venue": "WSDM",
            "year": 2017,
        },
        "converter_version": CONVERTER_VERSION,
        "source_time_origin": None,
        "iso_transport_epoch": "1970-01-01T00:00:00+00:00",
        "time_mapping": "t_output = t_source; no rescaling or fabricated calendar origin",
        "snapshot_policy": "13 equal-duration bins over the retained active prefix, rounded up to whole minutes; no internal windows removed",
        "truncation": {
            "start_inclusive": RETAINED_START_INCLUSIVE,
            "end_exclusive": RETAINED_END_EXCLUSIVE,
            "reason": "Fixed prefix cutoff verified against the long inactive gap in SNAP Dept3; no adaptive removal of internal gaps",
            "source_first_event_t": source_events[0]["t"],
            "source_last_event_t": source_events[-1]["t"],
            "retained_first_event_t": events[0]["t"],
            "retained_last_event_t": events[-1]["t"],
            "retained_event_fraction": len(events) / len(source_events),
            "largest_source_time_gaps": largest_time_gaps(source_events),
        },
        "empty_snapshots_preserved": True,
        "empty_snapshot_ids": [
            frame["snapshot_id"] for frame in frames if not frame["transactions"]
        ],
        "presence_policy": "All identified department members remain in every snapshot; no attendance or departure information is available.",
        "layout_method": "numeric-id-circle-v1; no temporal edges used",
        "anomaly_labels": None,
        "recommended_parameters": recommended_parameters,
        "counts": {
            "nodes": len(accounts),
            "input_events": len(source_events),
            "output_events": sum(len(f["transactions"]) for f in frames),
            "excluded_events": len(source_events) - len(events),
            "undirected_pairs": len(pairs),
            "repeated_pair_events": sum(count - 1 for count in pairs.values()),
            "exact_duplicate_events": len(events)
            - len({(e["u"], e["v"], e["t"]) for e in events}),
            "self_loops": sum(e["u"] == e["v"] for e in events),
            "by_snapshot": {f["snapshot_id"]: len(f["transactions"]) for f in frames},
        },
    }
    return {
        "manifest.json": manifest.model_dump(),
        "accounts.json": nodes,
        "observed.json": presence[:12],
        "replay.json": presence[12],
        "provenance.json": provenance,
        **{f"{frame['snapshot_id']}.csv": frame["transactions"] for frame in frames},
    }


def import_dataset(source: Path, output_dir: Path) -> dict:
    files = dataset_files(source)
    existing = output_dir / "manifest.json"
    if existing.exists():
        previous = json.loads(existing.read_text(encoding="utf-8"))
        if previous.get("dataset_id") != DATASET_ID:
            raise ValueError("目标目录已有其他数据集，拒绝覆盖")
    write_dataset(output_dir, files, indent=2)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Settings().data_dir / "raw" / SOURCE_FILENAME
    )
    parser.add_argument("--output", type=Path, default=Settings().data_dir / DATASET_ID)
    args = parser.parse_args()
    try:
        files = import_dataset(args.source, args.output)
    except (OSError, ValueError, EOFError) as error:
        parser.error(str(error))
    manifest = files["manifest.json"]
    print(
        json.dumps(
            {
                "dataset_id": DATASET_ID,
                "dataset_version": manifest["dataset_version"],
                "output": str(args.output.resolve()),
                "snapshot_minutes": manifest["snapshot_minutes"],
                "timestamp_basis": manifest["timestamp_basis"],
                **files["provenance.json"]["counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
