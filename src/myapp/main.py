"""Application entry point for generating Azure DevOps pull request KPI reports.

This module orchestrates end-to-end data collection and report generation:
CLI parsing, configuration loading, Azure DevOps API access, KPI extraction,
and final report rendering.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .ado_client import AdoClient
from .cli import parse_args
from .config import load_config
from .errors import ApiError, AuthenticationError, ConfigurationError
from .kpi import collect_kpi_samples
from .stats import generate_report


def orchestrate_kpi_generation() -> int:
    """Coordinate the KPI generation workflow from CLI to final report.

    Workflow:
    1. Parse CLI arguments.
    2. Load configuration and PAT from environment.
    3. Create Azure DevOps API client.
    4. Resolve repository name to repository ID.
    5. Build UTC time window from ``now - days`` to ``now``.
    6. Fetch pull requests in the time window.
    7. Compute KPI samples (dwell and completion times).
    8. Generate and print report.

    Returns:
        Process exit code:
        - ``0`` on success
        - ``2`` for configuration errors
        - ``3`` for authentication errors
        - ``4`` for Azure DevOps API errors
        - ``1`` for unexpected failures
    """
    try:
        print("Parsing CLI arguments...")
        args = parse_args()

        print("Loading configuration...")
        app_config = load_config(
            organization=args.org,
            project=args.project,
            repo_name=args.repo_name,
            days=args.days,
        )

        print("Initializing Azure DevOps client...")
        ado_client = AdoClient(config=app_config)

        print(f"Resolving repository '{app_config.repo_name}'...")
        repo_id = ado_client.resolve_repo_name_to_id(app_config.repo_name)

        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(days=app_config.days)

        print("Fetching PRs...")
        pull_requests = ado_client.list_pull_requests(
            repo_id=repo_id,
            min_time=window_start,
            max_time=window_end,
        )

        print("Computing KPIs...")
        dwell_times, completion_times = collect_kpi_samples(
            ado_client=ado_client,
            repo_id=repo_id,
            prs=pull_requests,
        )

        print("Generating report...")
        report = generate_report(
            repo_name=app_config.repo_name,
            dwell_times=dwell_times,
            completion_times=completion_times,
        )
        print(report)

        return 0
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 2
    except AuthenticationError as exc:
        print(f"Authentication error: {exc}")
        return 3
    except ApiError as exc:
        print(f"API error: {exc}")
        return 4
    except Exception as exc:  # pragma: no cover - defensive safety net
        print(f"Unexpected error: {exc}")
        return 1


def main() -> int:
    """Run the PR KPI generator application and return process exit code."""
    return orchestrate_kpi_generation()


if __name__ == "__main__":
    raise SystemExit(main())
