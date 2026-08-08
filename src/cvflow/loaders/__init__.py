"""Dataset loaders.

Loaders translate an on-disk dataset (YOLO, COCO, …) into CVFlow's normalized
:mod:`cvflow.model`. The analysis engine only ever sees the normalized model,
so adding a new format is a matter of adding a loader and registering it — no
changes to the rules, reporting, or CLI.
"""

from __future__ import annotations

from cvflow.loaders.base import DatasetLoader
from cvflow.loaders.coco import CocoLoader
from cvflow.loaders.registry import (
    available_formats,
    detect_format,
    load_dataset,
)
from cvflow.loaders.yolo import YoloLoader

__all__ = [
    "CocoLoader",
    "DatasetLoader",
    "YoloLoader",
    "available_formats",
    "detect_format",
    "load_dataset",
]
