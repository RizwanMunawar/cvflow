"""The analysis engine.

A :class:`Check` inspects a normalized :class:`~cvflow.model.Dataset` and yields
:class:`~cvflow.model.Issue` findings. The :class:`AnalysisEngine` runs a
collection of checks and returns their findings sorted most-severe-first.

This is the extensibility seam for all analysis: integrity (M3), annotation
geometry (M4), statistics (M5), duplicates (M6), and leakage (M7) are all just
checks registered here. Adding a rule never requires touching the engine, the
CLI, or the reporter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from cvflow.model import Dataset, Issue


class Check(ABC):
    """Base class for a single analysis check."""

    #: Stable, kebab-case identifier for the *category* of check, e.g.
    #: ``"integrity"``. Individual issues carry their own finer-grained codes.
    code: str = ""

    @abstractmethod
    def run(self, dataset: Dataset) -> Iterable[Issue]:
        """Inspect ``dataset`` and yield any findings."""


class CheckConfig:
    """Runtime options that influence which/how checks run.

    Kept intentionally small; checks read only what they need and ignore the
    rest, so new options don't ripple through every check.
    """

    def __init__(self, *, check_images: bool = True) -> None:
        #: When False, checks that read image bytes (e.g. corrupt-image
        #: detection) are skipped. Useful for a fast, metadata-only pass.
        self.check_images = check_images


class AnalysisEngine:
    """Runs a set of checks over a dataset and aggregates their findings."""

    def __init__(self, checks: Iterable[Check]) -> None:
        self._checks: list[Check] = list(checks)

    @property
    def checks(self) -> list[Check]:
        return list(self._checks)

    def run(self, dataset: Dataset) -> list[Issue]:
        """Run all checks and return findings sorted most-severe-first."""
        issues: list[Issue] = []
        for check in self._checks:
            issues.extend(check.run(dataset))
        issues.sort(key=Issue.sort_key)
        return issues
