"""The dashboard's data contract.

Turns a :class:`~cvflow.model.Dataset`, its findings, and (optionally) its
statistics into one plain, JSON-serializable dictionary. The HTML page is a dumb
renderer over this payload, so what the dashboard can show is decided here — in
Python, with types — rather than in the browser.

Everything is precomputed (bins, shares, sorted rankings) so the page never has
to reason about the dataset itself.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Any

from cvflow.model import Dataset, DatasetStatistics, Issue, Severity, Summary

#: Hard cap on the findings embedded in the page. Enough for any real dataset
#: while keeping the generated HTML a sane size; the overflow is reported.
MAX_ISSUES = 5000

#: Bucket edges (as a fraction of image area) for the box-size histogram.
_AREA_EDGES = (0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0)
#: Short axis label per bucket, and the full range used in tooltips and tables.
_AREA_LABELS = ("<0.1", "0.1", "0.5", "1", "5", "10", "25", ">50")
_AREA_RANGES = (
    "<0.1%",
    "0.1-0.5%",
    "0.5-1%",
    "1-5%",
    "5-10%",
    "10-25%",
    "25-50%",
    ">50%",
)

#: Box shape (width ÷ height) buckets, from tall through square to wide.
_SHAPE_EDGES = (0.25, 0.5, 0.8, 1.25, 2.0, 4.0)
_SHAPE_LABELS = ("<0.25", "0.25", "0.5", "0.8", "1.25", "2", ">4")
_SHAPE_RANGES = (
    "under 0.25 (very tall)",
    "0.25-0.5 (tall)",
    "0.5-0.8 (tall-ish)",
    "0.8-1.25 (square)",
    "1.25-2 (wide-ish)",
    "2-4 (wide)",
    "over 4 (very wide)",
)

#: Resolution of the box-center heatmap (cells per side).
_HEATMAP_GRID = 12

#: How many images the "most findings" chart lists.
_TOP_IMAGES = 10

# --------------------------------------------------------------------------- #
# Accuracy-impact heuristic
#
# A rough, transparent weighting of how much each class of problem typically
# costs a detector, so the dashboard can answer "what do I get for fixing
# this?". These are *estimates from published rules of thumb*, not measurements
# — CVFlow cannot know your model. The dashboard says so, and every input to the
# number (weight, share affected, formula) is shown to the user.
#
# weight: rough percentage points of mAP recoverable if every instance of this
#         problem were fixed across the whole dataset.
# scale:  what the finding count is measured against ("images" or "annotations").
# --------------------------------------------------------------------------- #
_IMPACT_WEIGHTS: dict[str, tuple[float, str]] = {
    # Broken data: the model never sees it, or trains on garbage.
    "corrupt-image": (9.0, "images"),
    "broken-image-path": (9.0, "images"),
    "images-not-found": (8.0, "images"),
    "invalid-annotation-file": (8.0, "images"),
    "invalid-image-dimension": (6.0, "images"),
    # Leakage inflates validation scores — the most expensive mistake here.
    "split-leakage": (12.0, "images"),
    # Duplicates skew the distribution and waste epochs.
    "exact-duplicate": (5.0, "images"),
    "near-duplicate": (4.0, "images"),
    "duplicate-filename": (3.0, "images"),
    # Wrong geometry teaches the model wrong boxes.
    "invalid-class-id": (7.0, "annotations"),
    "box-out-of-bounds": (5.0, "annotations"),
    "degenerate-box": (5.0, "annotations"),
    "duplicate-annotation": (3.5, "annotations"),
    "tiny-box": (2.5, "annotations"),
    "huge-box": (2.0, "annotations"),
    # Distribution problems: real, but slower-acting.
    "rare-class": (3.0, "annotations"),
    "class-imbalance": (3.0, "annotations"),
    "empty-image": (1.5, "images"),
    "objects-per-image-outlier": (1.0, "images"),
}
_IMPACT_DEFAULT = (1.0, "images")

#: Ceiling for the combined estimate. Gains overlap and saturate, so the total
#: is squashed toward this rather than summed naively.
_IMPACT_CAP = 15.0

#: How each supported annotation task is described in the UI.
TASK_LABELS = {
    "detect": "Object detection",
    "segment": "Instance segmentation",
    "obb": "Oriented boxes (OBB)",
}

_UNSPLIT = "(unsplit)"


def build_payload(
    dataset: Dataset,
    issues: list[Issue],
    *,
    stats: DatasetStatistics | None = None,
    version: str = "",
    max_issues: int = MAX_ISSUES,
) -> dict[str, Any]:
    """Build the JSON payload that drives the dashboard."""
    shown = issues[:max_issues]
    now = datetime.now().astimezone()
    classes = _class_distribution(dataset)

    return {
        "version": version,
        "generated": now.isoformat(timespec="seconds"),
        "generatedLabel": now.strftime("%d %b %Y, %H:%M"),
        "dataset": {
            "name": dataset.name,
            "root": dataset.root,
            "format": dataset.format.upper(),
            "task": dataset.task,
            "taskLabel": TASK_LABELS.get(dataset.task, dataset.task),
            "images": dataset.num_images,
            "annotations": dataset.num_annotations,
            "classes": dataset.num_classes,
            "splits": dataset.splits,
            "emptyImages": sum(1 for image in dataset.images if image.is_empty),
        },
        "stats": _stats_block(stats),
        "classes": classes,
        "classCoverage": _class_coverage(classes),
        "splits": _split_distribution(dataset),
        "objectsPerImage": _objects_histogram(dataset),
        "boxAreas": _area_histogram(dataset),
        "boxShapes": _shape_histogram(dataset),
        "boxCenters": _center_heatmap(dataset),
        "topImages": _top_images(issues),
        "severityCounts": _severity_counts(issues),
        "issueTypes": _issue_types(issues),
        "impact": _impact(dataset, issues),
        "issues": [_issue_dict(issue, dataset) for issue in shown],
        "issuesTotal": len(issues),
        "issuesTruncated": max(0, len(issues) - len(shown)),
    }


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #


def _severity_counts(issues: list[Issue]) -> dict[str, int]:
    counts = Counter(issue.severity for issue in issues)
    return {severity.label: counts.get(severity, 0) for severity in Severity}


def _issue_types(issues: list[Issue]) -> list[dict[str, Any]]:
    """Per-code counts, tagged with the worst severity seen for that code."""
    counts: Counter[str] = Counter(issue.code for issue in issues)
    worst: dict[str, Severity] = {}
    for issue in issues:
        current = worst.get(issue.code)
        if current is None or issue.severity > current:
            worst[issue.code] = issue.severity
    ranked = sorted(counts.items(), key=lambda kv: (-worst[kv[0]].rank, -kv[1], kv[0]))
    return [{"code": code, "severity": worst[code].label, "count": count} for code, count in ranked]


def _impact(dataset: Dataset, issues: list[Issue]) -> dict[str, Any]:
    """Estimate how much accuracy each class of problem is costing.

    Deliberately simple and inspectable: per issue code, the share of the
    dataset it touches times a fixed weight, then squashed so overlapping fixes
    don't add up past :data:`_IMPACT_CAP`. The dashboard shows every input, and
    labels the result an estimate — CVFlow has no model to measure.
    """
    counts: Counter[str] = Counter(issue.code for issue in issues)
    worst: dict[str, Severity] = {}
    for issue in issues:
        current = worst.get(issue.code)
        if current is None or issue.severity > current:
            worst[issue.code] = issue.severity

    images = max(dataset.num_images, 1)
    annotations = max(dataset.num_annotations, 1)

    items: list[dict[str, Any]] = []
    for code, count in counts.items():
        weight, scale = _IMPACT_WEIGHTS.get(code, _IMPACT_DEFAULT)
        share = min(1.0, count / (annotations if scale == "annotations" else images))
        # Sublinear in the affected share: a small fraction of broken data hurts
        # far more than its size suggests, and the last few percent add little.
        items.append(
            {
                "code": code,
                "severity": worst[code].label,
                "count": count,
                "scale": scale,
                "weight": weight,
                "share": share,
                "gain": round(weight * math.sqrt(share), 2),
            }
        )
    items.sort(key=lambda item: (-float(item["gain"]), str(item["code"])))

    return {
        "cap": _IMPACT_CAP,
        "total": _squash(sum(float(item["gain"]) for item in items)),
        "items": items,
        "formula": (
            "gain = weight x sqrt(share of the dataset affected), combined with diminishing returns"
        ),
    }


def _squash(raw: float) -> float:
    """Diminishing returns: many overlapping fixes never sum past the cap."""
    return round(_IMPACT_CAP * (1.0 - math.exp(-raw / _IMPACT_CAP)), 1)


#: Evidence keys the checks use to carry the files a finding covers.
_EVIDENCE_PATH_KEYS = ("examples", "paths", "example_pair", "pairs")

#: How many images to offer for one dataset-level finding.
_ISSUE_IMAGES = 12


def _issue_images(dataset: Dataset, issue: Issue) -> list[str]:
    """The images a finding concerns, so every finding can be *looked at*.

    Box-level findings name one file. Aggregated ones (empty images, duplicates,
    leakage) carry their files in evidence, and class-level ones (rare class,
    imbalance) name a class, which is resolved back to the images that contain
    it. Without this, the findings that matter most at the dataset level are the
    only ones a reader cannot see.
    """
    location = issue.location
    images: list[str] = [location.path] if location is not None and location.path else []

    for key in _EVIDENCE_PATH_KEYS:
        value = issue.evidence.get(key)
        if isinstance(value, (list, tuple)):
            for entry in value:
                if isinstance(entry, str):
                    images.append(entry)
                elif isinstance(entry, (list, tuple)):
                    images.extend(item for item in entry if isinstance(item, str))

    class_id = issue.evidence.get("class_id")
    if isinstance(class_id, int) and not isinstance(class_id, bool):
        images.extend(
            image.path
            for image in dataset.images
            if any(box.class_id == class_id for box in image.boxes)
        )

    seen: set[str] = set()
    unique: list[str] = []
    for path in images:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique[:_ISSUE_IMAGES]


def _issue_dict(issue: Issue, dataset: Dataset) -> dict[str, Any]:
    location = issue.location
    return {
        "code": issue.code,
        "severity": issue.severity.label,
        "message": issue.message,
        "why": issue.why or "",
        "suggestion": issue.suggestion or "",
        "where": location.describe() if location is not None else "",
        # The raw path (not the human description) is what the image editor
        # needs to ask the server for this file.
        "path": location.path if location is not None else None,
        "split": location.split if location is not None else None,
        # Which box on that image, when the check pinned one down — the editor
        # uses it to select the offending box and offer a fix.
        "annotationIndex": location.annotation_index if location is not None else None,
        "images": _issue_images(dataset, issue),
        "evidence": {key: _jsonable(value) for key, value in issue.evidence.items()},
    }


def _jsonable(value: Any) -> Any:
    """Coerce evidence values into something ``json.dumps`` accepts."""
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return str(value)


# --------------------------------------------------------------------------- #
# Statistics & distributions
# --------------------------------------------------------------------------- #


def _summary_dict(summary: Summary) -> dict[str, float]:
    return {
        "count": summary.count,
        "min": summary.minimum,
        "max": summary.maximum,
        "mean": summary.mean,
        "median": summary.median,
    }


def _stats_block(stats: DatasetStatistics | None) -> dict[str, Any] | None:
    if stats is None:
        return None
    return {
        "objectsPerImage": _summary_dict(stats.objects_per_image),
        "boxArea": _summary_dict(stats.box_area),
        "aspectRatio": _summary_dict(stats.aspect_ratio),
        "emptyImages": stats.empty_images,
    }


def _class_label(dataset: Dataset, class_id: int) -> str:
    """Display name for a class.

    Loaders infer ``{0: "0"}`` style names when a dataset ships no class list.
    A bare ``41`` on a chart axis reads as a value rather than an identity, so
    unnamed classes are spelled out instead.
    """
    name = dataset.class_names.get(class_id, "")
    if not name or name == str(class_id):
        return f"class {class_id}"
    return name


def _class_distribution(dataset: Dataset) -> list[dict[str, Any]]:
    """Annotations and image coverage per class, most frequent first.

    Computed from the dataset rather than :class:`DatasetStatistics` so the
    chart survives ``--no-stats``.
    """
    per_class: Counter[int] = Counter()
    images_per_class: Counter[int] = Counter()
    for image in dataset.images:
        seen: set[int] = set()
        for box in image.boxes:
            per_class[box.class_id] += 1
            seen.add(box.class_id)
        for class_id in seen:
            images_per_class[class_id] += 1

    total = sum(per_class.values()) or 1
    ranked = sorted(per_class.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "id": class_id,
            "name": _class_label(dataset, class_id),
            "annotations": count,
            "images": images_per_class[class_id],
            "share": count / total,
        }
        for class_id, count in ranked
    ]


def _class_coverage(classes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Cumulative share of annotations covered by the *n* largest classes.

    The shape of this curve is what a class-imbalance number can only hint at:
    a curve that jumps to 90% in three classes means the long tail is barely
    represented.
    """
    if len(classes) < 3:
        return None
    total = sum(entry["annotations"] for entry in classes) or 1
    points: list[dict[str, float]] = []
    running = 0
    for rank, entry in enumerate(classes, start=1):
        running += entry["annotations"]
        points.append({"classes": rank, "share": running / total})

    milestones: dict[str, int] = {}
    for target in (0.5, 0.8, 0.95):
        hit = next((point for point in points if point["share"] >= target), None)
        if hit is not None:
            milestones[str(int(target * 100))] = int(hit["classes"])
    return {"points": points, "milestones": milestones, "classes": len(classes)}


