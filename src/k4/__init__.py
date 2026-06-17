"""k4 — personal CLI for managing GitHub work with jj-vcs."""

__version__ = "0.1.0"


class K4Error(Exception):
    """User-facing error. The CLI prints the message and exits non-zero."""
