"""Integrity checks — deterministic, structural dataset problems.

These answer the first question a developer has about an unfamiliar dataset:
*is anything actually broken?* They are conservative about severity: something
is only an ``ERROR`` when it is objectively invalid. Ambiguous situations (an
image with no labels, an unknown-but-plausible class id) are ``WARNING``s.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from cvflow.analysis.engine import Check, CheckConfig
from cvflow.analysis.paths import resolve_image_path
from cvflow.imaging import is_readable_image
from cvflow.model import Dataset, ImageItem, Issue, Location, Severity


class DuplicateFilenameCheck(Check):
    """Flags image file names that appear more than once in the dataset."""

    code = "integrity"

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        seen: dict[str, list[ImageItem]] = {}
        for item in dataset.images:
            seen.setdefault(Path(item.path).name, []).append(item)
        for name, items in seen.items():
            if len(items) < 2:
                continue
            yield Issue(
                code="duplicate-filename",
                severity=Severity.WARNING,
                message=f"Duplicate image filename '{name}' appears {len(items)} times.",
                why=(
                    "The same file name in multiple places often means images were "
                    "merged carelessly and can shadow one another in tooling."
                ),
                location=Location(path=name),
                evidence={
                    "count": len(items),
                    "paths": [it.path for it in items][:10],
                },
                suggestion="Confirm these are distinct images; rename or de-duplicate if not.",
            )


class InvalidClassIdCheck(Check):
    """Flags annotations whose class id is missing from the class map."""

    code = "integrity"

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if not dataset.class_names:
            return  # nothing to validate against
        known = set(dataset.class_names)
        for item, box in dataset.iter_boxes():
            if box.class_id in known:
                continue
            severity = Severity.ERROR if box.class_id < 0 else Severity.WARNING
            yield Issue(
                code="invalid-class-id",
                severity=severity,
                message=f"Annotation uses class id {box.class_id}, which is not defined.",
                why=(
                    "The class id is not present in the dataset's class map "
                    f"(defined ids: {sorted(known)})."
                ),
                location=Location(path=item.path, split=item.split),
                evidence={"class_id": box.class_id, "known_ids": sorted(known)},
                suggestion="Fix the label or add the class to the dataset definition.",
            )


class EmptyAnnotationCheck(Check):
    """Reports images that carry no annotations.

    Not necessarily an error — background/negative images are legitimate — so
    this is a single aggregated WARNING for the developer to sanity-check.
    """

    code = "integrity"

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        empty = [item for item in dataset.images if item.is_empty]
        if not empty:
            return
        yield Issue(
            code="empty-image",
            severity=Severity.WARNING,
            message=f"{len(empty)} image(s) have no annotations.",
            why=(
                "Images without labels may be intentional background samples, or "
                "they may be unlabeled data that was meant to be annotated."
            ),
            evidence={
                "count": len(empty),
                "examples": [item.path for item in empty][:10],
            },
            suggestion="Confirm these are intended as background images.",
        )


class InvalidImageDimensionCheck(Check):
    """Flags images whose recorded pixel dimensions are non-positive."""

    code = "integrity"

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        for item in dataset.images:
            bad_w = item.width is not None and item.width <= 0
            bad_h = item.height is not None and item.height <= 0
            if not (bad_w or bad_h):
                continue
            yield Issue(
                code="invalid-image-dimension",
                severity=Severity.ERROR,
                message=f"Image has invalid recorded dimensions ({item.width}x{item.height}).",
                why="Width and height must be positive; a non-positive value is invalid.",
                location=Location(path=item.path, split=item.split),
                evidence={"width": item.width, "height": item.height},
                suggestion="Re-export the annotations with correct image dimensions.",
            )


class InvalidAnnotationFileCheck(Check):
    """Flags YOLO label files that contain unparseable lines."""

    code = "integrity"

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        for item in dataset.images:
            if not item.label_path:
                continue
            label_path = Path(item.label_path)
            if not label_path.is_file():
                continue
            bad_lines = _malformed_label_lines(label_path)
            if not bad_lines:
                continue
            yield Issue(
                code="invalid-annotation-file",
                severity=Severity.ERROR,
                message=f"Annotation file has {len(bad_lines)} malformed line(s).",
                why="Each YOLO label line must be 'class_id cx cy w h' with numeric values.",
                location=Location(path=item.label_path, split=item.split),
                evidence={"line_numbers": bad_lines[:10]},
                suggestion="Repair or regenerate the annotation file.",
            )


class ImageFileCheck(Check):
    """Broken image paths and corrupt/unreadable image files.

    If *no* image can be located next to the annotations (common for COCO, where
    images ship separately), per-image file checks are skipped with a single
    INFO note rather than flooding false positives.
    """

    code = "integrity"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._config = config or CheckConfig()

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if not dataset.images:
            return

        resolved = {id(item): resolve_image_path(dataset.root, item) for item in dataset.images}
        found = [p for p in resolved.values() if p is not None]

        if not found:
            yield Issue(
                code="images-not-found",
                severity=Severity.INFO,
                message="No image files were found next to the annotations.",
                why=(
                    "Image files could not be located under the dataset root, so "
                    "file-level checks (broken paths, corrupt images) were skipped."
                ),
                evidence={"image_count": dataset.num_images, "root": dataset.root},
                suggestion=(
                    "Point CVFlow at a root that contains the image files to enable these checks."
                ),
            )
            return

        for item in dataset.images:
            path = resolved[id(item)]
            if path is None:
                yield Issue(
                    code="broken-image-path",
                    severity=Severity.ERROR,
                    message="Referenced image file does not exist.",
                    why="The annotations reference an image that is missing from disk.",
                    location=Location(path=item.path, split=item.split),
                    evidence={"path": item.path},
                    suggestion="Restore the image or remove the dangling annotation entry.",
                )
                continue

            if self._config.check_images and not is_readable_image(path):
                yield Issue(
                    code="corrupt-image",
                    severity=Severity.ERROR,
                    message="Image file is unreadable or corrupt.",
                    why=(
                        "The image could not be decoded; it is likely truncated "
                        "or not a valid image."
                    ),
                    location=Location(path=str(path), split=item.split),
                    evidence={"path": str(path)},
                    suggestion="Re-download or re-export this image.",
                )


def _malformed_label_lines(label_path: Path) -> list[int]:
    """Return the 1-based line numbers of malformed YOLO label lines."""
    bad: list[int] = []
    text = label_path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue  # blank lines are harmless
        parts = stripped.split()
        if len(parts) < 5:
            bad.append(lineno)
            continue
        try:
            int(float(parts[0]))
            [float(v) for v in parts[1:5]]
        except ValueError:
            bad.append(lineno)
    return bad


def integrity_checks(config: CheckConfig | None = None) -> list[Check]:
    """Return the default set of integrity checks."""
    return [
        ImageFileCheck(config),
        InvalidAnnotationFileCheck(),
        InvalidClassIdCheck(),
        InvalidImageDimensionCheck(),
        DuplicateFilenameCheck(),
        EmptyAnnotationCheck(),
    ]
