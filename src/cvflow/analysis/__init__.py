"""Validation & analysis engine.

This package hosts the checks that inspect a normalized dataset and emit
:class:`cvflow.model.Issue` findings. The engine is organized so each family of
checks is independent and composable:

- integrity rules (corrupt images, missing/invalid annotations, …)
- annotation rules (out-of-bounds boxes, tiny/huge boxes, unknown classes, …)
- statistical analysis (class distribution, outliers, …)
- duplicate detection (exact + perceptual)
- split-leakage detection (cross-split similarity)

Concrete rules are introduced in later batches (M3 through M7).
"""

from __future__ import annotations

__all__: list[str] = []
