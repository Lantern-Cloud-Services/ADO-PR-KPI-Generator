"""Tests for Azure DevOps API client behavior with mocked HTTP."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from myapp.ado_client import AdoClient
from myapp.config import Config
from myapp.errors import ApiError
from myapp.models import Repository


def _build_client() -> AdoClient:
    config = Config(
        organization="org",
        project="proj",
        repo_name="repo",
        days=30,
        pat="pat-token",
    )
    return AdoClient(config=config)


def _response(status_code: int, payload: dict | None = None, text: str = "", headers: dict | None = None):
    response = Mock()
    response.status_code = status_code
    response.text = text
    response.headers = headers or {}
    response.json.return_value = payload if payload is not None else {}
    return response


def _pr_item(pr_id: int, created_by: str = "user-1") -> dict:
    return {
        "pullRequestId": pr_id,
        "creationDate": "2026-01-01T00:00:00Z",
        "createdBy": {"id": created_by},
        "closedDate": "2026-01-01T01:00:00Z",
        "status": "completed",
    }


def test_resolve_repo_name_to_id_found_case_insensitive():
    """Verify repository resolution matches names without case sensitivity."""
    client = _build_client()
    client.list_repositories = Mock(return_value=[
        Repository(id="1", name="Repo-One"),
        Repository(id="2", name="My-Repo"),
    ])

    repo_id = client.resolve_repo_name_to_id("my-repo")

    assert repo_id == "2"


def test_resolve_repo_name_to_id_not_found_raises_api_error():
    """Verify repository resolution raises ApiError when the repository does not exist."""
    client = _build_client()
    client.list_repositories = Mock(return_value=[Repository(id="1", name="Repo-One")])

    with pytest.raises(ApiError):
        client.resolve_repo_name_to_id("missing-repo")


def test_get_json_retries_on_429_and_succeeds():
    """Verify _get_json retries after HTTP 429 and eventually returns JSON payload."""
    client = _build_client()
    first = _response(429, payload={"value": []}, headers={"Retry-After": "1"})
    second = _response(200, payload={"value": [{"id": 1}]})

    client._session.get = Mock(side_effect=[first, second])

    with patch("myapp.ado_client.time.sleep") as sleep_mock:
        payload = client._get_json("git/repositories")

    assert payload == {"value": [{"id": 1}]}
    assert client._session.get.call_count == 2
    sleep_mock.assert_called_once_with(1)


def test_get_json_retries_on_5xx_and_raises_after_max_retries():
    """Verify _get_json retries retryable server errors and raises ApiError after limit."""
    client = _build_client()
    server_error = _response(503, payload={}, text="service unavailable")
    client._session.get = Mock(side_effect=[server_error] * client._MAX_RETRIES)

    with patch("myapp.ado_client.time.sleep") as sleep_mock:
        with pytest.raises(ApiError):
            client._get_json("git/repositories")

    assert client._session.get.call_count == client._MAX_RETRIES
    assert sleep_mock.call_count == client._MAX_RETRIES - 1


def test_list_pull_requests_uses_pagination_until_final_partial_page():
    """Verify pull-request listing paginates using $top/$skip and aggregates all pages."""
    client = _build_client()

    first_page = {"value": [_pr_item(i) for i in range(1, 101)]}
    second_page = {"value": [_pr_item(101), _pr_item(102)]}

    get_json_mock = Mock(side_effect=[first_page, second_page])
    client._get_json = get_json_mock

    prs = client.list_pull_requests(
        repo_id="repo-id",
        min_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        max_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert len(prs) == 102
    assert prs[0].pullRequestId == 1
    assert prs[-1].pullRequestId == 102
    assert get_json_mock.call_count == 2

    first_call = get_json_mock.call_args_list[0]
    second_call = get_json_mock.call_args_list[1]
    assert first_call.kwargs["params"]["$skip"] == 0
    assert first_call.kwargs["params"]["$top"] == client._PULL_REQUEST_PAGE_SIZE
    assert second_call.kwargs["params"]["$skip"] == client._PULL_REQUEST_PAGE_SIZE
    assert second_call.kwargs["params"]["$top"] == client._PULL_REQUEST_PAGE_SIZE


def test_list_pull_requests_without_time_bounds_omits_min_max_params():
    """Verify unbounded pull-request listing omits min/max time while keeping status=all."""
    client = _build_client()
    client._get_json = Mock(return_value={"value": [_pr_item(1)]})

    prs = client.list_pull_requests(repo_id="repo-id", min_time=None, max_time=None)

    assert len(prs) == 1
    call = client._get_json.call_args
    params = call.kwargs["params"]
    assert params["searchCriteria.status"] == "all"
    assert "searchCriteria.minTime" not in params
    assert "searchCriteria.maxTime" not in params
