"""Safe repository failures for routes to translate into HTTP responses."""


class WorkspaceNotFound(Exception):
    """Absent and unowned workspaces deliberately have the same failure."""


class UnsupportedDocumentType(Exception):
    """A balance sheet does not provide bank-statement transactions."""


class DatabaseUnauthorized(Exception):
    """The Data API rejected the caller's access token."""


class DatabaseUnavailable(Exception):
    """A database request failed or its response did not match the read contract."""
