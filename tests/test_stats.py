"""Tests for statistical calculations and report rendering."""

import sys
from pathlib import Path

import pytest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from myapp.stats import calculate_percentile, compute_statistics, format_duration, generate_report


def test_calculate_percentile_empty_returns_none():
    """Verify percentile calculation returns None when sample list is empty."""
    assert calculate_percentile([], 50) is None


def test_calculate_percentile_single_value_returns_same_for_common_percentiles():
    """Verify all common percentiles return the only value in a single-item sample."""
    values = [42.0]
    assert calculate_percentile(values, 50) == 42.0
    assert calculate_percentile(values, 75) == 42.0
    assert calculate_percentile(values, 90) == 42.0


def test_calculate_percentile_multiple_values_p50_p75_p90():
    """Verify linear interpolation percentile values for a multi-value sorted sample."""
    values = [10.0, 20.0, 30.0, 40.0]
    assert calculate_percentile(values, 50) == pytest.approx(25.0)
    assert calculate_percentile(values, 75) == pytest.approx(32.5)
    assert calculate_percentile(values, 90) == pytest.approx(37.0)


def test_compute_statistics_filters_invalid_and_computes_summary():
    """Verify statistics ignore invalid samples and compute count and percentiles."""
    samples = [10.0, 20.0, None, -5.0, float("nan"), 30.0]
    stats = compute_statistics(samples)

    assert stats["count"] == 3
    assert stats["p50"] == pytest.approx(20.0)
    assert stats["p75"] == pytest.approx(25.0)
    assert stats["p90"] == pytest.approx(28.0)


def test_format_duration_handles_none_zero_typical_and_large_values():
    """Verify duration formatter handles missing, small, and large values correctly."""
    assert format_duration(None) == "n/a"
    assert format_duration(0) == "00:00:00"
    assert format_duration(3661) == "01:01:01"
    assert format_duration(27 * 3600 + 5 * 60 + 9) == "27:05:09"


def test_generate_report_output_format_contains_expected_sections_and_values():
    """Verify report output includes repository header, sections, sample counts, and formatted percentiles."""
    report = generate_report(
        repo_name="my-repo",
        dwell_times=[60.0, 120.0, 180.0],
        completion_times=[300.0, 600.0, 900.0],
    )

    assert "Repository: my-repo" in report
    assert "PR KPI Report" in report
    assert "1) PR Review Dwell Time (First Response)" in report
    assert "2) PR Completion Time (Creation to Close)" in report
    assert "Samples: 3" in report
    assert "P50: 00:02:00" in report
    assert "P75: 00:02:30" in report
    assert "P90: 00:02:48" in report
