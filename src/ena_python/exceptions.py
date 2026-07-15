class ENAError(Exception):
    """Base exception for ena-python."""


class ValidationError(ENAError, ValueError):
    """Raised when input data do not satisfy ENA requirements."""


class NotPortedError(ENAError, NotImplementedError):
    """Raised for rENA features that have not yet been ported."""
