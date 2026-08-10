"""Tests for split-leakage detection."""

from __future__ import annotations

import random
import shutil
from pathlib import Path

from cvflow.analysis import CheckConfig
from cvflow.analysis.leakage import SplitLeakageCheck
from cvflow.loaders import load_dataset
from cvflow.model import Severity


def _noise_png(path: Path, seed: int, size: tuple[int, int] = (64, 64)) -> None:
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


def _label(root: Path, split: str, name: str) -> None:
    d = root / "labels" / split
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.txt").write_text("0 0.5 0.5 0.2 0.2\n")


def _leaky_dataset(tmp_path: Path, *, leak: bool) -> Path:
    """Train + val dataset; if ``leak``, a train image is copied into val."""
    root = tmp_path / ("leaky" if leak else "clean")
    _noise_png(root / "images" / "train" / "t1.png", seed=1)
    _noise_png(root / "images" / "train" / "t2.png", seed=2)
    _noise_png(root / "images" / "val" / "v1.png", seed=50)
    _label(root, "train", "t1")
    _label(root, "train", "t2")
    _label(root, "val", "v1")
    if leak:
        # The same image (t1) also appears in val -> leakage.
        shutil.copyfile(
            root / "images" / "train" / "t1.png", root / "images" / "val" / "t1_again.png"
        )
        _label(root, "val", "t1_again")
    (root / "data.yaml").write_text("names:\n  0: obj\ntrain: images/train\nval: images/val\n")
    return root


def test_leakage_detected_across_splits(tmp_path: Path) -> None:
    ds = load_dataset(_leaky_dataset(tmp_path, leak=True))
    issues = list(SplitLeakageCheck().run(ds))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity is Severity.WARNING
    assert issue.code == "split-leakage"
    assert {issue.evidence["split_a"], issue.evidence["split_b"]} == {"train", "val"}
    assert issue.evidence["pairs"] >= 1
    assert issue.evidence["highest_similarity"] == 1.0  # identical copy


def test_no_leakage_when_splits_disjoint(tmp_path: Path) -> None:
    ds = load_dataset(_leaky_dataset(tmp_path, leak=False))
    assert list(SplitLeakageCheck().run(ds)) == []


def test_leakage_skipped_without_images(tmp_path: Path) -> None:
    ds = load_dataset(_leaky_dataset(tmp_path, leak=True))
    assert list(SplitLeakageCheck(CheckConfig(check_images=False)).run(ds)) == []


def test_leakage_skipped_with_single_split(tmp_path: Path) -> None:
    root = tmp_path / "single"
    _noise_png(root / "images" / "train" / "a.png", seed=1)
    _label(root, "train", "a")
    (root / "data.yaml").write_text("names:\n  0: obj\ntrain: images/train\n")
    ds = load_dataset(root)
    assert list(SplitLeakageCheck().run(ds)) == []
