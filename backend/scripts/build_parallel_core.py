"""Build the local author solver adapter without editing the reference checkout."""

import argparse
import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from algorithms.core.parallel import wsl_command
from app.core.config import Settings

ADAPTER = Path(__file__).resolve().parents[1] / "algorithms" / "core" / "parallel_adapter.cpp"


def build(source: Path, binary: Path) -> None:
    if not (source / "KCore" / "kcore.h").is_file():
        raise FileNotFoundError(f"Could not find the Parallel-KCore source at {source}")
    parlay_include = Path("external/parlaylib/include")
    if not (source / parlay_include / "parlay" / "parallel.h").is_file():
        raise FileNotFoundError(f"ParlayLib is missing from {source / parlay_include}")

    binary.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=binary.parent, prefix="kcore-", suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
    try:
        output = str(temporary.resolve())
        if os.name == "nt":
            output = subprocess.check_output(
                wsl_command(source, "wslpath", "-a", "-u", output), encoding="utf-8",
            ).strip()
        command = [
            "g++", "-std=c++20", "-O3", "-mcx16", "-pthread", "-I.",
            f"-I{parlay_include.as_posix()}", "-x", "c++", "-", "-o", output,
        ]
        subprocess.run(
            wsl_command(source, *command) if os.name == "nt" else command,
            cwd=source, input=ADAPTER.read_bytes(), check=True,
        )
        if os.name != "nt":
            temporary.chmod(0o755)
        temporary.replace(binary)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir", type=Path,
        default=settings.project_root.parent / "参考论文" / "并行核分解" / "代码",
        help="Parallel-KCore source directory including external/parlaylib",
    )
    args = parser.parse_args()
    try:
        build(args.source_dir.resolve(), settings.parallel_core_binary)
    except (OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Build failed. Check g++ and the source directory. {error}\n")
    print(f"Built the parallel core solver at {settings.parallel_core_binary}")


if __name__ == "__main__":
    main()
