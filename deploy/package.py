"""Build the Vue UI and assemble the build context for the remote Linux Docker host."""

import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("ethereum-eth", "email-eu-core-dept3", "synthetic-small")
MODELS = (
    ("ethereum-eth", "slade", "current.json"),
    ("ethereum-eth", "zebra", "current.json"),
    ("ethereum-eth", "zebra", "current-h2.json"),
    ("ethereum-eth", "zebra", "current-h3.json"),
    ("email-eu-core-dept3", "slade", "current.json"),
    ("email-eu-core-dept3", "zebra", "current.json"),
    ("email-eu-core-dept3", "zebra", "current-h2.json"),
    ("email-eu-core-dept3", "zebra", "current-h3.json"),
    ("synthetic-small", "slade", "current.json"),
)


def active_model_files():
    root = ROOT / "models"
    pointers = [root / dataset / model / name for dataset, model, name in MODELS]
    for grain in ("monthly", "weekly"):
        for dataset, model, name in MODELS:
            if dataset == "email-eu-core-dept3" or (grain == "monthly" and dataset == "ethereum-eth" and model == "slade"):
                pointers.append(root / "granularity" / grain / dataset / model / name)
    for pointer in pointers:
        model = pointer.parent.name
        version = json.loads(pointer.read_text(encoding="utf-8"))["model_version"]
        if not re.fullmatch(rf"{model}-[0-9a-f]{{16}}", version):
            raise ValueError(f"Invalid model version in {pointer}")
        directory = pointer.parent / version
        manifest_file = directory / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        checkpoint = directory / "checkpoint.pt"
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if manifest["model_version"] != version or digest != manifest["checkpoint_sha256"]:
            raise ValueError(f"Checkpoint verification failed for {directory}")
        yield from (pointer, manifest_file, checkpoint)


def package_files():
    for name in ("Dockerfile", ".dockerignore", "README.md"):
        yield ROOT / "deploy" / name, name
    yield ROOT / "backend/.env.example", "fcore.env.example"
    files = [
        ROOT / name for name in (
            "backend/pyproject.toml", "backend/uv.lock", "backend/README.md",
            "backend/scripts/__init__.py", "backend/scripts/build_parallel_core.py",
            "backend/algorithms/core/parallel_adapter.cpp", "config/query-defaults.json",
        )
    ]
    for tree in ("backend/app", "backend/algorithms"):
        files.extend(sorted((ROOT / tree).rglob("*.py")))
    files.extend(sorted(p for p in (ROOT / "frontend/dist").rglob("*") if p.is_file()))
    for dataset in DATASETS:
        directory = ROOT / "data" / dataset
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        files.extend(directory / (meta["snapshot_id"] + ".csv") for meta in manifest["snapshots"])
        files.extend(directory / name for name in ("accounts.json", "manifest.json", "observed.json", "replay.json", "README.md"))
        files.append(directory / ("scenarios.json" if dataset == "synthetic-small" else "provenance.json"))
    vendor = ROOT / "backend/vendor/parallel-kcore"
    files.extend(sorted(path for path in vendor.rglob("*") if path.is_file()))
    files.extend(active_model_files())
    for path in files:
        yield path, path.relative_to(ROOT).as_posix()



def main():
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise SystemExit("Install Node.js and npm before packaging the frontend.")
    subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    output = ROOT / "exports/fcore-linux-amd64.tar.gz"
    output.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        archive = Path(temporary) / output.name
        with tarfile.open(archive, "w:gz") as bundle:
            for path, name in package_files():
                # The release contains regular files readable by the container's service user.
                info = bundle.gettarinfo(str(path), f"fcore-cpu/{name}")
                if not info.isfile():
                    raise ValueError(f"Expected a regular file at {path}")
                info.mode = 0o644
                with path.open("rb") as file:
                    bundle.addfile(info, file)
        archive.replace(output)
    print(output)


if __name__ == "__main__":
    main()
