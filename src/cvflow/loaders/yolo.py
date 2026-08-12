"""YOLO dataset loader.

Supports the two layouts seen in the wild:

1. **Ultralytics ``data.yaml``** — a YAML file describing ``names`` and the
   ``train``/``val``/``test`` image locations (optionally under a ``path`` root).
2. **``images/`` + ``labels/`` convention** — sibling directories, optionally
   split into ``train``/``val``/``test`` subdirectories, with class names taken
   from ``classes.txt`` (or inferred from the label files).

Label files contain one annotation per line: ``class_id cx cy w h`` with all
box values normalized to ``[0, 1]``. Malformed lines are skipped by the loader;
reporting invalid annotation files is the integrity engine's job.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from cvflow.exceptions import DatasetError
from cvflow.loaders.base import IMAGE_EXTENSIONS, DatasetLoader
from cvflow.model import BoundingBox, Dataset, ImageItem

_SPLIT_KEYS = ("train", "val", "test")


class YoloLoader(DatasetLoader):
    """Loader for YOLO-format datasets."""

    format = "yolo"

    def detect(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        if self._find_data_yaml(path) is not None:
            return True
        # images/ + labels/ convention (either flat or split into subdirs).
        return (path / "images").is_dir() and (path / "labels").is_dir()

    def load(self, path: Path) -> Dataset:
        if not path.is_dir():
            raise DatasetError(f"YOLO dataset path is not a directory: {path}")

        yaml_path = self._find_data_yaml(path)
        if yaml_path is not None:
            return self._load_from_yaml(path, yaml_path)
        if (path / "images").is_dir() and (path / "labels").is_dir():
            return self._load_from_convention(path)
        raise DatasetError(
            f"Not a recognizable YOLO dataset (no data.yaml and no images/+labels/): {path}"
        )

    # -- data.yaml layout ---------------------------------------------------
    @staticmethod
    def _find_data_yaml(path: Path) -> Path | None:
        for name in ("data.yaml", "data.yml", "dataset.yaml", "dataset.yml"):
            candidate = path / name
            if candidate.is_file():
                return candidate
        return None

    def _load_from_yaml(self, root: Path, yaml_path: Path) -> Dataset:
        with yaml_path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}

        class_names = _parse_names(data.get("names"))

        base = _resolve_base(yaml_path, data)

        images: list[ImageItem] = []
        tasks: set[str] = set()
        for split in _SPLIT_KEYS:
            entry = data.get(split)
            if not entry:
                continue
            for images_dir in _resolve_split_dirs(base, entry):
                images.extend(_load_split_images(images_dir, split, tasks))

        return Dataset(
            name=root.name,
            root=str(root.resolve()),
            format=self.format,
            task=resolve_task(tasks),
            images=images,
            class_names=class_names or _infer_class_names(images),
        )

    # -- images/ + labels/ convention --------------------------------------
    def _load_from_convention(self, root: Path) -> Dataset:
        images_root = root / "images"
        class_names = _parse_classes_txt(root)

        images: list[ImageItem] = []
        tasks: set[str] = set()
        subsplits = [d for d in images_root.iterdir() if d.is_dir()] if images_root.is_dir() else []
        split_dirs = {d.name: d for d in subsplits if d.name in _SPLIT_KEYS}

        if split_dirs:
            for split, images_dir in sorted(split_dirs.items()):
                images.extend(_load_split_images(images_dir, split, tasks))
        else:
            images.extend(_load_split_images(images_root, None, tasks))

        return Dataset(
            name=root.name,
            root=str(root.resolve()),
            format=self.format,
            task=resolve_task(tasks),
            images=images,
            class_names=class_names or _infer_class_names(images),
        )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _parse_names(names: Any) -> dict[int, str]:
    """Parse YOLO ``names`` which may be a list or an ``{id: name}`` mapping."""
    if isinstance(names, dict):
        result: dict[int, str] = {}
        for key, value in names.items():
            try:
                result[int(key)] = str(value)
            except (TypeError, ValueError):
                continue
        return result
    if isinstance(names, list):
        return {i: str(v) for i, v in enumerate(names)}
    return {}


def _parse_classes_txt(root: Path) -> dict[int, str]:
    for name in ("classes.txt", "classes.names"):
        candidate = root / name
        if candidate.is_file():
            lines = [ln.strip() for ln in candidate.read_text(encoding="utf-8").splitlines()]
            return {i: ln for i, ln in enumerate(lines) if ln}
    return {}


def _infer_class_names(images: list[ImageItem]) -> dict[int, str]:
    """Fallback: derive placeholder names from the class ids actually present."""
    ids = {box.class_id for img in images for box in img.boxes}
    return {cid: str(cid) for cid in sorted(ids)}


def _resolve_split_dirs(base: Path, entry: Any) -> list[Path]:
    """Resolve a YOLO split entry (str or list) into image directories.

    Supports directory entries. ``.txt`` list-file entries are resolved to the
    directory that contains them (a reasonable approximation for the MVP).
    """
    entries = entry if isinstance(entry, list) else [entry]
    dirs: list[Path] = []
    for item in entries:
        if not isinstance(item, str):
            continue
        resolved = (base / item).resolve()
        if resolved.is_dir():
            dirs.append(resolved)
        elif resolved.suffix.lower() == ".txt" and resolved.is_file():
            dirs.append(resolved.parent)
    return dirs


def _resolve_base(yaml_path: Path, data: dict[str, Any]) -> Path:
    """Work out which directory the split paths are relative to.

    Ultralytics dataset YAMLs carry a ``path:`` naming the dataset folder as it
    is *downloaded* (``path: construction-ppe``), while the file itself usually
    ships **inside** that folder. Joining blindly then points at
    ``construction-ppe/construction-ppe`` and every split resolves to nothing,
    which is silent: the load succeeds with zero images.

    So the candidates are tried in order and the first one whose split entries
    actually exist on disk wins. The yaml's own directory is both a candidate
    and the fallback, because that is where a self-contained dataset lives.
    """
    candidates: list[Path] = []
    raw = data.get("path")
    if isinstance(raw, str) and raw.strip():
        declared = Path(raw.strip())
        if declared.is_absolute():
            candidates.append(declared)
        else:
            candidates.append(yaml_path.parent / declared)
            # `path` may also name this very folder, or a sibling of it.
            candidates.append(yaml_path.parent.parent / declared)
    candidates.append(yaml_path.parent)

    entries = [data.get(split) for split in _SPLIT_KEYS]
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if any(_resolve_split_dirs(candidate, entry) for entry in entries if entry):
            return candidate
    return yaml_path.parent


def _label_path_for(image_path: Path) -> Path:
    """Map an image path to its YOLO label path (images/→labels/, ext→.txt)."""
    parts = list(image_path.parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "images":
            parts[i] = "labels"
            break
    return Path(*parts).with_suffix(".txt")


def _load_split_images(
    images_dir: Path, split: str | None, tasks: set[str] | None = None
) -> list[ImageItem]:
    if not images_dir.is_dir():
        return []
    items: list[ImageItem] = []
    for image_path in sorted(images_dir.rglob("*")):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        label_path = _label_path_for(image_path)
        boxes: list[BoundingBox] = []
        if label_path.is_file():
            boxes, found = _parse_label_file(label_path)
            if tasks is not None:
                tasks |= found
        items.append(
            ImageItem(
                path=str(image_path),
                split=split,
                boxes=boxes,
                label_path=str(label_path) if label_path.is_file() else None,
            )
        )
    return items


def _parse_label_file(label_path: Path) -> tuple[list[BoundingBox], set[str]]:
    """Parse one YOLO label file into boxes, and note which task wrote it.

    One text format serves three tasks, told apart by how many numbers follow
    the class id:

    - **4** ``cx cy w h`` -> detection.
    - **8** four ``x y`` corners -> oriented boxes (OBB).
    - **6 or more, even** -> a segmentation polygon.

    Polygons and oriented boxes are reduced to their axis-aligned extent so
    every check downstream keeps working on one geometry. (Exactly eight
    numbers is read as OBB; a four-point segmentation polygon is
    indistinguishable from one on disk, and the extent is identical either way.)
    """
    boxes: list[BoundingBox] = []
    tasks: set[str] = set()
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue  # blank or malformed; integrity checks report invalid files
        try:
            class_id = int(float(parts[0]))
            values = [float(value) for value in parts[1:]]
        except ValueError:
            continue

        if len(values) == 4:
            tasks.add("detect")
            boxes.append(BoundingBox.from_yolo(class_id, *values))
        elif len(values) == 8:
            tasks.add("obb")
            boxes.append(_bounds_of(class_id, values))
        elif len(values) >= 6 and len(values) % 2 == 0:
            tasks.add("segment")
            boxes.append(_bounds_of(class_id, values))
    return boxes, tasks


def _bounds_of(class_id: int, values: list[float]) -> BoundingBox:
    """A polygon or oriented box: its extent, keeping the real shape.

    The extent is what every existing check reads; the points are what the
    mask- and rotation-aware checks (and the dashboard's viewer) need, so the
    original annotation is never thrown away.
    """
    xs = values[0::2]
    ys = values[1::2]
    return BoundingBox(
        class_id=class_id,
        x_min=min(xs),
        y_min=min(ys),
        x_max=max(xs),
        y_max=max(ys),
        points=tuple(zip(xs, ys)),
    )


def resolve_task(tasks: set[str]) -> str:
    """Collapse the per-file task hints into one label for the dataset.

    A dataset mixing formats is described by its richest one, because that is
    what a consumer has to be able to read.
    """
    for task in ("segment", "obb"):
        if task in tasks:
            return task
    return "detect"
