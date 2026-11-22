"""Call the SIGMOD 2025 author's solver through a small WSL adapter."""

import logging
import os
import subprocess
from pathlib import Path
from shutil import which

METHOD = "sigmod25-parallel-kcore-v1"
BUILD_COMMAND = "uv run --directory demo/backend python -m scripts.build_parallel_core"
DISTRO = "Ubuntu-24.04"
_OUTPUT_PREFIX = b"KCORE_RESULT "
_LOGGER = logging.getLogger(__name__)


class ParallelCoreError(RuntimeError):
    pass


def wsl_command(directory: Path, *command: str) -> list[str]:
    return ["wsl.exe", "-d", DISTRO, "--cd", str(directory), "--exec", *command]


def is_built(binary: Path) -> bool:
    return binary.is_file() and which("wsl.exe") is not None


def decompose(
    graph: dict[str, set[str]], binary: Path, *, threads: int | None = None
) -> dict[str, int]:
    if not binary.is_file():
        raise ParallelCoreError(f"Build the parallel core solver first. Run {BUILD_COMMAND} from the project root.")
    if threads is None:
        threads = min(8, os.cpu_count() or 1)

    nodes = sorted(graph)
    indices = {node: index for index, node in enumerate(nodes)}
    offsets = [0]
    neighbors = []
    for node in nodes:
        neighbors.extend(sorted(indices[neighbor] for neighbor in graph[node]))
        offsets.append(len(neighbors))
    data = (
        f"{len(nodes)} {len(neighbors)}\n"
        + " ".join(map(str, offsets))
        + "\n"
        + " ".join(map(str, neighbors))
        + "\n"
    ).encode("ascii")

    command = wsl_command(
        binary.parent, "env", f"PARLAY_NUM_THREADS={threads}", f"./{binary.name}"
    )
    try:
        result = subprocess.run(
            command, input=data, capture_output=True, timeout=60, check=True
        )
    except subprocess.TimeoutExpired as error:
        raise ParallelCoreError("Parallel core decomposition timed out. Try again.") from error
    except subprocess.CalledProcessError as error:
        message = (error.stderr or error.stdout).decode("utf-8", errors="replace")[-1500:]
        _LOGGER.warning("Parallel k-core exited with status %s: %s", error.returncode, message)
        raise ParallelCoreError("Parallel core decomposition failed. Check WSL or rebuild the solver and try again.") from error
    except OSError as error:
        raise ParallelCoreError(f"Could not start WSL. Parallel core decomposition requires {DISTRO}.") from error

    try:
        line, = [
            line[len(_OUTPUT_PREFIX):]
            for line in result.stdout.splitlines()
            if line.startswith(_OUTPUT_PREFIX)
        ]
        numbers = [int(value) for value in line.split()]
        if len(numbers) != len(nodes) or any(
            number < 0 or number > len(graph[node]) for node, number in zip(nodes, numbers)
        ):
            raise ValueError("Invalid core numbers")
    except ValueError as error:
        raise ParallelCoreError("Parallel core decomposition returned an invalid result. Rebuild the solver and try again.") from error
    return dict(zip(nodes, numbers))
