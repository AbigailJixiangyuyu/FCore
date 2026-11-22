"""Generate the committed synthetic case: uv run python -m scripts.generate_sample."""

import math
import random
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

from app.core.config import Settings
from app.core.interactions import undirected_dataset_version, undirected_pair
from app.repositories.dataset_writer import write_dataset

DATASET_ID = "synthetic-small"
DATASET_VERSION = undirected_dataset_version("synthetic-small-v3")
SEED = 20261116
COLORS = ["#477be7", "#9670c7", "#36a194", "#c99c43"]


def account(number: int) -> str:
    return f"a-{number:03d}"


def accounts() -> list[dict]:
    rows = [
        [116, 224, 332, 440, 548],
        [80, 188, 296, 404, 512, 620],
        [116, 224, 332, 440, 548],
        [80, 188, 296, 404, 512, 620],
        [170, 278, 386, 494],
    ]
    result = []
    for row, positions in enumerate(rows):
        for x in positions:
            identifier = account(len(result) + 1)
            result.append(
                {"id": identifier, "label": identifier, "x": x, "y": 70 + row * 58}
            )
    return result


def scenarios() -> dict:
    definitions = {
        "periodic": [
            (
                "P1",
                [1, 2, 6, 7, 12, 13, 17, 18, 23],
                [1, 1, 10, 1, 1, 10, 1, 1, 10, 1, 1],
            ),
            (
                "P2",
                [3, 4, 8, 9, 14, 15, 19, 20, 24, 25],
                [1, 9, 1, 1, 1, 9, 1, 1, 1, 9, 1],
            ),
            ("P3", [5, 10, 11, 16, 21, 22, 26], [1, 8, 1, 8, 1, 8, 1, 8, 1, 8, 1]),
        ],
        "durable": [
            ("D1", list(range(1, 12)), [8, 8, 9, 9, 9, 8, 9, 8, 9, 9, 8]),
            ("D2", list(range(12, 17)), [0, 8, 8, 9, 8, 8, 9, 8, 9, 8, 8]),
            ("D3", list(range(17, 27)), [0, 0, 8, 9, 8, 9, 8, 8, 9, 9, 9]),
        ],
        "burst": [
            ("B1", [1, 2, 3, 6, 7, 12, 17], [1, 1, 1, 1, 1, 1, 2, 10, 15, 5, 1]),
            (
                "B2",
                [4, 5, 8, 9, 10, 13, 14, 18, 19, 23],
                [1, 1, 1, 1, 1, 2, 9, 15, 4, 1, 1],
            ),
            (
                "B3",
                [11, 15, 16, 20, 21, 22, 24, 25, 26],
                [1, 1, 1, 1, 1, 1, 1, 1, 2, 7, 13],
            ),
        ],
    }
    patterns = {}
    for kind, groups in definitions.items():
        patterns[kind] = [
            {
                "id": identifier,
                "members": list(map(account, members)),
                "color": COLORS[index],
                "generation_profile": profile,
                "description": "Preset members demonstrate coloring and snapshot tracking. Evidence summarizes the synthetic interactions.",
            }
            for index, (identifier, members, profile) in enumerate(groups)
        ]
    return {
        "patterns": patterns,
        "prediction_profile": [40, 30, 20, 10, 6, 4, 2],
    }


