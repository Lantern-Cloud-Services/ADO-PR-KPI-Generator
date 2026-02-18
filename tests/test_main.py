"""Tests for KPI generator script."""

import datetime as dt
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from myapp.main import format_seconds, main, parse_ado_datetime, percentile, summarize_metric
from myapp.main import parse_args


def test_percentile_linear_interpolation():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 50) == 25.0
    assert percentile(values, 75) == 32.5


def test_format_seconds_hhmmss_and_empty():
    assert format_seconds(3661) == "01:01:01"
    assert format_seconds(None) == "n/a"


def test_parse_ado_datetime_normalizes_zulu():
    result = parse_ado_datetime("2026-01-15T11:22:33Z")
    expected = dt.datetime(2026, 1, 15, 11, 22, 33, tzinfo=dt.timezone.utc)
    assert result == expected


def test_summarize_metric_outputs_expected_keys():
    summary = summarize_metric("x", [3, 1, 2])
    assert summary["metric"] == "x"
    assert summary["count"] == 3
    assert summary["p50"] == 2
    assert summary["p75"] == 2.5
    assert summary["p90"] == 2.8


def test_main_requires_pat(capsys):
    exit_code = main(["--org", "org", "--project", "proj", "--days", "1"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "PAT required" in captured.err


def test_parse_args_days_defaults_to_none_when_omitted():
    args = parse_args(["--org", "org", "--project", "proj", "--pat", "token"])
    assert args.days is None


def test_parse_args_days_accepts_integer_when_provided():
    args = parse_args(["--org", "org", "--project", "proj", "--pat", "token", "--days", "7"])
    assert args.days == 7
