"""Train/val/test leakage detection.

Finds visually similar images that appear across different dataset splits — a
common, silent cause of over-optimistic validation metrics, especially for
datasets built from consecutive video frames.

Reuses the perceptual hashing from duplicate detection. Findings are reported
per split-pair (aggregated), as ``WARNING`` leakage *candidates* — CVFlow never
claims similarity definitely means leakage; it flags pairs for review.
"""

from __future__ import annotations

from collections.abc import Iterable

from cvflow.analysis.engine import Check, CheckConfig
from cvflow.analysis.paths import resolve_all
from cvflow.imaging import hamming_distance, perceptual_hash
from cvflow.model import Dataset, ImageItem, Issue, Location, Severity

_HASH_BITS = 64


class SplitLeakageCheck(Check):
    """Cross-split perceptual-similarity detection."""

    code = "leakage"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._config = config or CheckConfig()

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        cfg = self._config
        if not cfg.check_images:
            return
        splits = dataset.splits
        if len(splits) < 2:
            return  # leakage is only meaningful across multiple splits

        resolved = resolve_all(dataset)
        by_split: dict[str, list[tuple[ImageItem, int]]] = {}
        for item in dataset.images:
            if item.split is None:
                continue
            path = resolved[id(item)]
            if path is None:
                continue
            phash = perceptual_hash(path)
            if phash is not None:
                by_split.setdefault(item.split, []).append((item, phash))

        threshold = cfg.leakage_max_hamming
        for a_idx in range(len(splits)):
            for b_idx in range(a_idx + 1, len(splits)):
                split_a, split_b = splits[a_idx], splits[b_idx]
                issue = self._compare_splits(
                    split_a,
                    by_split.get(split_a, []),
                    split_b,
                    by_split.get(split_b, []),
                    threshold,
                )
                if issue is not None:
                    yield issue

    def _compare_splits(
        self,
        split_a: str,
        items_a: list[tuple[ImageItem, int]],
        split_b: str,
        items_b: list[tuple[ImageItem, int]],
        threshold: int,
    ) -> Issue | None:
        matches: list[tuple[ImageItem, ImageItem, int]] = []
        for item_a, hash_a in items_a:
            for item_b, hash_b in items_b:
                distance = hamming_distance(hash_a, hash_b)
                if distance <= threshold:
                    matches.append((item_a, item_b, distance))
        if not matches:
            return None

        matches.sort(key=lambda m: m[2])  # smallest distance = highest similarity
        best_a, best_b, best_distance = matches[0]
        best_similarity = (_HASH_BITS - best_distance) / _HASH_BITS
        return Issue(
            code="split-leakage",
            severity=Severity.WARNING,
            message=(
                f"{len(matches)} highly similar image pair(s) between "
                f"'{split_a}' and '{split_b}': possible dataset leakage."
            ),
            why=(
                "Visually near-identical images appear in different splits. If the "
                "same sample is in train and validation, metrics can be inflated."
            ),
            location=Location(path=best_a.path, split=split_a),
            evidence={
                "split_a": split_a,
                "split_b": split_b,
                "pairs": len(matches),
                "highest_similarity": round(best_similarity, 4),
                "example": [best_a.path, best_b.path],
            },
            suggestion="Review these pairs; move or remove overlaps so splits don't share samples.",
        )


def leakage_checks(config: CheckConfig | None = None) -> list[Check]:
    """Return the default set of split-leakage checks."""
    return [SplitLeakageCheck(config)]