def _top_images(issues: list[Issue], limit: int = _TOP_IMAGES) -> list[dict[str, Any]]:
    """Images carrying the most findings, with their severity breakdown."""
    per_image: dict[tuple[str, str | None], Counter[str]] = {}
    for issue in issues:
        location = issue.location
        if location is None or not location.path:
            continue
        counts = per_image.setdefault((location.path, location.split), Counter())
        counts[issue.severity.label] += 1

    rows: list[dict[str, Any]] = [
        {
            "path": path,
            "name": path.replace("\\", "/").rsplit("/", 1)[-1],
            "split": split,
            "counts": {severity.label: counts.get(severity.label, 0) for severity in Severity},
            "total": sum(counts.values()),
        }
        for (path, split), counts in per_image.items()
    ]
    rows.sort(key=lambda row: (-int(row["total"]), str(row["path"])))
    return rows[:limit]


def _shape_histogram(dataset: Dataset) -> dict[str, Any] | None:
    """Distribution of box shape (width ÷ height), tall through wide.

    Normalized coordinates are relative to the frame, so a true pixel aspect
    ratio is only available when every annotated image reports its dimensions.
    The basis is reported alongside the bins rather than quietly mixed.
    """
    annotated = [image for image in dataset.images if image.boxes]
    pixel_basis = bool(annotated) and all(
        image.width and image.height and image.height > 0 for image in annotated
    )

    counts = [0] * len(_SHAPE_LABELS)
    total = 0
    for image, box in dataset.iter_boxes():
        if box.width <= 0 or box.height <= 0:
            continue
        ratio = box.width / box.height
        if pixel_basis and image.width and image.height:
            ratio *= image.width / image.height
        total += 1
        index = next(
            (i for i, edge in enumerate(_SHAPE_EDGES) if ratio < edge),
            len(_SHAPE_LABELS) - 1,
        )
        counts[index] += 1

    if not total:
        return None
    return {
        "basis": "pixels" if pixel_basis else "frame",
        "bins": [
            _bin(label, count, span)
            for label, span, count in zip(_SHAPE_LABELS, _SHAPE_RANGES, counts)
        ],
    }


