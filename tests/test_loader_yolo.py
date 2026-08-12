"""Tests for the YOLO loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvflow.exceptions import DatasetError
from cvflow.loaders import load_dataset
from cvflow.loaders.yolo import YoloLoader


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


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


def test_segmentation_labels_become_their_extent(tmp_path: Path) -> None:
    """A polygon label is read as a polygon, not as the first four numbers."""
    root = tmp_path / "seg"
    _write(root / "classes.txt", "cat\n")
    _touch(root / "images" / "train" / "a.jpg")
    # A five-point polygon; the axis-aligned extent is x 0.2-0.8, y 0.1-0.9.
    # (Four points would be indistinguishable from an oriented box on disk.)
    _write(root / "labels" / "train" / "a.txt", "0 0.5 0.1 0.8 0.5 0.5 0.9 0.2 0.5 0.35 0.3\n")

    dataset = load_dataset(root)

    assert dataset.task == "segment"
    box = dataset.images[0].boxes[0]
    assert box.x_min == pytest.approx(0.2)
    assert box.x_max == pytest.approx(0.8)
    assert box.y_min == pytest.approx(0.1)
    assert box.y_max == pytest.approx(0.9)


def test_obb_labels_become_their_extent(tmp_path: Path) -> None:
    root = tmp_path / "obb"
    _write(root / "classes.txt", "cat\n")
    _touch(root / "images" / "train" / "a.jpg")
    # Four corners of a rotated box.
    _write(root / "labels" / "train" / "a.txt", "0 0.3 0.2 0.7 0.4 0.6 0.8 0.2 0.6\n")

    dataset = load_dataset(root)

    assert dataset.task == "obb"
    box = dataset.images[0].boxes[0]
    assert box.x_min == pytest.approx(0.2)
    assert box.x_max == pytest.approx(0.7)
    assert box.y_min == pytest.approx(0.2)
    assert box.y_max == pytest.approx(0.8)


def test_detection_labels_stay_detection(yolo_convention_dataset: Path) -> None:
    assert load_dataset(yolo_convention_dataset).task == "detect"


def test_richest_task_wins_when_mixed(tmp_path: Path) -> None:
    root = tmp_path / "mixed"
    _write(root / "classes.txt", "cat\n")
    _touch(root / "images" / "train" / "a.jpg")
    _touch(root / "images" / "train" / "b.jpg")
    _write(root / "labels" / "train" / "a.txt", "0 0.5 0.5 0.2 0.2\n")
    _write(root / "labels" / "train" / "b.txt", "0 0.1 0.1 0.4 0.1 0.4 0.4 0.1 0.4 0.2 0.6\n")

    assert load_dataset(root).task == "segment"


def test_self_referential_path_in_yaml(tmp_path: Path) -> None:
    """`path:` naming the dataset's own folder must not lose every image.

    Ultralytics dataset YAMLs ship inside the folder their `path:` names
    (`path: construction-ppe`), so joining it to the yaml's directory points at
    a folder that does not exist. That used to load zero images and report a
    perfectly healthy dataset.
    """
    root = tmp_path / "construction-ppe"
    _write(
        root / "data.yaml",
        "path: construction-ppe\ntrain: images/train\nval: images/val\ntest: images/test\n"
        "names:\n  0: helmet\n",
    )
    for split in ("train", "val", "test"):
        _touch(root / "images" / split / f"{split}1.jpg")
        _write(root / "labels" / split / f"{split}1.txt", "0 0.5 0.5 0.2 0.2\n")

    dataset = load_dataset(root)

    assert dataset.num_images == 3
    assert dataset.num_annotations == 3
    assert dataset.splits == ["test", "train", "val"]


def test_absolute_path_in_yaml_is_honoured(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    _touch(elsewhere / "images" / "train" / "a.jpg")
    _write(elsewhere / "labels" / "train" / "a.txt", "0 0.5 0.5 0.2 0.2\n")

    root = tmp_path / "cfg"
    _write(
        root / "data.yaml",
        f"path: {elsewhere.as_posix()}\ntrain: images/train\nnames:\n  0: helmet\n",
    )

    assert load_dataset(root).num_images == 1
