"""CVFlow exception hierarchy.

Keeping these in one place lets callers catch the whole family
(:class:`CVFlowError`) or a specific failure.
"""

from __future__ import annotations


class CVFlowError(Exception):
    """Base class for all CVFlow errors."""


class DatasetError(CVFlowError):
    """A dataset could not be loaded or is structurally invalid."""


class UnsupportedFormatError(DatasetError):
    """The dataset format could not be detected or is not supported."""
