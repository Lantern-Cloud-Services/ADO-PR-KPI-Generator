"""Azure DevOps pull-request KPI generator."""

from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from requests.auth import HTTPBasicAuth


def percentile(sorted_values: Sequence[float], p: float) -> Optional[float]:
    """Return percentile value using linear interpolation."""
    if not sorted_values:
        return None
    if p <= 0:
        return float(sorted_values[0])
    if p >= 100:
        return float(sorted_values[-1])

    index = (len(sorted_values) - 1) * (p / 100.0)
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return float(sorted_values[int(index)])

    low_value = sorted_values[low]
    high_value = sorted_values[high]
    return float(low_value + (high_value - low_value) * (index - low))


def format_seconds(seconds: Optional[float]) -> str:
    """Format a duration in seconds as HH:MM:SS."""
    if seconds is None:
        return "n/a"
    total_seconds = max(0, int(round(seconds)))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


def parse_ado_datetime(value: str) -> dt.datetime:
    """Parse Azure DevOps ISO-8601 timestamp into UTC datetime."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return dt.datetime.fromisoformat(normalized).astimezone(dt.timezone.utc)


class AdoClient:
    """Small Azure DevOps REST client used by this script."""

    def __init__(self, org: str, project: str, pat: str):
        self.org = org
        self.project = project
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth("", pat)
        self.session.headers.update({"Accept": "application/json"})

    def _url(self, path: str) -> str:
        return f"https://dev.azure.com/{self.org}/{self.project}/{path.lstrip('/')}"

    def _get(self, url: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        response = None
        for attempt in range(1, 6):
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code in (429, 500, 502, 503, 504):
                retry_after = int(response.headers.get("Retry-After", "1"))
                time.sleep(min(30, retry_after * attempt))
                continue
            response.raise_for_status()
            return response.json(), dict(response.headers)

        if response is None:
            raise RuntimeError("HTTP request failed before response was created")
        response.raise_for_status()
        return {}, {}

    def list_repositories(self, include_hidden: bool = False) -> List[Dict[str, Any]]:
        url = self._url("/_apis/git/repositories")
        params = {
            "api-version": "7.1",
            "includeHidden": str(include_hidden).lower(),
        }
        data, _ = self._get(url, params)
        return data.get("value", [])

    def resolve_repo_names_to_ids(self, repo_names: Sequence[str], include_hidden: bool = False) -> Dict[str, str]:
        repositories = self.list_repositories(include_hidden=include_hidden)
        repos_by_name = {
            repo.get("name", "").lower(): repo.get("id")
            for repo in repositories
            if repo.get("name") and repo.get("id")
        }

        resolved: Dict[str, str] = {}
        for name in repo_names:
            normalized_name = name.strip()
            if not normalized_name:
                continue

            repo_id = repos_by_name.get(normalized_name.lower())
            if repo_id:
                resolved[normalized_name] = repo_id
                continue

            fallback_name = normalized_name.split("/")[-1]
            fallback_id = repos_by_name.get(fallback_name.lower())
            if fallback_id:
                resolved[normalized_name] = fallback_id

        return resolved

    def list_pull_requests(
        self,
        repo_id: str,
        status: str,
        min_time: Optional[dt.datetime] = None,
        max_time: Optional[dt.datetime] = None,
        top: int = 100,
    ) -> List[Dict[str, Any]]:
        url = self._url(f"/_apis/git/repositories/{repo_id}/pullrequests")
        pull_requests: List[Dict[str, Any]] = []
        continuation_token: Optional[str] = None

        while True:
            params: Dict[str, Any] = {
                "searchCriteria.status": status,
                "$top": top,
                "api-version": "7.1-preview.1",
            }
            if min_time is not None:
                params["searchCriteria.minTime"] = min_time.isoformat().replace("+00:00", "Z")
            if max_time is not None:
                params["searchCriteria.maxTime"] = max_time.isoformat().replace("+00:00", "Z")
            if continuation_token:
                params["continuationToken"] = continuation_token

            data, headers = self._get(url, params)
            pull_requests.extend(data.get("value", []))

            continuation_token = headers.get("x-ms-continuationtoken")
            if not continuation_token:
                break

        return pull_requests

    def list_threads(self, repo_id: str, pull_request_id: int) -> List[Dict[str, Any]]:
        url = self._url(f"/_apis/git/repositories/{repo_id}/pullRequests/{pull_request_id}/threads")
        data, _ = self._get(url, {"api-version": "7.1"})
        return data.get("value", [])

    def list_thread_comments(self, repo_id: str, pull_request_id: int, thread_id: int) -> List[Dict[str, Any]]:
        url = self._url(
            f"/_apis/git/repositories/{repo_id}/pullRequests/{pull_request_id}/threads/{thread_id}/comments"
        )
        data, _ = self._get(url, {"api-version": "7.1"})
        return data.get("value", [])


def first_non_author_comment_time(
    client: AdoClient,
    repo_id: str,
    pull_request: Dict[str, Any],
) -> Optional[dt.datetime]:
    """Return first comment timestamp by a user other than the PR author."""
    pull_request_id = pull_request.get("pullRequestId")
    author_id = (pull_request.get("createdBy") or {}).get("id")
    earliest: Optional[dt.datetime] = None

    if pull_request_id is None:
        return None

    for thread in client.list_threads(repo_id, int(pull_request_id)):
        thread_id = thread.get("id")
        if thread_id is None:
            continue

        for comment in client.list_thread_comments(repo_id, int(pull_request_id), int(thread_id)):
            timestamp = comment.get("publishedDate")
            commenter_id = (comment.get("author") or {}).get("id")

            if not timestamp:
                continue
            if author_id and commenter_id == author_id:
                continue

            comment_time = parse_ado_datetime(timestamp)
            if earliest is None or comment_time < earliest:
                earliest = comment_time

    return earliest


def summarize_metric(metric_name: str, values_in_seconds: Sequence[float]) -> Dict[str, Any]:
    valid_values = sorted(value for value in values_in_seconds if value >= 0)
    return {
        "metric": metric_name,
        "count": len(valid_values),
        "p50": percentile(valid_values, 50),
        "p75": percentile(valid_values, 75),
        "p90": percentile(valid_values, 90),
    }


def compute_repo_kpis(
    client: AdoClient,
    repo_id: str,
    min_time: Optional[dt.datetime],
    max_time: Optional[dt.datetime],
) -> Tuple[List[float], List[float]]:
    """Compute dwell and completion durations for a single repo."""
    dwell_seconds: List[float] = []
    completion_seconds: List[float] = []

    pull_requests = client.list_pull_requests(
        repo_id,
        "all",
        min_time=min_time,
        max_time=max_time,
    )

    for pull_request in pull_requests:
        created = pull_request.get("creationDate")
        if not created:
            continue
        created_at = parse_ado_datetime(created)

        first_response_at = first_non_author_comment_time(client, repo_id, pull_request)
        if first_response_at is not None:
            dwell_seconds.append((first_response_at - created_at).total_seconds())

        if (pull_request.get("status") or "").lower() == "completed":
            closed = pull_request.get("closedDate")
            if closed:
                closed_at = parse_ado_datetime(closed)
                completion_seconds.append((closed_at - created_at).total_seconds())

    return dwell_seconds, completion_seconds


def print_metric_summary(summary: Dict[str, Any]) -> None:
    print(
        f"{summary['metric']} | count={summary['count']}"
        f" | P50={format_seconds(summary['p50'])}"
        f" | P75={format_seconds(summary['p75'])}"
        f" | P90={format_seconds(summary['p90'])}"
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate PR KPI summaries from Azure DevOps REST APIs "
            "(review dwell first response + completion time)."
        )
    )
    parser.add_argument("--org", required=True, help="Azure DevOps organization name")
    parser.add_argument("--project", required=True, help="Azure DevOps project name")
    parser.add_argument("--repo-id", action="append", default=[], help="Repository ID (repeatable)")
    parser.add_argument("--repo-name", action="append", default=[], help="Repository name (repeatable)")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden repos in name resolution")
    parser.add_argument("--pat", default=os.getenv("ADO_PAT"), help="ADO Personal Access Token")
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Optional lookback window in days; omit to process all available PR data",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    if not args.pat:
        print("ERROR: PAT required via --pat or ADO_PAT environment variable.", file=sys.stderr)
        return 2

    max_time: Optional[dt.datetime] = None
    min_time: Optional[dt.datetime] = None
    if args.days is not None:
        max_time = dt.datetime.now(dt.timezone.utc)
        min_time = max_time - dt.timedelta(days=args.days)
    client = AdoClient(org=args.org, project=args.project, pat=args.pat)

    resolved_repo_ids: Dict[str, str] = {}
    if args.repo_name:
        resolved_repo_ids = client.resolve_repo_names_to_ids(args.repo_name, include_hidden=args.include_hidden)
        unresolved = [name for name in args.repo_name if name.strip() and name.strip() not in resolved_repo_ids]
        if unresolved:
            print("WARNING: Could not resolve repo names:")
            for name in unresolved:
                print(f"  - {name}")

    repo_ids = {repo_id for repo_id in args.repo_id if repo_id}
    repo_ids.update(resolved_repo_ids.values())

    if not repo_ids:
        repositories = client.list_repositories(include_hidden=args.include_hidden)
        repo_ids = {repo["id"] for repo in repositories if repo.get("id")}
        print(f"No repos specified; processing all repos in project (count={len(repo_ids)}).")

    all_dwell: List[float] = []
    all_completion: List[float] = []

    for repo_id in sorted(repo_ids):
        print(f"\n=== Repo: {repo_id} ===")
        dwell_seconds, completion_seconds = compute_repo_kpis(client, repo_id, min_time, max_time)
        all_dwell.extend(dwell_seconds)
        all_completion.extend(completion_seconds)

        print_metric_summary(summarize_metric("PR Review Dwell Time (First Response)", dwell_seconds))
        print_metric_summary(summarize_metric("PR Completion Time", completion_seconds))

    print("\n=== SUMMARY (across processed repos) ===")
    print_metric_summary(summarize_metric("PR Review Dwell Time (First Response)", all_dwell))
    print_metric_summary(summarize_metric("PR Completion Time", all_completion))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
