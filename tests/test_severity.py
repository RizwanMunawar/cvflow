"""Tests for the Severity primitive."""

from __future__ import annotations

import pytest

from cvflow.model import Severity


def test_ordering_is_by_seriousness() -> None:
    assert Severity.ERROR > Severity.WARNING > Severity.INFO
    assert Severity.INFO < Severity.ERROR
    assert Severity.WARNING <= Severity.WARNING


def test_rank_is_monotonic() -> None:
    ranks = [Severity.INFO.rank, Severity.WARNING.rank, Severity.ERROR.rank]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == 3


def test_labels_and_str() -> None:
    assert Severity.ERROR.label == "ERROR"
    assert str(Severity.WARNING) == "WARNING"


def test_sorting_most_severe_first() -> None:
    mixed = [Severity.INFO, Severity.ERROR, Severity.WARNING]
    most_severe_first = sorted(mixed, reverse=True)
    assert most_severe_first == [Severity.ERROR, Severity.WARNING, Severity.INFO]


def test_comparison_with_non_severity_raises() -> None:
    # Rich comparisons return NotImplemented for other types, which Python
    # surfaces as a TypeError rather than a silently wrong answer.
    for op in ("__lt__", "__le__", "__gt__", "__ge__"):
        assert getattr(Severity.ERROR, op)(1) is NotImplemented
    with pytest.raises(TypeError):
        _ = Severity.ERROR < 1
