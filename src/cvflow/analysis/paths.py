"""Shared helpers for locating image files referenced by a dataset.

Different formats record image paths differently (YOLO stores absolute paths;
COCO stores bare file names), so checks that read image bytes need a common,
best-effort way to resolve an :class:`~cvflow.model.ImageItem` to a file on
disk. Extracted here so integrity and duplicate detection share one resolver.
"""

from __future__ import annotations

from pathlib import Path

from cvflow.model import Dataset, ImageItem


def resolve_image_path(root: str, item: ImageItem) -> Path | None:
    """Best-effort resolution of an image path to an existing file.

    Tries the raw path (absolute), then a few common layouts relative to the
    dataset root. Returns ``None`` when the file cannot be found.
    """
    raw = Path(item.path)
    if raw.is_absolute() and raw.is_file():
        return raw

    root_path = Path(root)
    candidates = [
        root_path / item.path,
        root_path / "images" / item.path,
    ]
    if item.split:
        candidates.append(root_path / "images" / item.split / Path(item.path).name)
        candidates.append(root_path / item.split / Path(item.path).name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return raw if raw.is_file() else None


def resolve_all(dataset: Dataset) -> dict[int, Path | None]:
    """Resolve every image in the dataset, keyed by ``id(item)``."""
    return {id(item): resolve_image_path(dataset.root, item) for item in dataset.images}
