"""Tests for application orchestration in the main module."""

import sys
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from myapp.config import Config
from myapp.errors import ApiError, AuthenticationError
from myapp.main import orchestrate_kpi_generation


def test_orchestrate_kpi_generation_success(capsys):
    """Verify orchestration returns 0 and wires components correctly on success."""
    args = Namespace(org="org", project="project", repo_name="repo", days=30)
    config = Config(
        organization="org",
        project="project",
        repo_name="repo",
        days=30,
        pat="secret",
    )
    ado_client = Mock()
    ado_client.resolve_repo_name_to_id.return_value = "repo-id"
    ado_client.list_pull_requests.return_value = [Mock()]

    with patch("myapp.main.parse_args", return_value=args) as parse_args_mock, patch(
        "myapp.main.load_config", return_value=config
    ) as load_config_mock, patch(
        "myapp.main.AdoClient", return_value=ado_client
    ) as ado_client_ctor_mock, patch(
        "myapp.main.collect_kpi_samples", return_value=([120.0], [600.0])
    ) as collect_mock, patch(
        "myapp.main.generate_report", return_value="REPORT"
    ) as report_mock:
        exit_code = orchestrate_kpi_generation()

    assert exit_code == 0
    parse_args_mock.assert_called_once_with()
    load_config_mock.assert_called_once_with(
        organization="org",
        project="project",
        repo_name="repo",
        days=30,
    )
    ado_client_ctor_mock.assert_called_once_with(config=config)
    ado_client.resolve_repo_name_to_id.assert_called_once_with("repo")
    ado_client.list_pull_requests.assert_called_once()
    collect_mock.assert_called_once_with(
        ado_client=ado_client,
        repo_id="repo-id",
        prs=ado_client.list_pull_requests.return_value,
    )
    report_mock.assert_called_once_with(
        repo_name="repo",
        dwell_times=[120.0],
        completion_times=[600.0],
    )
    assert "REPORT" in capsys.readouterr().out


def test_orchestrate_kpi_generation_with_days_none_fetches_all_prs(capsys):
    """Verify days=None uses unbounded PR query mode and passes None time filters."""
    args = Namespace(org="org", project="project", repo_name="repo", days=None)
    config = Config(
        organization="org",
        project="project",
        repo_name="repo",
        days=None,
        pat="secret",
    )
    ado_client = Mock()
    ado_client.resolve_repo_name_to_id.return_value = "repo-id"
    ado_client.list_pull_requests.return_value = [Mock()]

    with patch("myapp.main.parse_args", return_value=args), patch(
        "myapp.main.load_config", return_value=config
    ), patch("myapp.main.AdoClient", return_value=ado_client), patch(
        "myapp.main.collect_kpi_samples", return_value=([120.0], [600.0])
    ), patch("myapp.main.generate_report", return_value="REPORT"):
        exit_code = orchestrate_kpi_generation()

    assert exit_code == 0
    ado_client.list_pull_requests.assert_called_once_with(
        repo_id="repo-id",
        min_time=None,
        max_time=None,
    )
    output = capsys.readouterr().out
    assert "Fetching all PRs for repository 'repo'..." in output
    assert "REPORT" in output


def test_orchestrate_kpi_generation_missing_pat_returns_auth_error():
    """Verify missing PAT/authentication failures return the authentication exit code."""
    args = Namespace(org="org", project="project", repo_name="repo", days=30)

    with patch("myapp.main.parse_args", return_value=args), patch(
        "myapp.main.load_config",
        side_effect=AuthenticationError("Missing required Azure DevOps Personal Access Token."),
    ):
        exit_code = orchestrate_kpi_generation()

    assert exit_code == 3


def test_orchestrate_kpi_generation_api_error_returns_api_exit_code():
    """Verify Azure DevOps API failures return the API error exit code."""
    args = Namespace(org="org", project="project", repo_name="repo", days=30)
    config = Config(
        organization="org",
        project="project",
        repo_name="repo",
        days=30,
        pat="secret",
    )
    ado_client = Mock()
    ado_client.resolve_repo_name_to_id.side_effect = ApiError("Repository not found")

    with patch("myapp.main.parse_args", return_value=args), patch(
        "myapp.main.load_config", return_value=config
    ), patch("myapp.main.AdoClient", return_value=ado_client):
        exit_code = orchestrate_kpi_generation()

    assert exit_code == 4


def test_orchestrate_kpi_generation_unexpected_error_returns_generic_exit_code():
    """Verify unexpected exceptions are mapped to the generic non-zero exit code."""
    with patch("myapp.main.parse_args", side_effect=RuntimeError("boom")):
        exit_code = orchestrate_kpi_generation()

    assert exit_code == 1
