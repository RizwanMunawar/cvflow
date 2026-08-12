"""Tests for the downloadable sample dataset.

No network: the archive is built locally and fetched over ``file://``, which
exercises the same download, unpack and cache path the real URL takes.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from cvflow.exceptions import DatasetError
from cvflow.sample import SAMPLE_URL, cache_dir, ensure_sample


def _make_archive(tmp_path: Path, name: str = "coco128") -> str:
    """A miniature YOLO dataset, zipped the way the real sample is."""
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{name}/data.yaml", "names:\n  0: cat\ntrain: images/train\n")
        bundle.writestr(f"{name}/images/train/a.jpg", "not really an image")
        bundle.writestr(f"{name}/labels/train/a.txt", "0 0.5 0.5 0.2 0.2\n")
    return archive.as_uri()


def test_downloads_and_unpacks(tmp_path: Path) -> None:
    dest = tmp_path / "cache"
    messages: list[str] = []

    root = ensure_sample(url=_make_archive(tmp_path), dest=dest, echo=messages.append)

    assert root == dest / "coco128"
    assert (root / "data.yaml").is_file()
    assert (root / "images" / "train" / "a.jpg").is_file()
    assert any("fetching" in message for message in messages)


def test_second_call_reuses_the_cache(tmp_path: Path) -> None:
    dest = tmp_path / "cache"
    url = _make_archive(tmp_path)
    ensure_sample(url=url, dest=dest)

    messages: list[str] = []
    # A URL that cannot resolve: proof nothing is fetched the second time.
    root = ensure_sample(url="https://example.invalid/none.zip", dest=dest, echo=messages.append)

    assert (root / "data.yaml").is_file()
    assert any("cached" in message for message in messages)


def test_a_failed_download_explains_itself(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="could not download"):
        ensure_sample(url="https://example.invalid/none.zip", dest=tmp_path / "cache")


def test_a_broken_archive_explains_itself(tmp_path: Path) -> None:
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"this is not a zip file")

    with pytest.raises(DatasetError, match="not a valid zip"):
        ensure_sample(url=broken.as_uri(), dest=tmp_path / "cache")


def test_refuses_to_unpack_outside_the_cache(tmp_path: Path) -> None:
    """A zip naming ../ would otherwise write anywhere on disk."""
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escaped.txt", "gotcha")

    with pytest.raises(DatasetError, match="outside the cache"):
        ensure_sample(url=archive.as_uri(), dest=tmp_path / "cache")
    assert not (tmp_path / "escaped.txt").exists()


def test_cache_dir_honours_the_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CVFLOW_CACHE", str(tmp_path / "somewhere"))
    assert cache_dir() == tmp_path / "somewhere"


def test_sample_url_points_at_the_published_asset() -> None:
    assert SAMPLE_URL.endswith("coco128.zip")
    assert SAMPLE_URL.startswith("https://github.com/ultralytics/assets/releases/")
