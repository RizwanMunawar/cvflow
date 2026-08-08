"""Tests for the text reporter."""

from __future__ import annotations

from cvflow.model import Dataset, ImageItem, Issue, Location, Severity
from cvflow.report import render_report


def _dataset() -> Dataset:
    return Dataset(
        name="d",
        root="/tmp/d",
        format="yolo",
        images=[ImageItem(path="a.jpg", split="train")],
        class_names={0: "cat"},
    )


def test_report_includes_overview_and_health() -> None:
    issues = [
        Issue(code="corrupt-image", severity=Severity.ERROR, message="corrupt", why="bad bytes"),
        Issue(code="empty-image", severity=Severity.WARNING, message="empty"),
        Issue(code="note", severity=Severity.INFO, message="fyi"),
    ]
    report = render_report(_dataset(), issues)
    assert "CVFlow Dataset Health" in report
    assert "Health Summary" in report
    assert "ERROR" in report
    assert "Most Important Problems" in report
    # INFO items are excluded from the priority list.
    assert "1. [ERROR] corrupt" in report


def test_report_clean_dataset() -> None:
    report = render_report(_dataset(), [])
    assert "No blocking problems detected" in report


def test_report_renders_location_and_suggestion() -> None:
    issues = [
        Issue(
            code="broken-image-path",
            severity=Severity.ERROR,
            message="missing",
            why="not on disk",
            location=Location(path="train/a.jpg", split="train"),
            suggestion="restore it",
        )
    ]
    report = render_report(_dataset(), issues)
    assert "train/a.jpg" in report
    assert "restore it" in report
