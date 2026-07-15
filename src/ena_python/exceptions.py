class PyENAError(Exception):
    """Base exception for pyENA."""


class ValidationError(PyENAError, ValueError):
    """Raised when input data do not satisfy ENA requirements."""


class NotPortedError(PyENAError, NotImplementedError):
    """Raised for rENA features that have not yet been ported."""
