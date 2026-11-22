"""Build the local author solver adapter without editing the reference checkout."""

import argparse
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from algorithms.core.parallel import DISTRO, wsl_command
from app.core.config import Settings

ADAPTER = Path(__file__).resolve().parents[1] / "algorithms" / "core" / "parallel_adapter.cpp"


def build(source: Path, binary: Path) -> None:
    if not (source / "KCore" / "kcore.h").is_file():
        raise FileNotFoundError(f"找不到 Parallel-KCore 作者源码: {source}")
    parlay_include = Path("external/parlaylib/include")
    if not (source / parlay_include / "parlay" / "parallel.h").is_file():
        raise FileNotFoundError(f"作者源码目录缺少 ParlayLib: {source / parlay_include}")

    binary.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=binary.parent, prefix="kcore-", suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
    try:
        linux_output = subprocess.check_output(
            wsl_command(source, "wslpath", "-a", "-u", str(temporary)),
            encoding="utf-8",
        ).strip()
        subprocess.run(
            wsl_command(
                source, "g++", "-std=c++20", "-O3", "-mcx16", "-march=native",
                "-pthread", "-I.", f"-I{parlay_include.as_posix()}",
                "-x", "c++", "-", "-o", linux_output,
            ),
            input=ADAPTER.read_bytes(),
            check=True,
        )
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
        parser.exit(1, f"编译失败，请检查 {DISTRO}、g++ 和作者源码目录：{error}\n")
    print(f"并行核分解已构建: {settings.parallel_core_binary}")


if __name__ == "__main__":
    main()
