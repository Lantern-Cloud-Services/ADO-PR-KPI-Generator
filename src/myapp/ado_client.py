"""Azure DevOps REST API client for KPI data retrieval."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth

from .config import Config
from .errors import ApiError
from .models import Comment, PullRequest, Repository, Thread


class AdoClient:
    """Small, typed client for Azure DevOps Git pull request APIs."""

    _API_VERSION = "7.1"
    _PULL_REQUEST_PAGE_SIZE = 100
    _MAX_RETRIES = 5
    _MAX_BACKOFF_SECONDS = 30

    def __init__(self, config: Config, timeout_seconds: int = 30) -> None:
        """Initialize an authenticated Azure DevOps API client.

        Args:
            config: Validated runtime configuration including org/project/PAT.
            timeout_seconds: Per-request timeout in seconds.
        """
        self._config = config
        self._timeout_seconds = timeout_seconds
        self._base_url = (
            f"https://dev.azure.com/{config.organization}/{config.project}/_apis"
        )

        self._session = requests.Session()
        self._session.auth = HTTPBasicAuth("", config.pat)
        self._session.headers.update({"Accept": "application/json"})

    def _build_url(self, path: str) -> str:
        """Build a fully qualified API URL from a path below ``_apis``."""
        return f"{self._base_url}/{path.lstrip('/')}"

    def _format_datetime(self, value: datetime) -> str:
        """Format a datetime as UTC ISO8601 suitable for Azure DevOps query params."""
        utc_value = value.astimezone(timezone.utc)
        return utc_value.isoformat().replace("+00:00", "Z")

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse Azure DevOps ISO8601 timestamps into timezone-aware datetimes."""
        if not value:
            return None

        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _extract_backoff_seconds(self, response: requests.Response, attempt: int) -> int:
        """Compute exponential backoff seconds, honoring Retry-After when available."""
        retry_after_header = response.headers.get("Retry-After")
        if retry_after_header:
            try:
                retry_after_seconds = int(retry_after_header)
                return min(self._MAX_BACKOFF_SECONDS, max(1, retry_after_seconds))
            except ValueError:
                pass

        return min(self._MAX_BACKOFF_SECONDS, 2 ** (attempt - 1))

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GET request with retry logic for 429/5xx responses.

        Raises:
            ApiError: If the request repeatedly fails, returns HTTP >= 400,
                or does not return valid JSON.
        """
        url = self._build_url(path)
        query = dict(params or {})
        query["api-version"] = self._API_VERSION

        last_error: Optional[Exception] = None

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = self._session.get(url, params=query, timeout=self._timeout_seconds)
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self._MAX_RETRIES:
                    raise ApiError(f"Azure DevOps request failed after retries: GET {url}") from exc
                time.sleep(min(self._MAX_BACKOFF_SECONDS, 2 ** (attempt - 1)))
                continue

            status_code = response.status_code
            is_retryable = status_code == 429 or 500 <= status_code <= 599

            if is_retryable and attempt < self._MAX_RETRIES:
                time.sleep(self._extract_backoff_seconds(response, attempt))
                continue

            if status_code >= 400:
                raise ApiError(
                    "Azure DevOps API request failed: "
                    f"GET {url} returned {status_code} - {response.text}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise ApiError(f"Azure DevOps API returned invalid JSON: GET {url}") from exc

            if not isinstance(payload, dict):
                raise ApiError(f"Azure DevOps API returned unexpected payload shape: GET {url}")

            return payload

        raise ApiError(f"Azure DevOps request failed after retries: GET {url}") from last_error

    def list_repositories(self) -> List[Repository]:
        """List repositories in the configured Azure DevOps project."""
        payload = self._get_json("git/repositories")
        repositories: List[Repository] = []

        for item in payload.get("value", []):
            repo_id = item.get("id")
            repo_name = item.get("name")
            if repo_id and repo_name:
                repositories.append(Repository(id=str(repo_id), name=str(repo_name)))

        return repositories

    def resolve_repo_name_to_id(self, repo_name: str) -> str:
        """Resolve a repository name to repository ID using case-insensitive matching.

        Args:
            repo_name: Human-readable repository name.

        Returns:
            Repository GUID/ID string.

        Raises:
            ApiError: If no repository with the given name exists in the project.
        """
        normalized = repo_name.strip().lower()
        for repository in self.list_repositories():
            if repository.name.lower() == normalized:
                return repository.id

        raise ApiError(f"Repository '{repo_name}' was not found in project '{self._config.project}'.")

    def list_pull_requests(
        self,
        repo_id: str,
        min_time: Optional[datetime],
        max_time: Optional[datetime],
    ) -> List[PullRequest]:
        """List pull requests for a repository with an optional time window.

        Always queries with ``searchCriteria.status=all`` and uses offset pagination
        via ``$top``/``$skip``. Time bounds are only applied when both ``min_time``
        and ``max_time`` are provided; when both are ``None`` no time filters are sent.
        """
        pull_requests: List[PullRequest] = []
        skip = 0

        while True:
            params: Dict[str, Any] = {
                "searchCriteria.status": "all",
                "$top": self._PULL_REQUEST_PAGE_SIZE,
                "$skip": skip,
            }

            if min_time is not None and max_time is not None:
                params["searchCriteria.minTime"] = self._format_datetime(min_time)
                params["searchCriteria.maxTime"] = self._format_datetime(max_time)

            payload = self._get_json(
                f"git/repositories/{repo_id}/pullrequests",
                params=params,
            )

            page_items = payload.get("value", [])
            for item in page_items:
                pr_id = item.get("pullRequestId")
                creation_date = self._parse_datetime(item.get("creationDate"))
                created_by = item.get("createdBy") or {}
                created_by_id = created_by.get("id")
                closed_date = self._parse_datetime(item.get("closedDate"))
                status = item.get("status")

                if pr_id is None or creation_date is None or not created_by_id or not status:
                    raise ApiError(
                        "Azure DevOps pull request payload is missing required fields: "
                        f"repo_id={repo_id}, payload={item}"
                    )

                pull_requests.append(
                    PullRequest(
                        pullRequestId=int(pr_id),
                        creationDate=creation_date,
                        createdById=str(created_by_id),
                        closedDate=closed_date,
                        status=str(status),
                    )
                )

            if len(page_items) < self._PULL_REQUEST_PAGE_SIZE:
                break

            skip += self._PULL_REQUEST_PAGE_SIZE

        return pull_requests

    def list_threads(self, repo_id: str, pr_id: int) -> List[Thread]:
        """List discussion threads for a pull request."""
        payload = self._get_json(f"git/repositories/{repo_id}/pullRequests/{pr_id}/threads")
        threads: List[Thread] = []

        for item in payload.get("value", []):
            thread_id = item.get("id")
            if thread_id is None:
                continue
            threads.append(Thread(id=int(thread_id)))

        return threads

    def list_thread_comments(self, repo_id: str, pr_id: int, thread_id: int) -> List[Comment]:
        """List comments for a given pull request thread."""
        payload = self._get_json(
            f"git/repositories/{repo_id}/pullRequests/{pr_id}/threads/{thread_id}/comments"
        )
        comments: List[Comment] = []

        for item in payload.get("value", []):
            author = item.get("author") or {}
            author_id = author.get("id")
            published_date = self._parse_datetime(item.get("publishedDate"))

            if not author_id:
                continue

            comments.append(
                Comment(
                    authorId=str(author_id),
                    publishedDate=published_date,
                )
            )

        return comments
