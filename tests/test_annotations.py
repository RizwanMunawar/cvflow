"""Tests for the annotation-geometry checks."""

from __future__ import annotations

from cvflow.analysis import CheckConfig, annotation_checks
from cvflow.analysis.annotations import (
    DegenerateBoxCheck,
    DuplicateBoxCheck,
    HugeBoxCheck,
    OutOfBoundsBoxCheck,
    TinyBoxCheck,
    _iou,
)
from cvflow.model import BoundingBox, Dataset, ImageItem, Severity


def _ds(*boxes: BoundingBox) -> Dataset:
    return Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=[ImageItem(path="a.jpg", split="train", boxes=list(boxes))],
        class_names={0: "cat", 1: "dog"},
    )


def test_iou_identical_boxes() -> None:
    a = BoundingBox(0, 0.1, 0.1, 0.5, 0.5)
    assert _iou(a, a) == 1.0


def test_iou_disjoint_boxes() -> None:
    a = BoundingBox(0, 0.0, 0.0, 0.1, 0.1)
    b = BoundingBox(0, 0.5, 0.5, 0.6, 0.6)
    assert _iou(a, b) == 0.0


def test_out_of_bounds_detects_overflow_and_negative() -> None:
    ds = _ds(
        BoundingBox(0, 0.1, 0.1, 1.2, 0.5),  # x_max > 1
        BoundingBox(0, -0.2, 0.1, 0.5, 0.5),  # negative x_min
        BoundingBox(0, 0.1, 0.1, 0.5, 0.5),  # fine
    )
    issues = list(OutOfBoundsBoxCheck().run(ds))
    assert len(issues) == 2
    assert all(i.severity is Severity.ERROR for i in issues)


def test_out_of_bounds_respects_epsilon() -> None:
    # 1.0005 is within the default 1e-3 tolerance -> not flagged.
    ds = _ds(BoundingBox(0, 0.0, 0.0, 1.0005, 0.5))
    assert list(OutOfBoundsBoxCheck().run(ds)) == []


def test_degenerate_box() -> None:
    ds = _ds(
        BoundingBox(0, 0.5, 0.5, 0.5, 0.7),  # zero width
        BoundingBox(0, 0.1, 0.1, 0.5, 0.5),  # fine
    )
    issues = list(DegenerateBoxCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].severity is Severity.ERROR


def test_tiny_box() -> None:
    ds = _ds(
        BoundingBox(0, 0.5, 0.5, 0.505, 0.505),  # 0.5% side -> tiny
        BoundingBox(0, 0.1, 0.1, 0.5, 0.5),  # fine
    )
    issues = list(TinyBoxCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].severity is Severity.WARNING


def test_huge_box() -> None:
    ds = _ds(
        BoundingBox(0, 0.0, 0.0, 1.0, 1.0),  # full frame
        BoundingBox(0, 0.1, 0.1, 0.3, 0.3),  # small
    )
    issues = list(HugeBoxCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].evidence["area"] >= 0.9


def test_duplicate_box_same_class() -> None:
    ds = _ds(
        BoundingBox(0, 0.10, 0.10, 0.50, 0.50),
        BoundingBox(0, 0.10, 0.10, 0.50, 0.50),  # identical, same class
        BoundingBox(1, 0.10, 0.10, 0.50, 0.50),  # same box, different class -> not dup
    )
    issues = list(DuplicateBoxCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].evidence["iou"] == 1.0


def test_thresholds_are_configurable() -> None:
    # With a very permissive tiny threshold, nothing is tiny.
    ds = _ds(BoundingBox(0, 0.5, 0.5, 0.505, 0.505))
    lenient = CheckConfig(tiny_box_side=0.0)
    checks = annotation_checks(lenient)
    tiny = [i for c in checks for i in c.run(ds) if i.code == "tiny-box"]
    assert tiny == []
