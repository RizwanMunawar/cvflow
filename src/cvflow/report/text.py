"""Human-friendly plain-text report.

Renders a dataset overview, a health summary (ERROR/WARNING/INFO counts), and a
prioritized list of findings. Each finding shows *what / why / where / evidence
/ suggestion*, matching CVFlow's philosophy of explaining rather than decreeing.

Kept dependency-free (plain strings) so it works everywhere; richer output can
be layered on later without changing callers.
"""

from __future__ import annotations

from collections import Counter

from cvflow.model import Dataset, Issue, Severity

_RULE = "─" * 52
_SEVERITY_ORDER = (Severity.ERROR, Severity.WARNING, Severity.INFO)


def render_report(dataset: Dataset, issues: list[Issue], *, max_details: int = 15) -> str:
    """Render a full text report for a dataset and its findings."""
    lines: list[str] = []
    lines.extend(_overview(dataset))
    lines.append("")
    lines.extend(_health_summary(issues))
    lines.append("")
    lines.extend(_priorities(issues))
    if issues:
        lines.append("")
        lines.extend(_by_type(issues))
        lines.append("")
        lines.extend(_details(issues, max_details))
    return "\n".join(lines)


def _overview(dataset: Dataset) -> list[str]:
    splits = ", ".join(dataset.splits) if dataset.splits else "—"
    return [
        "CVFlow Dataset Health",
        _RULE,
        f"{'Format':<16}{dataset.format.upper()}",
        f"{'Images':<16}{dataset.num_images:,}",
        f"{'Annotations':<16}{dataset.num_annotations:,}",
        f"{'Classes':<16}{dataset.num_classes:,}",
        f"{'Splits':<16}{splits}",
    ]


def _counts_by_severity(issues: list[Issue]) -> Counter[Severity]:
    return Counter(issue.severity for issue in issues)


def _health_summary(issues: list[Issue]) -> list[str]:
    counts = _counts_by_severity(issues)
    lines = ["Health Summary", _RULE]
    for severity in _SEVERITY_ORDER:
        lines.append(f"{severity.label:<10}{counts.get(severity, 0):>4}")
    return lines


def _priorities(issues: list[Issue], top: int = 5) -> list[str]:
    lines = ["Most Important Problems", _RULE]
    ranked = [i for i in issues if i.severity is not Severity.INFO][:top]
    if not ranked:
        lines.append("No blocking problems detected. 🎉")
        return lines
    for n, issue in enumerate(ranked, start=1):
        lines.append(f"{n}. [{issue.severity.label}] {issue.message}")
    return lines


def _by_type(issues: list[Issue]) -> list[str]:
    """Aggregate counts per issue code, most severe / most frequent first."""
    lines = ["Findings by Type", _RULE]
    # Track count and worst severity per code.
    counts: Counter[str] = Counter(issue.code for issue in issues)
    worst: dict[str, Severity] = {}
    for issue in issues:
        current = worst.get(issue.code)
        if current is None or issue.severity > current:
            worst[issue.code] = issue.severity
    for code, count in sorted(counts.items(), key=lambda kv: (-worst[kv[0]].rank, -kv[1])):
        lines.append(f"{worst[code].label:<8}{count:>5}  {code}")
    return lines


def _details(issues: list[Issue], max_details: int) -> list[str]:
    lines = ["Details", _RULE]
    shown = issues[:max_details]
    for issue in shown:
        lines.append(f"[{issue.severity.label}] {issue.code}: {issue.message}")
        if issue.why:
            lines.append(f"    Why:   {issue.why}")
        if issue.location is not None:
            lines.append(f"    Where: {issue.location.describe()}")
        if issue.suggestion:
            lines.append(f"    Next:  {issue.suggestion}")
        lines.append("")
    remaining = len(issues) - len(shown)
    if remaining > 0:
        lines.append(f"… and {remaining} more finding(s). ")
    return lines
