"""Tests for command-line argument parsing."""

import sys
from pathlib import Path

import pytest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from myapp.cli import parse_args


def test_parse_args_with_valid_arguments(monkeypatch):
    """Verify CLI parsing succeeds when all required arguments are provided."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ado-pr-kpi-generator",
            "--org",
            "my-org",
            "--project",
            "my-project",
            "--repo-name",
            "my-repo",
            "--days",
            "14",
        ],
    )

    args = parse_args()

    assert args.org == "my-org"
    assert args.project == "my-project"
    assert args.repo_name == "my-repo"
    assert args.days == 14


def test_parse_args_without_days(monkeypatch):
    """Verify CLI parsing sets days to None when --days is omitted."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ado-pr-kpi-generator",
            "--org",
            "my-org",
            "--project",
            "my-project",
            "--repo-name",
            "my-repo",
        ],
    )

    args = parse_args()

    assert args.days is None


def test_parse_args_with_explicit_days_30(monkeypatch):
    """Verify CLI parsing keeps backwards compatibility for --days 30."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ado-pr-kpi-generator",
            "--org",
            "my-org",
            "--project",
            "my-project",
            "--repo-name",
            "my-repo",
            "--days",
            "30",
        ],
    )

    args = parse_args()

    assert args.days == 30


def test_parse_args_with_negative_days_fails_validation(monkeypatch):
    """Verify CLI parsing exits with an error when --days is negative."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ado-pr-kpi-generator",
            "--org",
            "my-org",
            "--project",
            "my-project",
            "--repo-name",
            "my-repo",
            "--days",
            "-1",
        ],
    )

    with pytest.raises(SystemExit):
        parse_args()
