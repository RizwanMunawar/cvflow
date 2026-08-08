"""Dataset loaders.

Loaders translate an on-disk dataset (YOLO, COCO, …) into CVFlow's normalized
:mod:`cvflow.model`. The analysis engine only ever sees the normalized model,
so adding a new format is a matter of adding a loader here — no changes to the
rules, reporting, or CLI.

Concrete loaders are introduced in a later batch (M2 — Dataset Loaders).
"""

from __future__ import annotations

__all__: list[str] = []
