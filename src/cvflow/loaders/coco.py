"""COCO dataset loader.

Supports:

- A single COCO instances JSON file (``instances_train2017.json``, etc.).
- A dataset directory containing an ``annotations/`` folder of such JSON files,
  or JSON files directly in the root — each file is treated as one split.

A COCO JSON has three relevant arrays: ``images`` (``id``, ``file_name``,
``width``, ``height``), ``annotations`` (``image_id``, ``category_id``,
``bbox`` as absolute ``[x, y, w, h]``), and ``categories`` (``id``, ``name``).
Absolute boxes are normalized using each image's dimensions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cvflow.exceptions import DatasetError
from cvflow.loaders.base import DatasetLoader
from cvflow.model import BoundingBox, Dataset, ImageItem

_COCO_KEYS = ("images", "annotations", "categories")


class CocoLoader(DatasetLoader):
    """Loader for COCO-format datasets."""

    format = "coco"

    def detect(self, path: Path) -> bool:
        if path.is_file():
            return path.suffix.lower() == ".json" and _looks_like_coco(path)
        if path.is_dir():
            return any(_looks_like_coco(p) for p in _candidate_json_files(path))
        return False

    def load(self, path: Path) -> Dataset:
        json_files = self._collect_json_files(path)
        if not json_files:
            raise DatasetError(f"No COCO annotation JSON found at: {path}")

        root = path if path.is_dir() else path.parent
        class_names: dict[int, str] = {}
        images: list[ImageItem] = []

        for json_path in json_files:
            split = _infer_split(json_path)
            split_images, split_classes = _load_coco_json(json_path, split)
            images.extend(split_images)
            class_names.update(split_classes)

        return Dataset(
            name=root.name,
            root=str(root.resolve()),
            format=self.format,
            images=images,
            class_names=class_names,
        )

    @staticmethod
    def _collect_json_files(path: Path) -> list[Path]:
        if path.is_file():
            return [path] if _looks_like_coco(path) else []
        return [p for p in _candidate_json_files(path) if _looks_like_coco(p)]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _candidate_json_files(directory: Path) -> list[Path]:
    """JSON files worth checking: an ``annotations/`` dir first, then the root."""
    candidates: list[Path] = []
    ann_dir = directory / "annotations"
    if ann_dir.is_dir():
        candidates.extend(sorted(ann_dir.glob("*.json")))
    candidates.extend(sorted(directory.glob("*.json")))
    return candidates


def _looks_like_coco(path: Path) -> bool:
    """Cheaply check whether a JSON file has the COCO top-level structure."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and all(k in data for k in _COCO_KEYS)


def _infer_split(json_path: Path) -> str | None:
    stem = json_path.stem.lower()
    for split in ("train", "val", "test"):
        if split in stem:
            return split
    return None


def _load_coco_json(json_path: Path, split: str | None) -> tuple[list[ImageItem], dict[int, str]]:
    with json_path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)

    class_names = {
        int(c["id"]): str(c.get("name", c["id"])) for c in data.get("categories", []) if "id" in c
    }

    # Group annotations by image id.
    anns_by_image: dict[int, list[dict[str, Any]]] = {}
    for ann in data.get("annotations", []):
        image_id = ann.get("image_id")
        if image_id is None or "bbox" not in ann:
            continue
        anns_by_image.setdefault(int(image_id), []).append(ann)

    images: list[ImageItem] = []
    for img in data.get("images", []):
        if "id" not in img:
            continue
        image_id = int(img["id"])
        width = int(img["width"]) if img.get("width") else None
        height = int(img["height"]) if img.get("height") else None
        boxes = _boxes_for_image(anns_by_image.get(image_id, []), width or 0, height or 0)
        images.append(
            ImageItem(
                path=str(img.get("file_name", f"image_{image_id}")),
                split=split,
                width=width,
                height=height,
                boxes=boxes,
                image_id=image_id,
            )
        )
    return images, class_names


def _boxes_for_image(
    annotations: list[dict[str, Any]], width: int, height: int
) -> list[BoundingBox]:
    boxes: list[BoundingBox] = []
    for ann in annotations:
        bbox = ann.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            continue
        try:
            x, y, w, h = (float(v) for v in bbox[:4])
            class_id = int(ann["category_id"])
        except (KeyError, TypeError, ValueError):
            continue
        boxes.append(BoundingBox.from_coco(class_id, x, y, w, h, width, height))
    return boxes
