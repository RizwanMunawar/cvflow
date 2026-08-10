"""Shared pytest fixtures: builders for tiny synthetic datasets.

These create minimal-but-valid on-disk YOLO and COCO datasets in a temp dir so
loader tests exercise real file parsing without shipping binary fixtures. Image
files are empty placeholders — the loaders never read image bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_png(path: Path, size: tuple[int, int] = (16, 16)) -> None:
    """Write a small valid PNG using Pillow."""
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(120, 120, 120)).save(path)


def _write_corrupt(path: Path) -> None:
    """Write bytes that are not a decodable image."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"this is definitely not a valid image file")


@pytest.fixture
def yolo_yaml_dataset(tmp_path: Path) -> Path:
    """A YOLO dataset described by data.yaml with train/val splits.

    train: 1 image / 2 boxes; val: 1 image / 1 box; 1 background image (no label).
    Classes: {0: cat, 1: dog}.
    """
    root = tmp_path / "yolo_yaml"
    _write(
        root / "data.yaml",
        "names:\n  0: cat\n  1: dog\ntrain: images/train\nval: images/val\n",
    )
    _touch(root / "images" / "train" / "img1.jpg")
    _touch(root / "images" / "val" / "img2.jpg")
    _touch(root / "images" / "val" / "background.jpg")  # no label file
    _write(root / "labels" / "train" / "img1.txt", "0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n")
    _write(root / "labels" / "val" / "img2.txt", "1 0.5 0.5 0.4 0.4\n")
    return root


@pytest.fixture
def yolo_convention_dataset(tmp_path: Path) -> Path:
    """A YOLO dataset using the images/+labels/ convention and classes.txt."""
    root = tmp_path / "yolo_conv"
    _write(root / "classes.txt", "cat\ndog\n")
    _touch(root / "images" / "train" / "a.jpg")
    _touch(root / "images" / "val" / "b.png")
    _write(root / "labels" / "train" / "a.txt", "0 0.5 0.5 0.2 0.2\n")
    _write(root / "labels" / "val" / "b.txt", "")  # empty label -> no boxes
    return root


@pytest.fixture
def coco_dir_dataset(tmp_path: Path) -> Path:
    """A COCO dataset directory with an annotations/ folder (train split)."""
    root = tmp_path / "coco"
    data = {
        "images": [
            {"id": 1, "file_name": "000001.jpg", "width": 100, "height": 200},
            {"id": 2, "file_name": "000002.jpg", "width": 50, "height": 50},
        ],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 20, 30, 40]},
            {"id": 2, "image_id": 1, "category_id": 2, "bbox": [0, 0, 100, 200]},
            {"id": 3, "image_id": 2, "category_id": 1, "bbox": [5, 5, 10, 10]},
        ],
        "categories": [
            {"id": 1, "name": "person"},
            {"id": 2, "name": "car"},
        ],
    }
    _write(root / "annotations" / "instances_train.json", json.dumps(data))
    return root


@pytest.fixture
def integrity_dataset(tmp_path: Path) -> Path:
    """A YOLO dataset with real image files engineered to trip integrity checks.

    Triggers: corrupt-image, duplicate-filename, invalid-class-id, empty-image,
    and invalid-annotation-file.
    """
    root = tmp_path / "integrity"
    _write(root / "data.yaml", "names:\n  0: cat\n  1: dog\ntrain: images/train\nval: images/val\n")

    # A clean, valid image + label.
    _write_png(root / "images" / "train" / "good.png")
    _write(root / "labels" / "train" / "good.txt", "0 0.5 0.5 0.2 0.2\n")

    # A corrupt image (undecodable bytes) with a valid label.
    _write_corrupt(root / "images" / "train" / "corrupt.png")
    _write(root / "labels" / "train" / "corrupt.txt", "1 0.5 0.5 0.2 0.2\n")

    # Duplicate filename across splits.
    _write_png(root / "images" / "train" / "dupe.png")
    _write(root / "labels" / "train" / "dupe.txt", "0 0.5 0.5 0.2 0.2\n")
    _write_png(root / "images" / "val" / "dupe.png")
    _write(root / "labels" / "val" / "dupe.txt", "1 0.5 0.5 0.2 0.2\n")

    # An annotation with an undefined class id (5 is not in {0, 1}).
    _write_png(root / "images" / "train" / "badclass.png")
    _write(root / "labels" / "train" / "badclass.txt", "5 0.5 0.5 0.2 0.2\n")

    # An empty (background) image — valid file, no boxes.
    _write_png(root / "images" / "train" / "empty.png")
    _write(root / "labels" / "train" / "empty.txt", "")

    # A malformed annotation file (one good line, one garbage line).
    _write_png(root / "images" / "train" / "malformed.png")
    _write(root / "labels" / "train" / "malformed.txt", "0 0.5 0.5 0.2 0.2\ngarbage line here\n")

    return root


@pytest.fixture
def clean_dataset(tmp_path: Path) -> Path:
    """A valid YOLO dataset with real images and no ERROR-level problems.

    Contains one labeled image and one background image (empty label), so the
    only finding is an empty-image WARNING — handy for exit-code tests.
    """
    root = tmp_path / "clean"
    _write(root / "data.yaml", "names:\n  0: cat\ntrain: images/train\n")
    _write_png(root / "images" / "train" / "labeled.png")
    _write(root / "labels" / "train" / "labeled.txt", "0 0.5 0.5 0.2 0.2\n")
    _write_png(root / "images" / "train" / "background.png")
    _write(root / "labels" / "train" / "background.txt", "")
    return root


@pytest.fixture
def corrupt_only_dataset(tmp_path: Path) -> Path:
    """A YOLO dataset whose only ERROR is one corrupt image."""
    root = tmp_path / "corrupt_only"
    _write(root / "data.yaml", "names:\n  0: cat\ntrain: images/train\n")
    _write_png(root / "images" / "train" / "valid.png")
    _write(root / "labels" / "train" / "valid.txt", "0 0.5 0.5 0.2 0.2\n")
    _write_corrupt(root / "images" / "train" / "corrupt.png")
    _write(root / "labels" / "train" / "corrupt.txt", "0 0.5 0.5 0.2 0.2\n")
    return root


@pytest.fixture
def coco_json_file(tmp_path: Path) -> Path:
    """A single COCO instances JSON file (no split in the name)."""
    data = {
        "images": [{"id": 1, "file_name": "a.jpg", "width": 200, "height": 100}],
        "annotations": [{"id": 1, "image_id": 1, "category_id": 5, "bbox": [20, 10, 40, 20]}],
        "categories": [{"id": 5, "name": "bicycle"}],
    }
    path = tmp_path / "instances.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
