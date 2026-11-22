"""Reproduce the paper's TD + FT/AC pipeline with explicit numeric boundaries.

This is a deterministic reproduction of the published candidate-search flow,
not a globally exact solver of the LPC vertex-subset optimization problem.
See PERIODIC.md for the reproduction conventions and the known limitation.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from itertools import combinations
from math import ceil, cos, floor, isclose, isfinite, pi, sin
from random import Random

from algorithms.patterns.common import PatternResult, TemporalSnapshots

METHOD = "lpc-td-ftac-v1"
CONVENTIONS_VERSION = "td-ftac-boundaries-v1"
PERMUTATIONS = 100
SEED_PREFIX = "20261116:"
POWER_REL_TOLERANCE = 1e-10
POWER_ABS_TOLERANCE = 1e-12
EMPTY_NEIGHBORS: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class _PeriodicSegment:
    period: int
    frequency: int
    start_index: int
    end_index: int

    def as_dict(self) -> dict[str, int]:
        return {
            "period": self.period,
            "frequency": self.frequency,
            "start_index": self.start_index,
            "end_index": self.end_index,
        }


def _common_core(
    snapshots: TemporalSnapshots,
    times: tuple[int, ...],
    candidates: frozenset[str],
    account: str,
    k: int,
) -> frozenset[str]:
    """Algorithm 2: jointly peel vertices over every mandatory snapshot."""
    if account not in candidates:
        return frozenset()
    active = set(candidates)
    degrees = {
        time: {
            node: len(snapshots[time].get(node, EMPTY_NEIGHBORS) & active)
            for node in active
        }
        for time in times
    }
    queued = {node for node in active if any(degrees[time][node] < k for time in times)}
    queue = deque(sorted(queued))
    while queue:
        node = queue.popleft()
        if node == account:
            return frozenset()
        active.remove(node)
        for time in times:
            for neighbor in snapshots[time].get(node, EMPTY_NEIGHBORS) & active:
                degrees[time][neighbor] -= 1
                if degrees[time][neighbor] < k and neighbor not in queued:
                    queued.add(neighbor)
                    queue.append(neighbor)
    return frozenset(active)


def _td_candidates(
    snapshots: TemporalSnapshots, account: str, k: int
) -> tuple[frozenset[str], ...]:
    """Algorithm 1: initialize time pairs, then join equal-length prefixes."""
    vertices = frozenset(node for snapshot in snapshots for node in snapshot)
    record: set[frozenset[str]] = set()
    for first in range(len(snapshots) - 1):
        current = {}
        for second in range(first + 1, len(snapshots)):
            times = (first, second)
            members = _common_core(snapshots, times, vertices, account, k)
            if members:
                current[times] = members

        while current:
            record.update(current.values())
            prefixes = defaultdict(list)
            for times, members in sorted(current.items()):
                prefixes[times[:-1]].append((times, members))
            following = {}
            for entries in prefixes.values():
                for (left, left_members), (right, right_members) in combinations(
                    entries, 2
                ):
                    times = (*left, right[-1])
                    members = _common_core(
                        snapshots, times, left_members & right_members, account, k
                    )
                    if members:
                        following[times] = members
            current = following
    return tuple(sorted(record, key=lambda members: tuple(sorted(members))))


def _kcore_time_series(
    snapshots: TemporalSnapshots, members: frozenset[str], k: int
) -> tuple[int, ...]:
    return tuple(
        int(
            all(
                len(snapshot.get(node, EMPTY_NEIGHBORS) & members) >= k
                for node in members
            )
        )
        for snapshot in snapshots
    )


@lru_cache(maxsize=32)
def _dft_coefficients(length: int) -> tuple[tuple[complex, ...], ...]:
    return tuple(
        tuple(
            complex(
                cos(-2 * pi * frequency * time / length),
                sin(-2 * pi * frequency * time / length),
            )
            for time in range(length)
        )
        for frequency in range(1, length // 2 + 1)
    )


def _periodogram(series: tuple[int, ...] | list[int]) -> tuple[float, ...]:
    return tuple(
        abs(sum(value * coefficient for value, coefficient in zip(series, row))) ** 2
        for row in _dft_coefficients(len(series))
    )


def _local_peaks(
    autocorrelation: tuple[int, ...], start: int, end: int
) -> tuple[int, ...]:
    """Keep the leftmost lag of each peak plateau inside an inclusive range."""
    peaks = []
    index = start
    while index <= end:
        plateau_end = index
        while (
            plateau_end < end
            and autocorrelation[plateau_end + 1] == autocorrelation[index]
        ):
            plateau_end += 1
        above_left = index == start or (
            autocorrelation[index] > autocorrelation[index - 1]
        )
        above_right = plateau_end == end or (
            autocorrelation[index] > autocorrelation[plateau_end + 1]
        )
        if above_left and above_right:
            peaks.append(index)
        index = plateau_end + 1
    return tuple(peaks)


def _detect_periods(series: tuple[int, ...]) -> tuple[tuple[int, ...], dict]:
    length = len(series)
    if length < 4 or len(set(series)) < 2:
        return (), {}
    powers = _periodogram(series)
    binary = "".join(map(str, series))
    seed = int.from_bytes(
        sha256((SEED_PREFIX + binary).encode("ascii")).digest(), "big"
    )
    random = Random(seed)
    maxima = []
    for _ in range(PERMUTATIONS):
        permutation = list(series)
        random.shuffle(permutation)
        maxima.append(max(_periodogram(permutation)))
    threshold = sorted(maxima, reverse=True)[98]
    significant = [
        frequency
        for frequency, power in enumerate(powers, start=1)
        if power > threshold
        and not isclose(
            power,
            threshold,
            rel_tol=POWER_REL_TOLERANCE,
            abs_tol=POWER_ABS_TOLERANCE,
        )
    ]
    autocorrelation = tuple(
        sum(series[time] * series[(time + lag) % length] for time in range(length))
        for lag in range(length)
    )
    periods: set[int] = set()
    for frequency in significant:
        if frequency == 1:
            continue
        start = max(1, floor(length / frequency))
        end = min(length // 2, ceil(length / (frequency - 1)) - 1)
        periods.update(_local_peaks(autocorrelation, start, end))
    spectral = {
        "permutations": PERMUTATIONS,
        "threshold_rule": "99th-largest-of-100",
        "power_threshold": threshold,
        "positive_frequency_powers": list(powers),
        "significant_frequencies": significant,
        "candidate_periods": sorted(periods),
        "seed_scheme": "sha256('20261116:' + binary_series)",
        "power_tolerance": {
            "relative": POWER_REL_TOLERANCE,
            "absolute": POWER_ABS_TOLERANCE,
        },
    }
    return tuple(sorted(periods)), spectral


def _jaccard_at_least(left: int, right: int, epsilon: Fraction) -> bool:
    union = (left | right).bit_count()
    if not union:
        return True
    return (left & right).bit_count() * epsilon.denominator >= union * epsilon.numerator


def _periodic_segments(
    series: tuple[int, ...], periods: tuple[int, ...], epsilon: Fraction
) -> tuple[_PeriodicSegment, ...]:
    """Extract pairwise-compatible, whole-block maximal intervals in all phases."""
    packed = sum(value << time for time, value in enumerate(series))
    segments = []
    for period in periods:
        mask = (1 << period) - 1
        for start in range(len(series) - 2 * period + 1):
            blocks = []
            for block_start in range(start, len(series) - period + 1, period):
                block = (packed >> block_start) & mask
                if any(
                    not _jaccard_at_least(block, previous, epsilon)
                    for previous in blocks
                ):
                    break
                blocks.append(block)
            if len(blocks) >= 2 and any(blocks):
                segments.append(
                    _PeriodicSegment(
                        period, len(blocks), start, start + period * len(blocks) - 1
                    )
                )
    maximal = [
        segment
        for segment in segments
        if not any(
            other.period == segment.period
            and (segment.start_index - other.start_index) % segment.period == 0
            and other.start_index <= segment.start_index
            and other.end_index >= segment.end_index
            and other != segment
            for other in segments
        )
    ]
    return tuple(
        sorted(
            maximal,
            key=lambda segment: (
                -segment.frequency,
                segment.start_index,
                segment.period,
                segment.end_index,
            ),
        )
    )


def mine_periodic(
    snapshots: TemporalSnapshots,
    account: str = "a-001",
    k: int = 4,
    epsilon: float = 0.2,
) -> PatternResult | None:
    """Return one deterministic best LPC candidate from the paper's TD flow."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    if not isfinite(epsilon) or not 0 <= epsilon <= 1:
        raise ValueError("epsilon must be finite and between 0 and 1")
    if len(snapshots) < 2:
        return None
    similarity = Fraction(str(epsilon))
    analysis_by_series = {}
    best_frequency = 0
    best_results = []
    for members in _td_candidates(snapshots, account, k):
        series = _kcore_time_series(snapshots, members, k)
        if series not in analysis_by_series:
            periods, spectral = _detect_periods(series)
            segments = _periodic_segments(series, periods, similarity)
            analysis_by_series[series] = (segments, spectral)
        segments, spectral = analysis_by_series[series]
        if not segments or segments[0].frequency < best_frequency:
            continue
        best = segments[0]
        if best.frequency > best_frequency:
            best_frequency = best.frequency
            best_results = []
        best_results.append(
            PatternResult(
                tuple(sorted(members)),
                {
                    "kcore_series": list(series),
                    **best.as_dict(),
                    "periodic_segments": [segment.as_dict() for segment in segments],
                    "spectral": spectral,
                    "method": METHOD,
                    "conventions_version": CONVENTIONS_VERSION,
                },
            )
        )
    if not best_results:
        return None
    maximal = [
        result
        for result in best_results
        if not any(set(result.members) < set(other.members) for other in best_results)
    ]
    return min(maximal, key=lambda result: (-len(result.members), result.members))
