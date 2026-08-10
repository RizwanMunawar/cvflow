"""Normalized domain model shared across CVFlow.

These types are format-agnostic. Dataset loaders (YOLO, COCO, …) translate
their source formats into this model, and the analysis engine produces
:class:`Issue` values against it. Keeping the model here decouples *what* a
dataset is from *how* it was stored on disk.
"""

from __future__ import annotations

from cvflow.model.dataset import BoundingBox, Dataset, ImageItem
from cvflow.model.issue import Issue, Location
from cvflow.model.severity import Severity
from cvflow.model.stats import DatasetStatistics, Summary

__all__ = [
    "BoundingBox",
    "Dataset",
    "DatasetStatistics",
    "ImageItem",
    "Issue",
    "Location",
    "Severity",
    "Summary",
]
