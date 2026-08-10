"""Validation & analysis engine.

This package hosts the checks that inspect a normalized dataset and emit
:class:`cvflow.model.Issue` findings. The engine is organized so each family of
checks is independent and composable:

- integrity rules (corrupt images, missing/invalid annotations, …)
- annotation rules (out-of-bounds boxes, tiny/huge boxes, unknown classes, …)
- statistical analysis (class distribution, outliers, …)
- duplicate detection (exact + perceptual)
- split-leakage detection (cross-split similarity)
"""

from __future__ import annotations

from cvflow.analysis.annotations import annotation_checks
from cvflow.analysis.duplicates import duplicate_checks
from cvflow.analysis.engine import AnalysisEngine, Check, CheckConfig
from cvflow.analysis.integrity import integrity_checks
from cvflow.analysis.statistics import compute_statistics, statistics_checks

__all__ = [
    "AnalysisEngine",
    "Check",
    "CheckConfig",
    "annotation_checks",
    "compute_statistics",
    "default_checks",
    "duplicate_checks",
    "integrity_checks",
    "statistics_checks",
]


def default_checks(config: CheckConfig | None = None) -> list[Check]:
    """Return the default set of checks to run for ``cvflow inspect``.

    Grows as new check families land (leakage, …).
    """
    return [
        *integrity_checks(config),
        *annotation_checks(config),
        *statistics_checks(config),
        *duplicate_checks(config),
    ]
