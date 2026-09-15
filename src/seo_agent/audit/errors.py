"""Domain exceptions exposed across audit boundaries."""


class AuditError(Exception):
    """Base class for expected audit failures."""


class InvalidWebsiteUrlError(AuditError):
    """Raised when the supplied website URL is malformed or unsupported."""


class UnsafeUrlError(AuditError):
    """Raised before a request to a private or out-of-scope destination."""


class CollectionError(AuditError):
    """Raised when a required resource cannot be collected."""


class ResourceTooLargeError(CollectionError):
    """Raised when a response exceeds the configured byte limit."""


class ProviderConfigurationError(AuditError):
    """Raised when a required external provider is not configured."""


class ProviderResponseError(AuditError):
    """Raised when an external provider returns unusable data."""
