"""Reporting.

Turns a collection of :class:`cvflow.model.Issue` findings into
human-friendly, prioritized output (and, later, machine-readable formats).
Reporting is deliberately separate from analysis so new output formats can be
added without touching the rules that produced the findings.

Concrete reporters are introduced in later batches (M5 onward).
"""

from __future__ import annotations

__all__: list[str] = []
