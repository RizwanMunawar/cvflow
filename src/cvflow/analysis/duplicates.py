"""Duplicate and near-duplicate image detection.

Two checks, both reading image bytes (so they honor ``--no-images`` and skip
cleanly when images aren't on disk):

- :class:`ExactDuplicateCheck` groups images with identical file bytes (SHA-256).
- :class:`NearDuplicateCheck` finds visually similar images via perceptual
  hashing (dHash) and Hamming distance.

Findings are ``WARNING``s — potential duplicates worth reviewing — never errors.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from cvflow.analysis.engine import Check, CheckConfig
from cvflow.analysis.paths import resolve_all
from cvflow.imaging import file_hash, hamming_distance, perceptual_hash
from cvflow.model import Dataset, ImageItem, Issue, Location, Severity


class ExactDuplicateCheck(Check):
    """Groups images whose file bytes are byte-for-byte identical."""

    code = "duplicates"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._config = config or CheckConfig()

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        if not self._config.check_images:
            return
        resolved = resolve_all(dataset)
        by_hash: dict[str, list[ImageItem]] = {}
        for item in dataset.images:
            path = resolved[id(item)]
            if path is None:
                continue
            digest = file_hash(path)
            if digest is None:
                continue
            by_hash.setdefault(digest, []).append(item)

        for digest, items in by_hash.items():
            if len(items) < 2:
                continue
            paths = [it.path for it in items]
            yield Issue(
                code="exact-duplicate",
                severity=Severity.WARNING,
                message=f"{len(items)} images are exact duplicates (identical files).",
                why=(
                    "These files share an identical SHA-256 hash, so they are byte-for-byte copies."
                ),
                location=Location(path=items[0].path, split=items[0].split),
                evidence={"sha256": digest[:16], "count": len(items), "paths": paths[:10]},
                suggestion="Keep one copy and remove the rest to avoid redundant samples.",
            )


class NearDuplicateCheck(Check):
    """Finds visually similar images via perceptual hashing."""

    code = "duplicates"

    def __init__(self, config: CheckConfig | None = None) -> None:
        self._config = config or CheckConfig()

    def run(self, dataset: Dataset) -> Iterable[Issue]:
        cfg = self._config
        if not cfg.check_images:
            return
        resolved = resolve_all(dataset)

        # Compute one perceptual hash per resolvable image.
        hashed: list[tuple[ImageItem, int]] = []
        for item in dataset.images:
            path = resolved[id(item)]
            if path is None:
                continue
            phash = perceptual_hash(path)
            if phash is not None:
                hashed.append((item, phash))

        max_bits = 64
        reported = 0
        for i in range(len(hashed)):
            for j in range(i + 1, len(hashed)):
                if reported >= cfg.max_reported_duplicate_pairs:
                    return
                item_a, hash_a = hashed[i]
                item_b, hash_b = hashed[j]
                distance = hamming_distance(hash_a, hash_b)
                if distance > cfg.near_duplicate_max_hamming:
                    continue
                if distance == 0:
                    continue  # identical hash — likely an exact/near-exact dup already covered
                similarity = (max_bits - distance) / max_bits
                reported += 1
                yield Issue(
                    code="near-duplicate",
                    severity=Severity.WARNING,
                    message=(
                        f"Potential near-duplicate images ({similarity:.1%} similar): "
                        f"{Path(item_a.path).name} ↔ {Path(item_b.path).name}"
                    ),
                    why=(
                        "Their perceptual hashes differ by only "
                        f"{distance}/{max_bits} bits, so the images look nearly identical."
                    ),
                    location=Location(path=item_a.path, split=item_a.split),
                    evidence={
                        "similarity": round(similarity, 4),
                        "hamming": distance,
                        "pair": [item_a.path, item_b.path],
                        "splits": [item_a.split, item_b.split],
                    },
                    suggestion="Review the pair; de-duplicate if they are the same sample.",
                )


def duplicate_checks(config: CheckConfig | None = None) -> list[Check]:
    """Return the default set of duplicate-detection checks."""
    return [ExactDuplicateCheck(config), NearDuplicateCheck(config)]
