"""Domain models for Azure DevOps PR KPI data processing.

These dataclasses intentionally model only the subset of API payload fields that
are required for KPI computation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class Repository:
    """Represents a source repository returned by Azure DevOps APIs."""

    id: str
    name: str


@dataclass(slots=True)
class PullRequest:
    """Represents the minimal pull request data required for KPI calculations."""

    pullRequestId: int
    creationDate: datetime
    createdById: str
    closedDate: Optional[datetime]
    status: str


@dataclass(slots=True)
class Thread:
    """Represents a pull request discussion thread identifier."""

    id: int


@dataclass(slots=True)
class Comment:
    """Represents the minimal comment data used to find first review response."""

    authorId: str
    publishedDate: Optional[datetime]


@dataclass(slots=True)
class KPISample:
    """Represents one PR-level KPI measurement in seconds."""

    pr_id: int
    duration_seconds: float


@dataclass(slots=True)
class KPIStats:
    """Represents aggregated percentile KPI statistics for a repository."""

    p50: float
    p75: float
    p90: float
    count: int
    repo_name: str
