"""Dataset statistics and statistical-anomaly checks.

Two responsibilities:

- :func:`compute_statistics` derives descriptive aggregates
  (:class:`cvflow.model.DatasetStatistics`) for display.
- The checks below turn *unusual* patterns into :class:`~cvflow.model.Issue`
  findings. In keeping with CVFlow's philosophy, statistical anomalies are never
  ``ERROR``s — they are things "worth reviewing", surfaced as ``WARNING``/``INFO``.
"""

from __future__ import annotations

import statistics as _stats
from collections import Counter
from collections.abc import Iterable

from cvflow.analysis.engine import Check, CheckConfig
from cvflow.model import Dataset, DatasetStatistics, Issue, Location, Severity, Summary


def compute_statistics(dataset: Dataset) -> DatasetStatistics:
    """Compute descriptive statistics for a dataset."""
    class_counts: Counter[int] = Counter()
    images_per_class: Counter[int] = Counter()
    split_counts: Counter[str] = Counter()
    objects_per_image: list[float] = []
    box_areas: list[float] = []
    aspect_ratios: list[float] = []
    empty_images = 0

    for item in dataset.images:
        split_counts[item.split or "(unsplit)"] += 1
        objects_per_image.append(float(item.num_boxes))
        if item.is_empty:
            empty_images += 1

        classes_here: set[int] = set()
        for box in item.boxes:
            class_counts[box.class_id] += 1
            classes_here.add(box.class_id)
            if box.area > 0:
                box_areas.append(box.area)
        for class_id in classes_here:
            images_per_class[class_id] += 1

        if item.width and item.height and item.height > 0:
            aspect_ratios.append(item.width / item.height)

    return DatasetStatistics(
        num_images=dataset.num_images,
        num_annotations=dataset.num_annotations,
        num_classes=dataset.num_classes,
        class_counts=dict(class_counts),
        images_per_class=dict(images_per_class),
        split_counts=dict(split_counts),
        objects_per_image=Summary.from_values(objects_per_image),
        box_area=Summary.from_values(box_areas),
        aspect_ratio=Summary.from_values(aspect_ratios),
        empty_images=empty_images,
    )


class ObjectsPerImageOutlierCheck(Check):
    """Flags images with far more objects than is typical for the dataset."""

    code = "statistics"

    def __init__(self, config: CheckConfig | None = None) -> None:
        cfg = config or CheckConfig()
        self._sigma = cfg.objects_outlier_sigma
        self._floor = cfg.objects_outlier_floor

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        counts = [item.num_boxes for item in dataset.images]
        if len(counts) < 5:
            return  # too few images for a meaningful distribution
        mean = _stats.fmean(counts)
        std = _stats.pstdev(counts)
        threshold = max(float(self._floor), mean + self._sigma * std)
        typical_low = max(0, min(counts))
        typical_high = round(mean + std)
        for item in dataset.images:
            if item.num_boxes <= threshold:
                continue
            yield Issue(
                code="objects-per-image-outlier",
                severity=Severity.WARNING,
                message=f"Image contains {item.num_boxes} objects — a statistical outlier.",
                why=(
                    f"Typical images hold about {typical_low} to {typical_high} objects "
                    f"(mean {mean:.1f}); this one has far more."
                ),
                location=Location(path=item.path, split=item.split),
                evidence={
                    "objects": item.num_boxes,
                    "mean": round(mean, 2),
                    "threshold": round(threshold, 2),
                },
                suggestion="Review this image; it may be mislabeled or unusually dense.",
            )


class RareClassCheck(Check):
    """Reports classes that make up a very small share of all annotations."""

    code = "statistics"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._fraction = (config or CheckConfig()).rare_class_fraction

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        total = dataset.num_annotations
        if total < 50:
            return  # not enough data to call anything "rare"
        counts: Counter[int] = Counter()
        for _item, box in dataset.iter_boxes():
            counts[box.class_id] += 1
        for class_id, count in counts.items():
            fraction = count / total
            if fraction >= self._fraction:
                continue
            name = dataset.class_names.get(class_id, str(class_id))
            yield Issue(
                code="rare-class",
                severity=Severity.INFO,
                message=f"Class '{name}' represents only {fraction:.1%} of annotations.",
                why=(
                    "Under-represented classes are harder for models to learn and "
                    "may be worth augmenting or rebalancing."
                ),
                evidence={"class_id": class_id, "count": count, "fraction": round(fraction, 4)},
                suggestion="Consider collecting more examples or rebalancing this class.",
            )


class ClassImbalanceCheck(Check):
    """Reports a large gap between the most- and least-common classes."""

    code = "statistics"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._ratio = (config or CheckConfig()).class_imbalance_ratio

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        counts: Counter[int] = Counter()
        for _item, box in dataset.iter_boxes():
            counts[box.class_id] += 1
        if len(counts) < 2:
            return
        most_id, most = max(counts.items(), key=lambda kv: kv[1])
        least_id, least = min(counts.items(), key=lambda kv: kv[1])
        if least <= 0 or most / least < self._ratio:
            return
        most_name = dataset.class_names.get(most_id, str(most_id))
        least_name = dataset.class_names.get(least_id, str(least_id))
        yield Issue(
            code="class-imbalance",
            severity=Severity.INFO,
            message=f"Class distribution is heavily imbalanced ({most / least:.0f}x).",
            why=(
                f"'{most_name}' has {most} annotations while '{least_name}' has only "
                f"{least}. Large imbalance can bias training."
            ),
            evidence={
                "most_common": {"class_id": most_id, "count": most},
                "least_common": {"class_id": least_id, "count": least},
                "ratio": round(most / least, 2),
            },
            suggestion="Consider rebalancing, weighting the loss, or augmenting rare classes.",
        )


def statistics_checks(config: CheckConfig | None = None) -> list[Check]:
    """Return the default set of statistical-anomaly checks."""
    return [
        ObjectsPerImageOutlierCheck(config),
        RareClassCheck(config),
        ClassImbalanceCheck(config),
    ]
