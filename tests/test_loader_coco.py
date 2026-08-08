"""Tests for the COCO loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvflow.exceptions import DatasetError
from cvflow.loaders.coco import CocoLoader


def test_detect_dir_dataset(coco_dir_dataset: Path) -> None:
    assert CocoLoader().detect(coco_dir_dataset)


def test_detect_json_file(coco_json_file: Path) -> None:
    assert CocoLoader().detect(coco_json_file)


def test_detect_rejects_non_coco(tmp_path: Path) -> None:
    (tmp_path / "random.json").write_text('{"hello": "world"}')
    assert not CocoLoader().detect(tmp_path)


def test_load_dir_dataset(coco_dir_dataset: Path) -> None:
    ds = CocoLoader().load(coco_dir_dataset)
    assert ds.format == "coco"
    assert ds.class_names == {1: "person", 2: "car"}
    assert ds.num_images == 2
    assert ds.num_annotations == 3
    assert ds.splits == ["train"]  # inferred from instances_train.json


def test_load_normalizes_boxes(coco_dir_dataset: Path) -> None:
    ds = CocoLoader().load(coco_dir_dataset)
    img1 = next(img for img in ds.images if img.image_id == 1)
    assert img1.width == 100
    assert img1.height == 200
    # bbox [10,20,30,40] on a 100x200 image -> normalized xyxy
    person = next(b for b in img1.boxes if b.class_id == 1)
    assert person.x_min == pytest.approx(0.1)
    assert person.y_min == pytest.approx(0.1)
    assert person.x_max == pytest.approx(0.4)
    assert person.y_max == pytest.approx(0.3)
    # bbox [0,0,100,200] -> full image
    full = next(b for b in img1.boxes if b.class_id == 2)
    assert full.area == pytest.approx(1.0)


def test_load_single_json_file(coco_json_file: Path) -> None:
    ds = CocoLoader().load(coco_json_file)
    assert ds.num_images == 1
    assert ds.num_annotations == 1
    assert ds.class_names == {5: "bicycle"}
    assert ds.splits == []  # no split in the filename


def test_load_missing_json_raises(tmp_path: Path) -> None:
    with pytest.raises(DatasetError):
        CocoLoader().load(tmp_path)
