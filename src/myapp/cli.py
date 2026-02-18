"""Command-line argument parsing for the ADO PR KPI Generator."""

from __future__ import annotations

import argparse


def _positive_int(value: str) -> int:
    """Parse and validate a positive integer CLI value.

    Args:
        value: Raw command-line argument value.

    Returns:
        The validated positive integer.

    Raises:
        argparse.ArgumentTypeError: If value is not a positive integer.
    """
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")

    return parsed


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for KPI generation.

    Returns:
        Parsed CLI arguments containing organization, project, repository name,
        and days of history to query.
    """
    parser = argparse.ArgumentParser(
        prog="ado-pr-kpi-generator",
        description=(
            "Generate Azure DevOps pull-request KPI metrics for a repository "
            "(dwell time and completion time)."
        ),
    )

    parser.add_argument(
        "--org",
        required=True,
        help="Azure DevOps organization name.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Azure DevOps project name.",
    )
    parser.add_argument(
        "--repo-name",
        required=True,
        help="Azure DevOps repository name to analyze.",
    )
    parser.add_argument(
        "--days",
        type=_positive_int,
        default=30,
        help="Number of days of PR history to analyze (default: 30).",
    )

    return parser.parse_args()
