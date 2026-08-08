"""Tests for the Issue and Location primitives."""

from __future__ import annotations

import dataclasses

import pytest

from cvflow.model import Issue, Location, Severity


def test_minimal_issue() -> None:
    issue = Issue(code="corrupt-image", severity=Severity.ERROR, message="unreadable image")
    assert issue.code == "corrupt-image"
    assert issue.severity is Severity.ERROR
    assert issue.evidence == {}
    assert issue.location is None


def test_full_issue_carries_context() -> None:
    issue = Issue(
        code="potential-duplicate",
        severity=Severity.WARNING,
        message="Potential duplicate images detected.",
        why="Two images have a perceptual similarity of 98.7%.",
        location=Location(path="train/image_1832.jpg", split="train"),
        evidence={"similarity": 0.987, "peer": "train/image_9281.jpg"},
        suggestion="Review these images and remove one if they are the same sample.",
    )
    assert issue.evidence["similarity"] == pytest.approx(0.987)
    assert issue.why is not None
    assert issue.suggestion is not None


def test_empty_code_rejected() -> None:
    with pytest.raises(ValueError):
        Issue(code="", severity=Severity.INFO, message="x")


def test_empty_message_rejected() -> None:
    with pytest.raises(ValueError):
        Issue(code="x", severity=Severity.INFO, message="")


def test_sort_key_orders_by_severity_then_code() -> None:
    issues = [
        Issue(code="b-info", severity=Severity.INFO, message="i"),
        Issue(code="a-error", severity=Severity.ERROR, message="e"),
        Issue(code="c-error", severity=Severity.ERROR, message="e2"),
        Issue(code="a-warning", severity=Severity.WARNING, message="w"),
    ]
    ordered = sorted(issues, key=Issue.sort_key)
    assert [i.code for i in ordered] == ["a-error", "c-error", "a-warning", "b-info"]


def test_location_describe() -> None:
    assert Location().describe() == "<dataset>"
    loc = Location(path="val/img.jpg", split="val", annotation_index=3)
    described = loc.describe()
    assert "[val]" in described
    assert "val/img.jpg" in described
    assert "annotation #3" in described


def test_issue_is_frozen() -> None:
    issue = Issue(code="x", severity=Severity.INFO, message="m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        issue.code = "y"  # type: ignore[misc]
