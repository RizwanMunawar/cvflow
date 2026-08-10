"""The analysis engine.

A :class:`Check` inspects a normalized :class:`~cvflow.model.Dataset` and yields
:class:`~cvflow.model.Issue` findings. The :class:`AnalysisEngine` runs a
collection of checks and returns their findings sorted most-severe-first.

This is the extensibility seam for all analysis: integrity, annotation
geometry, statistics, duplicates, and leakage are all just checks registered
here. Adding a rule never requires touching the engine, the CLI, or the
reporter.
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

    def __init__(
        self,
        *,
        check_images: bool = True,
        out_of_bounds_eps: float = 1e-3,
        tiny_box_side: float = 0.01,
        huge_box_area: float = 0.9,
        duplicate_iou: float = 0.95,
        objects_outlier_sigma: float = 3.0,
        objects_outlier_floor: int = 10,
        rare_class_fraction: float = 0.01,
        class_imbalance_ratio: float = 100.0,
        near_duplicate_max_hamming: int = 5,
        max_reported_duplicate_pairs: int = 100,
        leakage_max_hamming: int = 5,
    ) -> None:
        #: When False, checks that read image bytes (e.g. corrupt-image
        #: detection) are skipped. Useful for a fast, metadata-only pass.
        self.check_images = check_images
        #: Tolerance before a normalized coordinate counts as out of bounds.
        self.out_of_bounds_eps = out_of_bounds_eps
        #: A box whose normalized width or height is below this is "tiny".
        self.tiny_box_side = tiny_box_side
        #: A box whose normalized area exceeds this is "huge" (near full frame).
        self.huge_box_area = huge_box_area
        #: Same-class boxes with IoU >= this are flagged as duplicates.
        self.duplicate_iou = duplicate_iou
        #: Objects-per-image above mean + sigma*std (and the floor) is an outlier.
        self.objects_outlier_sigma = objects_outlier_sigma
        #: Absolute floor so tiny datasets don't produce object-count outliers.
        self.objects_outlier_floor = objects_outlier_floor
        #: A class with fewer than this fraction of all annotations is "rare".
        self.rare_class_fraction = rare_class_fraction
        #: Most-common : least-common class ratio above this flags imbalance.
        self.class_imbalance_ratio = class_imbalance_ratio
        #: Perceptual-hash Hamming distance at/below which images are near-dupes.
        self.near_duplicate_max_hamming = near_duplicate_max_hamming
        #: Cap on reported near-duplicate pairs (avoids flooding).
        self.max_reported_duplicate_pairs = max_reported_duplicate_pairs
        #: Cross-split Hamming distance at/below which images are leakage candidates.
        self.leakage_max_hamming = leakage_max_hamming


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
