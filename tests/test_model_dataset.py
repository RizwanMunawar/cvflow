"""Tests for the normalized dataset model."""

from __future__ import annotations

import pytest

from cvflow.model import BoundingBox, Dataset, ImageItem


def test_bbox_geometry() -> None:
    box = BoundingBox(class_id=0, x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.4)
    assert box.width == pytest.approx(0.4)
    assert box.height == pytest.approx(0.2)
    assert box.area == pytest.approx(0.08)
    cx, cy = box.center
    assert cx == pytest.approx(0.3)
    assert cy == pytest.approx(0.3)


def test_bbox_area_clamped_for_degenerate_boxes() -> None:
    inverted = BoundingBox(class_id=0, x_min=0.6, y_min=0.6, x_max=0.4, y_max=0.4)
    assert inverted.width < 0
    assert inverted.area == 0.0


def test_bbox_from_yolo() -> None:
    box = BoundingBox.from_yolo(1, cx=0.5, cy=0.5, w=0.2, h=0.4)
    assert box.class_id == 1
    assert box.x_min == pytest.approx(0.4)
    assert box.x_max == pytest.approx(0.6)
    assert box.y_min == pytest.approx(0.3)
    assert box.y_max == pytest.approx(0.7)


def test_bbox_from_coco_normalizes() -> None:
    box = BoundingBox.from_coco(2, x=10, y=20, w=30, h=40, image_width=100, image_height=200)
    assert box.x_min == pytest.approx(0.1)
    assert box.y_min == pytest.approx(0.1)
    assert box.x_max == pytest.approx(0.4)
    assert box.y_max == pytest.approx(0.3)


def test_bbox_from_coco_missing_dims_keeps_absolute() -> None:
    # With unknown dimensions we keep raw values so the out-of-range shows up.
    box = BoundingBox.from_coco(0, x=10, y=20, w=30, h=40, image_width=0, image_height=0)
    assert box.x_min == pytest.approx(10)
    assert box.x_max == pytest.approx(40)


def test_image_item_empty() -> None:
    empty = ImageItem(path="a.jpg")
    assert empty.is_empty
    assert empty.num_boxes == 0
    populated = ImageItem(path="b.jpg", boxes=[BoundingBox(0, 0, 0, 1, 1)])
    assert not populated.is_empty
    assert populated.num_boxes == 1


def test_dataset_aggregates() -> None:
    ds = Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=[
            ImageItem(path="t1.jpg", split="train", boxes=[BoundingBox(0, 0, 0, 1, 1)]),
            ImageItem(path="t2.jpg", split="train", boxes=[]),
            ImageItem(path="v1.jpg", split="val", boxes=[BoundingBox(1, 0, 0, 1, 1)]),
        ],
        class_names={0: "cat", 1: "dog"},
    )
    assert ds.num_images == 3
    assert ds.num_annotations == 2
    assert ds.num_classes == 2
    assert ds.splits == ["train", "val"]
    assert len(ds.images_in_split("train")) == 2
    pairs = list(ds.iter_boxes())
    assert len(pairs) == 2


def test_dataset_splits_ignores_none() -> None:
    ds = Dataset(
        name="d",
        root="/tmp/d",
        format="coco",
        images=[ImageItem(path="a.jpg", split=None)],
    )
    assert ds.splits == []
