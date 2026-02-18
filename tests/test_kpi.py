"""Tests for KPI extraction logic."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from myapp.kpi import collect_kpi_samples, compute_completion_time, compute_first_response_time
from myapp.models import Comment, PullRequest, Thread


def _utc(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, minute, second, tzinfo=timezone.utc)


def _make_pr(
    pr_id: int = 1,
    status: str = "active",
    created_by: str = "author",
    creation: datetime | None = None,
    closed: datetime | None = None,
) -> PullRequest:
    return PullRequest(
        pullRequestId=pr_id,
        creationDate=creation or _utc(10, 0, 0),
        createdById=created_by,
        closedDate=closed,
        status=status,
    )


def test_compute_first_response_time_no_comments_returns_none():
    """Verify first-response KPI is None when PR threads have no comments."""
    client = Mock()
    client.list_threads.return_value = [Thread(id=1)]
    client.list_thread_comments.return_value = []

    result = compute_first_response_time(client, "repo-id", _make_pr())

    assert result is None


def test_compute_first_response_time_only_author_comments_returns_none():
    """Verify first-response KPI is None when only PR author comments are present."""
    pr = _make_pr(created_by="author")
    client = Mock()
    client.list_threads.return_value = [Thread(id=1)]
    client.list_thread_comments.return_value = [
        Comment(authorId="author", publishedDate=_utc(10, 5, 0)),
        Comment(authorId="author", publishedDate=_utc(10, 10, 0)),
    ]

    result = compute_first_response_time(client, "repo-id", pr)

    assert result is None


def test_compute_first_response_time_non_author_comment_returns_duration_seconds():
    """Verify first-response KPI returns elapsed seconds to first non-author comment."""
    pr = _make_pr(created_by="author", creation=_utc(10, 0, 0))
    client = Mock()
    client.list_threads.return_value = [Thread(id=1), Thread(id=2)]

    def _comments(repo_id: str, pr_id: int, thread_id: int):
        if thread_id == 1:
            return [Comment(authorId="author", publishedDate=_utc(10, 3, 0))]
        return [
            Comment(authorId="reviewer", publishedDate=_utc(10, 8, 0)),
            Comment(authorId="reviewer", publishedDate=_utc(10, 12, 0)),
        ]

    client.list_thread_comments.side_effect = _comments

    result = compute_first_response_time(client, "repo-id", pr)

    assert result == 8 * 60


def test_compute_completion_time_completed_pr_with_closed_date_returns_duration():
    """Verify completion KPI returns elapsed seconds for completed PRs with close time."""
    pr = _make_pr(status="completed", creation=_utc(9, 0, 0), closed=_utc(11, 30, 0))

    result = compute_completion_time(pr)

    assert result == 2.5 * 3600


def test_compute_completion_time_active_pr_returns_none():
    """Verify completion KPI is None for non-completed pull requests."""
    pr = _make_pr(status="active", creation=_utc(9, 0, 0), closed=_utc(11, 0, 0))

    result = compute_completion_time(pr)

    assert result is None


def test_compute_completion_time_completed_without_closed_date_returns_none():
    """Verify completion KPI is None when completed PR is missing closedDate."""
    pr = _make_pr(status="completed", creation=_utc(9, 0, 0), closed=None)

    result = compute_completion_time(pr)

    assert result is None


def test_collect_kpi_samples_collects_only_non_none_values():
    """Verify KPI sample collection filters out None values from per-PR computations."""
    pr1 = _make_pr(pr_id=1, status="completed", creation=_utc(10, 0, 0), closed=_utc(11, 0, 0))
    pr2 = _make_pr(pr_id=2, status="active", creation=_utc(12, 0, 0), closed=None)
    prs = [pr1, pr2]

    client = Mock()

    def _comments(repo_id: str, pr_id: int, thread_id: int):
        if pr_id == 1:
            return [Comment(authorId="reviewer", publishedDate=_utc(10, 15, 0))]
        return []

    client.list_threads.side_effect = lambda repo_id, pr_id: [Thread(id=1)]
    client.list_thread_comments.side_effect = _comments

    dwell_times, completion_times = collect_kpi_samples(client, "repo-id", prs)

    assert dwell_times == [15 * 60]
    assert completion_times == [3600.0]
