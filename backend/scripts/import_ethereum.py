"""Build the Ethereum mainnet weekly sample from two pinned Zenodo files."""

import argparse
import bz2
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from algorithms.core.queries import core_numbers
from app.core.config import Settings
from app.core.interactions import undirected_pair
from app.repositories.dataset_writer import write_dataset
from app.schemas.analysis import DatasetManifest
from app.services.dataset_import import account_catalog, snapshot_metadata

DATASET_ID = "ethereum-eth"
SOURCE = "https://doi.org/10.5281/zenodo.4718440"
BLOCK_TIMES = "eth-blocktime-0-999999.txt.bz2"
TRANSFERS = "eth-tx-0-999999.txt.bz2"
SOURCE_HASHES = {
    BLOCK_TIMES: "ad131dc61f472ed729ad8a9e7e29655bbf6eee408e2e687bd218ff18bd5d843e",
    TRANSFERS: "7d1d548440b12bd68cbad869d08122c7bedb9d768fe06e5e057ee870d4694436",
}
START = int(datetime(2015, 10, 5, tzinfo=timezone.utc).timestamp())
WEEK = 7 * 24 * 3600
SIZE = 89
ZERO_ADDRESS = "0x" + "0" * 40


def block_times(source: Path) -> dict[int, int]:
    times = {}
    with bz2.open(source, "rt", encoding="ascii") as stream:
        for line in stream:
            block, raw = line.split()
            timestamp = int(raw, 16)
            if START - 4 * WEEK <= timestamp < START + 13 * WEEK:
                times[int(block)] = timestamp
    return times


def transfers(source: Path, times: dict[int, int], start: int, end: int):
    with bz2.open(source, "rt", encoding="ascii") as stream:
        for line in stream:
            asset, block, position, sender, receiver, value = line.split()
            timestamp = times.get(int(block))
            if timestamp is None or not start <= timestamp < end:
                continue
            if asset != "ETH" or position == "0" or int(value, 16) == 0:
                continue
            # Rewards, contract creation and the null address have no two parties.
            if len(sender) != 42 or len(receiver) != 42 or sender == receiver:
                continue
            if ZERO_ADDRESS in (sender, receiver):
                continue
            yield sender, receiver, timestamp


def select_addresses(source: Path, times: dict[int, int]) -> dict[str, str]:
    graph = defaultdict(set)
    for u, v, _ in transfers(source, times, START - 4 * WEEK, START):
        graph[u].add(v)
        graph[v].add(u)
    numbers = core_numbers(graph)
    ranked = sorted(graph, key=lambda node: (-numbers[node], -len(graph[node]), node))
    if len(ranked) < SIZE:
        raise ValueError("The selection period has fewer than 89 eligible addresses.")
    return {address: f"E{index:03}" for index, address in enumerate(sorted(ranked[:SIZE]), 1)}


def dataset_files(directory: Path) -> dict:
    for filename, expected in SOURCE_HASHES.items():
        if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Unexpected SHA-256 for {filename}. Use Zenodo record 4718440, version 2.")
    source = directory / TRANSFERS
    times = block_times(directory / BLOCK_TIMES)
    ids = select_addresses(source, times)
    snapshots = snapshot_metadata(START // 60, WEEK // 60)
    windows = [[] for _ in snapshots]
    for sender, receiver, timestamp in transfers(source, times, START, START + len(windows) * WEEK):
        if sender in ids and receiver in ids:
            u, v = undirected_pair(ids[sender], ids[receiver])
            windows[(timestamp - START) // WEEK].append({"u": u, "v": v, "t": timestamp})
    for window in windows:
        window.sort(key=lambda event: event["t"])

    accounts = account_catalog(set(ids.values()))
    presence = [
        {"snapshot_id": meta.snapshot_id, "present_accounts": sorted(ids.values())}
        for meta in snapshots
    ]
    provenance = {
        "source": SOURCE, "paper": "https://doi.org/10.1007/s10586-021-03511-0",
        "authors": ["Can Özturan", "Alper Şen", "Baran Kılıç"],
        "license": "CC BY 4.0", "source_sha256": SOURCE_HASHES,
        "selection_start": datetime.fromtimestamp(START - 4 * WEEK, timezone.utc).isoformat(),
        "selection_end_exclusive": snapshots[0].starts_at,
        "selection": "Top 89 by coreness, then distinct neighbors, then address in the four preceding weeks.",
        "transfers": "Successful positive native ETH transfers between two distinct nonzero addresses in the cohort. One event per retained source row. Endpoints are unordered.",
        "address_by_id": {key: address for address, key in ids.items()},
        "events_per_snapshot": {meta.snapshot_id: len(rows) for meta, rows in zip(snapshots, windows)},
    }
    identity = json.dumps([provenance, windows], sort_keys=True, separators=(",", ":")).encode()
    manifest = DatasetManifest(
        dataset_id=DATASET_ID, dataset_version=f"{DATASET_ID}-v1-{hashlib.sha256(identity).hexdigest()[:12]}",
        name="Ethereum", synthetic=False, seed=0, snapshot_minutes=WEEK // 60,
        observed_until="S12", snapshots=snapshots,
    )
    return {
        "manifest.json": manifest.model_dump(), "accounts.json": accounts,
        "observed.json": presence[:-1], "replay.json": presence[-1], "provenance.json": provenance,
        **{f"{meta.snapshot_id}.csv": rows for meta, rows in zip(snapshots, windows)},
    }


def main():
    data = Settings().data_dir
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=data / "raw/ethereum-zenodo-4718440")
    args = parser.parse_args()
    files = dataset_files(args.source_dir)
    write_dataset(data / DATASET_ID, files, indent=2)
    print(files["manifest.json"]["dataset_version"], files["provenance.json"]["events_per_snapshot"])


if __name__ == "__main__":
    main()
