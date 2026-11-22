"""Contracts shared by the independent historical pattern algorithms."""

from dataclasses import dataclass
from typing import Any, TypeAlias

TemporalSnapshots: TypeAlias = tuple[dict[str, frozenset[str]], ...]


@dataclass(frozen=True, slots=True)
class PatternResult:
    """A single result; evidence uses zero-based inclusive time positions."""

    members: tuple[str, ...]
    evidence: dict[str, Any]
