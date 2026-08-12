"""Tests for the mask- and rotation-aware checks.

These exist because a polygon's bounding box says nothing about the polygon:
a rectangle traced as a mask, or four points that do not form a rectangle, are
invisible to every box-level check.
"""

from __future__ import annotations

import math

import pytest

from cvflow.analysis import CheckConfig, shape_checks
from cvflow.analysis.shapes import (
    EmptyMaskCheck,
    NonRectangularObbCheck,
    RectangularMaskCheck,
    SliverMaskCheck,
    SparsePolygonCheck,
    UnrotatedObbCheck,
)
from cvflow.model import BoundingBox, Dataset, ImageItem


def _shape(points: list[tuple[float, float]], class_id: int = 0) -> BoundingBox:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return BoundingBox(
        class_id=class_id,
        x_min=min(xs),
        y_min=min(ys),
        x_max=max(xs),
        y_max=max(ys),
        points=tuple(points),
    )


def _dataset(task: str, boxes: list[BoundingBox]) -> Dataset:
    dataset = Dataset(name="d", root=".", format="yolo", task=task)
    dataset.class_names = {0: "thing"}
    dataset.images.append(ImageItem(path="a.jpg", boxes=boxes))
    return dataset


def _codes(dataset: Dataset) -> list[str]:
    return [issue.code for check in shape_checks(CheckConfig()) for issue in check.run(dataset)]


# --------------------------------------------------------------------------- #
# Geometry on the model
# --------------------------------------------------------------------------- #


def test_polygon_area_and_fill_ratio() -> None:
    # A triangle filling half of its bounding box.
    triangle = _shape([(0.0, 0.0), (0.4, 0.0), (0.0, 0.4)])
    assert triangle.polygon_area == pytest.approx(0.08)
    assert triangle.fill_ratio == pytest.approx(0.5)

    # A rectangle traced as a mask fills all of it.
    rectangle = _shape([(0.1, 0.1), (0.5, 0.1), (0.5, 0.3), (0.1, 0.3)])
    assert rectangle.fill_ratio == pytest.approx(1.0)

    # A plain detection box has no shape of its own.
    assert BoundingBox(0, 0.1, 0.1, 0.2, 0.2).polygon_area == 0.0
    assert BoundingBox(0, 0.1, 0.1, 0.2, 0.2).fill_ratio == 0.0


def test_rotation_and_corner_squareness() -> None:
    axis_aligned = _shape([(0.1, 0.1), (0.5, 0.1), (0.5, 0.3), (0.1, 0.3)])
    assert axis_aligned.rotation == 0.0
    assert axis_aligned.corner_squareness == 0.0

    # The same rectangle turned 30 degrees stays square at the corners.
    angle = math.radians(30)
    corners = []
    for x, y in ((-0.2, -0.1), (0.2, -0.1), (0.2, 0.1), (-0.2, 0.1)):
        corners.append(
            (
                0.5 + x * math.cos(angle) - y * math.sin(angle),
                0.5 + x * math.sin(angle) + y * math.cos(angle),
            )
        )
    rotated = _shape(corners)
    assert rotated.rotation == pytest.approx(30.0)
    assert rotated.corner_squareness < 1e-6

    skewed = _shape([(0.1, 0.1), (0.5, 0.1), (0.6, 0.3), (0.1, 0.3)])
    assert skewed.corner_squareness > 5


# --------------------------------------------------------------------------- #
# Segmentation
# --------------------------------------------------------------------------- #


def test_sparse_polygon_is_an_error() -> None:
    dataset = _dataset("segment", [_shape([(0.1, 0.1), (0.4, 0.4)])])
    issues = list(SparsePolygonCheck().run(dataset))

    assert [issue.code for issue in issues] == ["sparse-polygon"]
    assert issues[0].location is not None
    assert issues[0].location.annotation_index == 0


def test_collinear_polygon_encloses_nothing() -> None:
    dataset = _dataset("segment", [_shape([(0.1, 0.1), (0.3, 0.3), (0.5, 0.5)])])
    assert [issue.code for issue in EmptyMaskCheck().run(dataset)] == ["empty-mask"]


def test_rectangle_traced_as_a_mask_is_flagged() -> None:
    dataset = _dataset("segment", [_shape([(0.1, 0.1), (0.5, 0.1), (0.5, 0.3), (0.1, 0.3)])])
    issues = list(RectangularMaskCheck(CheckConfig()).run(dataset))

    assert [issue.code for issue in issues] == ["rectangular-mask"]
    assert issues[0].evidence["fill_ratio"] == 1.0


def test_a_real_outline_is_not_flagged() -> None:
    star = _shape([(0.5, 0.1), (0.6, 0.4), (0.9, 0.4), (0.65, 0.6), (0.5, 0.9), (0.35, 0.6)])
    assert list(RectangularMaskCheck(CheckConfig()).run(_dataset("segment", [star]))) == []
    assert list(SliverMaskCheck(CheckConfig()).run(_dataset("segment", [star]))) == []


def test_sliver_mask_is_flagged() -> None:
    # A thin diagonal band: its bounding box is large, the mask itself is not.
    sliver = _shape([(0.1, 0.1), (0.9, 0.9), (0.9, 0.88), (0.1, 0.08)])
    assert [
        issue.code for issue in SliverMaskCheck(CheckConfig()).run(_dataset("segment", [sliver]))
    ] == ["sliver-mask"]


def test_segmentation_checks_skip_detection_datasets() -> None:
    dataset = _dataset("detect", [BoundingBox(0, 0.1, 0.1, 0.4, 0.4)])
    assert _codes(dataset) == []


# --------------------------------------------------------------------------- #
# Oriented boxes
# --------------------------------------------------------------------------- #


def test_non_rectangular_obb_is_flagged() -> None:
    skewed = _shape([(0.1, 0.1), (0.5, 0.1), (0.6, 0.3), (0.1, 0.3)])
    issues = list(NonRectangularObbCheck(CheckConfig()).run(_dataset("obb", [skewed])))

    assert [issue.code for issue in issues] == ["non-rectangular-obb"]
    assert issues[0].evidence["worst_corner_degrees"] > 5


def test_square_obb_passes() -> None:
    square = _shape([(0.1, 0.1), (0.5, 0.1), (0.5, 0.3), (0.1, 0.3)])
    assert list(NonRectangularObbCheck(CheckConfig()).run(_dataset("obb", [square]))) == []


def test_all_axis_aligned_obbs_are_reported_once() -> None:
    boxes = [
        _shape([(0.1, 0.1), (0.5, 0.1), (0.5, 0.3), (0.1, 0.3)]),
        _shape([(0.2, 0.6), (0.4, 0.6), (0.4, 0.8), (0.2, 0.8)]),
    ]
    issues = list(UnrotatedObbCheck(CheckConfig()).run(_dataset("obb", boxes)))

    assert [issue.code for issue in issues] == ["unrotated-obb"]
    assert issues[0].evidence["boxes"] == 2
    assert issues[0].location is None  # a dataset-wide observation


def test_a_rotated_dataset_is_not_reported_as_flat() -> None:
    angle = math.radians(20)
    corners = [
        (
            0.5 + x * math.cos(angle) - y * math.sin(angle),
            0.5 + x * math.sin(angle) + y * math.cos(angle),
        )
        for x, y in ((-0.2, -0.1), (0.2, -0.1), (0.2, 0.1), (-0.2, 0.1))
    ]
    dataset = _dataset("obb", [_shape(corners)])
    assert list(UnrotatedObbCheck(CheckConfig()).run(dataset)) == []
