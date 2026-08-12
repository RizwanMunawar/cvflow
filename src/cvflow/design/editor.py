"""Reading and writing annotations from the served dashboard.

The static HTML file is a report; the *served* dashboard can do one more thing —
open the actual image, draw its boxes, and write corrections back to disk. That
is what this module backs.

Two rules keep it safe to run on a laptop:

- **Nothing outside the dataset.** Every path from the browser is resolved and
  then checked to be inside the dataset root; anything else is refused. There is
  no directory listing and no arbitrary file read.
- **Only YOLO is written.** YOLO labels are one small text file per image, so a
  rewrite is contained and reversible. COCO keeps its annotations in a shared
  JSON that other tooling also owns, so it stays read-only for now and the UI
  says so rather than silently doing nothing.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from cvflow.analysis.paths import resolve_image_path
from cvflow.model import BoundingBox, Dataset, ImageItem

#: Written back with this many decimals — enough for pixel-accurate boxes on an
#: 8K image, short enough to keep label files readable in a diff.
_PRECISION = 6


class EditorError(Exception):
    """A request the editor refuses: unknown image, outside the root, or unsupported."""


class Editor:
    """Image and annotation access for one loaded dataset."""

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset
        self.root = Path(dataset.root).resolve()
        #: Only plain YOLO detection labels round-trip. Polygons and oriented
        #: boxes are held as their axis-aligned extent, so writing them back
        #: would silently flatten the real annotation — those open read-only.
        self.writable = dataset.format == "yolo" and dataset.task == "detect"
        self._index = {self._key(item.path): item for item in dataset.images}

    # -- lookup ------------------------------------------------------------ #

    @staticmethod
    def _key(path: str) -> str:
        """Normalize a path for matching, so `\\` and `/` agree."""
        return str(path).replace("\\", "/").lower()

    def info(self) -> dict[str, Any]:
        """What the browser needs to decide which controls to offer."""
        return {
            "enabled": True,
            "writable": self.writable,
            "format": self.dataset.format,
            "task": self.dataset.task,
            "classes": {str(k): v for k, v in self.dataset.class_names.items()},
        }

    def _item(self, path: str) -> ImageItem:
        item = self._index.get(self._key(path))
        if item is None:
            raise EditorError(f"not part of this dataset: {path}")
        return item

    def _inside_root(self, path: Path) -> Path:
        resolved = path.resolve()
        if self.root not in resolved.parents and resolved != self.root:
            raise EditorError("path is outside the dataset root")
        return resolved

    def image_file(self, path: str) -> Path:
        """Resolve an image path from the browser to a real file inside the root."""
        item = self._item(path)
        found = resolve_image_path(self.dataset.root, item)
        if found is None or not found.is_file():
            raise EditorError(f"image file not found on disk: {path}")
        return self._inside_root(found)

    # -- read -------------------------------------------------------------- #

    def image_bytes(self, path: str) -> tuple[bytes, str]:
        """Image bytes plus a content type, for ``GET /api/image``."""
        found = self.image_file(path)
        content_type = mimetypes.guess_type(found.name)[0] or "application/octet-stream"
        return found.read_bytes(), content_type

    def annotations(self, path: str) -> dict[str, Any]:
        """Boxes for one image, in the same normalized form the model uses."""
        item = self._item(path)
        return {
            "path": item.path,
            "split": item.split,
            "format": self.dataset.format,
            "writable": self.writable,
            "task": self.dataset.task,
            # The real geometry travels too: the viewer draws a polygon as a
            # polygon and an oriented box at its true angle, rather than
            # redrawing every task as an axis-aligned rectangle.
            "boxes": [
                {
                    "class_id": box.class_id,
                    "x_min": box.x_min,
                    "y_min": box.y_min,
                    "x_max": box.x_max,
                    "y_max": box.y_max,
                    "points": [list(point) for point in box.points] if box.points else None,
                }
                for box in item.boxes
            ],
        }

    # -- write -------------------------------------------------------------- #

    def save(self, path: str, boxes: list[dict[str, Any]]) -> str:
        """Write edited boxes back to the image's YOLO label file.

        Returns the path written, relative to the dataset root when possible.
        Updates the in-memory dataset too, so the dashboard and any later save
        agree with what is now on disk.
        """
        if not self.writable:
            reason = (
                f"{self.dataset.task} labels hold more than a box"
                if self.dataset.format == "yolo"
                else f"{self.dataset.format} annotations"
            )
            raise EditorError(f"read-only: {reason}, so CVFlow will not rewrite them")

        item = self._item(path)
        parsed = [_to_box(raw) for raw in boxes]
        target = self._label_target(item)
        target.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        for box in parsed:
            cx = (box.x_min + box.x_max) / 2
            cy = (box.y_min + box.y_max) / 2
            width = box.x_max - box.x_min
            height = box.y_max - box.y_min
            lines.append(
                f"{box.class_id} {cx:.{_PRECISION}f} {cy:.{_PRECISION}f} "
                f"{width:.{_PRECISION}f} {height:.{_PRECISION}f}"
            )
        target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        item.boxes = parsed
        item.label_path = str(target)
        try:
            return str(target.relative_to(self.root))
        except ValueError:  # pragma: no cover - label dir outside root is rejected above
            return str(target)

    def _label_target(self, item: ImageItem) -> Path:
        """Where this image's labels live, creating the path if it has none yet."""
        if item.label_path:
            return self._inside_root(Path(item.label_path))
        image = self.image_file(item.path)
        parts = list(image.parts)
        for index in range(len(parts) - 1, -1, -1):
            if parts[index] == "images":
                parts[index] = "labels"
                break
        return self._inside_root(Path(*parts).with_suffix(".txt"))


def _to_box(raw: dict[str, Any]) -> BoundingBox:
    """Validate one box from the browser into a :class:`BoundingBox`.

    Coordinates are clamped to the frame and ordered, so a box dragged past an
    edge or backwards still lands as valid data rather than a new finding.
    """
    try:
        class_id = int(raw["class_id"])
        values = [
            float(raw["x_min"]),
            float(raw["y_min"]),
            float(raw["x_max"]),
            float(raw["y_max"]),
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise EditorError(f"malformed box: {raw!r}") from exc

    x_min, y_min, x_max, y_max = (min(max(v, 0.0), 1.0) for v in values)
    if x_min > x_max:
        x_min, x_max = x_max, x_min
    if y_min > y_max:
        y_min, y_max = y_max, y_min
    if x_max - x_min <= 0 or y_max - y_min <= 0:
        raise EditorError("a box with zero width or height cannot be saved")
    return BoundingBox(class_id=class_id, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)