def background_topology(
    nodes: list[dict], index: int
) -> tuple[list[str], list[tuple[str, str]]]:
    if index == 11:
        pairs = set()
        motifs = [
            [1, 2, 7, 8, 13],
            [3, 4, 8, 9],
            [4, 5, 10, 11],
            [13, 14, 18, 19],
            [15, 16, 21, 22],
            [17, 18, 23, 24],
            [6, 7, 12],
        ]
        for members in motifs:
            for position, first in enumerate(members):
                pairs.update(
                    tuple(sorted((account(first), account(second))))
                    for second in members[position + 1 :]
                )
        pairs.update(
            (account(a), account(b))
            for a, b in [
                (9, 10),
                (9, 14),
                (14, 15),
                (19, 20),
                (20, 21),
                (20, 25),
                (24, 25),
                (25, 26),
                (22, 26),
            ]
        )
        return [node["id"] for node in nodes], sorted(pairs)

    availability = {"a-011": (0, 6), "a-025": (3, 10), "a-026": (7, 10)}
    present = [
        node["id"]
        for node in nodes
        if availability.get(node["id"], (0, 10))[0]
        <= index
        <= availability.get(node["id"], (0, 10))[1]
    ]
    possible = [
        (first["id"], second["id"])
        for position, first in enumerate(nodes)
        for second in nodes[position + 1 :]
        if math.hypot(first["x"] - second["x"], first["y"] - second["y"]) <= 112
    ]
    selected = []
    for edge_index, (source, target) in enumerate(possible):
        if source not in present or target not in present:
            continue
        phase = edge_index % 5
        keep = [
            True,
            (index + edge_index // 5) % 3 == 2,
            index >= 8,
            (index + edge_index) % 4 < 2,
            (index + edge_index) % 5 == 0,
        ][phase]
        if keep:
            selected.append((source, target))
    return present, selected


def historical_core_edges(index: int) -> set[tuple[str, str]]:
    """Create structural signals for the unchanged default mining parameters."""
    groups = []
    if index in (0, 3, 6, 9):
        groups.append((1, 2, 7, 8, 13))
    if 6 <= index <= 8:
        groups.append((14, 15, 16, 20, 21, 22))
    return {
        (account(first), account(second))
        for group in groups
        for first, second in combinations(group, 2)
    }


def generate_dataset(output_dir: Path) -> dict:
    rng = random.Random(SEED)
    nodes = accounts()
    annotations = scenarios()
    start = datetime(2026, 1, 1, 10, tzinfo=timezone(timedelta(hours=8)))
    manifest = {
        "dataset_id": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "name": "Synthetic Sample",
        "synthetic": True,
        "seed": SEED,
        "timestamp_unit": "seconds",
        "snapshot_minutes": 10,
        "observed_until": "S12",
        "snapshots": [],
    }
    snapshots = []
    for index in range(13):
        snapshot_id = f"S{index + 1:02d}"
        begins = start + timedelta(minutes=index * 10)
        kind = "history"
        if index == 11:
            kind = "present"
        elif index == 12:
            kind = "future"
        manifest["snapshots"].append(
            {
                "snapshot_id": snapshot_id,
                "index": index,
                "starts_at": begins.isoformat(),
                "ends_at": (begins + timedelta(minutes=10)).isoformat(),
                "kind": kind,
            }
        )
        if index < 12:
            present, pairs = background_topology(nodes, index)
        else:
            present, current_pairs = background_topology(nodes, 11)
            pairs = sorted(
                set(current_pairs)
                | {
                    (target, source)
                    for source, target in current_pairs
                    if target != "a-026"
                }
            )
        extra_pairs = historical_core_edges(index) - set(pairs) if index < 11 else set()
        # Keep the background RNG stream intact when adding historical transfers.
        core_rng = random.Random(f"{SEED}:history-cores:{snapshot_id}")
        transactions = []
        for source, target in [*pairs, *sorted(extra_pairs)]:
            edge_rng = core_rng if (source, target) in extra_pairs else rng
            u, v = undirected_pair(source, target)
            count = 2 + edge_rng.randrange(4)
            if index < 11:
                for groups in annotations["patterns"].values():
                    for group in groups:
                        if source in group["members"] and target in group["members"]:
                            count += group["generation_profile"][index]
            for _ in range(count):
                # Consume the former attribute draw to preserve v2 interaction times.
                edge_rng.randint(100, 999999)
                timestamp = begins + timedelta(seconds=edge_rng.randrange(600))
                transactions.append(
                    {
                        "u": u,
                        "v": v,
                        "t": int(timestamp.timestamp()),
                    }
                )
        transactions.sort(key=lambda item: item["t"])
        snapshots.append(
            {
                "snapshot_id": snapshot_id,
                "present_accounts": present,
                "transactions": transactions,
            }
        )
    snapshot_accounts = [
        {
            "snapshot_id": frame["snapshot_id"],
            "present_accounts": frame["present_accounts"],
        }
        for frame in snapshots
    ]
    files = {
        "manifest.json": manifest,
        "accounts.json": nodes,
        "scenarios.json": annotations,
        "observed.json": snapshot_accounts[:12],
        "replay.json": snapshot_accounts[12],
        **{f"{frame['snapshot_id']}.csv": frame["transactions"] for frame in snapshots},
    }
    write_dataset(output_dir, files)
    return files


if __name__ == "__main__":
    destination = Settings().data_dir / DATASET_ID
    result = generate_dataset(destination)
    print(
        f"Generated {DATASET_ID}: 26 accounts, 12 observed snapshots + 1 separate replay; {destination}"
    )
