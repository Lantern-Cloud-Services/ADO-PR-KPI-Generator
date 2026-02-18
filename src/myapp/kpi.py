"""KPI extraction logic for Azure DevOps pull request metrics.

This module computes PR-level duration samples in seconds for the two core KPIs:
- PR review dwell time (first non-author response)
- PR completion time (creation to close for completed PRs)
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from .ado_client import AdoClient
from .models import Comment, PullRequest, Thread

logger = logging.getLogger(__name__)


def compute_first_response_time(
    ado_client: AdoClient,
    repo_id: str,
    pr: PullRequest,
) -> Optional[float]:
    """Compute PR review dwell time as first non-author comment latency.

    Business logic:
    - Retrieve all threads for the pull request.
    - Retrieve all comments for each thread.
    - Identify the earliest comment where ``comment.authorId != pr.createdById``.
    - Ignore comments without ``publishedDate``.
    - Return elapsed seconds from PR creation to that first qualifying comment.

    Returns ``None`` when no qualifying review response exists or timestamps are
    insufficient to compute a safe duration.
    """
    if pr.creationDate is None:
        logger.debug(
            "Skipping first response computation due to missing PR creationDate",
            extra={"pr_id": pr.pullRequestId},
        )
        return None

    threads: List[Thread] = ado_client.list_threads(repo_id=repo_id, pr_id=pr.pullRequestId)
    first_response_at = None

    for thread in threads:
        comments: List[Comment] = ado_client.list_thread_comments(
            repo_id=repo_id,
            pr_id=pr.pullRequestId,
            thread_id=thread.id,
        )
        for comment in comments:
            if comment.authorId == pr.createdById:
                continue
            if comment.publishedDate is None:
                continue
            if first_response_at is None or comment.publishedDate < first_response_at:
                first_response_at = comment.publishedDate

    if first_response_at is None:
        return None

    try:
        duration_seconds = (first_response_at - pr.creationDate).total_seconds()
    except TypeError:
        logger.debug(
            "Skipping first response computation due to incompatible datetime types",
            extra={"pr_id": pr.pullRequestId},
        )
        return None

    if duration_seconds < 0:
        logger.debug(
            "Skipping first response computation due to negative duration",
            extra={"pr_id": pr.pullRequestId, "duration_seconds": duration_seconds},
        )
        return None

    return duration_seconds


def compute_completion_time(pr: PullRequest) -> Optional[float]:
    """Compute PR completion time (creation to close) in seconds.

    Business logic:
    - Only completed pull requests are eligible (``status == \"completed\"``).
    - ``closedDate`` must be present.
    - Duration is ``closedDate - creationDate`` in seconds.

    Returns ``None`` for non-completed PRs (for example active or abandoned),
    missing timestamps, or invalid negative durations.
    """
    if pr.status != "completed":
        return None

    if pr.creationDate is None or pr.closedDate is None:
        return None

    try:
        duration_seconds = (pr.closedDate - pr.creationDate).total_seconds()
    except TypeError:
        logger.debug(
            "Skipping completion time computation due to incompatible datetime types",
            extra={"pr_id": pr.pullRequestId},
        )
        return None

    if duration_seconds < 0:
        logger.debug(
            "Skipping completion time computation due to negative duration",
            extra={"pr_id": pr.pullRequestId, "duration_seconds": duration_seconds},
        )
        return None

    return duration_seconds


def collect_kpi_samples(
    ado_client: AdoClient,
    repo_id: str,
    prs: List[PullRequest],
) -> Tuple[List[float], List[float]]:
    """Collect per-PR KPI samples for dwell and completion time.

    For each PR, this function computes:
    - KPI 1: first response dwell time
    - KPI 2: completion time

    ``None`` samples are filtered out. Returned values are in seconds as:
    ``(dwell_times, completion_times)``.
    """
    dwell_times: List[float] = []
    completion_times: List[float] = []

    prs_without_response = 0
    prs_without_completion = 0

    for pr in prs:
        dwell = compute_first_response_time(ado_client=ado_client, repo_id=repo_id, pr=pr)
        if dwell is None:
            prs_without_response += 1
        else:
            dwell_times.append(dwell)

        completion = compute_completion_time(pr)
        if completion is None:
            prs_without_completion += 1
        else:
            completion_times.append(completion)

    logger.info(
        "Collected KPI samples",
        extra={
            "repo_id": repo_id,
            "prs_total": len(prs),
            "dwell_samples": len(dwell_times),
            "completion_samples": len(completion_times),
            "prs_without_response": prs_without_response,
            "prs_without_completion": prs_without_completion,
        },
    )

    return dwell_times, completion_times
