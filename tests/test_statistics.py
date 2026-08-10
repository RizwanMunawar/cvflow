"""Tests for dataset statistics and statistical-anomaly checks."""

from __future__ import annotations

from cvflow.analysis import CheckConfig, compute_statistics
from cvflow.analysis.statistics import (
    ClassImbalanceCheck,
    ObjectsPerImageOutlierCheck,
    RareClassCheck,
)
from cvflow.model import BoundingBox, Dataset, ImageItem, Severity


def _img(
    path: str,
    split: str,
    classes: list[int],
    *,
    w: int | None = None,
    h: int | None = None,
) -> ImageItem:
    boxes = [BoundingBox(c, 0.1, 0.1, 0.3, 0.3) for c in classes]
    return ImageItem(path=path, split=split, boxes=boxes, width=w, height=h)


def test_compute_statistics_basic() -> None:
    ds = Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=[
            _img("t1.jpg", "train", [0, 0, 1], w=100, h=50),
            _img("t2.jpg", "train", []),  # empty
            _img("v1.jpg", "val", [0]),
        ],
        class_names={0: "cat", 1: "dog"},
    )
    stats = compute_statistics(ds)
    assert stats.num_images == 3
    assert stats.num_annotations == 4
    assert stats.class_counts == {0: 3, 1: 1}
    assert stats.images_per_class == {0: 2, 1: 1}
    assert stats.split_counts == {"train": 2, "val": 1}
    assert stats.empty_images == 1
    assert stats.objects_per_image.maximum == 3
    assert stats.objects_per_image.minimum == 0
    assert stats.aspect_ratio.count == 1  # only t1 has dims
    assert stats.aspect_ratio.mean == 2.0  # 100/50


def test_objects_per_image_outlier() -> None:
    images = [_img(f"n{i}.jpg", "train", [0]) for i in range(15)]  # 1 object each
    images.append(_img("dense.jpg", "train", [0] * 40))  # clear outlier
    ds = Dataset(name="d", root="/tmp/d", format="yolo", images=images, class_names={0: "cat"})
    issues = list(ObjectsPerImageOutlierCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].severity is Severity.WARNING
    assert issues[0].evidence["objects"] == 40


def test_objects_outlier_skipped_for_small_datasets() -> None:
    ds = Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=[_img("a.jpg", "train", [0] * 100), _img("b.jpg", "train", [0])],
        class_names={0: "cat"},
    )
    assert list(ObjectsPerImageOutlierCheck().run(ds)) == []


def test_rare_class() -> None:
    # 99 of class 0, 1 of class 1 -> class 1 is ~1% (below default 1%? it's exactly 1%).
    images = [_img("a.jpg", "train", [0] * 99), _img("b.jpg", "train", [1])]
    ds = Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=images,
        class_names={0: "cat", 1: "dog"},
    )
    issues = list(RareClassCheck(CheckConfig(rare_class_fraction=0.05)).run(ds))
    codes = {i.evidence["class_id"] for i in issues}
    assert 1 in codes
    assert all(i.severity is Severity.INFO for i in issues)


def test_rare_class_skipped_for_small_datasets() -> None:
    ds = Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=[_img("a.jpg", "train", [0, 1])],
        class_names={0: "cat", 1: "dog"},
    )
    assert list(RareClassCheck().run(ds)) == []


def test_class_imbalance() -> None:
    images = [_img("a.jpg", "train", [0] * 300), _img("b.jpg", "train", [1])]
    ds = Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=images,
        class_names={0: "cat", 1: "dog"},
    )
    issues = list(ClassImbalanceCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].evidence["ratio"] == 300.0
    assert issues[0].severity is Severity.INFO


def test_class_imbalance_needs_two_classes() -> None:
    ds = Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=[_img("a.jpg", "train", [0] * 500)],
        class_names={0: "cat"},
    )
    assert list(ClassImbalanceCheck().run(ds)) == []
