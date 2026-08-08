"""Annotation checks — suspicious bounding-box geometry.

These operate purely on the normalized ``xyxy`` boxes in the dataset model, so
every threshold is image-size-independent. Following CVFlow's philosophy, only
objectively invalid geometry (out of bounds, zero/negative area) is an
``ERROR``; unusual-but-possibly-fine boxes (very small, very large, duplicated)
are ``WARNING``s the developer can judge.
"""

from __future__ import annotations

from collections.abc import Iterable

from cvflow.analysis.engine import Check, CheckConfig
from cvflow.model import BoundingBox, Dataset, ImageItem, Issue, Location, Severity


def _fmt_box(box: BoundingBox) -> dict[str, float]:
    return {
        "x_min": round(box.x_min, 4),
        "y_min": round(box.y_min, 4),
        "x_max": round(box.x_max, 4),
        "y_max": round(box.y_max, 4),
    }


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    """Intersection-over-union of two boxes (normalized coordinates)."""
    ix1 = max(a.x_min, b.x_min)
    iy1 = max(a.y_min, b.y_min)
    ix2 = min(a.x_max, b.x_max)
    iy2 = min(a.y_max, b.y_max)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


class OutOfBoundsBoxCheck(Check):
    """Boxes whose coordinates fall outside the normalized image frame."""

    code = "annotation"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._eps = (config or CheckConfig()).out_of_bounds_eps

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        lo, hi = -self._eps, 1.0 + self._eps
        for item, box in dataset.iter_boxes():
            coords = (box.x_min, box.y_min, box.x_max, box.y_max)
            if all(lo <= c <= hi for c in coords):
                continue
            negative = box.x_min < lo or box.y_min < lo
            why = "One or more coordinates fall outside the image frame [0, 1]."
            if negative:
                why = "One or more coordinates are negative (outside the image frame)."
            yield Issue(
                code="box-out-of-bounds",
                severity=Severity.ERROR,
                message="Bounding box extends outside the image boundaries.",
                why=why,
                location=Location(path=item.path, split=item.split),
                evidence={"box": _fmt_box(box), "class_id": box.class_id},
                suggestion="Clip the box to the image or fix the annotation.",
            )


class DegenerateBoxCheck(Check):
    """Boxes with zero or negative width/height (no area)."""

    code = "annotation"

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        for item, box in dataset.iter_boxes():
            if box.width > 0 and box.height > 0:
                continue
            yield Issue(
                code="degenerate-box",
                severity=Severity.ERROR,
                message="Bounding box has zero or negative width/height.",
                why="A valid box must have positive width and height.",
                location=Location(path=item.path, split=item.split),
                evidence={
                    "box": _fmt_box(box),
                    "width": round(box.width, 4),
                    "height": round(box.height, 4),
                },
                suggestion="Remove or correct this annotation.",
            )


class TinyBoxCheck(Check):
    """Boxes that are unusually small in normalized size."""

    code = "annotation"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._min_side = (config or CheckConfig()).tiny_box_side

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        for item, box in dataset.iter_boxes():
            if box.width <= 0 or box.height <= 0:
                continue  # degenerate boxes are handled elsewhere
            if box.width >= self._min_side and box.height >= self._min_side:
                continue
            yield Issue(
                code="tiny-box",
                severity=Severity.WARNING,
                message="Unusually small bounding box detected.",
                why=(
                    f"A side is below {self._min_side:.0%} of the image; such "
                    "boxes are often labeling noise or mistakes."
                ),
                location=Location(path=item.path, split=item.split),
                evidence={
                    "box": _fmt_box(box),
                    "width": round(box.width, 4),
                    "height": round(box.height, 4),
                },
                suggestion="Review whether this small object is correctly labeled.",
            )


class HugeBoxCheck(Check):
    """Boxes that cover almost the entire image."""

    code = "annotation"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._max_area = (config or CheckConfig()).huge_box_area

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        for item, box in dataset.iter_boxes():
            if box.area <= self._max_area:
                continue
            yield Issue(
                code="huge-box",
                severity=Severity.WARNING,
                message="Bounding box covers almost the entire image.",
                why=(
                    f"The box covers {box.area:.0%} of the image; near-full-frame "
                    "boxes are sometimes accidental or overly coarse labels."
                ),
                location=Location(path=item.path, split=item.split),
                evidence={"box": _fmt_box(box), "area": round(box.area, 4)},
                suggestion="Confirm the object really fills the frame.",
            )


class DuplicateBoxCheck(Check):
    """Near-identical, same-class boxes within a single image."""

    code = "annotation"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._iou = (config or CheckConfig()).duplicate_iou

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        for item in dataset.images:
            yield from self._check_image(item)

    def _check_image(self, item: ImageItem) -> Iterable[Issue]:
        boxes = item.boxes
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a.class_id != b.class_id or a.area <= 0 or b.area <= 0:
                    continue
                iou = _iou(a, b)
                if iou < self._iou:
                    continue
                yield Issue(
                    code="duplicate-annotation",
                    severity=Severity.WARNING,
                    message="Two same-class boxes overlap almost completely.",
                    why=(
                        f"Boxes #{i} and #{j} (class {a.class_id}) have IoU "
                        f"{iou:.2f}; this often means a duplicated annotation."
                    ),
                    location=Location(path=item.path, split=item.split, annotation_index=j),
                    evidence={"iou": round(iou, 4), "class_id": a.class_id},
                    suggestion="Remove the duplicate box if they mark the same object.",
                )


def annotation_checks(config: CheckConfig | None = None) -> list[Check]:
    """Return the default set of annotation-geometry checks."""
    return [
        OutOfBoundsBoxCheck(config),
        DegenerateBoxCheck(),
        TinyBoxCheck(config),
        HugeBoxCheck(config),
        DuplicateBoxCheck(config),
    ]
