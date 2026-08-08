"""Validation & analysis engine.

This package hosts the checks that inspect a normalized dataset and emit
:class:`cvflow.model.Issue` findings. The engine is organized so each family of
checks is independent and composable:

- integrity rules (corrupt images, missing/invalid annotations, …)  [M3]
- annotation rules (out-of-bounds boxes, tiny/huge boxes, unknown classes, …)  [M4]
- statistical analysis (class distribution, outliers, …)  [M5]
- duplicate detection (exact + perceptual)  [M6]
- split-leakage detection (cross-split similarity)  [M7]
"""

from __future__ import annotations

from cvflow.analysis.engine import AnalysisEngine, Check, CheckConfig
from cvflow.analysis.integrity import integrity_checks

__all__ = [
    "AnalysisEngine",
    "Check",
    "CheckConfig",
    "default_checks",
    "integrity_checks",
]


def default_checks(config: CheckConfig | None = None) -> list[Check]:
    """Return the default set of checks to run for ``cvflow inspect``.

    Grows as new check families land (annotation geometry, statistics, …).
    """
    return integrity_checks(config)
