"""Checks for annotations that are not axis-aligned boxes.

A segmentation polygon and an oriented box both *have* a bounding box, and the
rest of the engine audits that extent. But the extent is not the annotation:
a mask can be a rectangle somebody drew instead of tracing the object, and a
"rotated box" can be four points that do not form a rectangle at all. Neither
is visible from the extent, so those problems live here.

Each check is a no-op on datasets whose task does not apply, so the default
check set can carry all of them and a detection dataset pays nothing.
"""

from __future__ import annotations

from collections.abc import Iterable

from cvflow.analysis.engine import Check, CheckConfig
from cvflow.model import BoundingBox, Dataset, ImageItem, Issue, Location, Severity


def _shapes(dataset: Dataset) -> Iterable[tuple[ImageItem, int, BoundingBox]]:
    """Every annotation that kept its original geometry, with its index."""
    for item in dataset.images:
        for index, box in enumerate(item.boxes):
            if box.points:
                yield item, index, box


class SparsePolygonCheck(Check):
    """Segmentation polygons with too few points to enclose anything."""

    code = "segmentation"

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if dataset.task != "segment":
            return
        for item, index, box in _shapes(dataset):
            count = len(box.points or ())
            if count >= 3:
                continue
            yield Issue(
                code="sparse-polygon",
                severity=Severity.ERROR,
                message=f"Segmentation polygon has only {count} point(s).",
                why="A mask needs at least three points to enclose any area.",
                location=Location(path=item.path, split=item.split, annotation_index=index),
                evidence={"points": count, "class_id": box.class_id},
                suggestion="Re-trace this instance or remove the annotation.",
            )


class EmptyMaskCheck(Check):
    """Polygons that enclose (almost) no area, however many points they have."""

    code = "segmentation"

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if dataset.task != "segment":
            return
        for item, index, box in _shapes(dataset):
            if len(box.points or ()) < 3 or box.polygon_area > 0:
                continue
            yield Issue(
                code="empty-mask",
                severity=Severity.ERROR,
                message="Segmentation polygon encloses no area.",
                why=(
                    "The points are collinear or repeated, so the mask is a line "
                    "rather than a region and contributes nothing to training."
                ),
                location=Location(path=item.path, split=item.split, annotation_index=index),
                evidence={"points": len(box.points or ()), "class_id": box.class_id},
                suggestion="Re-trace this instance or remove the annotation.",
            )


class RectangularMaskCheck(Check):
    """Masks that are really just their bounding box.

    Common when a dataset is converted from detection, or when an annotator
    clicks four corners instead of tracing: the segmentation head then learns
    boxes, and the extra channel buys nothing.
    """

    code = "segmentation"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._fill = (config or CheckConfig()).rectangular_mask_fill

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if dataset.task != "segment":
            return
        for item, index, box in _shapes(dataset):
            if box.polygon_area <= 0 or box.fill_ratio < self._fill:
                continue
            yield Issue(
                code="rectangular-mask",
                severity=Severity.WARNING,
                message="Segmentation mask is effectively a rectangle.",
                why=(
                    f"The polygon fills {box.fill_ratio:.0%} of its own bounding box, "
                    "so it carries no more shape information than a detection label."
                ),
                location=Location(path=item.path, split=item.split, annotation_index=index),
                evidence={
                    "fill_ratio": round(box.fill_ratio, 3),
                    "points": len(box.points or ()),
                    "class_id": box.class_id,
                },
                suggestion="Trace the object's outline, or train a detector instead.",
            )


class SliverMaskCheck(Check):
    """Masks that cover a tiny sliver of the box they span."""

    code = "segmentation"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._fill = (config or CheckConfig()).sliver_mask_fill

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if dataset.task != "segment":
            return
        for item, index, box in _shapes(dataset):
            if box.polygon_area <= 0 or box.fill_ratio > self._fill:
                continue
            yield Issue(
                code="sliver-mask",
                severity=Severity.WARNING,
                message="Segmentation mask covers very little of its own extent.",
                why=(
                    f"The polygon fills only {box.fill_ratio:.1%} of its bounding box, "
                    "which usually means a stray point dragged the outline away."
                ),
                location=Location(path=item.path, split=item.split, annotation_index=index),
                evidence={
                    "fill_ratio": round(box.fill_ratio, 4),
                    "points": len(box.points or ()),
                    "class_id": box.class_id,
                },
                suggestion="Check for an outlying vertex in this outline.",
            )


class NonRectangularObbCheck(Check):
    """Oriented boxes whose four corners are not a rectangle."""

    code = "obb"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._tolerance = (config or CheckConfig()).obb_corner_tolerance

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if dataset.task != "obb":
            return
        for item, index, box in _shapes(dataset):
            if len(box.points or ()) != 4:
                continue
            worst = box.corner_squareness
            if worst <= self._tolerance:
                continue
            yield Issue(
                code="non-rectangular-obb",
                severity=Severity.WARNING,
                message="Oriented box is not a rectangle.",
                why=(
                    f"Its worst corner is {worst:.0f}° off square. Consumers of OBB "
                    "labels assume four right angles, so a skewed quad is read wrong."
                ),
                location=Location(path=item.path, split=item.split, annotation_index=index),
                evidence={"worst_corner_degrees": round(worst, 1), "class_id": box.class_id},
                suggestion="Redraw this box, or export it as a segmentation polygon.",
            )


class UnrotatedObbCheck(Check):
    """Oriented boxes that carry no rotation at all.

    Not wrong, but worth knowing: a whole dataset of them means the oriented
    format is costing you nothing that plain detection would not give.
    """

    code = "obb"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._tolerance = (config or CheckConfig()).obb_flat_tolerance

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if dataset.task != "obb":
            return
        flat = 0
        total = 0
        for _item, _index, box in _shapes(dataset):
            if len(box.points or ()) != 4:
                continue
            total += 1
            rotation = box.rotation
            if min(rotation, 90.0 - rotation) <= self._tolerance:
                flat += 1
        if not total or flat != total:
            return
        yield Issue(
            code="unrotated-obb",
            severity=Severity.INFO,
            message="Every oriented box is axis-aligned.",
            why=(
                f"All {total:,} oriented boxes sit within {self._tolerance:.0f}° of the "
                "image axes, so the rotation this format carries is unused."
            ),
            evidence={"boxes": total, "tolerance_degrees": self._tolerance},
            suggestion="Confirm the rotation was exported; plain detection may fit better.",
        )


def shape_checks(config: CheckConfig | None = None) -> list[Check]:
    """Every mask- and rotation-aware check, in report order."""
    cfg = config or CheckConfig()
    return [
        SparsePolygonCheck(),
        EmptyMaskCheck(),
        RectangularMaskCheck(cfg),
        SliverMaskCheck(cfg),
        NonRectangularObbCheck(cfg),
        UnrotatedObbCheck(cfg),
    ]
