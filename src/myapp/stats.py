"""Statistics and formatting helpers for PR KPI reporting.

This module provides utilities for:
- Computing linear-interpolation percentiles from pre-sorted samples.
- Aggregating common KPI summary statistics (P50, P75, P90, count).
- Formatting second-based durations as ``HH:MM:SS``.
- Building a human-readable report for dwell and completion KPI metrics.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, cast


def calculate_percentile(sorted_values: List[float], p: float) -> Optional[float]:
    """Calculate a percentile using linear interpolation.

    The input sequence is expected to already be sorted in ascending order.
    This implementation matches the reference approach:
    - Empty input returns ``None``.
    - ``p <= 0`` returns the first value.
    - ``p >= 100`` returns the last value.
    - Otherwise, percentile is linearly interpolated between adjacent ranks.

    Args:
        sorted_values: Sorted numeric samples.
        p: Percentile in the inclusive range ``[0, 100]``.

    Returns:
        Percentile value as ``float`` or ``None`` when input is empty.

    Raises:
        ValueError: If ``p`` is outside ``[0, 100]``.
    """
    if not 0 <= p <= 100:
        raise ValueError("Percentile 'p' must be in the range [0, 100].")

    if not sorted_values:
        return None

    if p <= 0:
        return sorted_values[0]

    if p >= 100:
        return sorted_values[-1]

    position = (len(sorted_values) - 1) * (p / 100.0)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return sorted_values[int(position)]

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    return lower_value + (upper_value - lower_value) * (position - lower_index)


def compute_statistics(samples: List[float]) -> Dict[str, Optional[float]]:
    """Compute P50, P75, P90, and sample count for duration samples.

    Samples are sorted internally before percentile calculations. ``None`` and
    negative values are ignored defensively to keep downstream reporting robust.

    Args:
        samples: Duration samples in seconds.

    Returns:
        Dictionary with keys ``p50``, ``p75``, ``p90``, and ``count``.
        Percentiles are ``None`` when no valid samples exist.
        ``count`` is always the number of valid samples included.
    """
    clean_samples = sorted(
        sample
        for sample in samples
        if sample is not None and not math.isnan(sample) and sample >= 0
    )

    return {
        "p50": calculate_percentile(clean_samples, 50),
        "p75": calculate_percentile(clean_samples, 75),
        "p90": calculate_percentile(clean_samples, 90),
        "count": cast(Optional[float], len(clean_samples)),
    }


def format_duration(seconds: Optional[float]) -> str:
    """Format seconds as ``HH:MM:SS``.

    Args:
        seconds: Duration in seconds.

    Returns:
        ``"n/a"`` when ``seconds`` is ``None``; otherwise a rounded
        ``HH:MM:SS`` string.
    """
    if seconds is None:
        return "n/a"

    total_seconds = int(round(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


def generate_report(repo_name: str, dwell_times: List[float], completion_times: List[float]) -> str:
    """Generate a human-readable KPI report for a repository.

    The report includes sample counts and P50/P75/P90 values for:
    - PR review dwell time
    - PR completion time

    All durations are formatted using :func:`format_duration`.

    Args:
        repo_name: Repository display name.
        dwell_times: Dwell-time samples in seconds.
        completion_times: Completion-time samples in seconds.

    Returns:
        Formatted multi-line text report.
    """
    dwell_stats = compute_statistics(dwell_times)
    completion_stats = compute_statistics(completion_times)

    dwell_count = int(cast(float, dwell_stats["count"]))
    completion_count = int(cast(float, completion_stats["count"]))

    lines = [
        f"Repository: {repo_name}",
        "PR KPI Report",
        "",
        "1) PR Review Dwell Time (First Response)",
        f"   Samples: {dwell_count}",
        f"   P50: {format_duration(dwell_stats['p50'])}",
        f"   P75: {format_duration(dwell_stats['p75'])}",
        f"   P90: {format_duration(dwell_stats['p90'])}",
        "",
        "2) PR Completion Time (Creation to Close)",
        f"   Samples: {completion_count}",
        f"   P50: {format_duration(completion_stats['p50'])}",
        f"   P75: {format_duration(completion_stats['p75'])}",
        f"   P90: {format_duration(completion_stats['p90'])}",
    ]

    return "\n".join(lines)