def _center_heatmap(dataset: Dataset, grid: int = _HEATMAP_GRID) -> dict[str, Any] | None:
    """Where box centers land in the frame, as a ``grid``-by-``grid`` count map.

    Reveals framing bias — everything hugging one edge, or a blank band the
    annotator never covered — which no single number shows.
    """
    cells = [0] * (grid * grid)
    total = 0
    for _, box in dataset.iter_boxes():
        if box.area <= 0:
            continue
        center_x, center_y = box.center
        column = min(max(int(center_x * grid), 0), grid - 1)
        row = min(max(int(center_y * grid), 0), grid - 1)
        cells[row * grid + column] += 1
        total += 1
    if not total:
        return None
    return {"grid": grid, "cells": cells, "max": max(cells), "total": total}


def _split_distribution(dataset: Dataset) -> list[dict[str, Any]]:
    """Image/annotation counts per split, including unsplit images."""
    images: Counter[str] = Counter()
    annotations: Counter[str] = Counter()
    for image in dataset.images:
        name = image.split or _UNSPLIT
        images[name] += 1
        annotations[name] += image.num_boxes
    return [
        {"name": name, "images": count, "annotations": annotations[name]}
        for name, count in sorted(images.items())
    ]


def _bin(label: str, count: int, span: str = "") -> dict[str, Any]:
    return {"label": label, "range": span or label, "count": count}


