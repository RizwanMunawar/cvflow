"""Tests for exact and near-duplicate detection."""

from __future__ import annotations

import random
import shutil
from pathlib import Path

from cvflow.analysis import CheckConfig
from cvflow.analysis.duplicates import ExactDuplicateCheck, NearDuplicateCheck
from cvflow.imaging import file_hash, hamming_distance, perceptual_hash
from cvflow.loaders import load_dataset
from cvflow.model import Severity


def _make_png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (64, 64)) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=color).save(path)


def _noise_png(path: Path, seed: int, size: tuple[int, int] = (64, 64)) -> None:
    """Deterministic pseudo-random image — gives a well-distributed dHash."""
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    data = [
        (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        for _ in range(size[0] * size[1])
    ]
    img = Image.new("RGB", size)
    img.putdata(data)
    img.save(path)


def _near_variant(src: Path, dst: Path) -> None:
    """A near-duplicate: same image with its top band blacked out (a few bits)."""
    from PIL import Image

    img = Image.open(src).convert("RGB")
    for y in range(8):
        for x in range(img.width):
            img.putpixel((x, y), (0, 0, 0))
    img.save(dst)


def _dup_dataset(tmp_path: Path) -> Path:
    """YOLO dataset: an exact-duplicate pair, a near-duplicate pair, one distinct."""
    root = tmp_path / "dups"
    train = root / "images" / "train"
    _noise_png(train / "a.png", seed=1)
    shutil.copyfile(train / "a.png", train / "a_copy.png")  # exact duplicate
    _noise_png(train / "near1.png", seed=5)
    _near_variant(train / "near1.png", train / "near2.png")  # near-duplicate of near1
    _noise_png(train / "distinct.png", seed=900)
    for name in ("a", "a_copy", "near1", "near2", "distinct"):
        (root / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (root / "labels" / "train" / f"{name}.txt").write_text("0 0.5 0.5 0.2 0.2\n")
    (root / "data.yaml").write_text("names:\n  0: obj\ntrain: images/train\n")
    return root


def test_file_hash_matches_for_identical_bytes(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    _make_png(a, (1, 2, 3))
    shutil.copyfile(a, b)
    assert file_hash(a) == file_hash(b)


def test_perceptual_hash_similar_and_different(tmp_path: Path) -> None:
    base = tmp_path / "base.png"
    near = tmp_path / "near.png"
    other = tmp_path / "other.png"
    _noise_png(base, seed=1)
    _near_variant(base, near)
    _noise_png(other, seed=2)
    hb, hn, ho = perceptual_hash(base), perceptual_hash(near), perceptual_hash(other)
    assert hb is not None and hn is not None and ho is not None
    # The near-variant is much closer to the base than an independent image.
    assert hamming_distance(hb, hn) < hamming_distance(hb, ho)


def test_exact_duplicate_check(tmp_path: Path) -> None:
    ds = load_dataset(_dup_dataset(tmp_path))
    issues = list(ExactDuplicateCheck().run(ds))
    assert len(issues) == 1
    assert issues[0].severity is Severity.WARNING
    assert issues[0].evidence["count"] == 2


def test_near_duplicate_check(tmp_path: Path) -> None:
    ds = load_dataset(_dup_dataset(tmp_path))
    issues = list(NearDuplicateCheck(CheckConfig(near_duplicate_max_hamming=12)).run(ds))
    # The near1/near2 pair should be flagged as near-duplicates.
    assert any("near1" in i.message and "near2" in i.message for i in issues)
    assert all(i.severity is Severity.WARNING for i in issues)
    assert all(0.0 < i.evidence["similarity"] <= 1.0 for i in issues)


def test_duplicate_checks_skipped_without_images(tmp_path: Path) -> None:
    ds = load_dataset(_dup_dataset(tmp_path))
    cfg = CheckConfig(check_images=False)
    assert list(ExactDuplicateCheck(cfg).run(ds)) == []
    assert list(NearDuplicateCheck(cfg).run(ds)) == []


def test_near_duplicate_respects_report_cap(tmp_path: Path) -> None:
    ds = load_dataset(_dup_dataset(tmp_path))
    cfg = CheckConfig(near_duplicate_max_hamming=64, max_reported_duplicate_pairs=2)
    issues = list(NearDuplicateCheck(cfg).run(ds))
    assert len(issues) <= 2
