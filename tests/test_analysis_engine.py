"""Tests for the analysis engine."""

from __future__ import annotations

from collections.abc import Iterable

from cvflow.analysis import AnalysisEngine, Check
from cvflow.model import Dataset, Issue, Severity


class _FixedCheck(Check):
    def __init__(self, issues: list[Issue]) -> None:
        self._issues = issues

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        return self._issues


def _dataset() -> Dataset:
    return Dataset(name="d", root="/tmp/d", format="yolo")


def test_engine_aggregates_and_sorts_by_severity() -> None:
    info = Issue(code="a-info", severity=Severity.INFO, message="i")
    error = Issue(code="z-error", severity=Severity.ERROR, message="e")
    warning = Issue(code="m-warn", severity=Severity.WARNING, message="w")
    engine = AnalysisEngine([_FixedCheck([info]), _FixedCheck([error, warning])])

    issues = engine.run(_dataset())

    assert [i.severity for i in issues] == [Severity.ERROR, Severity.WARNING, Severity.INFO]


def test_engine_with_no_checks_returns_empty() -> None:
    assert AnalysisEngine([]).run(_dataset()) == []


def test_engine_exposes_checks() -> None:
    check = _FixedCheck([])
    engine = AnalysisEngine([check])
    assert engine.checks == [check]