def _objects_histogram(dataset: Dataset, max_bins: int = 12) -> list[dict[str, Any]]:
    """Distribution of annotations-per-image, one bin per count when it fits.

    Each bin carries a short axis ``label`` (the bucket's lower edge) and the
    full ``range`` for the tooltip and the data table — a binned axis has to
    stay readable in a narrow card.
    """
    values = [image.num_boxes for image in dataset.images]
    if not values:
        return []
    highest = max(values)
    if highest < max_bins:
        counts = Counter(values)
        return [_bin(str(n), counts.get(n, 0)) for n in range(highest + 1)]

    width = math.ceil((highest + 1) / max_bins)
    counts = Counter(min(value // width, max_bins - 1) for value in values)
    bins: list[dict[str, Any]] = []
    for index in range(max_bins):
        start = index * width
        end = min(start + width - 1, highest)
        span = str(start) if start == end else f"{start}-{end}"
        bins.append(_bin(str(start), counts.get(index, 0), span))
    return bins


def _area_histogram(dataset: Dataset) -> list[dict[str, Any]]:
    """Distribution of box area as a share of the image, in fixed buckets."""
    counts = [0] * len(_AREA_EDGES)
    total = 0
    for _, box in dataset.iter_boxes():
        area = box.area
        if area <= 0:
            continue  # degenerate boxes are a finding, not a size
        total += 1
        for index, edge in enumerate(_AREA_EDGES):
            if area < edge or index == len(_AREA_EDGES) - 1:
                counts[index] += 1
                break
    if not total:
        return []
    return [
        _bin(label, count, span) for label, span, count in zip(_AREA_LABELS, _AREA_RANGES, counts)
    ]
