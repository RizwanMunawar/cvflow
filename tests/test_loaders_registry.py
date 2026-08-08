"""Tests for the loader registry and load_dataset entry point."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvflow.exceptions import UnsupportedFormatError
from cvflow.loaders import available_formats, detect_format, load_dataset


def test_available_formats() -> None:
    formats = available_formats()
    assert "yolo" in formats
    assert "coco" in formats


def test_detect_format_yolo(yolo_yaml_dataset: Path) -> None:
    assert detect_format(yolo_yaml_dataset) == "yolo"


def test_detect_format_coco(coco_dir_dataset: Path) -> None:
    assert detect_format(coco_dir_dataset) == "coco"


def test_detect_format_unknown(tmp_path: Path) -> None:
    assert detect_format(tmp_path) is None


def test_load_dataset_autodetects_yolo(yolo_yaml_dataset: Path) -> None:
    ds = load_dataset(yolo_yaml_dataset)
    assert ds.format == "yolo"
    assert ds.num_images == 3


def test_load_dataset_autodetects_coco(coco_dir_dataset: Path) -> None:
    ds = load_dataset(coco_dir_dataset)
    assert ds.format == "coco"
    assert ds.num_annotations == 3


def test_load_dataset_explicit_format(coco_json_file: Path) -> None:
    ds = load_dataset(coco_json_file, fmt="coco")
    assert ds.format == "coco"


def test_load_dataset_unknown_format_raises(coco_json_file: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        load_dataset(coco_json_file, fmt="pascal-voc")


def test_load_dataset_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        load_dataset(tmp_path / "nope")


def test_load_dataset_undetectable_raises(tmp_path: Path) -> None:
    (tmp_path / "readme.txt").write_text("not a dataset")
    with pytest.raises(UnsupportedFormatError):
        load_dataset(tmp_path)
