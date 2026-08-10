"""Descriptive dataset statistics (pure data).

These types hold *computed* aggregates about a dataset. They live in the model
layer so the reporter can render them without depending on the analysis package.
The computation itself lives in :mod:`cvflow.analysis.statistics`.
"""

from __future__ import annotations

import statistics as _stats
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Summary:
    """A small numeric summary of a sequence of values."""

    count: int = 0
    minimum: float = 0.0
    maximum: float = 0.0
    mean: float = 0.0
    median: float = 0.0

    @classmethod
    def from_values(cls, values: Sequence[float]) -> Summary:
        if not values:
            return cls()
        return cls(
            count=len(values),
            minimum=float(min(values)),
            maximum=float(max(values)),
            mean=float(_stats.fmean(values)),
            median=float(_stats.median(values)),
        )


@dataclass(frozen=True)
class DatasetStatistics:
    """Computed, descriptive statistics for a dataset."""

    num_images: int = 0
    num_annotations: int = 0
    num_classes: int = 0
    #: annotations per class id
    class_counts: dict[int, int] = field(default_factory=dict)
    #: number of images containing at least one box of a class id
    images_per_class: dict[int, int] = field(default_factory=dict)
    #: images per split (uses "(unsplit)" for images without a split)
    split_counts: dict[str, int] = field(default_factory=dict)
    objects_per_image: Summary = field(default_factory=Summary)
    box_area: Summary = field(default_factory=Summary)
    aspect_ratio: Summary = field(default_factory=Summary)
    empty_images: int = 0
