"""Tests for the YOLO loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvflow.exceptions import DatasetError
from cvflow.loaders.yolo import YoloLoader


def test_detect_yaml_dataset(yolo_yaml_dataset: Path) -> None:
    assert YoloLoader().detect(yolo_yaml_dataset)


def test_detect_convention_dataset(yolo_convention_dataset: Path) -> None:
    assert YoloLoader().detect(yolo_convention_dataset)


def test_detect_rejects_non_yolo(tmp_path: Path) -> None:
    assert not YoloLoader().detect(tmp_path)
    assert not YoloLoader().detect(tmp_path / "does-not-exist")


def test_load_yaml_dataset(yolo_yaml_dataset: Path) -> None:
    ds = YoloLoader().load(yolo_yaml_dataset)
    assert ds.format == "yolo"
    assert ds.class_names == {0: "cat", 1: "dog"}
    assert ds.splits == ["train", "val"]
    # 1 train image + 2 val images (img2 + background) = 3
    assert ds.num_images == 3
    # 2 boxes in train + 1 in val = 3
    assert ds.num_annotations == 3

    train = ds.images_in_split("train")
    assert len(train) == 1
    assert train[0].num_boxes == 2

    val = ds.images_in_split("val")
    labeled = [img for img in val if not img.is_empty]
    background = [img for img in val if img.is_empty]
    assert len(labeled) == 1
    assert len(background) == 1  # background.jpg has no label file


def test_load_yaml_box_values_are_normalized(yolo_yaml_dataset: Path) -> None:
    ds = YoloLoader().load(yolo_yaml_dataset)
    box = next(b for img, b in ds.iter_boxes() if b.class_id == 0)
    # from "0 0.5 0.5 0.2 0.2"
    assert box.x_min == pytest.approx(0.4)
    assert box.x_max == pytest.approx(0.6)


def test_load_convention_dataset(yolo_convention_dataset: Path) -> None:
    ds = YoloLoader().load(yolo_convention_dataset)
    assert ds.class_names == {0: "cat", 1: "dog"}
    assert ds.num_images == 2
    assert ds.num_annotations == 1  # b.txt is empty
    assert ds.splits == ["train", "val"]


def test_names_as_list(tmp_path: Path) -> None:
    root = tmp_path / "d"
    (root).mkdir()
    (root / "data.yaml").write_text("names: ['a', 'b', 'c']\ntrain: images/train\n")
    (root / "images" / "train").mkdir(parents=True)
    (root / "images" / "train" / "x.jpg").touch()
    (root / "labels" / "train").mkdir(parents=True)
    (root / "labels" / "train" / "x.txt").write_text("2 0.5 0.5 0.1 0.1\n")
    ds = YoloLoader().load(root)
    assert ds.class_names == {0: "a", 1: "b", 2: "c"}
    assert ds.num_annotations == 1


def test_malformed_label_lines_skipped(tmp_path: Path) -> None:
    root = tmp_path / "d"
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir(parents=True)
    (root / "images" / "x.jpg").touch()
    (root / "labels" / "x.txt").write_text(
        "0 0.5 0.5 0.2 0.2\ngarbage line\n1 0.1\n2 0.5 0.5 0.1 0.1\n"
    )
    ds = YoloLoader().load(root)
    # Two valid lines parse; the malformed/short lines are skipped.
    assert ds.num_annotations == 2


def test_load_rejects_bad_path(tmp_path: Path) -> None:
    with pytest.raises(DatasetError):
        YoloLoader().load(tmp_path / "nope")
    # An empty directory is not a YOLO dataset.
    with pytest.raises(DatasetError):
        YoloLoader().load(tmp_path)
