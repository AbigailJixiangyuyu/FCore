"""Serialize a dataset package using the demo's interaction CSV format."""

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory


def write_dataset(output_dir: Path, files: dict, *, indent: int | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_options = {"separators": (",", ":")} if indent is None else {"indent": indent}
    for filename, payload in files.items():
        path = output_dir / filename
        if filename.endswith(".csv"):
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream, fieldnames=["u", "v", "t"]
                )
                writer.writeheader()
                writer.writerows(payload)
        else:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, **json_options) + "\n",
                encoding="utf-8",
            )


def publish_dataset(data_dir: Path, dataset_id: str, files: dict) -> None:
    """Expose a new manifest only after every snapshot is written."""
    destination = data_dir / dataset_id
    manifest_path = destination / "manifest.json"
    if manifest_path.is_file():
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".import-", dir=data_dir) as staging:
        package = Path(staging) / dataset_id
        write_dataset(package, files)
        try:
            package.rename(destination)
        except OSError:
            if not manifest_path.is_file():
                raise
