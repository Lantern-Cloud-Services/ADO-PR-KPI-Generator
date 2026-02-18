"""Configuration parsing and validation for the ADO PR KPI Generator."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import AuthenticationError, ConfigurationError


@dataclass(frozen=True)
class Config:
    """Validated runtime settings used by the KPI generator."""

    organization: str
    project: str
    repo_name: str
    days: int
    pat: str


def load_config(organization: str, project: str, repo_name: str, days: int) -> Config:
    """Build and validate application configuration.

    Args:
        organization: Azure DevOps organization name.
        project: Azure DevOps project name.
        repo_name: Azure DevOps repository name.
        days: Positive number of days of history to query.

    Returns:
        A validated ``Config`` instance.

    Raises:
        ConfigurationError: If ``days`` is not greater than ``0``.
        AuthenticationError: If ``ADO_PAT`` is not configured.
    """
    if days <= 0:
        raise ConfigurationError("Invalid value for 'days': expected an integer greater than 0.")

    pat: str = os.getenv("ADO_PAT", "").strip()
    if not pat:
        raise AuthenticationError(
            "Missing required Azure DevOps Personal Access Token. "
            "Set the 'ADO_PAT' environment variable before running the KPI generator."
        )

    return Config(
        organization=organization,
        project=project,
        repo_name=repo_name,
        days=days,
        pat=pat,
    )
