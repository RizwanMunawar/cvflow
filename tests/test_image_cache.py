from pathlib import Path

import pytest
from PIL import Image

from cvflow.analysis.image_cache import ImageScanCache


def test_reuses_unchanged_images_and_invalidates_modified_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "a.png"
    Image.new("RGB", (8, 8), "red").save(image)
    path = tmp_path / "cache.json"
    first = ImageScanCache(path, workers=2)
    first.scan([image, image])
    original = first.result(image, "sha256")
    assert original is not None
    first.save()

    import cvflow.analysis.image_cache as module

    def unexpected_scan(path: Path) -> str:
        raise AssertionError("unchanged image must not be hashed again")

    monkeypatch.setattr(module, "file_hash", unexpected_scan)
    second = ImageScanCache(path, workers=2)
    second.scan([image])
    assert second.result(image, "sha256") == original

    monkeypatch.undo()
    Image.new("RGB", (9, 8), "blue").save(image)
    third = ImageScanCache(path, workers=2)
    third.scan([image])
    assert third.result(image, "sha256") != original


def test_invalid_image_and_no_persistent_cache(tmp_path: Path) -> None:
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    cache = ImageScanCache(workers=1)
    cache.scan([broken])
    assert cache.result(broken, "readable") is False
    assert cache.result(broken, "dhash") is None
    cache.save()
