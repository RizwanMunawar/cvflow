"""Loader registry and the top-level ``load_dataset`` entry point.

The registry is the seam that keeps format support pluggable: register a
:class:`~cvflow.loaders.base.DatasetLoader`, and both explicit loading
(``fmt="yolo"``) and auto-detection pick it up with no other changes.
"""

from __future__ import annotations

from pathlib import Path

from cvflow.exceptions import UnsupportedFormatError
from cvflow.loaders.base import DatasetLoader
from cvflow.loaders.coco import CocoLoader
from cvflow.loaders.yolo import YoloLoader
from cvflow.model import Dataset

# Order matters for auto-detection: COCO's JSON signature is more specific, so
# it is checked before YOLO's broader directory heuristics.
_LOADERS: tuple[DatasetLoader, ...] = (CocoLoader(), YoloLoader())


def available_formats() -> list[str]:
    """Return the list of registered format identifiers."""
    return [loader.format for loader in _LOADERS]


def _get_loader(fmt: str) -> DatasetLoader:
    for loader in _LOADERS:
        if loader.format == fmt:
            return loader
    raise UnsupportedFormatError(
        f"Unknown dataset format {fmt!r}. Available: {', '.join(available_formats())}."
    )


def detect_format(path: Path) -> str | None:
    """Auto-detect the dataset format at ``path``, or ``None`` if unrecognized."""
    for loader in _LOADERS:
        if loader.detect(path):
            return loader.format
    return None


def load_dataset(path: str | Path, fmt: str | None = None) -> Dataset:
    """Load a dataset from ``path`` into the normalized model.

    Args:
        path: Dataset root directory (or a COCO JSON file).
        fmt: Force a specific format. When ``None``, the format is auto-detected.

    Raises:
        UnsupportedFormatError: If ``path`` does not exist, or the format cannot
            be detected / is not supported.
        cvflow.exceptions.DatasetError: If detected but the dataset fails to load.
    """
    path = Path(path)
    if not path.exists():
        raise UnsupportedFormatError(f"Dataset path does not exist: {path}")

    if fmt is not None:
        return _get_loader(fmt).load(path)

    detected = detect_format(path)
    if detected is None:
        raise UnsupportedFormatError(
            f"Could not detect a supported dataset format at: {path}. "
            f"Supported formats: {', '.join(available_formats())}. "
            f"Try specifying the format explicitly."
        )
    return _get_loader(detected).load(path)
