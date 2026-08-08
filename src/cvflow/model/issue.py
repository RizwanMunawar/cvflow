"""The :class:`Issue` — CVFlow's unit of feedback.

Every check in the analysis engine, whatever it inspects, reports its findings
as :class:`Issue` values. This uniformity is what lets reporting, sorting, and
visualization stay independent of the individual rules.

The product philosophy is baked into the shape of the type: don't just say
something is *wrong*, explain *why* it was flagged, *where*, how severe it is,
the *evidence*, and a *suggested next action*. Those fields are first-class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cvflow.model.severity import Severity


@dataclass(frozen=True)
class Location:
    """Where a finding was detected.

    All fields are optional so the same type works for image-level,
    annotation-level, and dataset-level findings.
    """

    path: str | None = None
    """Filesystem path to the relevant image or annotation file."""

    split: str | None = None
    """Dataset split, e.g. ``"train"``, ``"val"``, ``"test"``."""

    annotation_index: int | None = None
    """Index of the offending annotation within its file, when applicable."""

    def describe(self) -> str:
        """Human-readable one-line description of the location."""
        parts: list[str] = []
        if self.split:
            parts.append(f"[{self.split}]")
        if self.path:
            parts.append(self.path)
        if self.annotation_index is not None:
            parts.append(f"(annotation #{self.annotation_index})")
        return " ".join(parts) if parts else "<dataset>"


@dataclass(frozen=True)
class Issue:
    """A single finding produced by the analysis engine.

    Attributes:
        code: Stable machine-readable identifier, e.g. ``"corrupt-image"``.
            Enables filtering, suppression, and documentation lookups.
        severity: :class:`Severity` of the finding.
        message: Short, human-friendly summary of *what* was detected.
        why: Explanation of *why* this was flagged (the reasoning/heuristic).
        location: *Where* it was detected. Optional for dataset-wide findings.
        evidence: Structured metrics backing the finding (e.g. similarity
            scores, box coordinates, counts). Kept as plain data so reports and
            machine-readable exports can render it however they like.
        suggestion: Recommended next action, phrased as guidance not a command.
    """

    code: str
    severity: Severity
    message: str
    why: str | None = None
    location: Location | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    suggestion: str | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("Issue.code must be a non-empty identifier")
        if not self.message:
            raise ValueError("Issue.message must be a non-empty string")

    def sort_key(self) -> tuple[int, str]:
        """Sort key that orders most-severe-first, then by code for stability."""
        return (-self.severity.rank, self.code)
