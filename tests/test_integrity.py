"""Tests for the integrity checks."""

from __future__ import annotations

from pathlib import Path

from cvflow.analysis import AnalysisEngine, CheckConfig, default_checks
from cvflow.analysis.integrity import (
    DuplicateFilenameCheck,
    EmptyAnnotationCheck,
    InvalidClassIdCheck,
    InvalidImageDimensionCheck,
)
from cvflow.loaders import load_dataset
from cvflow.model import BoundingBox, Dataset, ImageItem, Issue, Severity


def _codes(issues: list[Issue]) -> set[str]:
    return {i.code for i in issues}


def test_integrity_end_to_end(integrity_dataset: Path) -> None:
    dataset = load_dataset(integrity_dataset)
    issues = AnalysisEngine(default_checks()).run(dataset)
    codes = _codes(issues)
    assert "corrupt-image" in codes
    assert "duplicate-filename" in codes
    assert "invalid-class-id" in codes
    assert "empty-image" in codes
    assert "invalid-annotation-file" in codes


def test_no_images_config_skips_corrupt_check(integrity_dataset: Path) -> None:
    dataset = load_dataset(integrity_dataset)
    issues = AnalysisEngine(default_checks(CheckConfig(check_images=False))).run(dataset)
    assert "corrupt-image" not in _codes(issues)
    # Non-image checks still run.
    assert "invalid-class-id" in _codes(issues)


def test_corrupt_image_is_error(integrity_dataset: Path) -> None:
    dataset = load_dataset(integrity_dataset)
    issues = AnalysisEngine(default_checks()).run(dataset)
    corrupt = next(i for i in issues if i.code == "corrupt-image")
    assert corrupt.severity is Severity.ERROR
    assert corrupt.location is not None
    assert corrupt.suggestion


def _make_dataset(images: list[ImageItem], class_names: dict[int, str]) -> Dataset:
    return Dataset(name="d", root="/tmp/d", format="yolo", images=images, class_names=class_names)


def test_duplicate_filename_check() -> None:
    ds = _make_dataset(
        [ImageItem(path="a/img.jpg"), ImageItem(path="b/img.jpg"), ImageItem(path="c/other.jpg")],
        {},
    )
    issues = list(DuplicateFilenameCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].evidence["count"] == 2
    assert issues[0].severity is Severity.WARNING


def test_invalid_class_id_severity() -> None:
    ds = _make_dataset(
        [
            ImageItem(path="a.jpg", boxes=[BoundingBox(5, 0, 0, 1, 1)]),
            ImageItem(path="b.jpg", boxes=[BoundingBox(-1, 0, 0, 1, 1)]),
        ],
        {0: "cat", 1: "dog"},
    )
    issues = list(InvalidClassIdCheck().run(ds))
    by_id = {i.evidence["class_id"]: i for i in issues}
    assert by_id[5].severity is Severity.WARNING  # unknown but non-negative
    assert by_id[-1].severity is Severity.ERROR  # negative is objectively invalid


def test_invalid_class_id_skipped_without_class_map() -> None:
    ds = _make_dataset([ImageItem(path="a.jpg", boxes=[BoundingBox(99, 0, 0, 1, 1)])], {})
    assert list(InvalidClassIdCheck().run(ds)) == []


def test_empty_annotation_check() -> None:
    ds = _make_dataset(
        [ImageItem(path="a.jpg"), ImageItem(path="b.jpg", boxes=[BoundingBox(0, 0, 0, 1, 1)])],
        {0: "cat"},
    )
    issues = list(EmptyAnnotationCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].evidence["count"] == 1


def test_invalid_image_dimension_check() -> None:
    ds = _make_dataset(
        [
            ImageItem(path="a.jpg", width=0, height=100),
            ImageItem(path="b.jpg", width=50, height=50),
        ],
        {},
    )
    issues = list(InvalidImageDimensionCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].severity is Severity.ERROR


def test_coco_images_not_found_is_info(coco_dir_dataset: Path) -> None:
    # COCO ships annotations only; images can't be located -> single INFO note.
    dataset = load_dataset(coco_dir_dataset)
    issues = AnalysisEngine(default_checks()).run(dataset)
    codes = _codes(issues)
    assert "images-not-found" in codes
    assert "corrupt-image" not in codes
    assert "broken-image-path" not in codes
