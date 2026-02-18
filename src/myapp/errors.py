"""Custom exception types for the ADO PR KPI Generator."""


class KPIGeneratorError(Exception):
    """Base exception for all recoverable KPI generator errors."""


class ConfigurationError(KPIGeneratorError):
    """Raised when runtime configuration values are missing or invalid."""


class AuthenticationError(KPIGeneratorError):
    """Raised when Azure DevOps authentication credentials are unavailable or invalid."""


class ApiError(KPIGeneratorError):
    """Raised when an Azure DevOps API request fails or returns an unexpected response."""


class DataValidationError(KPIGeneratorError):
    """Raised when API payloads or computed KPI data do not meet expected constraints."""
