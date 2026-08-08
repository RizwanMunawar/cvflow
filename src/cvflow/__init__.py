"""CVFlow — ESLint / DevTools for computer-vision datasets.

CVFlow helps computer-vision developers quickly discover suspicious, broken,
duplicated, inconsistent, or potentially problematic data without manually
inspecting thousands of images and annotations.

This top-level package exposes the stable, cross-cutting primitives that the
rest of the system is built on. Feature areas (dataset loaders, the analysis
engine, reporting, and visualization) live in dedicated subpackages so that new
formats, rules, and outputs can be added without touching the core.
"""

from __future__ import annotations

from importlib import metadata

from cvflow.model import Issue, Location, Severity

__all__ = ["Issue", "Location", "Severity", "__version__"]


def _resolve_version() -> str:
    """Return the installed package version, falling back for source checkouts."""
    try:
        return metadata.version("cvflow")
    except metadata.PackageNotFoundError:  # pragma: no cover - editable/source use
        return "0.1.0"


__version__ = _resolve_version()
