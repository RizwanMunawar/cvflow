"""Issue severity levels.

CVFlow deliberately distinguishes objective problems from things that merely
*look* suspicious. Every finding carries one of three severities so developers
can triage quickly and decide for themselves what to act on.
"""

from __future__ import annotations

from enum import Enum


class Severity(Enum):
    """How serious a detected finding is.

    - :attr:`ERROR`   — objectively invalid; the dataset is broken here.
    - :attr:`WARNING` — potentially problematic; worth reviewing.
    - :attr:`INFO`    — a useful observation, not necessarily a problem.

    Members are ordered by seriousness, so they sort and compare naturally
    (``Severity.ERROR > Severity.WARNING``). The integer ``rank`` is a stable,
    machine-friendly value suitable for sorting and prioritizing reports.
    """

    INFO = 0
    WARNING = 1
    ERROR = 2

    @property
    def rank(self) -> int:
        """Numeric seriousness; higher means more severe."""
        return int(self.value)

    @property
    def label(self) -> str:
        """Uppercase display label, e.g. ``"ERROR"``."""
        return self.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank >= other.rank

    def __str__(self) -> str:
        return self.label
